"""
prepare_retrospective.py
================================================================================
Phase 1 Groq Bridge -- generates a rich, structured prompt from backtest output
files, registers a session in logs/groq_bridge/session_registry.jsonl, and
writes the prompt to a file for the user to relay to Groq.

SUPPORTED SOURCE FILES (auto-detected):
  1. results/<run_folder>/EURUSD_trades.csv   <-- RECOMMENDED
       Real executed trades with PnL outcomes + all 35 CRT features.
       Use this for post-trade retrospective analysis.

  2. results/<run_folder>/EURUSD_summary.json
       Aggregate BacktestMetrics. Use alongside trades CSV or alone.

  3. results/<run_folder>/EURUSD_events.jsonl
       Raw per-bar events. Very large; use only if trades CSV is missing.

  4. results.csv (legacy root-level signal log, reject-only data)

USAGE
-----
  # Best: use the trades CSV from the latest run
  python scripts/groq_bridge/prepare_retrospective.py ^
      --source results/run_20260507_012430_EURUSD/EURUSD_trades.csv ^
      --instrument EURUSD

  # With summary JSON for richer aggregate stats
  python scripts/groq_bridge/prepare_retrospective.py ^
      --source results/run_20260507_012430_EURUSD/EURUSD_trades.csv ^
      --summary results/run_20260507_012430_EURUSD/EURUSD_summary.json ^
      --instrument EURUSD

  # Dry run (no files written)
  python scripts/groq_bridge/prepare_retrospective.py ^
      --source results/run_20260507_012430_EURUSD/EURUSD_trades.csv ^
      --dry-run

Session ID format: RETRO_{YYYYMMDD}_{HHMMSS}_{instrument}_{n_trades}
================================================================================
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, stdev
from typing import Any

# ── Path bootstrap ────────────────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent.parent
_LOGS_BRIDGE = _REPO_ROOT / "logs" / "groq_bridge"

_REGISTRY_FILE = _LOGS_BRIDGE / "session_registry.jsonl"
_TRACE_INDEX   = _LOGS_BRIDGE / "trace_index.md"

# Session label mapping (numeric encoded -> human readable)
_SESSION_MAP = {"0.0": "LONDON", "1.0": "NEW_YORK", "2.0": "ASIA",
                "0": "LONDON", "1": "NEW_YORK", "2": "ASIA"}
_VOL_MAP     = {"1.0": "LOW", "2.0": "MEDIUM", "3.0": "HIGH",
                "1": "LOW",   "2": "MEDIUM",   "3": "HIGH"}


# ============================================================================
# COMPRESSED-SUMMARY / HYPERTUNE PROMPT
# ============================================================================

def _fmt_corr_pairs(pairs, n=5):
    safe = pairs[:n] if pairs else []
    return ", ".join(f"{name}={val:+.3f}" for name, val in safe) or "n/a"


def _build_target_model_prompt(compressed: dict, target: str, instrument: str) -> str:
    """Build an LLM prompt requesting hyperparameters for a specific model.

    Schema of `compressed`: {summary, data, anomalies} (output of
    scripts/analysis/compress_logs_for_llm.py).
    """
    summary = compressed.get("summary", {})
    data = compressed.get("data", {})
    n_total = summary.get("n_total", 0)
    counts_outcome = summary.get("counts_outcome", {})
    top_pos = data.get("top_positive_corr", [])
    top_neg = data.get("top_negative_corr", [])
    delta = data.get("top_tp_minus_sl_delta", [])

    common_header = (
        f"[SYSTEM] You are the Tradelatest hypertuning agent. Output ONLY a "
        f"single JSON object — no prose. Be deterministic.\n\n"
        f"[DATA SOURCE] compressed opportunity summary for {instrument}\n"
        f"records={n_total}  outcomes={counts_outcome}  "
        f"rr_mean={summary.get('rr_mean')}  rr_std={summary.get('rr_std')}\n\n"
        f"[TOP FEATURE CORRELATIONS WITH RR]\n"
        f"positive: {_fmt_corr_pairs(top_pos)}\n"
        f"negative: {_fmt_corr_pairs(top_neg)}\n"
        f"tp_minus_sl_delta: {_fmt_corr_pairs(delta)}\n\n"
    )

    if target == "gaussian":
        return common_header + (
            "[TASK] Suggest hyperparameters for the GaussianNB retraining pass.\n"
            "[OUTPUT FORMAT]\n"
            "{\n"
            "  \"feature_subset\": [<canonical feature names to keep>],\n"
            "  \"class_weights\": [<float per class — length must equal n_classes>],\n"
            "  \"rr_buckets\":    [<ascending rr upper-bound edges>]\n"
            "}"
        )
    if target == "zone":
        return common_header + (
            "[TASK] Suggest clustering hyperparameters for zone discovery.\n"
            "[OUTPUT FORMAT]\n"
            "{\n"
            "  \"n_clusters\":      <int>,\n"
            "  \"min_samples\":     <int>,\n"
            "  \"feature_weights\": [<float per feature in CANONICAL_FEATURE_ORDER>]\n"
            "}"
        )
    if target == "rr":
        return common_header + (
            "[TASK] Suggest hyperparameters for the RR fusion model.\n"
            "[OUTPUT FORMAT]\n"
            "{\n"
            "  \"ridge_alpha\":                  <float>,\n"
            "  \"confidence_bypass_threshold\":  <float>,\n"
            "  \"drift_threshold\":              <float>\n"
            "}"
        )
    raise ValueError(f"Unknown target_model: {target}")


# ============================================================================
# DATA LOADING
# ============================================================================

def _is_trades_csv(path: Path) -> bool:
    """Return True if file has the EURUSD_trades.csv schema (pnl_rr_net column)."""
    with open(path, newline="", encoding="utf-8") as f:
        header = f.readline()
    return "pnl_rr_net" in header


def _load_trades_csv(path: Path, last_n: int) -> list[dict]:
    """Load EURUSD_trades.csv — the best source for Groq retrospective."""
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                row["_pnl"] = float(row.get("pnl_rr_net", 0) or 0)
                row["_win"] = row["_pnl"] > 0
            except (ValueError, TypeError):
                row["_pnl"] = 0.0
                row["_win"] = False
            rows.append(row)
    return rows[-last_n:]


def _load_legacy_csv(path: Path, last_n: int) -> list[dict]:
    """Load legacy results.csv (signal log, no PnL outcomes)."""
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("reason") == "data_integrity_failed":
                continue
            rows.append(row)
    return rows[-last_n:]


def _load_events_jsonl(path: Path, last_n: int) -> list[dict]:
    """Load EURUSD_events.jsonl — large file, sample only."""
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows[-last_n:]


def _load_summary_json(path: Path) -> dict:
    """Load EURUSD_summary.json for aggregate metrics."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ============================================================================
