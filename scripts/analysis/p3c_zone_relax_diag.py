# -*- coding: utf-8 -*-
"""
P3c Diagnostic - Zone threshold relaxation.

Hypothesis:
  6 of 14 RETEST->EXECUTION setups (baseline) are blocked by the zone-position
  filter, which rejects LONG entries above the range midpoint and SHORT entries
  below it. If zone rejects cluster near the midpoint (see P3a results), a
  moderate threshold relaxation captures them without admitting structurally
  bad entries.

Configuration:
  Set ZONE_RELAX_PCT at top of script before running.
  Run at 0.60 first (P3a guidance). Run at 0.67 only if P3a shows rejects
  above 60% AND avg_R at 60% >= baseline.

  ZONE_RELAX_PCT = 0.60  -> LONG: entry allowed up to 60% of range from l_ref
                            SHORT: entry allowed down to 40% of range from l_ref
  ZONE_RELAX_PCT = 0.67  -> LONG: 67%; SHORT: 33%

Patch (state save/restore wrapper):
  1. Monkeypatch EventLogger.record to track the last FILTER_REJECTED reason.
  2. Monkeypatch CRTEngine.process_candle:
     - Save key state fields (deepcopy) BEFORE calling original.
     - Call original.
     - If action is FILTER_REJECTED for zone reason AND entry_pct is within
       ZONE_RELAX_PCT: restore state to RETEST, re-run session check, execute.

  State fields cleared by reset_to_range (must restore):
    current_state, retest_candle, retest_candle_index, direction,
    risk_score, cached_features, evaluating_soft_conf, soft_conf_candles.
  NOTE: active_range is NOT cleared by reset_to_range; restored for safety.

Baseline (htf=4, ETHUSDT M15):
  Zone-position rejects  : 6  (3 discount + 3 premium)
  Trades                 : 4
  PnL net R              : +1.57R
  avg_R per trade        : +0.39R

Usage:
    cd D:\\Tradelatest
    # First run (P3a must have been run and analysed first):
    python scripts\\analysis\\p3c_zone_relax_diag.py
    # Edit ZONE_RELAX_PCT = 0.67 then run again if justified.
"""

import sys
import os
import json
import time
import copy
import collections
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_ROOT = Path(__file__).resolve().parents[2]
_SRC  = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
os.chdir(_ROOT)

# ── Configurable threshold ────────────────────────────────────────────────────
# LONG:  entry_price allowed up to   ZONE_RELAX_PCT  of range above l_ref
# SHORT: entry_price allowed down to (1 - ZONE_RELAX_PCT) of range above l_ref
ZONE_RELAX_PCT: float = 0.60   # <-- edit to 0.67 for second run
# ─────────────────────────────────────────────────────────────────────────────

# Import before patching
from config_layer.crt_engine_v2 import (
    CRTEngine, EventLogger, Direction, CRTState,
)

print(f"[P3c] Zone relaxation threshold: {ZONE_RELAX_PCT:.0%}")
print("[P3c] Applying monkeypatches...")

# =============================================================================
# PATCH SUPPORT: track last FILTER_REJECTED reason via EventLogger.record
# =============================================================================
_last_reject_reason: list = [None]   # list so inner function can mutate
_orig_record = EventLogger.record

def _record_tracking(self, event_type, candle, **kwargs):
    if event_type == "FILTER_REJECTED":
        _last_reject_reason[0] = kwargs.get("reason", "")
    return _orig_record(self, event_type, candle, **kwargs)

EventLogger.record = _record_tracking
print("[P3c] Patch 1: EventLogger.record -> tracks last FILTER_REJECTED reason")

# =============================================================================
# PATCH 2 — CRTEngine.process_candle: zone threshold relaxation
# State save uses copy.deepcopy to prevent reference aliasing on mutable
# fields (cached_features dict, risk_score object).
# =============================================================================
_orig_process = CRTEngine.process_candle

# Telemetry counters
_stats = {
    "zone_blocked_original": 0,
    "zone_admitted_relaxed":  0,
    "zone_still_blocked":     0,
    "session_still_blocked":  0,
}

