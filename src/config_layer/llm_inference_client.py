"""
llm_inference_client.py
═══════════════════════════════════════════════════════════════════════════════
LLM HTTP transport layer — endpoint management, Groq cloud fallback, audit
logging, and multi-turn chat.

This is the infrastructure base of a 3-file split:
  llm_inference_client.py  (this file) — HTTP comms, config, Groq, audit, chat
  llm_scorer.py                        — numeric score computation
  llm_narrative.py                     — prose insight generation

Backward-compatibility re-exports at the bottom of this file mean that
existing callers doing ``import config_layer.llm_inference_client as lg``
continue to access lg.llm_score, lg.llm_insight, etc. without changes.
New code should import directly from llm_scorer or llm_narrative.

Public API (transport layer)
-----------------------------
  SERVER_URL               str   — primary inference endpoint
  llm_chat(messages, ...)  str   — multi-turn chat with local/Groq fallback
  FAIL_COUNT               int   — chat circuit-breaker counter (module-level)
"""

import json
import logging
import os
import time as _time
import urllib.request
import urllib.error
from pathlib import Path

logger = logging.getLogger("LlamaGate")
logger.setLevel(logging.DEBUG)

# ── .env loader (stdlib only, no python-dotenv required) ─────────────────────
def _load_dotenv(start: Path = Path(__file__).resolve()) -> None:
    """
    Walk up from *start* until a .env file is found, then inject any
    KEY=VALUE pairs into os.environ (existing env vars are NOT overwritten).

    Supports:
      - KEY=VALUE  and  KEY="VALUE"  and  KEY='VALUE'
      - Inline # comments after the value
      - Blank lines and full-line # comments are ignored
      - export KEY=VALUE  prefix is stripped
    """
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
            return  # stop at first .env found


_load_dotenv()

# ── Load llama_gate section from production config (required — no defaults) ──
def _require_lg(cfg: dict, key: str) -> object:
    if key not in cfg:
        raise KeyError(
            f"llama_gate: required config key '{key}' missing from 'llama_gate' section. "
            "Add it to configs/production/v1_multi_2026_03.json under 'llama_gate'."
        )
    return cfg[key]


from config_layer.production_config import get_prod_section as _get_section
_LG_CFG = _get_section("llama_gate")

SERVER_URL:           str   = str(_require_lg(_LG_CFG, "server_url"))
_REQUEST_TIMEOUT:     float = float(_require_lg(_LG_CFG, "request_timeout"))
_PROBE_TIMEOUT:       float = float(_require_lg(_LG_CFG, "probe_timeout"))
_FAIL_COUNT_DISABLE:  int   = int(_require_lg(_LG_CFG, "fail_count_disable"))
_SCORE_N_PREDICT:     int   = int(_require_lg(_LG_CFG, "score_n_predict"))
_SCORE_TEMPERATURE:   float = float(_require_lg(_LG_CFG, "score_temperature"))
_INSIGHT_MAX_TOKENS:  int   = int(_require_lg(_LG_CFG, "insight_max_tokens"))
_INSIGHT_TEMPERATURE: float = float(_require_lg(_LG_CFG, "insight_temperature"))

# Chat config — optional keys; graceful defaults until added to production config
_CHAT_MAX_TOKENS:  int   = int(_LG_CFG.get("chat_max_tokens", 512))
_CHAT_TEMPERATURE: float = float(_LG_CFG.get("chat_temperature", 0.2))
_CHAT_STOP_SEQS:   list  = list(_LG_CFG.get("chat_stop_sequences", ["<|user|>", "</s>"]))

# Groq fallback config — optional keys, safe defaults
_GROQ_FALLBACK_ENABLED:  bool  = bool(_LG_CFG.get("groq_fallback_enabled", True))
_GROQ_MODEL:             str   = str(_LG_CFG.get("groq_model", "llama3-70b-8192"))
_GROQ_SCORE_MAX_TOKENS:  int   = int(_LG_CFG.get("groq_score_max_tokens", 8))
_GROQ_SCORE_TEMPERATURE: float = float(_LG_CFG.get("groq_score_temperature", 0.0))