# STATS — TRADES CSV (primary path)
# ============================================================================

def _f(row: dict, key: str, decimals: int = 3) -> str:
    """Format a float field safely."""
    try:
        return f"{float(row.get(key, 0) or 0):.{decimals}f}"
    except (ValueError, TypeError):
        return "?"


def _compute_trades_stats(rows: list[dict], summary: dict | None) -> dict[str, Any]:
    wins   = [r for r in rows if r.get("_win")]
    losses = [r for r in rows if not r.get("_win")]

    def _avg(subset, key):
        vals = []
        for r in subset:
            try:
                vals.append(float(r.get(key, 0) or 0))
            except (ValueError, TypeError):
                pass
        return mean(vals) if vals else 0.0

    # Feature comparison: wins vs losses
    feature_keys = [
        "body_ratio", "disp_strength", "retest_depth",
        "momentum_score", "risk_score", "volatility_ratio",
        "atr", "rsi_14", "trend_bias", "trend_strength",
    ]
    feature_delta = {}
    for k in feature_keys:
        w = _avg(wins, k)
        l = _avg(losses, k)
        feature_delta[k] = {"wins": round(w, 4), "losses": round(l, 4),
                             "delta": round(w - l, 4)}

    # Session distribution
    session_wins   = Counter(_SESSION_MAP.get(str(r.get("session", "")), str(r.get("session", ""))) for r in wins)
    session_losses = Counter(_SESSION_MAP.get(str(r.get("session", "")), str(r.get("session", ""))) for r in losses)

    # Direction split
    dir_wins   = Counter(r.get("direction", "?") for r in wins)
    dir_losses = Counter(r.get("direction", "?") for r in losses)

    # Exit reasons
    exit_reasons = Counter(r.get("exit_reason", "?") for r in rows)

    # PnL stats
    pnls = [r["_pnl"] for r in rows]
    win_pnls  = [r["_pnl"] for r in wins]
    loss_pnls = [r["_pnl"] for r in losses]

    # Duration
    avg_duration_wins   = _avg(wins, "duration_candles")
    avg_duration_losses = _avg(losses, "duration_candles")

    # Risk score correlation
    risk_score_wins   = _avg(wins, "risk_score")
    risk_score_losses = _avg(losses, "risk_score")

    # Top 5 wins and losses by absolute pnl
    top_wins   = sorted(wins,   key=lambda r: r["_pnl"], reverse=True)[:5]
    top_losses = sorted(losses, key=lambda r: r["_pnl"])[:5]

    return {
        "mode": "trades",
        "total": len(rows),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / max(len(rows), 1),
        "total_pnl": round(sum(pnls), 4),
        "avg_win_rr": round(mean(win_pnls), 4) if win_pnls else 0.0,
        "avg_loss_rr": round(mean(loss_pnls), 4) if loss_pnls else 0.0,
        "expectancy": round(mean(pnls), 4) if pnls else 0.0,
        "max_win": round(max(win_pnls), 4) if win_pnls else 0.0,
        "max_loss": round(min(loss_pnls), 4) if loss_pnls else 0.0,
        "feature_delta": feature_delta,
        "session_wins": dict(session_wins.most_common()),
        "session_losses": dict(session_losses.most_common()),
        "dir_wins": dict(dir_wins),
        "dir_losses": dict(dir_losses),
        "exit_reasons": dict(exit_reasons.most_common()),
        "avg_duration_wins": round(avg_duration_wins, 1),
        "avg_duration_losses": round(avg_duration_losses, 1),
        "risk_score_wins": round(risk_score_wins, 4),
        "risk_score_losses": round(risk_score_losses, 4),
        "top_wins": top_wins,
        "top_losses": top_losses,
        "summary": summary or {},
    }