def _process_zone_relax(self, candle, htf_candle_id):
    # Save state BEFORE calling original (deepcopy guards mutable objects)
    _saved = copy.deepcopy({
        "current_state":        self.state.current_state,
        "active_range":         self.state.active_range,      # not cleared by reset, saved for safety
        "retest_candle":        getattr(self.state, "retest_candle", None),
        "retest_candle_index":  getattr(self.state, "retest_candle_index", 0),
        "direction":            self.state.direction,
        "risk_score":           self.state.risk_score,
        "cached_features":      self.state.cached_features,
        "evaluating_soft_conf": self.state.evaluating_soft_conf,
        "soft_conf_candles":    self.state.soft_conf_candles,
    })
    _last_reject_reason[0] = None

    action = _orig_process(self, candle, htf_candle_id)

    # Check if zone filter blocked this setup
    reason = _last_reject_reason[0] or ""
    if not (action.get("action") == "FILTER_REJECTED" and
            ("discount zone" in reason or "premium zone" in reason)):
        return action

    _stats["zone_blocked_original"] += 1

    # Guard: need saved geometry
    rng     = _saved["active_range"]
    ret_c   = _saved["retest_candle"]
    if rng is None or ret_c is None:
        return action

    span    = rng.h_ref - rng.l_ref
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

    # Entry within relaxed zone -- restore state to RETEST
    self.state.current_state        = _saved["current_state"]       # was RETEST
    self.state.active_range         = _saved["active_range"]
    self.state.retest_candle        = _saved["retest_candle"]
    self.state.retest_candle_index  = _saved["retest_candle_index"]
    self.state.direction            = _saved["direction"]
    self.state.risk_score           = _saved["risk_score"]
    self.state.cached_features      = _saved["cached_features"]
    self.state.evaluating_soft_conf = _saved["evaluating_soft_conf"]
    self.state.soft_conf_candles    = _saved["soft_conf_candles"]

    # Session check (preserve session filter as-is)
    _ts_time  = candle.timestamp.time()
    _sess_name = "OFF_SESSION"
    for _name, (_start, _end) in self.config.session_windows.items():
        if _start <= _ts_time <= _end:
            _sess_name = _name
            break
    if _sess_name not in self.config.allowed_sessions:
        # Session still blocks -- re-reset cleanly
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
                "id":         trade.id,
                "sl":         trade.sl_price,
                "tp1":        trade.tp1_price,
                "tp2":        trade.tp2_price,
                "risk_pct":   trade.risk_pct,
                "via":        "P3c_zone_relax",
                "zone_pct":   round(entry_pct, 3),
                "zone_threshold": ZONE_RELAX_PCT,
            },
        )
        action["action"]   = "TRADE_OPENED"
        action["trade_id"] = trade.id
        _stats["zone_admitted_relaxed"] += 1
    else:
        # build_trade returned None (other guard inside executor)
        self.sm.reset_to_range(self.state, "build_trade_none_p3c", candle, self.ev_log)
        action["action"] = "FILTER_REJECTED"

    return action

CRTEngine.process_candle = _process_zone_relax
print(f"[P3c] Patch 2: process_candle -> zone relax at {ZONE_RELAX_PCT:.0%} threshold")
print("[P3c] Session filter preserved. Retrace/extension guards preserved.")

# =============================================================================
# RUN BACKTEST
# =============================================================================
from runtime.backtest_v2 import (
    BacktestRunner, BacktestConfig, CandleLoader,
    load_prod_config_from_registry, PROD_VERSION, MultiInstrumentRunner,
)

CSV_PATH   = str(_ROOT / "data" / "ETHUSDT_M15.csv")
INSTRUMENT = "ETHUSDT"
OUTPUT_DIR = str(_ROOT / "results")

print(f"\n[P3c] Running backtest: {CSV_PATH}")
print(f"      instrument     : {INSTRUMENT}")
print(f"      prod_ver       : {PROD_VERSION}")
print(f"      zone_relax_pct : {ZONE_RELAX_PCT:.0%}\n")

crt_cfg = load_prod_config_from_registry(PROD_VERSION, INSTRUMENT)
cfg = BacktestConfig.from_prod_config(crt_config=crt_cfg)
cfg.instrument = INSTRUMENT
cfg.pip_size   = MultiInstrumentRunner.INSTRUMENT_PIP.get(INSTRUMENT, 0.0001)

loader = CandleLoader(CSV_PATH, INSTRUMENT)
runner = BacktestRunner(
    cfg, csv_path=CSV_PATH,
    overrides={"diagnostic": f"P3c_zone_relax_{int(ZONE_RELAX_PCT*100)}pct"},
)

