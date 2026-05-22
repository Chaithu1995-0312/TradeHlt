# -*- coding: utf-8 -*-
"""
P3b Diagnostic - Session relaxation: add ASIA + OFF_SESSION to allowed_sessions.

Hypothesis:
  4 of 14 RETEST->EXECUTION setups (baseline) are blocked by the session filter
  (3 OFF_SESSION, 1 ASIA). If the session filter is too conservative, relaxing
  it should add trades with quality >= baseline.

Patch:
  Single config attribute override on the loaded CRTConfig instance.
  No source files modified.

  crt_cfg.allowed_sessions = ("LONDON", "NEWYORK", "OVERLAP", "ASIA", "OFF_SESSION")

Baseline (htf=4, ETHUSDT M15):
  RETEST -> EXECUTION  : 4 / 14  (28.6%)
  Off-session rejects  : 4  (3 OFF_SESSION + 1 ASIA)
  Trades               : 4
  PnL net R            : +1.57R
  avg_R per trade      : +0.39R

Metrics collected post-run:
  - Trades added (count of new trades vs baseline)
  - R expectancy of ADDED trades only (not portfolio average)
  - avg_R portfolio (blended baseline + new)
  - Win rate on new trades
  - Session histogram of new trades (which sessions they came from)
  - MaxDD
  - RETEST -> EXECUTION conversion rate

Decision rule:
  PASS  : trades > 4 AND R_expectancy_added >= 0.39R AND MaxDD <= 0.0132
  MIXED : trades > 4 AND R_expectancy_added < 0.39R
    -> Session filter is quality governor; OFF_SESSION adds noise
  NONE  : trades = 4 (session-allowed setups blocked by other guards)

Usage:
    cd D:\\Tradelatest
    python scripts\\analysis\\p3b_session_relax_diag.py
"""

import sys
import os
import json
import time
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

CSV_PATH   = str(_ROOT / "data" / "ETHUSDT_M15.csv")
INSTRUMENT = "ETHUSDT"
OUTPUT_DIR = str(_ROOT / "results")

# =============================================================================
# PATCH — override allowed_sessions after config load (one attribute change)
# CRTConfig is a frozen dataclass; use dataclasses.replace to produce a new
# instance with the relaxed session set.
# =============================================================================
crt_cfg_orig = load_prod_config_from_registry(PROD_VERSION, INSTRUMENT)

_baseline_sessions = tuple(crt_cfg_orig.allowed_sessions)  # snapshot before patch
_patched_sessions  = ("LONDON", "NEWYORK", "OVERLAP", "ASIA", "OFF_SESSION")
crt_cfg = dataclasses.replace(crt_cfg_orig, allowed_sessions=_patched_sessions)

print(f"[P3b] Session patch applied:")
print(f"      baseline  : {_baseline_sessions}")
print(f"      patched   : {_patched_sessions}")
print(f"      added     : {set(_patched_sessions) - set(_baseline_sessions)}")

cfg = BacktestConfig.from_prod_config(crt_config=crt_cfg)
cfg.instrument = INSTRUMENT
cfg.pip_size   = MultiInstrumentRunner.INSTRUMENT_PIP.get(INSTRUMENT, 0.0001)

print(f"\n[P3b] Running backtest: {CSV_PATH}")
print(f"      instrument : {INSTRUMENT}")
print(f"      prod_ver   : {PROD_VERSION}\n")

loader = CandleLoader(CSV_PATH, INSTRUMENT)
runner = BacktestRunner(cfg, csv_path=CSV_PATH, overrides={"diagnostic": "P3b_session_relax"})

_t0 = time.time()
metrics = runner.run(loader.stream(), loader.count(), OUTPUT_DIR)
_elapsed = time.time() - _t0
print(f"\n[P3b] Backtest complete in {_elapsed:.1f}s")

# =============================================================================
# FIND EVENTS JSONL
# =============================================================================
results_root = Path(OUTPUT_DIR)
candidates = sorted(
    results_root.glob(f"run_*_{INSTRUMENT}/{INSTRUMENT}_events.jsonl"),
    key=lambda p: p.stat().st_mtime,
    reverse=True,
)
if not candidates:
    print("[P3b] ERROR: events JSONL not found")
    sys.exit(1)

events_path = candidates[0]
print(f"[P3b] Parsing: {events_path}\n")

with open(events_path, encoding="utf-8") as f:
    events = [json.loads(line) for line in f if line.strip()]