def _format_trade_row(r: dict) -> str:
    session = _SESSION_MAP.get(str(r.get("session", "")), str(r.get("session", "")))
    return (
        f"  {r.get('trade_id','?')} {r.get('direction','?')} "
        f"pnl={_f(r,'pnl_rr_net',3)}R  "
        f"session={session}  "
        f"body={_f(r,'body_ratio',3)}  disp={_f(r,'disp_strength',3)}  "
        f"retest={_f(r,'retest_depth',3)}  momentum={_f(r,'momentum_score',3)}  "
        f"risk_score={_f(r,'risk_score',4)}  "
        f"exit={r.get('exit_reason','?')}  dur={r.get('duration_candles','?')}c"
    )


# ============================================================================
# STATS — LEGACY CSV (fallback path)
# ============================================================================

def _compute_legacy_stats(rows: list[dict]) -> dict[str, Any]:
    """Stats for the old results.csv signal log (no PnL data)."""
    decision_values: Counter = Counter(r.get("decision", "") for r in rows)
    has_accepts = decision_values.get("ACCEPT", 0) > 0

    if has_accepts:
        high_quality = [r for r in rows if r.get("decision") == "ACCEPT"]
        low_quality  = [r for r in rows if r.get("decision") != "ACCEPT"]
        hq_label, lq_label = "ACCEPT", "REJECT"
    else:
        high_quality = [r for r in rows if r.get("decision") == "REJECT"]
        low_quality  = [r for r in rows if r.get("decision") == "BITNET_REJECT"]
        hq_label, lq_label = "REJECT", "BITNET_REJECT"

    def _scores(subset):
        out = []
        for r in subset:
            try:
                s = float(r.get("score") or 0)
                if s > 0:
                    out.append(s)
            except (ValueError, TypeError):
                pass
        return out

    scores_hq  = _scores(high_quality)
    scores_lq  = _scores(low_quality)
    scores_all = _scores(rows)

    return {
        "mode": "legacy",
        "total": len(rows),
        "has_accepts": has_accepts,
        "hq_label": hq_label,
        "lq_label": lq_label,
        "accepts": len(high_quality),
        "rejects": len(low_quality),
        "accept_rate": len(high_quality) / max(len(rows), 1),
        "decision_counts": dict(decision_values.most_common()),
        "avg_score_all": mean(scores_all) if scores_all else 0.0,
        "avg_score_accept": mean(scores_hq) if scores_hq else 0.0,
        "avg_score_reject": mean(scores_lq) if scores_lq else 0.0,
        "std_score_accept": stdev(scores_hq) if len(scores_hq) > 1 else 0.0,
        "top_regimes": Counter(r.get("regime", "") for r in high_quality if r.get("regime")).most_common(5),
        "top_engines": Counter(r.get("selected_engine", "") for r in high_quality if r.get("selected_engine")).most_common(5),
        "reject_reasons": Counter(r.get("reason", "") for r in rows if r.get("reason")).most_common(8),
        "accept_buckets": Counter(r.get("confidence_bucket", "") for r in high_quality).most_common(5),
        "reject_buckets": Counter(r.get("confidence_bucket", "") for r in low_quality).most_common(5),
        "bitnet_agree": sum(1 for r in high_quality if r.get("bitnet_decision") == "ACCEPT"),
        "bitnet_disagree": sum(1 for r in high_quality if r.get("bitnet_decision") == "REJECT"),
        "sample_accepts": high_quality[:5],
        "sample_rejects": low_quality[:5],
    }


