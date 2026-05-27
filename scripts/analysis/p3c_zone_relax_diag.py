# -*- coding: utf-8 -*-
"""
P3c Diagnostic - Zone threshold relaxation.

Hypothesis:
  A portion of RETEST->EXECUTION setups are blocked by the zone-position
  filter, which rejects LONG entries above the range midpoint and SHORT
  entries below it. If zone rejects cluster near the midpoint (see P3a),
  a moderate threshold relaxation captures them without admitting
  structurally bad entries.

Configuration:
  --zone-relax-pct 0.60  -> LONG: entry allowed up to 60% of range from l_ref
                             SHORT: entry allowed down to 40% of range from l_ref
  --zone-relax-pct 0.67  -> LONG: 67%; SHORT: 33%

Patch (state save/restore wrapper):
  1. Monkeypatch EventLogger.record to track the last FILTER_REJECTED reason.
  2. Monkeypatch CRTEngine.process_candle:
     - Save key state fields (deepcopy) BEFORE calling original.
     - Call original.
     - If action is FILTER_REJECTED for zone reason AND entry_pct is within
       ZONE_RELAX_PCT: restore state to RETEST, re-run session check, execute.

  State fields cleared by reset_to_range (must restore):
    current_state, retest_candle, retest_candle_index, direction,
    risk_score, cached_features, evaluating_soft_conf, soft_conf_candles,
    sweep_event (P3c.1 fix), displacement_candle (P3c.1 fix).
  active_range is NOT cleared by reset_to_range; saved for safety.

Auto-baseline:
  This script runs TWO backtests:
  Run 0 (baseline) — no zone relaxation (original filter logic)
  Run 1 (patched)  — zone relaxation at --zone-relax-pct threshold
  Delta is computed as Run1 - Run0 for all metrics.

Usage:
    cd D:\\Tradelatest
    # First run (P3a must have been analysed first):
    python scripts\\analysis\\p3c_zone_relax_diag.py --instrument BTCUSDT
    python scripts\\analysis\\p3c_zone_relax_diag.py --instrument SOLUSDT
    python scripts\\analysis\\p3c_zone_relax_diag.py --instrument ETHUSDT --zone-relax-pct 0.60
    # Second run at 0.67 if 0.60 justified:
    python scripts\\analysis\\p3c_zone_relax_diag.py --instrument BTCUSDT --zone-relax-pct 0.67
"""

import sys
import os
import json
import time
import copy
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

_ap = argparse.ArgumentParser(description="P3c zone threshold relaxation diagnostic")
_ap.add_argument("--instrument",     required=True,
                 help="Symbol to run, e.g. BTCUSDT, SOLUSDT, ETHUSDT")
_ap.add_argument("--csv",            default=None,
                 help="Explicit path to data file (CSV). Auto-resolved if omitted.")
_ap.add_argument("--output-dir",     default=str(_ROOT / "results"),
                 help="Directory for backtest run output (default: results)")
_ap.add_argument("--zone-relax-pct", type=float, default=0.60,
                 help="Zone relaxation threshold (default: 0.60). "
                      "LONG: entry up to this fraction of range; SHORT: 1-this.")
args = _ap.parse_args()

INSTRUMENT     = args.instrument
CSV_PATH       = _resolve_data_file(args.instrument, args.csv)
OUTPUT_DIR     = args.output_dir
ZONE_RELAX_PCT = args.zone_relax_pct

# =============================================================================
# IMPORT BEFORE PATCHING (patches must be applied before the run)
# =============================================================================
from config_layer.crt_engine_v2 import (
    CRTEngine, EventLogger, Direction, CRTState,
)

print(f"[P3c] Zone relaxation threshold : {ZONE_RELAX_PCT:.0%}")
print(f"[P3c] Instrument                : {INSTRUMENT}")
print(f"[P3c] Data file                 : {CSV_PATH}")
print("[P3c] Applying monkeypatches...")