# =============================================================================
# PARSE EVENTS
# =============================================================================
trans_counts = collections.Counter(
    (e.get("state_from"), e.get("state_to"))
    for e in events if e.get("event") == "STATE_TRANSITION"
    and "state_from" in e and "state_to" in e
)

range_to_sweep  = trans_counts.get(("RANGE",        "SWEEP"),        0)
sweep_to_disp   = trans_counts.get(("SWEEP",        "DISPLACEMENT"), 0)
disp_to_exp     = trans_counts.get(("DISPLACEMENT", "EXPANSION"),    0)
exp_to_retest   = trans_counts.get(("EXPANSION",    "RETEST"),       0)
retest_to_exec  = trans_counts.get(("RETEST",       "EXECUTION"),    0)
exec_to_res     = trans_counts.get(("EXECUTION",    "RESOLUTION"),   0)

# FILTER_REJECTED breakdown
all_rejects  = [e for e in events if e.get("event") == "FILTER_REJECTED"]
zone_rejects = [e for e in all_rejects if "zone" in e.get("reason", "").lower()]
sess_rejects = [e for e in all_rejects if "off_session" in e.get("reason", "").lower()]

# Session histogram of remaining off_session rejects (should now be 0 if patch worked)
sess_by_name = collections.Counter(
    e.get("metadata", {}).get("session_name", "?") for e in sess_rejects
)

# Trade metrics
trades   = metrics.approved_trades     if metrics else "?"
pnl_net  = round(metrics.total_pnl_rr_net, 4) if metrics else "?"
win_rate = round(metrics.win_rate, 4)          if metrics else "?"
max_dd   = round(getattr(metrics, "max_drawdown_pct", 0.0) or 0.0, 4) if metrics else "?"

# Per-trade R computation
trade_events = [e for e in events if e.get("event") == "TRADE_OPENED"]
# Compute R expectancy from RESOLUTION events (which have pnl_rr)
resolution_events = [e for e in events if e.get("event") in
                     ("TRADE_TP1", "TRADE_TP2", "TRADE_STOPPED")]

# Try to get per-trade R from trade logger / resolution events
# The backtest metrics object should have per-trade breakdown
per_trade_rr = []
if metrics and hasattr(metrics, "trades") and metrics.trades:
    for t in metrics.trades:
        rr = getattr(t, "pnl_rr_net", None) or getattr(t, "pnl_rr", None)
        if rr is not None:
            per_trade_rr.append((getattr(t, "id", "?"), round(float(rr), 4)))

# If per-trade breakdown not available, compute avg_R from totals
avg_rr_portfolio = round(metrics.total_pnl_rr_net / max(metrics.approved_trades, 1), 4) \
    if metrics else "?"

# Estimate added trades vs baseline
BASELINE_TRADES = 4
BASELINE_AVG_RR = 0.39
added_trades = (trades - BASELINE_TRADES) if isinstance(trades, int) else "?"

# R expectancy of ADDED trades:
# total_pnl = baseline_pnl + added_pnl
# added_pnl = total_pnl - baseline_pnl (approx: assume baseline trades unchanged)
BASELINE_TOTAL_PNL = 1.57
if isinstance(pnl_net, float) and isinstance(added_trades, int) and added_trades > 0:
    added_total_rr = pnl_net - BASELINE_TOTAL_PNL
    r_expectancy_added = round(added_total_rr / added_trades, 4)
else:
    r_expectancy_added = "?"

# Session histogram of new trades (from TRADE_OPENED metadata if session recorded)
session_histogram = collections.Counter()
for e in events:
    if e.get("event") == "TRADE_OPENED":
        sess = e.get("metadata", {}).get("session", "UNKNOWN")
        session_histogram[sess] += 1

# =============================================================================
# REPORT
# =============================================================================
SEP = "-" * 68

print(SEP)
print("P3b DIAGNOSTIC RESULTS - Session relaxation (ASIA + OFF_SESSION added)")
print(SEP)
print()

print("-- Session patch --")
print(f"  Baseline sessions : {_baseline_sessions}")
print(f"  Patched sessions  : {_patched_sessions}")
print()