# ============================================================================
# PROMPT BUILDERS
# ============================================================================

def _build_trades_prompt(stats: dict, instrument: str, source_label: str) -> str:
    """Rich prompt built from EURUSD_trades.csv — uses actual PnL outcomes."""
    s = stats
    summary = s.get("summary", {})

    # Feature delta table
    feat_lines = []
    for feat, vals in s["feature_delta"].items():
        direction = "WINS higher" if vals["delta"] > 0.01 else ("LOSSES higher" if vals["delta"] < -0.01 else "similar")
        feat_lines.append(
            f"  {feat:<22} wins={vals['wins']:.4f}  losses={vals['losses']:.4f}  "
            f"delta={vals['delta']:+.4f}  ({direction})"
        )
    feature_table = "\n".join(feat_lines)

    # Session breakdown
    session_str = (
        f"  Wins by session:   {s['session_wins']}\n"
        f"  Losses by session: {s['session_losses']}"
    )

    # Direction breakdown
    dir_str = (
        f"  Wins:   {s['dir_wins']}\n"
        f"  Losses: {s['dir_losses']}"
    )

    # Top trades
    top_wins_str   = "\n".join(_format_trade_row(r) for r in s["top_wins"])   or "  None"
    top_losses_str = "\n".join(_format_trade_row(r) for r in s["top_losses"]) or "  None"

    # Summary metrics from summary.json if available
    agg_block = ""
    if summary:
        agg_block = f"""
===== AGGREGATE METRICS (from summary.json) =====
  Total candles processed : {summary.get('total_candles', 'N/A'):,}
  Total setups evaluated  : {summary.get('total_setups', 'N/A')}
  Approval rate           : {summary.get('approval_rate', 0):.1%}
  Max drawdown            : {summary.get('max_drawdown_pct', 0):.1%}
  Max win streak          : {summary.get('max_win_streak', 'N/A')}
  Max loss streak         : {summary.get('max_loss_streak', 'N/A')}
  TP1 hits / TP2 hits     : {summary.get('tp1_hits', 'N/A')} / {summary.get('tp2_hits', 'N/A')}
  Rejection reasons       : {summary.get('rejection_reasons', {})}
  State distribution      : {summary.get('state_distribution', {})}"""

    prompt = f"""You are an expert quantitative trading analyst specializing in CRT (Change of Range Theory) strategies. Analyze these backtest trade results to find actionable config improvements for higher ROI.

===== RUN SUMMARY =====
Instrument  : {instrument}
Source      : {source_label}
Total trades: {s['total']}  (Wins: {s['wins']}  Losses: {s['losses']})
Win rate    : {s['win_rate']:.1%}
Expectancy  : {s['expectancy']:+.4f}R per trade
Total PnL   : {s['total_pnl']:+.4f}R
Avg win     : {s['avg_win_rr']:+.4f}R    Max win: {s['max_win']:+.4f}R
Avg loss    : {s['avg_loss_rr']:+.4f}R   Max loss: {s['max_loss']:+.4f}R
{agg_block}

===== EXIT REASON ANALYSIS =====
{s['exit_reasons']}
NOTE: If all exits are RESET_CLOSE, trades are being force-closed by gap resets
before reaching TP/SL. This is a major signal quality issue to investigate.

===== DIRECTION SPLIT =====
{dir_str}

===== SESSION SPLIT =====
{session_str}

===== FEATURE COMPARISON: WINS vs LOSSES =====
(Positive delta = feature is higher in winning trades)
{feature_table}

===== RISK SCORE (LLM confidence) =====
  Avg risk_score in WINS  : {s['risk_score_wins']:.4f}
  Avg risk_score in LOSSES: {s['risk_score_losses']:.4f}
  Interpretation: Higher risk_score = LLM was more confident. Is the LLM predictive?

===== TRADE DURATION =====
  Avg candles in WINS  : {s['avg_duration_wins']}
  Avg candles in LOSSES: {s['avg_duration_losses']}

===== TOP 5 WINNING TRADES =====
{top_wins_str}

===== TOP 5 LOSING TRADES =====
{top_losses_str}

===== YOUR ANALYSIS TASK =====
Based on this data, provide expert analysis:

1. FEATURE THRESHOLDS: Which feature(s) best separate wins from losses?
   Give a specific filter rule (e.g. "only trade when body_ratio > 0.35 AND disp_strength > 0.5").

2. SESSION FILTER: Which session(s) should be avoided or prioritized?

3. DIRECTION BIAS: Should we filter by direction given the split above?

4. EXIT ISSUE: If all exits are RESET_CLOSE, the strategy never reaches TP.
   What parameter changes would allow trades to survive to TP1/TP2?

5. RISK SCORE: Is the LLM risk_score predictive (higher in wins)? Should we
   raise the minimum risk_score threshold?

6. CONFIG CHANGES: Give exactly 3 concrete parameter changes with expected impact.
   Use the actual parameter names from the CRT system:
   retest_depth_max, body_ratio_min, expansion_atr_min_distance,
   atr_multiplier_min, retest_atr_depth_fraction, or any session/risk params.

7. TRAP PATTERN: What is the most common losing trade setup? How to filter it?

Respond ONLY in valid JSON:
{{
  "top_engine_signal": {{"engine": "crt", "regime": "<str>", "threshold": <float>, "rationale": "<str>"}},
  "sessions_to_avoid": [{{"regime": "<str>", "engine": "<str>", "reason": "<str>"}}],
  "recommended_fusion_min": <float>,
  "bitnet_disagreement_verdict": "<risky|acceptable|investigate>",
  "config_changes": [
    {{"param": "<exact_param_name>", "from": <current_value>, "to": <recommended_value>, "rationale": "<str>"}},
    {{"param": "<exact_param_name>", "from": <current_value>, "to": <recommended_value>, "rationale": "<str>"}},
    {{"param": "<exact_param_name>", "from": <current_value>, "to": <recommended_value>, "rationale": "<str>"}}
  ],
  "trap_pattern": {{"description": "<str>", "filter_rule": "<str>"}},
  "feature_filter_rule": "<e.g. body_ratio > 0.35 AND disp_strength > 0.5>",
  "session_recommendation": "<e.g. trade only LONDON, avoid NEW_YORK>",
  "exit_issue_fix": "<str explaining what to change to reach TP>"
}}"""

    return prompt