# =============================================================================
# PATCH SUPPORT: track last FILTER_REJECTED reason via EventLogger.record
# Applied for BOTH runs so we get consistent rejection capture.
# =============================================================================
_last_reject_reason: list = [None]
_orig_record = EventLogger.record

def _record_tracking(self, event_type, candle, **kwargs):
    if event_type == "FILTER_REJECTED":
        _last_reject_reason[0] = kwargs.get("reason", "")
    return _orig_record(self, event_type, candle, **kwargs)

EventLogger.record = _record_tracking
print("[P3c] Patch 1: EventLogger.record -> tracks last FILTER_REJECTED reason")

# =============================================================================
# PATCH 2 — CRTEngine.process_candle: zone threshold relaxation
# save dict includes sweep_event + displacement_candle (P3c.1 fix).
# =============================================================================
_orig_process = CRTEngine.process_candle

# Telemetry counters (reset between runs via _reset_stats)
_stats = {
    "zone_blocked_original": 0,
    "zone_admitted_relaxed":  0,
    "zone_still_blocked":     0,
    "session_still_blocked":  0,
}

def _reset_stats():
    for k in _stats:
        _stats[k] = 0

# Flag: enable/disable the relaxation logic (disabled for Run 0)
_zone_relax_active = False

def _process_zone_relax(self, candle, htf_candle_id):
    if not _zone_relax_active:
        return _orig_process(self, candle, htf_candle_id)

    # Save state BEFORE calling original
    # (includes sweep_event + displacement_candle — P3c.1 fix)
    _saved = copy.deepcopy({
        "current_state":        self.state.current_state,
        "active_range":         self.state.active_range,
        "retest_candle":        getattr(self.state, "retest_candle",        None),
        "retest_candle_index":  getattr(self.state, "retest_candle_index",  0),
        "sweep_event":          getattr(self.state, "sweep_event",          None),
        "displacement_candle":  getattr(self.state, "displacement_candle",  None),
        "direction":            self.state.direction,
        "risk_score":           self.state.risk_score,
        "cached_features":      self.state.cached_features,
        "evaluating_soft_conf": self.state.evaluating_soft_conf,
        "soft_conf_candles":    self.state.soft_conf_candles,
    })
    _last_reject_reason[0] = None

    action = _orig_process(self, candle, htf_candle_id)

    reason = _last_reject_reason[0] or ""
    if not (action.get("action") == "FILTER_REJECTED" and
            ("discount zone" in reason or "premium zone" in reason)):
        return action

    # Guard: only zone-relax when the saved state was RETEST.
    # If the engine was in EXECUTION state and still fired a zone reject
    # (e.g. because a P3c-opened trade wasn't registered in the engine's
    # trade tracker and EXECUTION logic fell through to entry re-evaluation),
    # we must NOT re-open another trade. Restoring + executing from a non-RETEST
    # saved state causes cascading duplicate trades (P3c.2 fix).
    if _saved["current_state"] != CRTState.RETEST:
        return action

    _stats["zone_blocked_original"] += 1

    rng   = _saved["active_range"]
    ret_c = _saved["retest_candle"]
    if rng is None or ret_c is None:
        return action

    span = rng.h_ref - rng.l_ref
    if span <= 0:
        return action

    entry     = ret_c.close
    entry_pct = (entry - rng.l_ref) / span
    dir_long  = (_saved["direction"] == Direction.LONG)

    relaxed_pass = (
        (dir_long  and entry_pct <= ZONE_RELAX_PCT) or
        (not dir_long and entry_pct >= 1.0 - ZONE_RELAX_PCT)
    )

    if not relaxed_pass:
        _stats["zone_still_blocked"] += 1
        return action

    # Restore state to RETEST (including sweep_event + displacement_candle)
    self.state.current_state        = _saved["current_state"]
    self.state.active_range         = _saved["active_range"]
    self.state.retest_candle        = _saved["retest_candle"]
    self.state.retest_candle_index  = _saved["retest_candle_index"]
    self.state.sweep_event          = _saved["sweep_event"]
    self.state.displacement_candle  = _saved["displacement_candle"]
    self.state.direction            = _saved["direction"]
    self.state.risk_score           = _saved["risk_score"]
    self.state.cached_features      = _saved["cached_features"]
    self.state.evaluating_soft_conf = _saved["evaluating_soft_conf"]
    self.state.soft_conf_candles    = _saved["soft_conf_candles"]

    # Session check (preserve session filter)
    _ts_time  = candle.timestamp.time()
    _sess_name = "OFF_SESSION"
    for _name, (_start, _end) in self.config.session_windows.items():
        if _start <= _ts_time <= _end:
            _sess_name = _name
            break
    if _sess_name not in self.config.allowed_sessions:
        self.sm.reset_to_range(self.state, "off_session_filter_p3c", candle, self.ev_log)
        self.ev_log.record(
            "FILTER_REJECTED", candle,
            reason=f"off_session:{_sess_name}",
            metadata={"session_name": _sess_name, "via": "P3c_session_guard"},
        )
        action["action"] = "FILTER_REJECTED"
        _stats["session_still_blocked"] += 1
        return action

    # Proceed to execution
    self.sm.try_retest_to_execution(self.state, candle, self.ev_log)
    trade = self.executor.build_trade(self.state, self.risk)

    if trade:
        self.executor.open_trade(trade, candle.timestamp)
        self.state.active_trade = trade
        self.ev_log.record(
            "TRADE_OPENED", candle,
            direction=trade.direction.value,
            price=trade.entry_price,
            metadata={
                "id":             trade.id,
                "sl":             trade.sl_price,
                "tp1":            trade.tp1_price,
                "tp2":            trade.tp2_price,
                "risk_pct":       trade.risk_pct,
                "via":            "P3c_zone_relax",
                "zone_pct":       round(entry_pct, 3),
                "zone_threshold": ZONE_RELAX_PCT,
            },
        )
        action["action"]   = "TRADE_OPENED"
        action["trade_id"] = trade.id
        _stats["zone_admitted_relaxed"] += 1
    else:
        self.sm.reset_to_range(self.state, "build_trade_none_p3c", candle, self.ev_log)
        action["action"] = "FILTER_REJECTED"

    return action