_t0 = time.time()
metrics = runner.run(loader.stream(), loader.count(), OUTPUT_DIR)
_elapsed = time.time() - _t0
print(f"\n[P3c] Backtest complete in {_elapsed:.1f}s")

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
    print("[P3c] ERROR: events JSONL not found")
    sys.exit(1)

events_path = candidates[0]
print(f"[P3c] Parsing: {events_path}\n")

with open(events_path, encoding="utf-8") as f:
    events = [json.loads(line) for line in f if line.strip()]

# =============================================================================
# PARSE
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

all_rejects  = [e for e in events if e.get("event") == "FILTER_REJECTED"]
zone_rejects = [e for e in all_rejects if "zone" in e.get("reason", "").lower()]
sess_rejects = [e for e in all_rejects if "off_session" in e.get("reason", "").lower()]

# Zone-admitted trades (those opened via P3c relaxation)
p3c_trades = [e for e in events
              if e.get("event") == "TRADE_OPENED"
              and e.get("metadata", {}).get("via") == "P3c_zone_relax"]

# Zone positions of admitted trades
p3c_zone_pcts = [e.get("metadata", {}).get("zone_pct", "?") for e in p3c_trades]

# Trade metrics
trades   = metrics.approved_trades     if metrics else "?"
pnl_net  = round(metrics.total_pnl_rr_net, 4) if metrics else "?"
win_rate = round(metrics.win_rate, 4)          if metrics else "?"
max_dd   = round(getattr(metrics, "max_drawdown_pct", 0.0) or 0.0, 4) if metrics else "?"
avg_rr_portfolio = round(metrics.total_pnl_rr_net / max(metrics.approved_trades, 1), 4) \
    if metrics else "?"

BASELINE_TRADES    = 4
BASELINE_AVG_RR    = 0.39
BASELINE_TOTAL_PNL = 1.57

added_trades = (trades - BASELINE_TRADES) if isinstance(trades, int) else "?"

if isinstance(pnl_net, float) and isinstance(added_trades, int) and added_trades > 0:
    added_total_rr = pnl_net - BASELINE_TOTAL_PNL
    r_expectancy_added = round(added_total_rr / added_trades, 4)
else:
    r_expectancy_added = "?"

# =============================================================================
# REPORT
# =============================================================================
SEP = "-" * 68

print(SEP)
print(f"P3c DIAGNOSTIC RESULTS - Zone relaxation at {ZONE_RELAX_PCT:.0%}")
print(SEP)
print()

print("-- Zone patch internals --")
print(f"  zone_blocked_original  : {_stats['zone_blocked_original']}  (setups zone filter would have blocked)")
print(f"  zone_admitted_relaxed  : {_stats['zone_admitted_relaxed']}  (admitted by {ZONE_RELAX_PCT:.0%} threshold)")
print(f"  zone_still_blocked     : {_stats['zone_still_blocked']}  (entry_pct > {ZONE_RELAX_PCT:.0%}; still blocked)")
print(f"  session_still_blocked  : {_stats['session_still_blocked']}  (admitted by zone, blocked by session)")
print()

print("-- Funnel (P3c) vs Baseline --")
print(f"  {'Transition':<32} {'P3c':>8}  {'Baseline':>8}  {'Delta':>8}")
print(f"  {'RANGE -> SWEEP':<32} {range_to_sweep:>8}  {'1,726':>8}  {range_to_sweep-1726:>+8}")
print(f"  {'SWEEP -> DISPLACEMENT':<32} {sweep_to_disp:>8}  {'357':>8}  {sweep_to_disp-357:>+8}")
print(f"  {'DISPLACEMENT -> EXPANSION':<32} {disp_to_exp:>8}  {'15':>8}  {disp_to_exp-15:>+8}")
print(f"  {'EXPANSION -> RETEST':<32} {exp_to_retest:>8}  {'14':>8}  {exp_to_retest-14:>+8}")
print(f"  {'RETEST -> EXECUTION':<32} {retest_to_exec:>8}  {'4':>8}  {retest_to_exec-4:>+8}  <- KEY")
print(f"  {'EXECUTION -> RESOLUTION':<32} {exec_to_res:>8}  {'4':>8}  {exec_to_res-4:>+8}")
print()

print("-- FILTER_REJECTED breakdown --")
print(f"  Zone rejects remaining : {len(zone_rejects)}  (baseline: 6, target: < 6)")
print(f"  Session rejects        : {len(sess_rejects)}  (baseline: 4, should be unchanged)")
print()

