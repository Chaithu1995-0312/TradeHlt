"""
llm_scorer.py
═══════════════════════════════════════════════════════════════════════════════
LLM score-computation layer — builds prompts and routes scoring requests
through the local llama.cpp server (primary) and Groq cloud (fallback).

Extracted from llm_inference_client.py (3-way split). All HTTP primitives
and shared config vars live in llm_inference_client.py; this module imports
only what it needs and owns the numeric-output responsibility.

Public API
----------
  build_prompt(metrics)            → str
  llm_score(metrics, endpoint)     → float
  llm_score_batch(metrics_list)    → list[float]
  llm_score_safe(metrics)          → float   (circuit-breaker wrapper)
  llm_score_cached(metrics)        → float
  cached_llm_score(key)            → float   (lru_cache variant)
  LLMEndpointUnavailableError      exception
"""
from __future__ import annotations

import json
import logging
import re
import time as _time
import urllib.request
import urllib.error
from functools import lru_cache

from config_layer.llm_inference_client import (
    SERVER_URL,
    _REQUEST_TIMEOUT,
    _PROBE_TIMEOUT,
    _FAIL_COUNT_DISABLE,
    _SCORE_N_PREDICT,
    _SCORE_TEMPERATURE,
    _GROQ_MODEL,
    _GROQ_SCORE_MAX_TOKENS,
    _GROQ_SCORE_TEMPERATURE,
    _groq_available,
    _groq_request,
    _append_llm_audit,
)

logger = logging.getLogger("LlamaGate")

# Independent circuit-breaker counter for scoring (separate from llm_chat counter)
FAIL_COUNT = 0
# True once the circuit has tripped — callers query this to distinguish
# "LLM scored 1.0" from "LLM gate is open and returning neutral fallback"
CIRCUIT_OPEN = False


class LLMEndpointUnavailableError(RuntimeError):
    """Raised when the LLM endpoint cannot be reached and no fallback is configured."""


def build_prompt(metrics: dict) -> str:
    """Constructs a strict, zero-shot prompt forcing a numeric output in [0.0, 1.0]."""
    return (
        "You are a strict quantitative trading risk evaluator. "
        "Review the following backtest metrics and output a single float between "
        "0.0 (terrible, high risk of overfitting) and 1.0 (excellent, robust). "
        "Do not include any other text, explanations, or formatting.\n\n"
        "Metrics:\n"
        f"Win Rate: {metrics.get('win_rate', 0):.2%}\n"
        f"Expectancy: {metrics.get('expectancy_rr', 0):.2f}R\n"
        f"Trades: {metrics.get('approved_trades', 0)}\n"
        f"Max Drawdown: {metrics.get('max_drawdown_pct', 0):.2%}\n"
        f"Expansions to Retests Ratio: {metrics.get('retests', 0)} / "
        f"{max(metrics.get('expansions', 1), 1)}\n\n"
        "Score:"
    )


def _groq_score(prompt: str) -> tuple[float, str]:
    """
    Call Groq cloud API to score a prompt string via stdlib urllib.

    Returns (score, raw_output) — score in [0.0, 1.0], or (1.0, "") on failure.
    Raises nothing.
    """
    if not _groq_available():
        return 1.0, ""  # fail-open neutral (see docstring; CLAUDE.md §4)

    # Late-bind _groq_request through the parent module so that monkeypatch
    # on llm_inference_client._groq_request (the standard test pattern) is
    # visible here at call time, not just at module-load time.
    import config_layer.llm_inference_client as _client
    _groq_req = getattr(_client, "_groq_request", _groq_request)

    raw = _groq_req(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=_GROQ_SCORE_MAX_TOKENS,
        temperature=_GROQ_SCORE_TEMPERATURE,
    )
    logger.debug("_groq_score raw output: '%s'", raw)

    if not raw:
        return 1.0, ""  # fail-open neutral

    match = re.search(r"\b(0\.\d+|1\.0|0\.0)\b", raw)
    if match:
        score = max(0.0, min(1.0, float(match.group(1))))
        logger.info("_groq_score → %.4f  (model=%s  raw='%s')", score, _GROQ_MODEL, raw)
        return score, raw
    logger.warning("_groq_score: could not parse float from '%s'. Returning 1.0 (fail-open neutral).", raw)
    return 1.0, raw


