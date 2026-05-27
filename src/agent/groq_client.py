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

_DEFAULTS = {
    "api_key_env":        "GROQ_API_KEY",
    "model":              "llama-3.1-70b-versatile",
    "endpoint":           "https://api.groq.com/openai/v1/chat/completions",
    "request_timeout_s":  8.0,
    "max_tokens":         1024,
    "fail_count_disable": 5,
}

# Default redaction tokens — overridable from agent.findings.redact_patterns
_DEFAULT_REDACT = ("api_key", "secret", "password", "token", "AV_API_KEY", "GROQ_API_KEY")


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _short_hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()[:16]


def _load_cfg() -> dict:
    """Resolve agent.groq subsection (or defaults if missing)."""
    try:
        from config_layer.production_config import get_prod_section
        agent_cfg = get_prod_section("agent") or {}
    except Exception:
        agent_cfg = {}
    groq_cfg = dict(_DEFAULTS)
    groq_cfg.update(agent_cfg.get("groq") or {})
    findings_cfg = agent_cfg.get("findings") or {}
    groq_cfg["_redact_patterns"] = tuple(
        findings_cfg.get("redact_patterns") or _DEFAULT_REDACT
    )
    return groq_cfg


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
        self._api_key = os.environ.get(str(self.cfg.get("api_key_env", "GROQ_API_KEY")), "")
        self._fail_count = 0
        self._missing_key_logged = False

    # ── internal helpers ─────────────────────────────────────────────────────
    def _circuit_open(self) -> bool:
        return self._fail_count >= int(self.cfg.get("fail_count_disable", 5))

    def _key_present(self) -> bool:
        if not self._api_key:
            if not self._missing_key_logged:
                env = self.cfg.get("api_key_env", "GROQ_API_KEY")
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

        max_tokens = int(max_tokens or self.cfg.get("max_tokens", 1024))
        endpoint = str(self.cfg.get("endpoint", _DEFAULTS["endpoint"]))
        model = str(self.cfg.get("model", _DEFAULTS["model"]))
        timeout = float(self.cfg.get("request_timeout_s", _DEFAULTS["request_timeout_s"]))
        redact_patterns = self.cfg.get("_redact_patterns") or _DEFAULT_REDACT

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
            "temperature": float(self.cfg.get("temperature", 0.1)),
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

        if error and self._fail_count == int(self.cfg.get("fail_count_disable", 5)):
            logger.warning(
                "GroqClient: %d consecutive failures — circuit OPEN. "
                "Future synthesis calls return empty until process restart.",
                self._fail_count,
            )

        return response_text
