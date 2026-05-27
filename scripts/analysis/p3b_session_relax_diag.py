# -*- coding: utf-8 -*-
"""
P3b Diagnostic - Session relaxation: add ASIA + OFF_SESSION to allowed_sessions.

Hypothesis:
  A portion of RETEST->EXECUTION setups are blocked by the session filter
  (OFF_SESSION, ASIA). If the session filter is too conservative, relaxing it
  should add trades with quality >= baseline.

Patch:
  Single config attribute override on the loaded CRTConfig instance.
  No source files modified.

  crt_cfg.allowed_sessions = baseline_sessions + add_sessions

Auto-baseline:
  This script runs TWO backtests automatically:
  Run 0 (baseline)  — original allowed_sessions (from production config)
  Run 1 (patched)   — baseline + add_sessions
  Delta is computed as Run1 - Run0 for all metrics.

Decision rule:
  PASS  : added_trades > 0 AND r_expectancy_added >= min_r_exp AND MaxDD <= max_dd
  MIXED : added_trades > 0 AND r_expectancy_added < min_r_exp
    -> Session filter is quality governor; added sessions bring noise
  NONE  : added_trades = 0 (session-allowed setups blocked by other guards)

Usage:
    cd D:\\Tradelatest
    python scripts\\analysis\\p3b_session_relax_diag.py --instrument BTCUSDT
    python scripts\\analysis\\p3b_session_relax_diag.py --instrument SOLUSDT
    python scripts\\analysis\\p3b_session_relax_diag.py --instrument BNBUSDT --min-r-exp 0.20
    python scripts\\analysis\\p3b_session_relax_diag.py --instrument ETHUSDT
    python scripts\\analysis\\p3b_session_relax_diag.py --instrument BTCUSDT --csv data/BTCUSDT_M15.csv
"""

import sys
import os
import json
import time
import argparse
import collections
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_ROOT = Path(__file__).resolve().parents[2]
_SRC  = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
os.chdir(_ROOT)

import dataclasses

from runtime.backtest_v2 import (
    BacktestRunner, BacktestConfig, CandleLoader,
    load_prod_config_from_registry, PROD_VERSION, MultiInstrumentRunner,
)