def _build_legacy_prompt(stats: dict, instrument: str, source_label: str) -> str:
    """Prompt for legacy results.csv (no PnL outcomes)."""
    s = stats
    hq, lq = s["hq_label"], s["lq_label"]

    decision_dist_str = "  " + ", ".join(f"{k}={v}" for k, v in s["decision_counts"].items())
    reject_reasons_str = "\n".join(f"  - {r}: {c}" for r, c in s["reject_reasons"]) or "  None"

    if s["has_accepts"]:
        focus = (
            "1. Which regime + engine combination has the highest execution rate?\n"
            "2. What fusion score minimum cuts losers without removing good setups?\n"
            "3. Give 3 concrete config parameter changes with ROI rationale.\n"
            "4. Identify any trap pattern that looks valid but fails consistently."
        )
    else:
        focus = (
            "1. Why is the system rejecting 100% of signals? Which gate is the bottleneck?\n"
            "2. What threshold tweak would allow quality setups through?\n"
            "3. Give 3 concrete config parameter changes to unlock quality trades.\n"
            "4. Is the BitNet zone gate miscalibrated?"
        )

    return f"""You are a quantitative trading analyst. Analyze these signal decisions.

NOTE: This is a signal log without PnL outcomes. For richer analysis, use
EURUSD_trades.csv from the results/<run_folder>/ directory instead.

===== DATA SOURCE =====
Instrument: {instrument} | Source: {source_label}
Total signals: {s['total']}
{decision_dist_str}

===== REJECTION REASONS =====
{reject_reasons_str}

===== YOUR ANALYSIS =====
{focus}

Respond ONLY in valid JSON:
{{
  "top_engine_signal": {{"engine": "<str>", "regime": "<str>", "threshold": <float>, "rationale": "<str>"}},
  "sessions_to_avoid": [{{"regime": "<str>", "engine": "<str>", "reason": "<str>"}}],
  "recommended_fusion_min": <float>,
  "bitnet_disagreement_verdict": "<risky|acceptable|investigate>",
  "config_changes": [{{"param": "<str>", "from": <value>, "to": <value>, "rationale": "<str>"}}],
  "trap_pattern": {{"description": "<str>", "filter_rule": "<str>"}},
  "feature_filter_rule": "<str>",
  "session_recommendation": "<str>",
  "exit_issue_fix": "<str>"
}}"""