# API key resolution — read from os.environ (populated by _load_dotenv above).
_GROQ_API_KEY:  str = os.environ.get("GROQ_API_KEY", "")
_GROQ_ENDPOINT: str = "https://api.groq.com/openai/v1/chat/completions"

# Audit log path
_LLM_AUDIT_LOG: str = str(_LG_CFG.get("audit_log_path", "logs/llm_audit.jsonl"))

# Chat circuit-breaker counter (independent from scoring counter in llm_scorer.py)
FAIL_COUNT = 0


def _groq_available() -> bool:
    """Return True iff Groq fallback is enabled AND an API key is present."""
    if not _GROQ_FALLBACK_ENABLED:
        return False
    if not _GROQ_API_KEY:
        logger.warning(
            "llama_gate: GROQ_API_KEY not set — Groq fallback disabled. "
            "Add it to the .env file at the repo root: GROQ_API_KEY=gsk_..."
        )
        return False
    return True


def _groq_request(
    messages: list[dict],
    max_tokens: int,
    temperature: float,
    stop: list[str] | None = None,
) -> str:
    """
    POST to the Groq chat-completions endpoint via stdlib urllib (no openai package).

    Returns the assistant content string, or "" on any error.
    """
    payload: dict = {
        "model": _GROQ_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if stop:
        payload["stop"] = stop

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        _GROQ_ENDPOINT,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_GROQ_API_KEY}",
            # Cloudflare 1010 blocks Python's default urllib UA — mimic the Groq SDK
            "User-Agent": "groq-python/0.9.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return body["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as exc:
        logger.error(
            "_groq_request: HTTP %s — %s",
            exc.code,
            exc.read().decode("utf-8", errors="replace")[:200],
        )
        return ""
    except Exception as exc:
        logger.error("_groq_request: failed: %s", exc)
        return ""


def _append_llm_audit(record: dict) -> None:
    """Append one JSONL line to the LLM audit log (fire-and-forget, never raises)."""
    try:
        Path(_LLM_AUDIT_LOG).parent.mkdir(parents=True, exist_ok=True)
        with open(_LLM_AUDIT_LOG, "a", encoding="utf-8") as _f:
            _f.write(json.dumps(record) + "\n")
    except Exception as _exc:
        logger.debug("llm_audit write failed: %s", _exc)