print("-- Funnel (P3b) vs Baseline --")
print(f"  {'Transition':<32} {'P3b':>8}  {'Baseline':>8}  {'Delta':>8}")
print(f"  {'RANGE -> SWEEP':<32} {range_to_sweep:>8}  {'1,726':>8}  {range_to_sweep-1726:>+8}")
print(f"  {'SWEEP -> DISPLACEMENT':<32} {sweep_to_disp:>8}  {'357':>8}  {sweep_to_disp-357:>+8}")
print(f"  {'DISPLACEMENT -> EXPANSION':<32} {disp_to_exp:>8}  {'15':>8}  {disp_to_exp-15:>+8}")
print(f"  {'EXPANSION -> RETEST':<32} {exp_to_retest:>8}  {'14':>8}  {exp_to_retest-14:>+8}")
print(f"  {'RETEST -> EXECUTION':<32} {retest_to_exec:>8}  {'4':>8}  {retest_to_exec-4:>+8}  <- KEY")
print(f"  {'EXECUTION -> RESOLUTION':<32} {exec_to_res:>8}  {'4':>8}  {exec_to_res-4:>+8}")
print()

print("-- FILTER_REJECTED breakdown (P3b) --")
print(f"  Total FILTER_REJECTED  : {len(all_rejects)}  (baseline: 10)")
print(f"  Zone-position rejects  : {len(zone_rejects)}  (baseline: 6, should be unchanged)")
print(f"  Off-session rejects    : {len(sess_rejects)}  (target: 0 — all sessions allowed)")
if sess_by_name:
    print(f"  Remaining session rejects by name:")
    for name, cnt in sess_by_name.most_common():
        print(f"    {name:<15} : {cnt}")
print()

print("-- Trade metrics (P3b) vs Baseline --")
print(f"  Trades              : {str(trades):>6}   (baseline: 4)")
print(f"  Added trades        : {str(added_trades):>6}")
print(f"  PnL net R           : {str(pnl_net):>6}   (baseline: +1.57R)")
print(f"  avg_R (portfolio)   : {str(avg_rr_portfolio):>6}   (baseline: +0.39R)")
print(f"  R expectancy added  : {str(r_expectancy_added):>6}   (target: >= +0.39R)")
print(f"  Win rate            : {str(win_rate):>6}   (baseline: 0.5)")
print(f"  Max DD              : {str(max_dd):>6}   (baseline: 0.011)")
print()

if per_trade_rr:
    print("-- Per-trade R breakdown --")
    for tid, rr in per_trade_rr:
        flag = "  (new)" if len(per_trade_rr) > BASELINE_TRADES else ""
        print(f"  {tid}  {rr:>+8.4f}R{flag}")
    print()

if session_histogram:
    print("-- Session histogram of executed trades --")
    for sess, cnt in session_histogram.most_common():
        print(f"  {sess:<15} : {cnt}")
    print()

# =============================================================================
# CRITERIA CHECK
# =============================================================================
print("-- Success criteria --")
criteria = [
    ("Trades > baseline (4)",
     isinstance(trades, int) and trades > BASELINE_TRADES,
     f"{trades}"),
    ("R expectancy added >= 0.39R",
     isinstance(r_expectancy_added, float) and r_expectancy_added >= BASELINE_AVG_RR,
     f"{r_expectancy_added}"),
    ("Portfolio avg_R >= 0.39R",
     isinstance(avg_rr_portfolio, float) and avg_rr_portfolio >= BASELINE_AVG_RR,
     f"{avg_rr_portfolio}"),
    ("MaxDD <= 0.0132 (baseline x1.2)",
     isinstance(max_dd, float) and max_dd <= 0.0132,
     f"{max_dd}"),
    ("Off-session rejects = 0",
     len(sess_rejects) == 0,
     f"{len(sess_rejects)} remaining"),
]
for label, passed, val in criteria:
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {label:<40} {val}")
print()

# =============================================================================
# VERDICT
# =============================================================================
print("-- Verdict --")
all_pass = all(p for _, p, _ in criteria)
trades_up = isinstance(trades, int) and trades > BASELINE_TRADES
r_ok      = isinstance(r_expectancy_added, float) and r_expectancy_added >= BASELINE_AVG_RR

if not trades_up:
    print("  Trades unchanged. Session-allowed setups blocked by other guards.")
    print("  Session filter was not the execution governor.")
elif trades_up and r_ok and all_pass:
    print("  PASS: trades up, R expectancy of added trades >= baseline.")
    print("  Session relaxation is ROI-positive.")
    print("  -> Proceed to P3c (zone relax). Then config-gate allowed_sessions.")
elif trades_up and not r_ok:
    print("  MIXED: trades up but R expectancy of added trades below baseline.")
    print("  Session filter IS a quality governor for OFF_SESSION setups.")
    print("  -> Do NOT relax globally. Investigate per-session quality separately.")
else:
    print("  PARTIAL: review criteria table above.")
print()
print(f"[P3b] Events JSONL : {events_path}")
print(f"[P3b] Total events : {len(events)}")
print(SEP)