def llm_score(metrics: dict, endpoint: str = SERVER_URL) -> float:
    """
    Score a metrics dict via the local inference server with Groq fallback.

    Returns 1.0 on failure (fail-open). Every call is appended to
    logs/llm_audit.jsonl regardless of outcome.

    Fallback chain:
        1. Local llama.cpp server (SERVER_URL)
        2. Groq cloud API  ← if groq_fallback_enabled=true and local fails
        3. fail-open 1.0   ← if both unavailable
    """
    from config_layer.llm_inference_client import _GROQ_FALLBACK_ENABLED, _GROQ_API_KEY

    prompt = build_prompt(metrics)
    _t0 = _time.time()

    # ── 1. Try local llama.cpp ──────────────────────────────────────────────
    payload = {
        "prompt": prompt,
        "n_predict": _SCORE_N_PREDICT,
        "temperature": _SCORE_TEMPERATURE,
        "cache_prompt": True,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        endpoint, data=data, headers={"Content-Type": "application/json"}
    )

    _local_error: str | None = None
    try:
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as response:
            result = json.loads(response.read().decode("utf-8"))
            raw_output = result.get("content", "").strip()
            logger.debug("Local LLM raw output: '%s'", raw_output)

            match = re.search(r"\b(0\.\d+|1\.0|0\.0)\b", raw_output)
            if match:
                score = max(0.0, min(1.0, float(match.group(1))))
                _append_llm_audit({
                    "ts":            _time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "elapsed_ms":    round((_time.time() - _t0) * 1000, 1),
                    "source":        "local",
                    "endpoint":      endpoint,
                    "model":         "llama.cpp-local",
                    "status":        "ok",
                    "input_metrics": metrics,
                    "prompt":        prompt,
                    "raw_output":    raw_output,
                    "parsed_score":  score,
                })
                logger.info("llm_score [local] → %.4f  raw='%s'", score, raw_output)
                return score
            logger.warning("Local LLM: could not parse float from '%s'.", raw_output)
            _local_error = f"parse_failed: '{raw_output}'"

    except urllib.error.URLError as e:
        _local_error = (
            f"{'timeout' if isinstance(e.reason, TimeoutError) else 'url_error'}: {e}"
        )
        logger.warning("Local LLM unavailable (%s) — trying Groq fallback.", _local_error)
    except Exception as e:
        _local_error = f"exception: {e}"
        logger.error("Local LLM unexpected error (%s) — trying Groq fallback.", _local_error)

    # ── 2. Groq fallback ───────────────────────────────────────────────────
    if _groq_available():
        groq_score_val, groq_raw = _groq_score(prompt)
        if groq_raw:
            _append_llm_audit({
                "ts":            _time.strftime("%Y-%m-%dT%H:%M:%S"),
                "elapsed_ms":    round((_time.time() - _t0) * 1000, 1),
                "source":        "groq",
                "endpoint":      f"groq:{_GROQ_MODEL}",
                "model":         _GROQ_MODEL,
                "status":        "ok",
                "input_metrics": metrics,
                "prompt":        prompt,
                "raw_output":    groq_raw,
                "parsed_score":  groq_score_val,
                "local_error":   _local_error,
            })
            logger.info(
                "llm_score [groq:%s] → %.4f  raw='%s'",
                _GROQ_MODEL, groq_score_val, groq_raw,
            )
            return groq_score_val
        logger.warning("llm_score: Groq also failed — falling to fail-open.")

    # ── 3. fail-open neutral ────────────────────────────────────────────────
    # Neutral = 1.0 (multiplier no-op), not 0.5 — the documented contract
    # (module docstring, CLAUDE.md §4, tests/test_llm_connectivity.py). The LLM is an
    # advisory tie-breaker; a failed backend must NOT pull the fused score toward 0.
    logger.warning(
        "llm_score: all backends failed (local=%s, groq_enabled=%s, groq_key_set=%s). "
        "Returning 1.0 (fail-open neutral).",
        _local_error, _GROQ_FALLBACK_ENABLED, bool(_GROQ_API_KEY),
    )
    _append_llm_audit({
        "ts":            _time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_ms":    round((_time.time() - _t0) * 1000, 1),
        "source":        "failopen",
        "endpoint":      endpoint,
        "model":         None,
        "status":        "failopen",
        "input_metrics": metrics,
        "prompt":        prompt,
        "raw_output":    None,
        "parsed_score":  1.0,
        "local_error":   _local_error,
    })
    return 1.0


