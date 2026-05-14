"""
llm_inference_client.py
═══════════════════════════════════════════════════════════════════════════════
LLM inference client providing scoring, narrative generation, and chat via a
persistent local inference server (llama.cpp) with Groq cloud fallback.

Also provides llm_insight() — generative narrative reporting for trade
decisions, session summaries, and evaluation reports. Used by insight_reporter.
"""

import json
import logging
import re
import os
import time as _time
import urllib.request
import urllib.error
from functools import lru_cache
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

# ── Load llama_gate section from production config (required — no defaults) ────
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
_CHAT_MAX_TOKENS:   int   = int(_LG_CFG.get("chat_max_tokens", 512))
_CHAT_TEMPERATURE:  float = float(_LG_CFG.get("chat_temperature", 0.2))
_CHAT_STOP_SEQS:    list  = list(_LG_CFG.get("chat_stop_sequences", ["<|user|>", "</s>"]))

# Groq fallback for llm_score — optional keys, safe defaults
_GROQ_FALLBACK_ENABLED:    bool  = bool(_LG_CFG.get("groq_fallback_enabled", True))
_GROQ_MODEL:               str   = str(_LG_CFG.get("groq_model", "llama3-70b-8192"))
_GROQ_SCORE_MAX_TOKENS:    int   = int(_LG_CFG.get("groq_score_max_tokens", 8))
_GROQ_SCORE_TEMPERATURE:   float = float(_LG_CFG.get("groq_score_temperature", 0.0))

# API key resolution — read from os.environ (populated by _load_dotenv above).
# Worker processes spawned by ProcessPoolExecutor import the module fresh and
# re-run _load_dotenv(), so the key is always available without pickling.
_GROQ_API_KEY: str = os.environ.get("GROQ_API_KEY", "")
_GROQ_ENDPOINT: str = "https://api.groq.com/openai/v1/chat/completions"


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
        logger.error("_groq_request: HTTP %s — %s", exc.code, exc.read().decode("utf-8", errors="replace")[:200])
        return ""
    except Exception as exc:
        logger.error("_groq_request: failed: %s", exc)
        return ""


FAIL_COUNT = 0

# ── LLM call audit log ────────────────────────────────────────────────────────
_LLM_AUDIT_LOG: str = str(_LG_CFG.get("audit_log_path", "logs/llm_audit.jsonl"))


def _append_llm_audit(record: dict) -> None:
    """Append one JSONL line to the LLM audit log (fire-and-forget, never raises)."""
    try:
        Path(_LLM_AUDIT_LOG).parent.mkdir(parents=True, exist_ok=True)
        with open(_LLM_AUDIT_LOG, "a", encoding="utf-8") as _f:
            _f.write(json.dumps(record) + "\n")
    except Exception as _exc:
        logger.debug("llm_audit write failed: %s", _exc)


def _groq_score(prompt: str) -> tuple[float, str]:
    """
    Call Groq cloud API to score a prompt string via stdlib urllib (no openai package).

    Returns
    -------
    (score, raw_output)
        score      : float in [0.0, 1.0], or 1.0 on any failure (fail-open)
        raw_output : raw text the model returned, or "" on failure

    Raises nothing — all errors are caught and logged.
    """
    if not _groq_available():
        return 1.0, ""

    raw = _groq_request(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=_GROQ_SCORE_MAX_TOKENS,
        temperature=_GROQ_SCORE_TEMPERATURE,
    )
    logger.debug("_groq_score raw output: '%s'", raw)

    if not raw:
        return 1.0, ""

    match = re.search(r"\b(0\.\d+|1\.0|0\.0)\b", raw)
    if match:
        score = max(0.0, min(1.0, float(match.group(1))))
        logger.info("_groq_score → %.4f  (model=%s  raw='%s')", score, _GROQ_MODEL, raw)
        return score, raw
    else:
        logger.warning("_groq_score: could not parse float from '%s'. Returning 1.0.", raw)
        return 1.0, raw


