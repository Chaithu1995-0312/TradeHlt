"""
groq_client.py — Agent-tier Groq LLM client with request logging + redaction
─────────────────────────────────────────────────────────────────────────────
Used by the findings_synthesizer (and any future agent-side LLM caller) when
post-run reasoning over code + logs is required. Distinct from
``config_layer.llm_inference_client.llm_chat`` which fronts BitNet-local and
is reserved for low-latency hot-path scoring.

Design mirrors ``config_layer.llm_inference_client``:
  - stdlib urllib only (no openai dep)
  - circuit-breaker on consecutive failures
  - empty-string fallback so callers handle gracefully
  - JSONL request log at logs/agent_llm_requests.jsonl (redacted)

Configuration is read from ``configs/production/v1_multi_2026_03.json``
under ``agent.groq``; if section absent, conservative defaults are used and
the client logs MISSING_CONFIG once.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable
from config_layer.strict_config import (
    ConfigKeyMissingError, require, require_all, require_section,
)

logger = logging.getLogger("AgentGroqClient")

_REQUEST_LOG = "logs/agent_llm_requests.jsonl"


# ── .env loader (stdlib only — mirrors llm_inference_client._load_dotenv) ────
def _load_dotenv(start: Path = Path(__file__).resolve()) -> None:
    """Walk up from *start* until a .env file is found; inject KEY=VALUE pairs
    into os.environ without overwriting vars already set in the process env."""
    for parent in [start, *start.parents]:
        dotenv = parent / ".env"
        if dotenv.is_file():
            try:
                for raw in dotenv.read_text(encoding="utf-8").splitlines():
                    line = raw.strip()
                    if not line or line.startswith("#"):
                        continue
                    line = line.removeprefix("export").strip()
                    if "=" not in line:
                        continue
                    key, _, val = line.partition("=")
                    key = key.strip()
                    val = val.split("#")[0].strip().strip("\"'")
                    if key and key not in os.environ:
                        os.environ[key] = val
                logger.debug("Loaded .env from %s", dotenv)
            except Exception as exc:
                logger.debug("Could not load .env at %s: %s", dotenv, exc)
            return


_load_dotenv()

# redact() callers that omit patterns. GroqClient reads agent.findings.redact_patterns.
_DEFAULT_REDACT = ("api_key", "secret", "password", "token", "AV_API_KEY", "GROQ_API_KEY")

_GROQ_KEYS = (
    "api_key_env",
    "model",
    "endpoint",
    "request_timeout_s",
    "max_tokens",
    "fail_count_disable",
    "temperature",
)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _short_hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()[:16]


def _load_cfg() -> dict:
    """Resolve agent.groq and agent.findings.redact_patterns. Missing section raises."""
    from config_layer.production_config import get_prod_section
    try:
        agent_cfg = get_prod_section("agent")
    except Exception as exc:
        raise ConfigKeyMissingError(
            ["agent"], section="<root>", consumer="GroqClient",
        ) from exc
    groq_cfg = require_section(agent_cfg, "groq", consumer="GroqClient")
    loaded = require_all(
        groq_cfg, _GROQ_KEYS, section_name="agent.groq", consumer="GroqClient",
    )
    findings_cfg = require_section(agent_cfg, "findings", consumer="GroqClient")
    loaded["_redact_patterns"] = tuple(require(
        findings_cfg, "redact_patterns",
        section_name="agent.findings", consumer="GroqClient",
    ))
    return loaded


def _compile_redactors(patterns: Iterable[str]) -> list[re.Pattern]:
    """
    Build redactors that mask values for any matched key in JSON-like text.
    Matches either ``"key": "value"`` (JSON) or ``KEY=value`` (env-style).
    """
    compiled = []
    for p in patterns:
        key = re.escape(p)
        # "key": "...."
        compiled.append(re.compile(rf'("{key}"\s*:\s*")[^"]*(")', re.IGNORECASE))
        # KEY=value (line-oriented)
        compiled.append(re.compile(rf'(\b{key}\s*=\s*)\S+', re.IGNORECASE))
    return compiled


def redact(text: str, patterns: Iterable[str] = _DEFAULT_REDACT) -> str:
    """Mask secret values in any prompt before logging or send."""
    if not text:
        return text
    for rx in _compile_redactors(patterns):
        text = rx.sub(lambda m: m.group(1) + "***REDACTED***" + (m.group(2) if m.lastindex and m.lastindex >= 2 else ""), text)
    return text


def _append_request_log(record: dict) -> None:
    """Fire-and-forget JSONL append; never raises."""
    try:
        Path(_REQUEST_LOG).parent.mkdir(parents=True, exist_ok=True)
        with open(_REQUEST_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.debug("agent_llm_requests append failed: %s", exc)


class GroqClient:
    """
    Thin, stdlib-only Groq chat client used by the agent's findings layer.

    Public API:
      chat(prompt, system="", max_tokens=None) -> str
        Returns assistant content, or "" on any failure. Never raises.
    """

    def __init__(self, cfg: dict | None = None):
        self.cfg = cfg if cfg is not None else _load_cfg()
        require_all(self.cfg, _GROQ_KEYS, section_name="agent.groq", consumer="GroqClient")
        if "_redact_patterns" not in self.cfg:
            raise ConfigKeyMissingError(
                ["redact_patterns"], section="agent.findings", consumer="GroqClient",
            )
        self._api_key = os.environ.get(str(self.cfg["api_key_env"]), "")
        self._fail_count = 0
        self._missing_key_logged = False

    # ── internal helpers ─────────────────────────────────────────────────────
    def _circuit_open(self) -> bool:
        return self._fail_count >= int(require(self.cfg, "fail_count_disable", section_name="agent", consumer="groq_client"))

    def _key_present(self) -> bool:
        if not self._api_key:
            if not self._missing_key_logged:
                env = require(self.cfg, "api_key_env", section_name="agent", consumer="groq_client")
                logger.warning(
                    "GroqClient: %s not set — findings synthesis disabled. "
                    "Add it to repo-root .env: %s=gsk_...",
                    env, env,
                )
                self._missing_key_logged = True
            return False
        return True

    # ── public API ───────────────────────────────────────────────────────────
    def chat(self, prompt: str, system: str = "", max_tokens: int | None = None) -> str:
        # Always log the attempt (even short-circuits) so the request log
        # is a complete audit trail of every agent → LLM intent.
        if self._circuit_open():
            _append_request_log({
                "ts": _now_iso(), "model": self.cfg.get("model"),
                "prompt_hash": _short_hash(prompt), "prompt_redacted": "",
                "response": "", "latency_ms": 0,
                "error": "CIRCUIT_OPEN", "fail_count": self._fail_count, "circuit": "OPEN",
            })
            return ""
        if not self._key_present():
            _append_request_log({
                "ts": _now_iso(), "model": self.cfg.get("model"),
                "prompt_hash": _short_hash(prompt), "prompt_redacted": "",
                "response": "", "latency_ms": 0,
                "error": "MISSING_KEY", "fail_count": self._fail_count, "circuit": "CLOSED",
            })
            return ""

        max_tokens = int(max_tokens or require(self.cfg, "max_tokens", section_name="agent", consumer="groq_client"))
        endpoint = str(require(self.cfg, "endpoint", section_name="agent", consumer="groq_client"))
        model = str(require(self.cfg, "model", section_name="agent", consumer="groq_client"))
        timeout = float(require(self.cfg, "request_timeout_s", section_name="agent", consumer="groq_client"))
        redact_patterns = self.cfg["_redact_patterns"]

        # Redact secrets BEFORE building payload — defence in depth.
        safe_system = redact(system or "", redact_patterns)
        safe_prompt = redact(prompt or "", redact_patterns)

        messages = []
        if safe_system:
            messages.append({"role": "system", "content": safe_system})
        messages.append({"role": "user", "content": safe_prompt})

        payload = json.dumps({
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": float(require(self.cfg, "temperature", section_name="agent", consumer="groq_client")),
        }).encode("utf-8")

        req = urllib.request.Request(
            endpoint,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
                "User-Agent": "tradelatest-agent/0.1",
            },
        )

        t0 = time.monotonic()
        response_text, error = "", None
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                response_text = (body.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
                self._fail_count = 0
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:300]
            except Exception:
                detail = ""
            error = f"HTTP {exc.code}: {detail}"
            self._fail_count += 1
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            self._fail_count += 1
        latency_ms = int((time.monotonic() - t0) * 1000)

        _append_request_log({
            "ts": _now_iso(),
            "model": model,
            "prompt_hash": _short_hash(safe_prompt),
            "system_hash": _short_hash(safe_system) if safe_system else None,
            "prompt_redacted": safe_prompt[:4000],   # cap to keep log line bounded
            "response": response_text[:4000],
            "max_tokens": max_tokens,
            "latency_ms": latency_ms,
            "error": error,
            "fail_count": self._fail_count,
            "circuit": "OPEN" if self._circuit_open() else "CLOSED",
        })

        if error and self._fail_count == int(require(self.cfg, "fail_count_disable", section_name="agent", consumer="groq_client")):
            logger.warning(
                "GroqClient: %d consecutive failures — circuit OPEN. "
                "Future synthesis calls return empty until process restart.",
                self._fail_count,
            )

        return response_text