def llm_score_batch(
    metrics_list: list[dict],
    endpoint: str = SERVER_URL,
    fail_on_unavailable: bool = False,
) -> list[float]:
    """
    Score a batch of metrics dicts via the LLM inference server.

    Returns list[float] of length len(metrics_list), each in [0.0, 1.0].
    Raises LLMEndpointUnavailableError if fail_on_unavailable=True and the
    endpoint is unreachable after all items are scored.
    """
    if not metrics_list:
        return []

    scores: list[float] = []
    for metrics in metrics_list:
        try:
            scores.append(llm_score(metrics, endpoint=endpoint))
        except Exception as exc:
            logger.error("llm_score_batch: unexpected error scoring item: %s", exc)
            scores.append(1.0)  # fail-open neutral

    if fail_on_unavailable and scores:
        probe_payload = json.dumps(
            {"prompt": "test", "n_predict": 1, "temperature": 0.0}
        ).encode("utf-8")
        probe_req = urllib.request.Request(
            endpoint,
            data=probe_payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(probe_req, timeout=_PROBE_TIMEOUT):
                pass
        except Exception as probe_exc:
            raise LLMEndpointUnavailableError(
                f"llm_score_batch: LLM endpoint '{endpoint}' is unavailable. "
                f"Probe failed: {probe_exc}. "
                "Either start the inference server or set fail_on_unavailable=False."
            ) from probe_exc

    return scores


@lru_cache(maxsize=5000)
def cached_llm_score(metrics_key: str) -> float:
    metrics = json.loads(metrics_key)
    return llm_score(metrics)


def llm_score_cached(metrics: dict) -> float:
    key = json.dumps(metrics, sort_keys=True)
    return cached_llm_score(key)


def llm_score_safe(metrics: dict) -> float:
    """Circuit-breaker wrapper: returns 0.5 (neutral abstention) after _FAIL_COUNT_DISABLE failures.

    Callers should check llm_scorer.CIRCUIT_OPEN to distinguish a genuine 0.5
    score from a fallback neutral returned because the gate is disabled.
    """
    global FAIL_COUNT, CIRCUIT_OPEN
    try:
        score = llm_score(metrics)
        FAIL_COUNT = 0
        return score
    except Exception as _exc:
        FAIL_COUNT += 1
        if FAIL_COUNT > _FAIL_COUNT_DISABLE:
            if not CIRCUIT_OPEN:
                CIRCUIT_OPEN = True
                logger.error(
                    "LLM scoring circuit OPEN after %d failures — gate disabled, "
                    "returning neutral 0.5 for all subsequent calls. Last error: %s",
                    FAIL_COUNT, _exc,
                )
            return 0.5  # circuit open — gate disabled
        logger.warning(
            "LLM scoring failure %d/%d — returning neutral 0.5. Error: %s",
            FAIL_COUNT, _FAIL_COUNT_DISABLE, _exc,
        )
        return 0.5  # transient failure — gate still active