def build_prompt(metrics: dict) -> str:
    """
    Constructs a strict, zero-shot prompt forcing a numeric output.
    """
    prompt = (
        "You are a strict quantitative trading risk evaluator. "
        "Review the following backtest metrics and output a single float between "
        "0.0 (terrible, high risk of overfitting) and 1.0 (excellent, robust). "
        "Do not include any other text, explanations, or formatting.\n\n"
        f"Metrics:\n"
        f"Win Rate: {metrics.get('win_rate', 0):.2%}\n"
        f"Expectancy: {metrics.get('expectancy_rr', 0):.2f}R\n"
        f"Trades: {metrics.get('approved_trades', 0)}\n"
        f"Max Drawdown: {metrics.get('max_drawdown_pct', 0):.2%}\n"
        f"Expansions to Retests Ratio: {metrics.get('retests', 0)} / {max(metrics.get('expansions', 1), 1)}\n\n"
        "Score:"
    )
    return prompt

def llm_score(metrics: dict, endpoint: str = SERVER_URL) -> float:
    """
    Calls the local inference server. Returns 1.0 on failure to ensure the pipeline
    doesn't break, but logs the error. Returns 0.0 if the LLM explicitly rejects the metrics.

    Every call — success or failure — is appended to logs/llm_audit.jsonl with:
        timestamp, source (local/groq/failopen), endpoint, prompt, raw_output, parsed_score, status

    Fallback chain:
        1. Local llama.cpp server (SERVER_URL)
        2. Groq cloud API  ← if groq_fallback_enabled=true and local fails
        3. fail-open 1.0   ← if both unavailable
    """
    prompt = build_prompt(metrics)
    _t0 = _time.time()

    # ── 1. Try local llama.cpp ──────────────────────────────────────────────
    payload = {
        "prompt": prompt,
        "n_predict": _SCORE_N_PREDICT,
        "temperature": _SCORE_TEMPERATURE,
        "cache_prompt": True,
    }
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(endpoint, data=data, headers={'Content-Type': 'application/json'})

    _local_error: str | None = None
    try:
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as response:
            result = json.loads(response.read().decode('utf-8'))
            raw_output = result.get('content', '').strip()
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
            else:
                logger.warning("Local LLM: could not parse float from '%s'.", raw_output)
                _local_error = f"parse_failed: '{raw_output}'"

    except urllib.error.URLError as e:
        _local_error = f"{'timeout' if isinstance(e.reason, TimeoutError) else 'url_error'}: {e}"
        logger.warning("Local LLM unavailable (%s) — trying Groq fallback.", _local_error)
    except Exception as e:
        _local_error = f"exception: {e}"
        logger.error("Local LLM unexpected error (%s) — trying Groq fallback.", _local_error)

    # ── 2. Groq fallback ───────────────────────────────────────────────────
    if _groq_available():
        groq_score, groq_raw = _groq_score(prompt)
        if groq_raw:
            # Groq responded — write audit and return its score
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
                "parsed_score":  groq_score,
                "local_error":   _local_error,
            })
            logger.info("llm_score [groq:%s] → %.4f  raw='%s'", _GROQ_MODEL, groq_score, groq_raw)
            return groq_score
        # groq_raw == "" → Groq API itself failed; fall through to failopen
        logger.warning("llm_score: Groq also failed — falling to fail-open.")

    # ── 3. fail-open ───────────────────────────────────────────────────────
    logger.warning(
        "llm_score: all backends failed (local=%s, groq_enabled=%s, groq_key_set=%s). "
        "Returning 1.0 (fail-open).",
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
class LLMEndpointUnavailableError(RuntimeError):
    """Raised when the LLM endpoint cannot be reached and no fallback is configured."""
    pass


def llm_score_batch(
    metrics_list: list[dict],
    endpoint: str = SERVER_URL,
    fail_on_unavailable: bool = False,
) -> list[float]:
    """
    Score a batch of metrics dicts via the LLM inference server.

    ISSUE 7 FIX: Previously this function had a payload dict but no HTTP call,
    response parsing, or return statement — it returned None silently.

    Strategy:
      - Each item in metrics_list is scored via llm_score() (which has its own
        retry / timeout logic and returns 1.0 on failure).
      - If the endpoint is unavailable for ALL items → raises
        LLMEndpointUnavailableError when fail_on_unavailable=True,
        or returns [1.0, ...] when fail_on_unavailable=False (safe mode).

    Args:
        metrics_list: list of metric dicts (each passed to llm_score individually)
        endpoint: LLM server URL (default: SERVER_URL)
        fail_on_unavailable: if True, raise LLMEndpointUnavailableError when
                             the endpoint cannot be reached for any item.
                             Default False → safe mode (returns 1.0 per item).

    Returns:
        list[float] of length len(metrics_list), each in [0.0, 1.0]

    Raises:
        LLMEndpointUnavailableError: if fail_on_unavailable=True and endpoint
                                     is unreachable for all items
    """
    if not metrics_list:
        return []

    scores: list[float] = []
    failure_count = 0

    for metrics in metrics_list:
        try:
            score = llm_score(metrics, endpoint=endpoint)
            # llm_score returns 1.0 on connection failure — detect this case
            # by checking if it's exactly 1.0 when no prior success occurred.
            scores.append(score)
        except Exception as exc:
            logger.error("llm_score_batch: unexpected error scoring item: %s", exc)
            failure_count += 1
            scores.append(1.0)

    # Check if all items returned the "unavailable" sentinel (1.0)
    if fail_on_unavailable and len(scores) > 0:
        # Probe endpoint directly to distinguish "all scored 1.0" from "endpoint down"
        probe_payload = json.dumps({
            "prompt": "test",
            "n_predict": 1,
            "temperature": 0.0,
        }).encode("utf-8")
        probe_req = urllib.request.Request(
            endpoint,
            data=probe_payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(probe_req, timeout=_PROBE_TIMEOUT):
                pass  # endpoint is up
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
FAIL_COUNT = 0

def llm_score_safe(metrics):
    global FAIL_COUNT
    
    try:
        score = llm_score(metrics)
        FAIL_COUNT = 0
        return score
    except:
        FAIL_COUNT += 1
        if FAIL_COUNT > _FAIL_COUNT_DISABLE:
            return 1.0  # disable gate
        return 1.0


# ─────────────────────────────────────────────────────────────────────────────
# GENERATIVE INSIGHT FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

_INSIGHT_PROMPTS = {
    "trade_decision": (
        "You are a senior quantitative trading analyst. Review this CRT trade evaluation and write "
        "2-3 clear sentences explaining the decision to a trader. Be specific about which sub-scores "
        "are strong or weak and why the decision was made. No bullet points — prose only.\n\n"
        "Trade Data:\n"
        "  Gaussian Score:     {gaussian_score}\n"
        "  ML Expected RR:     {ml_expected_rr}\n"
        "  ML Win Probability: {ml_win_prob}\n"
        "  Sweep Score:        {sweep}\n"
        "  Breakout Score:     {breakout}\n"
        "  Retest Score:       {retest}\n"
        "  Time Decay Score:   {time}\n"
        "  Final Decision:     {decision}\n"
        "  Decision Reason:    {reason}\n\n"
        "Analyst Narrative:"
    ),
    "session_summary": (
        "You are a trading performance analyst. Summarize this trading session in 3 sentences. "
        "Identify the key driver of performance (positive or negative) and give one actionable insight. "
        "No bullet points — prose only.\n\n"
        "Session Data:\n"
        "  Symbol:             {symbol}\n"
        "  Session:            {session}\n"
        "  Total Trades:       {n_trades}\n"
        "  Approved Trades:    {approved_trades}\n"
        "  Win Rate:           {win_rate}\n"
        "  Net RR:             {net_rr}\n"
        "  Avg Gaussian Score: {avg_gaussian}\n"
        "  Avg ML Expected RR: {avg_ml_rr}\n"
        "  Max Drawdown:       {max_drawdown}\n\n"
        "Session Narrative:"
    ),
    "eval_report": (
        "You are a model evaluation specialist. Write a 3-sentence assessment of this model's "
        "performance. Focus on what the correlation and calibration numbers mean in practical "
        "trading terms. No bullet points — prose only.\n\n"
        "Evaluation Data:\n"
        "  Model Type:              {model_type}\n"
        "  Samples Evaluated:       {n_samples}\n"
        "  Corr(expected_rr, pnl):  {corr_expected_rr}\n"
        "  Calibration Error:       {calibration_error}\n"
        "  Mean Predicted RR:       {mean_expected_rr}\n"
        "  Mean Actual RR:          {mean_actual_rr}\n"
        "  Class Distribution:      {class_distribution}\n\n"
        "Evaluation Narrative:"
    ),
    "backtest_summary": (
        "You are a trading system analyst reviewing a backtest. Write 4 sentences summarizing "
        "the system's overall performance quality, risk profile, and whether it appears robust "
        "or overfitted. Conclude with one concrete recommendation. No bullet points — prose only.\n\n"
        "Backtest Results:\n"
        "  Symbol:          {symbol}\n"
        "  Total Trades:    {total_trades}\n"
        "  Win Rate:        {win_rate}\n"
        "  Expectancy:      {expectancy_rr}\n"
        "  Max Drawdown:    {max_drawdown_pct}\n"
        "  Sharpe (est):    {sharpe}\n"
        "  Expansions:      {expansions}\n"
        "  Retests:         {retests}\n\n"
        "Backtest Narrative:"
    ),
    "regime_alert": (
        "You are a market regime analyst. In 2 sentences, explain what this regime shift means "
        "for the current trading strategy and what adjustment is recommended. No bullet points — prose only.\n\n"
        "Regime Data:\n"
        "  Previous Regime: {prev_regime}\n"
        "  Current Regime:  {curr_regime}\n"
        "  Volatility:      {volatility}\n"
        "  Session:         {session}\n"
        "  Symbol:          {symbol}\n\n"
        "Regime Alert:"
    ),
}


def build_insight_prompt(context: dict, report_type: str) -> str:
    """
    Build a generative narrative prompt for the local LLM.

    Parameters
    ----------
    context     : dict of values matching the template's {placeholders}
    report_type : one of 'trade_decision', 'session_summary', 'eval_report',
                  'backtest_summary', 'regime_alert'

    Returns
    -------
    str — formatted prompt ready for the inference server
    """
    template = _INSIGHT_PROMPTS.get(report_type)
    if template is None:
        raise ValueError(
            f"Unknown report_type '{report_type}'. "
            f"Valid types: {list(_INSIGHT_PROMPTS.keys())}"
        )
    safe_ctx = {k: (v if v is not None else "N/A") for k, v in context.items()}
    # Fill any missing placeholders with "N/A"
    all_keys = re.findall(r"\{(\w+)\}", template)
    for k in all_keys:
        safe_ctx.setdefault(k, "N/A")
    try:
        return template.format_map(safe_ctx)
    except Exception as e:
        logger.warning(f"build_insight_prompt: format error for report_type='{report_type}': {e}")
        return template.format_map({k: "N/A" for k in all_keys})


def llm_insight(
    context: dict,
    report_type: str,
    endpoint: str = SERVER_URL,
    max_tokens: int = _INSIGHT_MAX_TOKENS,
    timeout: float = 8.0,
) -> str:
    """
    Call the local inference server for a narrative insight report.

    Unlike llm_score() which returns a float, this returns a natural-language
    string. Used by insight_reporter.py for trade/session/eval narration.

    Parameters
    ----------
    context     : dict with values for the prompt template
    report_type : one of 'trade_decision', 'session_summary', 'eval_report',
                  'backtest_summary', 'regime_alert'
    endpoint    : inference server URL
    max_tokens  : max tokens to generate (default 300)
    timeout     : request timeout in seconds (default 8.0)

    Returns
    -------
    str — generated narrative, or a static fallback on failure
    """
    try:
        prompt = build_insight_prompt(context, report_type)
    except Exception as e:
        logger.error(f"llm_insight: failed to build prompt: {e}")
        return _fallback_insight(context, report_type)

    payload = {
        "prompt": prompt,
        "n_predict": max_tokens,
        "temperature": _INSIGHT_TEMPERATURE,
        "stop": ["\n\n", "---"],
        "cache_prompt": False,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        endpoint, data=data, headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
            raw = result.get("content", "").strip()
            if raw:
                logger.debug(f"LLM insight ({report_type}): {raw[:120]}...")
                return raw
            else:
                logger.warning("llm_insight: empty response from server, using fallback")
                return _fallback_insight(context, report_type)

    except urllib.error.URLError as e:
        if isinstance(e.reason, TimeoutError):
            logger.warning(f"llm_insight: server timed out (>{timeout}s), using fallback")
        else:
            logger.warning(f"llm_insight: server unreachable ({e}), using fallback")
        return _fallback_insight(context, report_type)
    except Exception as e:
        logger.error(f"llm_insight: unexpected error: {e}, using fallback")
        return _fallback_insight(context, report_type)


def llm_chat(
    messages: list[dict],
    max_tokens: int = _CHAT_MAX_TOKENS,
    stop: list[str] | None = None,
    temperature: float = _CHAT_TEMPERATURE,
    endpoint: str = SERVER_URL,
) -> str:
    """
    Multi-turn chat with the local inference server.

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
    str — raw model output (caller parses JSON if needed).
    Returns "" on any error so callers can handle gracefully.
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
    print("\n" + "="*80)
    print("📤 LLM FULL INPUT PAYLOAD:")
    print(prompt)
    print("="*80 + "\n")

    # Try primary endpoint first
    try:
        payload = {
            "prompt": prompt,
            "n_predict": max_tokens,
            "temperature": temperature,
            "stop": stop if stop is not None else _CHAT_STOP_SEQS,
            "cache_prompt": False,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(endpoint, data=data, headers={"Content-Type": "application/json"})
        
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as response:
            result = json.loads(response.read().decode("utf-8"))
            raw = result.get("content", "").strip()
            logger.debug("llm_chat (%d chars): %s", len(raw), raw[:80])
            FAIL_COUNT = 0
            return raw
    except (urllib.error.URLError, TimeoutError) as e:
        pass
    
    # Fallback to Groq if available (pure urllib — no openai package required)
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

    # All endpoints failed
    FAIL_COUNT += 1
    
    # Circuit breaker: fast fail after threshold
    if FAIL_COUNT > _FAIL_COUNT_DISABLE:
        return ""
    
    if FAIL_COUNT == _FAIL_COUNT_DISABLE:
        logger.warning("llm_chat: all endpoints unreachable after %d attempts. Circuit breaker activated. Suppressing future warnings.", _FAIL_COUNT_DISABLE)
    elif FAIL_COUNT < _FAIL_COUNT_DISABLE:
        logger.warning("llm_chat: server unreachable, attempt %d/%d, returning empty string", FAIL_COUNT, _FAIL_COUNT_DISABLE)
    
    return ""


def _fallback_insight(context: dict, report_type: str) -> str:
    """
    Static fallback when the LLM server is unavailable.
    Mirrors what a static logger would have produced.
    """
    if report_type == "trade_decision":
        return (
            f"Trade decision: {context.get('decision', 'N/A')} "
            f"(reason: {context.get('reason', 'N/A')}). "
            f"Gaussian={context.get('gaussian_score', 'N/A')}, "
            f"ML expected RR={context.get('ml_expected_rr', 'N/A')}, "
            f"win prob={context.get('ml_win_prob', 'N/A')}."
        )
    elif report_type == "session_summary":
        return (
            f"Session {context.get('session', 'N/A')} on {context.get('symbol', 'N/A')}: "
            f"{context.get('approved_trades', 'N/A')} approved trades, "
            f"win rate {context.get('win_rate', 'N/A')}, "
            f"net RR {context.get('net_rr', 'N/A')}, "
            f"max drawdown {context.get('max_drawdown', 'N/A')}."
        )
    elif report_type == "eval_report":
        return (
            f"Model evaluation ({context.get('model_type', 'N/A')}): "
            f"n={context.get('n_samples', 'N/A')}, "
            f"corr(expected_rr, pnl)={context.get('corr_expected_rr', 'N/A')}, "
            f"calibration error={context.get('calibration_error', 'N/A')}."
        )
    elif report_type == "backtest_summary":
        return (
            f"Backtest {context.get('symbol', 'N/A')}: "
            f"{context.get('total_trades', 'N/A')} trades, "
            f"win rate {context.get('win_rate', 'N/A')}, "
            f"expectancy {context.get('expectancy_rr', 'N/A')}, "
            f"max drawdown {context.get('max_drawdown_pct', 'N/A')}."
        )
    elif report_type == "regime_alert":
        return (
            f"Regime shift: {context.get('prev_regime', 'N/A')} → "
            f"{context.get('curr_regime', 'N/A')} "
            f"on {context.get('symbol', 'N/A')} ({context.get('session', 'N/A')})."
        )
    else:
        return f"[{report_type}] " + str(context)