if p3c_trades:
    print(f"-- Zone-relaxed trades admitted (via P3c_zone_relax) --")
    for e in p3c_trades:
        m = e.get("metadata", {})
        print(f"  {e.get('timestamp','?')[:19]}  dir={e.get('direction','?'):<6} "
              f"price={m.get('entry_price',e.get('price',0)):.4f}  "
              f"zone_pct={m.get('zone_pct','?')}")
    print()

print("-- Trade metrics (P3c) vs Baseline --")
print(f"  Trades              : {str(trades):>6}   (baseline: 4)")
print(f"  Added trades        : {str(added_trades):>6}")
print(f"  P3c-admitted trades : {len(p3c_trades):>6}")
print(f"  PnL net R           : {str(pnl_net):>6}   (baseline: +1.57R)")
print(f"  avg_R (portfolio)   : {str(avg_rr_portfolio):>6}   (baseline: +0.39R)")
print(f"  R expectancy added  : {str(r_expectancy_added):>6}   (target: >= +0.39R)")
print(f"  Win rate            : {str(win_rate):>6}   (baseline: 0.5)")
print(f"  Max DD              : {str(max_dd):>6}   (baseline: 0.011, limit: 0.0132)")
print()

# =============================================================================
# CRITERIA CHECK
# =============================================================================
print("-- Success criteria --")
criteria = [
    ("Trades > baseline (4)",
     isinstance(trades, int) and trades > BASELINE_TRADES,
     f"{trades}"),
    (f"zone_admitted > 0 at {ZONE_RELAX_PCT:.0%}",
     _stats["zone_admitted_relaxed"] > 0,
     f"{_stats['zone_admitted_relaxed']} admitted"),
    ("R expectancy added >= 0.39R",
     isinstance(r_expectancy_added, float) and r_expectancy_added >= BASELINE_AVG_RR,
     f"{r_expectancy_added}"),
    ("Portfolio avg_R >= 0.39R",
     isinstance(avg_rr_portfolio, float) and avg_rr_portfolio >= BASELINE_AVG_RR,
     f"{avg_rr_portfolio}"),
    ("MaxDD <= 0.0132 (baseline x1.2)",
     isinstance(max_dd, float) and max_dd <= 0.0132,
     f"{max_dd}"),
    ("Funnel above RETEST unchanged",
     disp_to_exp == 15 and sweep_to_disp == 357,
     f"disp_to_exp={disp_to_exp}, sweep_to_disp={sweep_to_disp}"),
]
for label, passed, val in criteria:
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {label:<42} {val}")
print()

# =============================================================================
# VERDICT
# =============================================================================
print("-- Verdict --")
admitted = _stats["zone_admitted_relaxed"]
trades_up = isinstance(trades, int) and trades > BASELINE_TRADES
r_ok = isinstance(r_expectancy_added, float) and r_expectancy_added >= BASELINE_AVG_RR
dd_ok = isinstance(max_dd, float) and max_dd <= 0.0132

if admitted == 0:
    print(f"  Zone relax at {ZONE_RELAX_PCT:.0%} admitted 0 setups.")
    print("  Zone rejects are above this threshold (structurally unfavourable entries).")
    print("  -> Check P3a zone_pct distribution. If p95 > 67%, zone filter is correct.")
elif trades_up and r_ok and dd_ok:
    print(f"  PASS: {admitted} zone rejects admitted, R expectancy >= baseline, MaxDD safe.")
    print(f"  Zone threshold {ZONE_RELAX_PCT:.0%} is ROI-positive.")
    print("  -> If this was 60%: run at 67% to test sensitivity curve.")
    print("  -> If this was 67%: config-gate zone_discount_pct / zone_premium_pct.")
elif trades_up and not r_ok:
    print(f"  MIXED: {admitted} zone rejects admitted but R expectancy below baseline.")
    print(f"  Zone filter at 50% is a quality governor at this threshold.")
    if ZONE_RELAX_PCT < 0.67:
        print(f"  -> Do NOT run at 67%; quality already degrading at {ZONE_RELAX_PCT:.0%}.")
    else:
        print("  -> REJECT zone relaxation. Keep midpoint filter.")
else:
    print("  PARTIAL: review criteria table. DD or funnel integrity may have failed.")
print()
print(f"[P3c] Events JSONL    : {events_path}")
print(f"[P3c] Total events    : {len(events)}")
print(f"[P3c] ZONE_RELAX_PCT  : {ZONE_RELAX_PCT:.0%}")
print(SEP)