# ============================================================================
# SESSION REGISTRY
# ============================================================================

def _make_session_id(instrument: str, n_trades: int) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"RETRO_{ts}_{instrument}_{n_trades}"


def _register_session(
    session_id: str, instrument: str, n_trades: int,
    prompt_file: Path, prompt_hash: str, stats: dict,
) -> None:
    _LOGS_BRIDGE.mkdir(parents=True, exist_ok=True)
    win_rate = stats.get("win_rate", stats.get("accept_rate", 0.0))
    record = {
        "session_id": session_id,
        "ts": datetime.now(timezone.utc).isoformat(),
        "instrument": instrument,
        "trades_analyzed": n_trades,
        "win_rate_before": round(win_rate, 4),
        "expectancy_before": round(stats.get("expectancy", 0.0), 4),
        "baseline_score": None,
        "prompt_hash": prompt_hash,
        "prompt_file": str(prompt_file),
        "response_file": None,
        "insights_applied": False,
        "config_version_before": "v1_multi_2026_03",
        "config_version_after": None,
        "score_after": None,
        "roi_delta": None,
        "status": "PENDING_RESPONSE",
    }
    with open(_REGISTRY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def _update_trace_index(session_id: str, instrument: str, n_trades: int, stats: dict) -> None:
    header = (
        "| Session ID | Date | Instrument | Trades | Win Rate | Expectancy | Status |\n"
        "|-----------|------|-----------|--------|----------|-----------|--------|\n"
    )
    win_rate   = stats.get("win_rate", stats.get("accept_rate", 0.0))
    expectancy = stats.get("expectancy", 0.0)
    date_str   = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    new_row = (
        f"| {session_id} | {date_str} | {instrument} | {n_trades} "
        f"| {win_rate:.1%} | {expectancy:+.4f}R | PENDING |\n"
    )
    _LOGS_BRIDGE.mkdir(parents=True, exist_ok=True)
    if _TRACE_INDEX.exists():
        content = _TRACE_INDEX.read_text(encoding="utf-8")
        _TRACE_INDEX.write_text(content + new_row, encoding="utf-8")
    else:
        _TRACE_INDEX.write_text(
            "# Groq Bridge Session Trace Index\n\n" + header + new_row,
            encoding="utf-8",
        )


# ============================================================================
# MAIN
# ============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare a Groq retrospective prompt from backtest output files."
    )
    parser.add_argument(
        "--source",
        default=None,
        help=(
            "Path to source file. Best choice: results/<run>/EURUSD_trades.csv. "
            "Also accepts: EURUSD_summary.json, EURUSD_events.jsonl, results.csv. "
            "Mutually exclusive with --compressed-summary."
        ),
    )
    parser.add_argument(
        "--compressed-summary",
        default=None,
        help=(
            "Path to a pre-computed summary JSON produced by "
            "scripts/analysis/compress_logs_for_llm.py. When set, the prompt "
            "is built directly from the summary."
        ),
    )
    parser.add_argument(
        "--target-model",
        default=None,
        choices=("gaussian", "zone", "rr"),
        help=(
            "When --compressed-summary is set, ask the LLM for hyperparameters "
            "for this specific model. Drives the prompt template."
        ),
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional explicit output path for the prompt. Defaults to "
             "logs/groq_bridge/pending_{session_id}.txt",
    )
    parser.add_argument(
        "--summary",
        default=None,
        help="Optional: path to EURUSD_summary.json to enrich the prompt with aggregate stats.",
    )
    parser.add_argument(
        "--last-n",
        type=int,
        default=200,
        help="Max number of recent trades/rows to analyze (default: 200)",
    )
    parser.add_argument(
        "--instrument",
        default="UNKNOWN",
        help="Instrument label for session ID (default: UNKNOWN)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print prompt preview without writing files or registering session",
    )
    args = parser.parse_args()

    if args.compressed_summary and args.source:
        print("ERROR: --compressed-summary is mutually exclusive with --source",
              file=sys.stderr)
        sys.exit(2)
    if not args.compressed_summary and not args.source:
        print("ERROR: provide either --compressed-summary or --source",
              file=sys.stderr)
        sys.exit(2)

    # ── Compressed-summary branch: skips raw log parsing entirely ─────────────
    if args.compressed_summary:
        cs_path = Path(args.compressed_summary)
        if not cs_path.is_absolute():
            cs_path = _REPO_ROOT / cs_path
        if not cs_path.exists():
            print(f"ERROR: compressed summary not found: {cs_path}", file=sys.stderr)
            sys.exit(1)
        compressed = json.loads(cs_path.read_text(encoding="utf-8"))
        prompt = _build_target_model_prompt(
            compressed, args.target_model or "gaussian", args.instrument,
        )
        n_items = compressed.get("summary", {}).get("n_total", 0)
        mode = f"hypertune:{args.target_model or 'gaussian'}"
        stats = {"mode": mode, "total": n_items,
                 "win_rate": 0.0, "expectancy": 0.0}

        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
        if args.dry_run:
            print(f"\n===== DRY RUN ({mode}, {n_items} records) =====")
            print(prompt[:1000])
            print(f"...\n[dry-run: {len(prompt)} chars total]")
            return

        session_id = _make_session_id(args.instrument, n_items)
        if args.output:
            prompt_file = Path(args.output)
            if not prompt_file.is_absolute():
                prompt_file = _REPO_ROOT / prompt_file
            prompt_file.parent.mkdir(parents=True, exist_ok=True)
        else:
            _LOGS_BRIDGE.mkdir(parents=True, exist_ok=True)
            prompt_file = _LOGS_BRIDGE / f"pending_{session_id}.txt"
        prompt_file.write_text(prompt, encoding="utf-8")

        _register_session(session_id, args.instrument, n_items, prompt_file,
                          prompt_hash, stats)
        print(f"\nSESSION ID : {session_id}\n  Mode     : {mode}\n  Prompt   : {prompt_file}")
        return

    source_path = Path(args.source)
    if not source_path.is_absolute():
        source_path = _REPO_ROOT / source_path

    if not source_path.exists():
        print(f"ERROR: source file not found: {source_path}", file=sys.stderr)
        print("\nTip: Pass the trades CSV from your latest run, e.g.:", file=sys.stderr)
        print("  --source results/run_20260507_012430_EURUSD/EURUSD_trades.csv", file=sys.stderr)
        sys.exit(1)

    # Load optional summary JSON
    summary = None
    if args.summary:
        summary_path = Path(args.summary)
        if not summary_path.is_absolute():
            summary_path = _REPO_ROOT / summary_path
        if summary_path.exists():
            summary = _load_summary_json(summary_path)
            print(f"Loaded summary: {summary_path}")
        else:
            print(f"WARNING: summary file not found: {summary_path}", file=sys.stderr)

    # Auto-detect format and load
    suffix = source_path.suffix.lower()
    print(f"Loading from: {source_path}")

    if suffix == ".csv" and _is_trades_csv(source_path):
        rows = _load_trades_csv(source_path, args.last_n)
        source_label = f"{source_path.name} (last {len(rows)} trades — EURUSD_trades format)"
        stats = _compute_trades_stats(rows, summary)
        prompt = _build_trades_prompt(stats, args.instrument, source_label)
        mode = "trades"

    elif suffix == ".csv":
        rows = _load_legacy_csv(source_path, args.last_n)
        source_label = f"{source_path.name} (last {len(rows)} signals — legacy results.csv)"
        stats = _compute_legacy_stats(rows)
        prompt = _build_legacy_prompt(stats, args.instrument, source_label)
        mode = "legacy"

    elif suffix == ".jsonl":
        rows = _load_events_jsonl(source_path, args.last_n)
        source_label = f"{source_path.name} (last {len(rows)} events)"
        # Reuse legacy stats as best-effort for events
        stats = {"mode": "events", "total": len(rows), "win_rate": 0.0, "expectancy": 0.0}
        prompt = (
            f"You are a trading analyst. Analyze these {len(rows)} raw backtest events "
            f"from {source_label} for the {args.instrument} instrument.\n\n"
            + "\n".join(json.dumps(r) for r in rows[:30])
            + "\n\n[Respond in the standard JSON format with config_changes, trap_pattern, etc.]"
        )
        mode = "events"

    elif suffix == ".json":
        summary = _load_summary_json(source_path)
        rows = []
        source_label = f"{source_path.name} (summary only)"
        stats = {
            "mode": "summary_only",
            "total": summary.get("approved_trades", 0),
            "win_rate": summary.get("win_rate", 0.0),
            "expectancy": summary.get("avg_rr_net", 0.0),
            "wins": summary.get("wins", 0),
            "losses": summary.get("losses", 0),
            "total_pnl": summary.get("total_pnl_rr_net", 0.0),
            "avg_win_rr": 0.0, "avg_loss_rr": 0.0,
            "max_win": 0.0, "max_loss": 0.0,
            "feature_delta": {}, "session_wins": {}, "session_losses": {},
            "dir_wins": {}, "dir_losses": {},
            "exit_reasons": {}, "avg_duration_wins": 0, "avg_duration_losses": 0,
            "risk_score_wins": 0.0, "risk_score_losses": 0.0,
            "top_wins": [], "top_losses": [], "summary": summary,
        }
        prompt = _build_trades_prompt(stats, args.instrument, source_label)
        mode = "summary"
    else:
        print(f"ERROR: unsupported file type: {suffix}", file=sys.stderr)
        sys.exit(1)

    if not rows and mode not in ("summary", "summary_only"):
        print("ERROR: no usable rows found in source file.", file=sys.stderr)
        sys.exit(1)

    n_items = len(rows) if rows else stats.get("total", 0)
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]

    if args.dry_run:
        print(f"\n===== DRY RUN ({mode} mode, {n_items} records) =====")
        print(prompt[:1000])
        print(f"...\n[dry-run: {len(prompt)} chars total, no files written]")
        return

    session_id  = _make_session_id(args.instrument, n_items)
    _LOGS_BRIDGE.mkdir(parents=True, exist_ok=True)
    prompt_file = _LOGS_BRIDGE / f"pending_{session_id}.txt"
    prompt_file.write_text(prompt, encoding="utf-8")

    _register_session(session_id, args.instrument, n_items, prompt_file, prompt_hash, stats)
    _update_trace_index(session_id, args.instrument, n_items, stats)

    print(f"\n{'='*65}")
    print(f"  SESSION ID  : {session_id}")
    print(f"  Mode        : {mode}  ({n_items} records)")
    if mode == "trades":
        print(f"  Win rate    : {stats['win_rate']:.1%}  "
              f"Expectancy: {stats['expectancy']:+.4f}R")
    print(f"  Prompt file : {prompt_file}")
    print(f"  Registry    : {_REGISTRY_FILE}")
    print(f"{'='*65}")
    print("\nNEXT STEPS:")
    print(f"  1. Open and copy: {prompt_file}")
    print("  2. Paste into Groq at https://console.groq.com/playground")
    print("  3. Copy Groq's JSON response into a text file, then run:")
    print(f"     python scripts/groq_bridge/ingest_response.py ^")
    print(f"       --session {session_id} ^")
    print(f"       --response-file <path_to_response.txt>")


if __name__ == "__main__":
    main()