CRTEngine.process_candle = _process_zone_relax
print(f"[P3c] Patch 2: process_candle -> zone relax at {ZONE_RELAX_PCT:.0%} (disabled for Run 0)")
print("[P3c] Session filter preserved. sweep_event + displacement_candle included in save set.")

# =============================================================================
# BACKTEST RUNNER IMPORTS
# =============================================================================
from runtime.backtest_v2 import (
    BacktestRunner, BacktestConfig, CandleLoader,
    load_prod_config_from_registry, PROD_VERSION, MultiInstrumentRunner,
)

crt_cfg = load_prod_config_from_registry(PROD_VERSION, INSTRUMENT)

# =============================================================================
# TWO-RUN HELPER
# =============================================================================
def _run_one(label: str) -> tuple:
    """Run a single backtest and return (metrics, events_path)."""
    cfg = BacktestConfig.from_prod_config(crt_config=crt_cfg)
    cfg.instrument = INSTRUMENT
    cfg.pip_size   = MultiInstrumentRunner.INSTRUMENT_PIP.get(INSTRUMENT, 0.0001)

    loader = CandleLoader(CSV_PATH, INSTRUMENT)
    overrides_label = (f"P3c_zone_relax_{int(ZONE_RELAX_PCT*100)}pct"
                       if "patched" in label.lower() else "P3c_baseline")
    runner = BacktestRunner(
        cfg, csv_path=CSV_PATH,
        overrides={"diagnostic": overrides_label, "instrument": INSTRUMENT},
    )

    t0 = time.time()
    metrics = runner.run(loader.stream(), loader.count(), OUTPUT_DIR)
    elapsed = time.time() - t0
    print(f"[P3c] {label} complete in {elapsed:.1f}s  "
          f"({metrics.approved_trades} trades, pnl={metrics.total_pnl_rr_net:+.4f}R)")

    results_root = Path(OUTPUT_DIR)
    candidates = sorted(
        results_root.glob(f"run_*_{INSTRUMENT}/{INSTRUMENT}_events.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        sys.exit(f"[P3c] ERROR: events JSONL not found after {label}")
    return metrics, candidates[0]

# =============================================================================
# RUN 0 — BASELINE (no zone relaxation)
# =============================================================================
print("\n[P3c] Run 0: baseline (zone filter unchanged)...")
_zone_relax_active = False
_reset_stats()
baseline_metrics, baseline_events_path = _run_one("baseline")

# =============================================================================
# RUN 1 — PATCHED (zone relaxation enabled)
# =============================================================================
print(f"[P3c] Run 1: patched (zone relax at {ZONE_RELAX_PCT:.0%})...")
_zone_relax_active = True
_reset_stats()
patched_metrics, patched_events_path = _run_one("patched")

# =============================================================================
# PARSE EVENTS
# =============================================================================
print(f"\n[P3c] Parsing patched events: {patched_events_path}")
with open(patched_events_path, encoding="utf-8") as f:
    events = [json.loads(line) for line in f if line.strip()]

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

_PAIRS = [
    ("RANGE",        "SWEEP",        "RANGE -> SWEEP"),
    ("SWEEP",        "DISPLACEMENT", "SWEEP -> DISPLACEMENT"),
    ("DISPLACEMENT", "EXPANSION",    "DISPLACEMENT -> EXPANSION"),
    ("EXPANSION",    "RETEST",       "EXPANSION -> RETEST"),
    ("RETEST",       "EXECUTION",    "RETEST -> EXECUTION"),
    ("EXECUTION",    "RESOLUTION",   "EXECUTION -> RESOLUTION"),
]

all_rejects_p  = [e for e in events         if e.get("event") == "FILTER_REJECTED"]
zone_rejects_p = [e for e in all_rejects_p  if "zone" in e.get("reason", "").lower()]
sess_rejects_p = [e for e in all_rejects_p  if "off_session" in e.get("reason", "").lower()]

all_rejects_b  = [e for e in baseline_events if e.get("event") == "FILTER_REJECTED"]
zone_rejects_b = [e for e in all_rejects_b   if "zone" in e.get("reason", "").lower()]

p3c_trades = [e for e in events
              if e.get("event") == "TRADE_OPENED"
              and e.get("metadata", {}).get("via") == "P3c_zone_relax"]
p3c_zone_pcts = [e.get("metadata", {}).get("zone_pct", "?") for e in p3c_trades]

# Trade metrics
trades_p          = patched_metrics.approved_trades
trades_b          = baseline_metrics.approved_trades
pnl_net_p         = round(patched_metrics.total_pnl_rr_net,  4)
pnl_net_b         = round(baseline_metrics.total_pnl_rr_net, 4)
win_rate_p        = round(patched_metrics.win_rate, 4)
max_dd_p          = round(getattr(patched_metrics, "max_drawdown_pct", 0.0) or 0.0, 4)
avg_rr_portfolio  = round(pnl_net_p / max(trades_p, 1), 4)
avg_rr_baseline   = round(pnl_net_b / max(trades_b, 1), 4)

# Delta
added_trades       = trades_p - trades_b
added_pnl          = pnl_net_p - pnl_net_b
r_expectancy_added = round(added_pnl / max(added_trades, 1), 4) if added_trades > 0 else 0.0
BASELINE_AVG_RR    = avg_rr_baseline   # for criteria labels

# =============================================================================
# REPORT
# =============================================================================
SEP = "-" * 68

print()
print(SEP)
print(f"P3c DIAGNOSTIC RESULTS - Zone relaxation at {ZONE_RELAX_PCT:.0%} ({INSTRUMENT})")
print(SEP)
print()

print("-- Zone patch internals (Run 1 only) --")
print(f"  zone_blocked_original  : {_stats['zone_blocked_original']}  (setups zone filter would have blocked)")
print(f"  zone_admitted_relaxed  : {_stats['zone_admitted_relaxed']}  (admitted by {ZONE_RELAX_PCT:.0%} threshold)")
print(f"  zone_still_blocked     : {_stats['zone_still_blocked']}  (entry_pct > {ZONE_RELAX_PCT:.0%}; still blocked)")
print(f"  session_still_blocked  : {_stats['session_still_blocked']}  (admitted by zone, blocked by session)")
print()

print("-- Funnel: Patched vs Baseline --")
print(f"  {'Transition':<32} {'Patched':>8}  {'Baseline':>8}  {'Delta':>8}")
for from_s, to_s, label in _PAIRS:
    p_val = tc_patched.get((from_s, to_s), 0)
    b_val = tc_baseline.get((from_s, to_s), 0)
    marker = "  <- KEY" if to_s == "EXECUTION" else ""
    print(f"  {label:<32} {p_val:>8}  {b_val:>8}  {p_val-b_val:>+8}{marker}")
print()

print("-- FILTER_REJECTED breakdown --")
print(f"  Zone rejects  : patched={len(zone_rejects_p)}  baseline={len(zone_rejects_b)}  "
      f"(delta={len(zone_rejects_p)-len(zone_rejects_b):+d})")
print(f"  Session rej.  : patched={len(sess_rejects_p)}  baseline={len(all_rejects_b)-len(zone_rejects_b)}  "
      f"(should be unchanged)")
print()

if p3c_trades:
    print(f"-- Zone-relaxed trades admitted (via P3c_zone_relax) --")
    for e in p3c_trades:
        m = e.get("metadata", {})
        print(f"  {e.get('timestamp','?')[:19]}  dir={e.get('direction','?'):<6} "
              f"price={m.get('entry_price', e.get('price', 0)):.4f}  "
              f"zone_pct={m.get('zone_pct','?')}")
    print()

print("-- Trade metrics: Patched vs Baseline --")
print(f"  Trades              : {trades_p:>6}   (baseline: {trades_b})")
print(f"  Added trades        : {added_trades:>6}")
print(f"  P3c-admitted trades : {len(p3c_trades):>6}")
print(f"  PnL net R           : {pnl_net_p:>+7.4f}   (baseline: {pnl_net_b:+.4f}R)")
print(f"  avg_R (portfolio)   : {avg_rr_portfolio:>+7.4f}   (baseline: {avg_rr_baseline:+.4f}R)")
print(f"  R expectancy added  : {r_expectancy_added:>+7.4f}   (target: >= {BASELINE_AVG_RR:+.4f}R)")
print(f"  Win rate            : {win_rate_p:>7.4f}   (baseline: {baseline_metrics.win_rate:.4f})")
print(f"  Max DD              : {max_dd_p:>7.4f}   (baseline: {baseline_metrics.max_drawdown_pct:.4f})")
print()

# Funnel integrity check
disp_to_exp_p  = tc_patched.get(("DISPLACEMENT", "EXPANSION"), 0)
disp_to_exp_b  = tc_baseline.get(("DISPLACEMENT", "EXPANSION"), 0)
sweep_to_disp_p = tc_patched.get(("SWEEP", "DISPLACEMENT"), 0)
sweep_to_disp_b = tc_baseline.get(("SWEEP", "DISPLACEMENT"), 0)

# =============================================================================
# CRITERIA CHECK
# =============================================================================
print("-- Success criteria --")
criteria = [
    (f"Trades > baseline ({trades_b})",
     trades_p > trades_b,
     f"{trades_p}"),
    (f"zone_admitted > 0 at {ZONE_RELAX_PCT:.0%}",
     _stats["zone_admitted_relaxed"] > 0,
     f"{_stats['zone_admitted_relaxed']} admitted"),
    (f"R expectancy added >= baseline avg ({BASELINE_AVG_RR:+.4f}R)",
     added_trades > 0 and r_expectancy_added >= BASELINE_AVG_RR,
     f"{r_expectancy_added:+.4f}R"),
    (f"Portfolio avg_R >= baseline avg ({BASELINE_AVG_RR:+.4f}R)",
     avg_rr_portfolio >= BASELINE_AVG_RR,
     f"{avg_rr_portfolio:+.4f}R"),
    (f"MaxDD <= baseline x1.2 ({baseline_metrics.max_drawdown_pct*1.2:.4f})",
     max_dd_p <= max(baseline_metrics.max_drawdown_pct * 1.2, 0.0132),
     f"{max_dd_p:.4f}"),
    ("Funnel above RETEST unchanged",
     disp_to_exp_p == disp_to_exp_b and sweep_to_disp_p == sweep_to_disp_b,
     f"disp_to_exp={disp_to_exp_p} ({'+' if disp_to_exp_p>=disp_to_exp_b else ''}"
     f"{disp_to_exp_p-disp_to_exp_b:+d}), "
     f"sweep_to_disp={sweep_to_disp_p} ({sweep_to_disp_p-sweep_to_disp_b:+d})"),
]
for label, passed, val in criteria:
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {label:<50} {val}")
print()

# =============================================================================
# VERDICT
# =============================================================================
print("-- Verdict --")
admitted   = _stats["zone_admitted_relaxed"]
trades_up  = trades_p > trades_b
r_ok       = added_trades > 0 and r_expectancy_added >= BASELINE_AVG_RR
dd_ok      = max_dd_p <= max(baseline_metrics.max_drawdown_pct * 1.2, 0.0132)

if admitted == 0:
    print(f"  Zone relax at {ZONE_RELAX_PCT:.0%} admitted 0 setups.")
    print("  Zone rejects are above this threshold (structurally unfavourable entries).")
    print("  -> Check P3a zone_pct distribution. If p95 > 67%, zone filter is correct.")
elif trades_up and r_ok and dd_ok:
    print(f"  PASS: {admitted} zone rejects admitted, R expectancy >= baseline, MaxDD safe.")
    print(f"  Zone threshold {ZONE_RELAX_PCT:.0%} is ROI-positive for {INSTRUMENT}.")
    if ZONE_RELAX_PCT < 0.67:
        print(f"  -> Run at 0.67 to test sensitivity curve.")
    else:
        print("  -> Config-gate zone_discount_pct / zone_premium_pct.")
elif trades_up and not r_ok:
    print(f"  MIXED: {admitted} zone rejects admitted but R expectancy below baseline.")
    print(f"  Zone filter at 50% is a quality governor at {ZONE_RELAX_PCT:.0%} threshold.")
    if ZONE_RELAX_PCT < 0.67:
        print(f"  -> Do NOT run at 0.67; quality already degrading at {ZONE_RELAX_PCT:.0%}.")
    else:
        print("  -> REJECT zone relaxation. Keep midpoint filter.")
else:
    print("  PARTIAL: review criteria table. DD or funnel integrity may have failed.")
print()
print(f"[P3c] Baseline events  : {baseline_events_path}")
print(f"[P3c] Patched events   : {patched_events_path}")
print(f"[P3c] ZONE_RELAX_PCT   : {ZONE_RELAX_PCT:.0%}")
print(f"[P3c] instrument       : {INSTRUMENT}")
print(SEP)
