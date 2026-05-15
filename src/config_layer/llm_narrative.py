"""
llm_narrative.py
═══════════════════════════════════════════════════════════════════════════════
LLM narrative-generation layer — prompt templates and generative-insight
functions that produce prose reports for trade decisions, session summaries,
model evaluations, backtest results, and regime alerts.

Extracted from llm_inference_client.py (3-way split). HTTP primitives and
shared config vars live in llm_inference_client.py.

Public API
----------
  build_insight_prompt(context, report_type)  → str
  llm_insight(context, report_type, ...)      → str  (prose narrative)
  _fallback_insight(context, report_type)     → str  (static fallback)
  _INSIGHT_PROMPTS                            dict   (template registry)
"""
from __future__ import annotations

import json
import logging
import re
import urllib.request
import urllib.error

from config_layer.llm_inference_client import (
    SERVER_URL,
    _INSIGHT_MAX_TOKENS,
    _INSIGHT_TEMPERATURE,
)

logger = logging.getLogger("LlamaGate")

# ── Prompt templates (one per report type) ────────────────────────────────────
_INSIGHT_PROMPTS: dict[str, str] = {
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

    Raises
    ------
    ValueError  if report_type is not in _INSIGHT_PROMPTS
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
        logger.warning(
            "build_insight_prompt: format error for report_type='%s': %s", report_type, e
        )
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
    endpoint    : inference server URL (default: SERVER_URL)
    max_tokens  : max tokens to generate (default: from config)
    timeout     : request timeout in seconds (default: 8.0)

    Returns
    -------
    str — generated narrative, or a static fallback string on failure
    """
    try:
        prompt = build_insight_prompt(context, report_type)
    except Exception as e:
        logger.error("llm_insight: failed to build prompt: %s", e)
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
                logger.debug("LLM insight (%s): %s...", report_type, raw[:120])
                return raw
            logger.warning("llm_insight: empty response from server, using fallback")
            return _fallback_insight(context, report_type)

    except urllib.error.URLError as e:
        if isinstance(e.reason, TimeoutError):
            logger.warning("llm_insight: server timed out (>%ss), using fallback", timeout)
        else:
            logger.warning("llm_insight: server unreachable (%s), using fallback", e)
        return _fallback_insight(context, report_type)
    except Exception as e:
        logger.error("llm_insight: unexpected error: %s, using fallback", e)
        return _fallback_insight(context, report_type)


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
    return f"[{report_type}] " + str(context)