def llm_chat(
    messages: list[dict],
    max_tokens: int = _CHAT_MAX_TOKENS,
    stop: list[str] | None = None,
    temperature: float = _CHAT_TEMPERATURE,
    endpoint: str = SERVER_URL,
) -> str:
    """
    Multi-turn chat with the local inference server, with Groq fallback.

    Flattens a messages list to BitNet-compatible prompt format
    (<|system|> / <|user|> / <|assistant|> markers).

    Parameters
    ----------
    messages    : list of {"role": "system"|"user"|"assistant", "content": str}
    max_tokens  : max tokens to generate
    stop        : stop sequences (defaults to _CHAT_STOP_SEQS)
    temperature : sampling temperature (0.0 = deterministic)
    endpoint    : inference server URL

    Returns
    -------
    str — raw model output; "" on all-backend failure so callers handle gracefully
    """
    global FAIL_COUNT

    parts = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            parts.append(f"<|system|>\n{content}")
        elif role == "user":
            parts.append(f"<|user|>\n{content}")
        elif role == "assistant":
            parts.append(f"<|assistant|>\n{content}")
    parts.append("<|assistant|>")  # open assistant turn
    prompt = "\n".join(parts)

    # Debug: print full prompt being sent to LLM
    print("\n" + "=" * 80)
    print("📤 LLM FULL INPUT PAYLOAD:")
    print(prompt)
    print("=" * 80 + "\n")

    # ── Try primary endpoint ────────────────────────────────────────────────
    try:
        payload = {
            "prompt": prompt,
            "n_predict": max_tokens,
            "temperature": temperature,
            "stop": stop if stop is not None else _CHAT_STOP_SEQS,
            "cache_prompt": False,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            endpoint, data=data, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as response:
            result = json.loads(response.read().decode("utf-8"))
            raw = result.get("content", "").strip()
            logger.debug("llm_chat (%d chars): %s", len(raw), raw[:80])
            FAIL_COUNT = 0
            return raw
    except (urllib.error.URLError, TimeoutError):
        pass

    # ── Groq fallback ───────────────────────────────────────────────────────
    if _groq_available():
        logger.debug("llm_chat: local server unreachable, falling back to Groq cloud")
        raw = _groq_request(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=stop if stop is not None else _CHAT_STOP_SEQS,
        )
        if raw:
            logger.debug("llm_chat (Groq) (%d chars): %s", len(raw), raw[:80])
            FAIL_COUNT = 0
            return raw
        logger.debug("llm_chat: Groq fallback also failed")

    # ── All endpoints failed ────────────────────────────────────────────────
    FAIL_COUNT += 1
    if FAIL_COUNT == _FAIL_COUNT_DISABLE:
        logger.warning(
            "llm_chat: all endpoints unreachable after %d attempts. "
            "Circuit breaker activated. Suppressing future warnings.",
            _FAIL_COUNT_DISABLE,
        )
    elif FAIL_COUNT < _FAIL_COUNT_DISABLE:
        logger.warning(
            "llm_chat: server unreachable, attempt %d/%d, returning empty string",
            FAIL_COUNT, _FAIL_COUNT_DISABLE,
        )
    return ""


# ── Backward-compatibility re-exports (lazy via PEP 562 __getattr__) ─────────
# Callers that do ``import config_layer.llm_inference_client as lg`` and then
# access lg.llm_score, lg.build_insight_prompt, etc. continue to work unchanged.
# New code should import directly from llm_scorer or llm_narrative.
#
# Lazy loading (instead of eager ``from llm_scorer import ...`` at module level)
# breaks the mutual-import cycle:
#   llm_scorer     → imports from llm_inference_client (transport vars)
#   llm_inference_client → re-exports from llm_scorer
# If the re-exports were eager, importing llm_scorer first would cause Python to
# start loading llm_inference_client which would immediately try to import the
# partially-initialised llm_scorer → ImportError on the first access.
# __getattr__ is only called AFTER this module is fully initialised, so by the
# time any attribute is looked up, llm_scorer can import cleanly.

_SCORER_NAMES: frozenset = frozenset({
    "build_prompt", "llm_score", "llm_score_safe", "llm_score_batch",
    "llm_score_cached", "cached_llm_score", "LLMEndpointUnavailableError",
    "_groq_score",   # also re-exported for test backward compat
})
_NARRATIVE_NAMES: frozenset = frozenset({
    "_INSIGHT_PROMPTS", "build_insight_prompt", "llm_insight", "_fallback_insight",
})


def __getattr__(name: str):  # noqa: N807 — PEP 562 module-level __getattr__
    """Lazy backward-compat re-export; triggered by ``from llm_inference_client import X``."""
    import sys as _sys
    _mod = _sys.modules[__name__]

    if name in _SCORER_NAMES:
        from config_layer.llm_scorer import (       # noqa: PLC0415
            build_prompt, llm_score, llm_score_safe, llm_score_batch,
            llm_score_cached, cached_llm_score, LLMEndpointUnavailableError,
            _groq_score,
        )
        # Cache on the module object so subsequent access is O(1) dict lookup.
        _mod.build_prompt              = build_prompt
        _mod.llm_score                 = llm_score
        _mod.llm_score_safe            = llm_score_safe
        _mod.llm_score_batch           = llm_score_batch
        _mod.llm_score_cached          = llm_score_cached
        _mod.cached_llm_score          = cached_llm_score
        _mod.LLMEndpointUnavailableError = LLMEndpointUnavailableError
        _mod._groq_score               = _groq_score
        return locals()[name]

    if name in _NARRATIVE_NAMES:
        from config_layer.llm_narrative import (    # noqa: PLC0415
            _INSIGHT_PROMPTS, build_insight_prompt, llm_insight, _fallback_insight,
        )
        _mod._INSIGHT_PROMPTS      = _INSIGHT_PROMPTS
        _mod.build_insight_prompt  = build_insight_prompt
        _mod.llm_insight           = llm_insight
        _mod._fallback_insight     = _fallback_insight
        return locals()[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