# =============================================================================
# CLI ARGUMENTS + DATA FILE RESOLUTION
# =============================================================================
def _resolve_data_file(instrument: str, csv_override: str | None) -> str:
    if csv_override:
        p = Path(csv_override)
        if not p.exists():
            sys.exit(f"[ERROR] --csv path not found: {csv_override}")
        return str(p)
    candidates = [
        _ROOT / "data" / f"{instrument}_M15.csv",
        _ROOT / "data" / f"{instrument}_M15_2year.csv",
        _ROOT / "data" / f"{instrument}_M15_2year.xlsx",
        _ROOT / "data" / f"{instrument}_M15.xlsx",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    checked = "\n  ".join(str(c) for c in candidates)
    sys.exit(f"[ERROR] No data file found for {instrument}. Checked:\n  {checked}")

_ap = argparse.ArgumentParser(description="P3b session relaxation diagnostic")
_ap.add_argument("--instrument",   required=True,
                 help="Symbol to run, e.g. BTCUSDT, SOLUSDT, ETHUSDT")
_ap.add_argument("--csv",          default=None,
                 help="Explicit path to data file (CSV). Auto-resolved if omitted.")
_ap.add_argument("--output-dir",   default=str(_ROOT / "results"),
                 help="Directory for backtest run output (default: results)")
_ap.add_argument("--add-sessions", default="ASIA,OFF_SESSION",
                 help="Comma-separated sessions to ADD to allowed_sessions "
                      "(default: ASIA,OFF_SESSION)")
_ap.add_argument("--min-r-exp",    type=float, default=0.39,
                 help="Quality gate: min R expectancy on ADDED trades (default: 0.39)")
_ap.add_argument("--max-dd",       type=float, default=0.0132,
                 help="Quality gate: max drawdown fraction (default: 0.0132)")
args = _ap.parse_args()

INSTRUMENT   = args.instrument
CSV_PATH     = _resolve_data_file(args.instrument, args.csv)
OUTPUT_DIR   = args.output_dir
ADD_SESSIONS = tuple(s.strip() for s in args.add_sessions.split(",") if s.strip())
MIN_R_EXP    = args.min_r_exp
MAX_DD       = args.max_dd

# =============================================================================
# LOAD PRODUCTION CONFIG
# =============================================================================
crt_cfg_orig = load_prod_config_from_registry(PROD_VERSION, INSTRUMENT)

_baseline_sessions = tuple(crt_cfg_orig.allowed_sessions)
_patched_sessions  = _baseline_sessions + tuple(s for s in ADD_SESSIONS
                                                  if s not in _baseline_sessions)
crt_cfg_patched = dataclasses.replace(crt_cfg_orig, allowed_sessions=_patched_sessions)

print(f"[P3b] Session patch for {INSTRUMENT}:")
print(f"      baseline  : {_baseline_sessions}")
print(f"      patched   : {_patched_sessions}")
print(f"      added     : {set(_patched_sessions) - set(_baseline_sessions)}")
print(f"      min_r_exp : {MIN_R_EXP}  max_dd: {MAX_DD}")
print(f"      data      : {CSV_PATH}")
print(f"      prod_ver  : {PROD_VERSION}\n")

# =============================================================================
# TWO-RUN HELPER
# =============================================================================
def _run_one(crt_cfg, label: str):
    """Run a single backtest and return (metrics, events_path)."""
    cfg = BacktestConfig.from_prod_config(crt_config=crt_cfg)
    cfg.instrument = INSTRUMENT
    cfg.pip_size   = MultiInstrumentRunner.INSTRUMENT_PIP.get(INSTRUMENT, 0.0001)

    loader = CandleLoader(CSV_PATH, INSTRUMENT)
    runner = BacktestRunner(
        cfg, csv_path=CSV_PATH,
        overrides={"diagnostic": label, "instrument": INSTRUMENT},
    )

    t0 = time.time()
    metrics = runner.run(loader.stream(), loader.count(), OUTPUT_DIR)
    elapsed = time.time() - t0
    print(f"[P3b] {label} complete in {elapsed:.1f}s  "
          f"({metrics.approved_trades} trades, pnl={metrics.total_pnl_rr_net:+.4f}R)")

    results_root = Path(OUTPUT_DIR)
    candidates = sorted(
        results_root.glob(f"run_*_{INSTRUMENT}/{INSTRUMENT}_events.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        sys.exit(f"[P3b] ERROR: events JSONL not found after {label}")
    return metrics, candidates[0]

# =============================================================================
# RUN 0 — BASELINE (original sessions)
# =============================================================================
print("[P3b] Run 0: baseline (original sessions)...")
baseline_metrics, baseline_events_path = _run_one(crt_cfg_orig, "P3b_baseline")

# =============================================================================
# RUN 1 — PATCHED (session-relaxed)
# =============================================================================
print("[P3b] Run 1: patched (session-relaxed)...")
patched_metrics, patched_events_path = _run_one(crt_cfg_patched, "P3b_session_relax")

# =============================================================================
# PARSE EVENTS — Run 1 (patched)
# =============================================================================
print(f"\n[P3b] Parsing patched events: {patched_events_path}")
with open(patched_events_path, encoding="utf-8") as f:
    events = [json.loads(line) for line in f if line.strip()]

# =============================================================================
# PARSE EVENTS — Run 0 (baseline, for funnel baseline column)
# =============================================================================
with open(baseline_events_path, encoding="utf-8") as f:
    baseline_events = [json.loads(line) for line in f if line.strip()]

def _trans_counts(ev_list):
    return collections.Counter(
        (e.get("state_from"), e.get("state_to"))
        for e in ev_list if e.get("event") == "STATE_TRANSITION"
        and "state_from" in e and "state_to" in e
    )

tc_patched  = _trans_counts(events)
tc_baseline = _trans_counts(baseline_events)

def _tc(tc, pair):
    return tc.get(pair, 0)

# Funnel transitions
_PAIRS = [
    ("RANGE",        "SWEEP",        "RANGE -> SWEEP"),
    ("SWEEP",        "DISPLACEMENT", "SWEEP -> DISPLACEMENT"),
    ("DISPLACEMENT", "EXPANSION",    "DISPLACEMENT -> EXPANSION"),
    ("EXPANSION",    "RETEST",       "EXPANSION -> RETEST"),
    ("RETEST",       "EXECUTION",    "RETEST -> EXECUTION"),
    ("EXECUTION",    "RESOLUTION",   "EXECUTION -> RESOLUTION"),
]

# FILTER_REJECTED breakdown
all_rejects_p  = [e for e in events        if e.get("event") == "FILTER_REJECTED"]
zone_rejects_p = [e for e in all_rejects_p if "zone" in e.get("reason", "").lower()]
sess_rejects_p = [e for e in all_rejects_p if "off_session" in e.get("reason", "").lower()]

all_rejects_b  = [e for e in baseline_events if e.get("event") == "FILTER_REJECTED"]
zone_rejects_b = [e for e in all_rejects_b   if "zone" in e.get("reason", "").lower()]
sess_rejects_b = [e for e in all_rejects_b   if "off_session" in e.get("reason", "").lower()]

sess_by_name = collections.Counter(
    e.get("metadata", {}).get("session_name", "?") for e in sess_rejects_p
)

# Trade metrics
trades_p   = patched_metrics.approved_trades
trades_b   = baseline_metrics.approved_trades
pnl_net_p  = round(patched_metrics.total_pnl_rr_net,  4)
pnl_net_b  = round(baseline_metrics.total_pnl_rr_net, 4)
win_rate_p = round(patched_metrics.win_rate, 4)
max_dd_p   = round(getattr(patched_metrics, "max_drawdown_pct", 0.0) or 0.0, 4)

# Delta computation (replaces BASELINE_* hardcoded constants)
added_trades      = trades_p - trades_b
added_total_pnl   = pnl_net_p - pnl_net_b
r_expectancy_added = round(added_total_pnl / max(added_trades, 1), 4) if added_trades > 0 else 0.0
avg_rr_portfolio  = round(pnl_net_p / max(trades_p, 1), 4)
avg_rr_baseline   = round(pnl_net_b / max(trades_b, 1), 4)

# Session histogram of executed trades (patched run)
session_histogram = collections.Counter()
for e in events:
    if e.get("event") == "TRADE_OPENED":
        sess = e.get("metadata", {}).get("session_name", "UNKNOWN")
        session_histogram[sess] += 1

# =============================================================================
# REPORT
# =============================================================================
SEP = "-" * 68

print()
print(SEP)
print(f"P3b DIAGNOSTIC RESULTS - Session relaxation ({INSTRUMENT})")
print(SEP)
print()

print("-- Session patch --")
print(f"  Baseline sessions : {_baseline_sessions}")
print(f"  Patched sessions  : {_patched_sessions}")
print()

print("-- Funnel: Patched vs Baseline --")
print(f"  {'Transition':<32} {'Patched':>8}  {'Baseline':>8}  {'Delta':>8}")
for from_s, to_s, label in _PAIRS:
    p_val = _tc(tc_patched,  (from_s, to_s))
    b_val = _tc(tc_baseline, (from_s, to_s))
    marker = "  <- KEY" if to_s == "EXECUTION" else ""
    print(f"  {label:<32} {p_val:>8}  {b_val:>8}  {p_val-b_val:>+8}{marker}")
print()

print("-- FILTER_REJECTED breakdown --")
print(f"  Total FILTER_REJECTED  : patched={len(all_rejects_p)}  baseline={len(all_rejects_b)}")
print(f"  Zone-position rejects  : patched={len(zone_rejects_p)}  baseline={len(zone_rejects_b)}")
print(f"  Off-session rejects    : patched={len(sess_rejects_p)}  baseline={len(sess_rejects_b)}  (target: 0)")
if sess_by_name:
    print(f"  Remaining off-session rejects by name:")
    for name, cnt in sess_by_name.most_common():
        print(f"    {name:<15} : {cnt}")
print()

print("-- Trade metrics: Patched vs Baseline --")
print(f"  Trades              : {trades_p:>6}   (baseline: {trades_b})")
print(f"  Added trades        : {added_trades:>6}")
print(f"  PnL net R           : {pnl_net_p:>+7.4f}   (baseline: {pnl_net_b:+.4f}R)")
print(f"  avg_R (portfolio)   : {avg_rr_portfolio:>+7.4f}   (baseline: {avg_rr_baseline:+.4f}R)")
print(f"  R expectancy added  : {r_expectancy_added:>+7.4f}   (target: >= {MIN_R_EXP:+.2f}R)")
print(f"  Win rate            : {win_rate_p:>6.4f}   (baseline: {baseline_metrics.win_rate:.4f})")
print(f"  Max DD              : {max_dd_p:>6.4f}   (baseline: {baseline_metrics.max_drawdown_pct:.4f})")
print()

if session_histogram:
    print("-- Session histogram of executed trades (patched run) --")
    for sess, cnt in session_histogram.most_common():
        print(f"  {sess:<15} : {cnt}")
    print()

# =============================================================================
# CRITERIA CHECK
# =============================================================================
print("-- Success criteria --")
criteria = [
    (f"Trades > baseline ({trades_b})",
     trades_p > trades_b,
     f"{trades_p}"),
    (f"R expectancy added >= {MIN_R_EXP:.2f}R",
     added_trades > 0 and r_expectancy_added >= MIN_R_EXP,
     f"{r_expectancy_added:+.4f}R"),
    (f"Portfolio avg_R >= {MIN_R_EXP:.2f}R",
     avg_rr_portfolio >= MIN_R_EXP,
     f"{avg_rr_portfolio:+.4f}R"),
    (f"MaxDD <= {MAX_DD:.4f}",
     max_dd_p <= MAX_DD,
     f"{max_dd_p:.4f}"),
    ("Off-session rejects = 0",
     len(sess_rejects_p) == 0,
     f"{len(sess_rejects_p)} remaining"),
]
for label, passed, val in criteria:
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {label:<44} {val}")
print()

# =============================================================================
# VERDICT
# =============================================================================
print("-- Verdict --")
trades_up = trades_p > trades_b
r_ok      = added_trades > 0 and r_expectancy_added >= MIN_R_EXP
all_pass  = all(p for _, p, _ in criteria)

if not trades_up:
    print("  Trades unchanged. Session-allowed setups blocked by other guards.")
    print("  Session filter was NOT the execution governor for this instrument.")
elif trades_up and r_ok and all_pass:
    print(f"  PASS: {added_trades} trades added, R expectancy of added trades >= {MIN_R_EXP:.2f}R.")
    print("  Session relaxation is ROI-positive.")
    print("  -> Proceed to P3c (zone relax). Then config-gate allowed_sessions.")
elif trades_up and not r_ok:
    print(f"  MIXED: {added_trades} trades added but R expectancy below {MIN_R_EXP:.2f}R.")
    print("  Session filter IS a quality governor for these sessions.")
    print("  -> Do NOT relax globally. Investigate per-session quality separately.")
else:
    print("  PARTIAL: review criteria table above.")
print()
print(f"[P3b] Baseline events : {baseline_events_path}")
print(f"[P3b] Patched events  : {patched_events_path}")
print(f"[P3b] Total events    : baseline={len(baseline_events)}  patched={len(events)}")
print(SEP)
