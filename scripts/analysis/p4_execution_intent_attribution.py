# -*- coding: utf-8 -*-
"""
P4 Diagnostic — Execution Intent Attribution.

Goal:
  Understand WHY these specific 4 setups executed while 10 were rejected.
  Not "why only 4" (P3 answered that — session/zone filters).
  But "what characterises the 4 that survived all filters."

  Compare executed vs rejected setups across:
    - intent (liq_sweep / pullback / breakout / reversal)
    - zone_pct at approval time
    - session at approval time
    - risk_score (sweep, breakout, retest, time, final)
    - retest_depth (from cached_features)
    - disp_strength (from cached_features)
    - body_ratio (from cached_features)
    - candles_since_retest (from cached_features)
    - soft_conf_candle_at_approval (how many candles into window before score crossed)

No filter changes. No threshold tuning. Observation only.

Context:
  All 14 RETEST setups passed approve_with_soft_conf (BEGIN_SOFT_CONF=14,
  CONFIRMATION_FAILED=0). The 10 rejections are entirely zone (6) and
  session (4) post-approval filters. This diagnostic asks: is there a
  detectable feature signature that correlates with "passed all filters"
  vs "blocked by zone or session"?

  If the executed setups have systematically different feature profiles,
  those profiles inform future quality signals (not threshold adjustments).

Patches:
  Patch 1 — EventLogger.record: when FILTER_REJECTED is recorded, state
             is still intact (reset_to_range fires AFTER the record call).
             Capture full feature snapshot from self._state.
  Patch 2 — ExecutionEngine.build_trade: capture feature snapshot when
             called (same moment as execution intent).

  Both patches are observation-only. No execution logic changed.

Baseline (htf=4, ETHUSDT M15):
  RETEST -> EXECUTION  : 4 / 14
  Zone rejects         : 6  (LONG above mid, SHORT below mid)
  Session rejects      : 4  (3 ASIA, 1 OFF_SESSION)
  Trades               : 4
  PnL net R            : +1.57R

Usage:
    cd D:\\Tradelatest
    python scripts\\analysis\\p4_execution_intent_attribution.py
"""

import sys
import os
import json
import time
import copy
import collections
import statistics
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_ROOT = Path(__file__).resolve().parents[2]
_SRC  = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
os.chdir(_ROOT)

from config_layer.crt_engine_v2 import (
    EventLogger, ExecutionEngine, Direction, CRTState,
)

print("[P4] Applying attribution patches (observation only)...")

# =============================================================================
# SHARED CAPTURE STORES
# =============================================================================
_rejected_setups  = []  # zone/session rejects — captured at ev_log.record call
_executed_setups  = []  # successful build_trade calls

# =============================================================================
# HELPER — state snapshot (called when state is still intact)
# =============================================================================
def _capture_state(state, label: str, candle=None) -> dict:
    feats = state.cached_features or {}
    rng   = state.active_range
    ret   = getattr(state, "retest_candle", None)

    zone_pct = None
    if rng is not None and ret is not None:
        span = rng.h_ref - rng.l_ref
        if span > 0:
            zone_pct = round((ret.close - rng.l_ref) / span, 4)

    # Session from candle timestamp
    session_name = "UNKNOWN"
    if candle is not None:
        ts_time = candle.timestamp.time()
        from datetime import time as _time
        _session_map = {
            "LONDON":  (_time(7,  0), _time(10, 0)),
            "NEWYORK": (_time(13, 0), _time(16, 0)),
            "ASIA":    (_time(0,  0), _time(3,  0)),
        }
        for _name, (_start, _end) in _session_map.items():
            if _start <= ts_time <= _end:
                session_name = _name
                break
        else:
            session_name = "OFF_SESSION"

    # Intent
    _intent = "n/a"
    try:
        _intent = ExecutionEngine._derive_trade_intent(feats)
    except Exception:
        pass

    rs = state.risk_score

    # candles_since_retest: NOT stored in cached_features — computed from engine state.
    # Using None (not 0) when either index is unavailable to avoid silently encoding missing→0.
    _cur_idx = getattr(state, "current_candle_index", None)
    _ret_idx = getattr(state, "retest_candle_index",  None)
    _csr = (max(0, _cur_idx - _ret_idx)
            if (_cur_idx is not None and _ret_idx is not None) else None)

    # double_sweep is stored in cached_features as bool (False in this dataset);
    # explicit int() conversion keeps it numeric for _stat() comparisons.
    _ds = feats.get("double_sweep", None)
    _ds = int(_ds) if _ds is not None else None

    return {
        "label":               label,
        "direction":           state.direction.value if state.direction else "NONE",
        "zone_pct":            zone_pct,
        "session":             session_name,
        "intent":              _intent,
        "risk_score_final":    round(rs.final, 4)          if rs else None,
        "risk_score_sweep":    round(rs.sweep_score, 4)    if rs else None,
        "risk_score_breakout": round(rs.breakout_score, 4) if rs else None,
        "risk_score_retest":   round(rs.retest_score, 4)   if rs else None,
        "risk_score_time":     round(rs.time_score, 4)     if rs else None,
        "risk_score_decay":    round(rs.decay_factor, 4)   if rs else None,
        # Canonical features from cached_features (see crt_engine_v2.py:737-744)
        # Present: retest_depth, body_ratio, disp_strength, double_sweep, session, retest_index
        # Absent:  momentum_score, volume_ratio, volume_spike, sweep_detected, candles_since_retest
        "retest_depth":        float(feats.get("retest_depth",  0.0)) if "retest_depth"  in feats else None,
        "disp_strength":       float(feats.get("disp_strength", 0.0)) if "disp_strength" in feats else None,
        "body_ratio":          float(feats.get("body_ratio",    0.0)) if "body_ratio"    in feats else None,
        "candles_since_retest": _csr,  # derived from engine state, NOT cached_features
        "double_sweep":        _ds,    # stored as bool in cached_features; None if absent
        # Genuinely absent from cached_features (show None so _stat() reports 'n/a' correctly)
        "momentum_score":      None,
        "sweep_detected":      None,
        "volume_ratio":        None,
        "volume_spike":        None,
        "n_feats":             len(feats),
        # Range geometry
        "range_h_ref":         round(rng.h_ref, 6) if rng else None,
        "range_l_ref":         round(rng.l_ref, 6) if rng else None,
        "entry_close":         round(ret.close, 6) if ret else None,
        "timestamp":           str(candle.timestamp) if candle else None,
    }

# =============================================================================
# PATCH 1 — EventLogger.record
# Capture full state snapshot when FILTER_REJECTED fires.
# State is still intact at this point (reset_to_range fires after the record call).
# =============================================================================
_orig_record = EventLogger.record

def _record_with_attribution(self, event_type, candle, **kwargs):
    if event_type == "FILTER_REJECTED":
        reason = kwargs.get("reason", "")
        snap = _capture_state(self._state, reason, candle)
        snap["filter_reason"] = reason
        if "zone" in reason.lower():
            snap["filter_type"] = "zone"
        elif "off_session" in reason.lower():
            snap["filter_type"] = "session"
        else:
            snap["filter_type"] = "other"
        _rejected_setups.append(snap)
    return _orig_record(self, event_type, candle, **kwargs)

EventLogger.record = _record_with_attribution
print("[P4] Patch 1: EventLogger.record -> captures state at FILTER_REJECTED")

# =============================================================================
# PATCH 2 — ExecutionEngine.build_trade
# Capture feature snapshot when build_trade is called (only for the approved path).
# =============================================================================
_orig_build_trade = ExecutionEngine.build_trade

def _build_trade_with_attribution(self, state, risk_engine=None):
    result = _orig_build_trade(self, state, risk_engine)
    if result is not None:
        # Use the candle from retest_candle as the "entry candle" proxy
        # (retest_candle IS the entry candle at this point)
        ret = getattr(state, "retest_candle", None)
        snap = _capture_state(state, "EXECUTED", ret)
        snap["trade_id"]    = result.id
        snap["entry_price"] = round(result.entry_price, 6)
        snap["sl"]          = round(result.sl_price,    6)
        snap["risk_dist"]   = round(abs(result.entry_price - result.sl_price), 6)
        snap["risk_pct"]    = result.risk_pct
        snap["filter_type"] = "executed"
        _executed_setups.append(snap)
    return result

ExecutionEngine.build_trade = _build_trade_with_attribution
print("[P4] Patch 2: ExecutionEngine.build_trade -> captures features at execution")

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

print(f"\n[P4] Running backtest: {CSV_PATH}")
print(f"     instrument : {INSTRUMENT}")
print(f"     prod_ver   : {PROD_VERSION}\n")

crt_cfg = load_prod_config_from_registry(PROD_VERSION, INSTRUMENT)
cfg = BacktestConfig.from_prod_config(crt_config=crt_cfg)
cfg.instrument = INSTRUMENT
cfg.pip_size   = MultiInstrumentRunner.INSTRUMENT_PIP.get(INSTRUMENT, 0.0001)

loader = CandleLoader(CSV_PATH, INSTRUMENT)
runner = BacktestRunner(
    cfg, csv_path=CSV_PATH,
    overrides={"diagnostic": "P4_execution_intent_attribution"},
)

_t0 = time.time()
metrics = runner.run(loader.stream(), loader.count(), OUTPUT_DIR)
_elapsed = time.time() - _t0
print(f"\n[P4] Backtest complete in {_elapsed:.1f}s")

# Trade PnL from metrics
trades  = metrics.approved_trades    if metrics else "?"
pnl_net = round(metrics.total_pnl_rr_net, 4) if metrics else "?"

# =============================================================================
# ANALYSIS HELPERS
# =============================================================================
def _fmt(v, decimals=3):
    if v is None: return "None"
    if isinstance(v, float): return f"{v:.{decimals}f}"
    return str(v)

def _safe(v, decimals=3):
    """Format stat mean — None (missing data) → 'n/a'; 0.0 → '0.000' (valid zero, not n/a)."""
    if v is None: return "n/a"
    return _fmt(v, decimals)

def _stat(lst, key, filter_fn=None):
    vals = [r[key] for r in lst if r.get(key) is not None]
    if filter_fn:
        vals = [v for v in vals if filter_fn(v)]
    if not vals:
        return {"n": 0, "mean": None, "med": None, "min": None, "max": None}
    s = sorted(vals)
    return {
        "n":   len(s),
        "mean": round(statistics.mean(s), 4),
        "med":  round(statistics.median(s), 4),
        "min":  round(min(s), 4),
        "max":  round(max(s), 4),
    }

# =============================================================================
# REPORT
# =============================================================================
SEP = "-" * 72

print()
print(SEP)
print("P4 DIAGNOSTIC RESULTS — Execution Intent Attribution")
print(SEP)
print()

all_setups    = _executed_setups + _rejected_setups
zone_rejects  = [r for r in _rejected_setups if r.get("filter_type") == "zone"]
sess_rejects  = [r for r in _rejected_setups if r.get("filter_type") == "session"]
executed      = _executed_setups

print(f"  Setups captured at RETEST approval      : {len(all_setups)}  (baseline: 14)")
print(f"  -> Executed                             : {len(executed)}  (baseline: 4)")
print(f"  -> Zone rejected                        : {len(zone_rejects)}  (baseline: 6)")
print(f"  -> Session rejected                     : {len(sess_rejects)}  (baseline: 4)")
print(f"  Trade count / PnL                       : {trades} trades / {pnl_net}R")
print()

# =============================================================================
# SECTION 1: INTENT DISTRIBUTION
# =============================================================================
print("-- Intent Distribution --")
print(f"  {'Intent':<15} {'Executed':>9} {'Zone-rej':>9} {'Sess-rej':>9}")
all_intents = sorted(set(r.get("intent","?") for r in all_setups))
for intent in all_intents:
    e_cnt = sum(1 for r in executed    if r.get("intent") == intent)
    z_cnt = sum(1 for r in zone_rejects if r.get("intent") == intent)
    s_cnt = sum(1 for r in sess_rejects if r.get("intent") == intent)
    print(f"  {intent:<15} {e_cnt:>9} {z_cnt:>9} {s_cnt:>9}")
print()

# Intent Lift = executed_count(intent) / candidate_count(intent)
# Lift > 1.0 means intent is over-represented in executed setups.
# Lift < 1.0 means intent is filtered away at higher rate.
print("-- Intent Lift  [lift = executed / candidates] --")
print(f"  {'Intent':<15} {'Candidates':>11} {'Executed':>9} {'Lift':>8}  note")
for intent in all_intents:
    candidates = sum(1 for r in all_setups if r.get("intent") == intent)
    exec_cnt   = sum(1 for r in executed   if r.get("intent") == intent)
    lift       = exec_cnt / candidates if candidates > 0 else 0.0
    note = ""
    if lift >= 0.75:
        note = "<- high survival"
    elif lift == 0.0 and candidates > 0:
        note = "<- fully filtered"
    elif lift < 0.25:
        note = "<- low survival"
    print(f"  {intent:<15} {candidates:>11} {exec_cnt:>9} {lift:>8.2f}  {note}")
print()

# =============================================================================
# SECTION 2: ZONE POSITION
# =============================================================================
print("-- Zone Position at Approval (zone_pct = (entry-l_ref)/(h_ref-l_ref)) --")
print(f"  Executed   : {[_fmt(r['zone_pct']) for r in executed]}")
print(f"  Zone-rej   : {[_fmt(r['zone_pct']) for r in zone_rejects]}")
print(f"  Sess-rej   : {[_fmt(r['zone_pct']) for r in sess_rejects]}")
print()
print(f"  {'Group':<14} {'mean':>8} {'median':>8} {'min':>8} {'max':>8}")
for label, group in [("Executed", executed), ("Zone-rej", zone_rejects), ("Sess-rej", sess_rejects)]:
    s = _stat(group, "zone_pct")
    if s["n"]:
        print(f"  {label:<14} {_fmt(s['mean']):>8} {_fmt(s['med']):>8} {_fmt(s['min']):>8} {_fmt(s['max']):>8}")
    else:
        print(f"  {label:<14}  (no data)")
print()

# =============================================================================
# SECTION 3: SESSION DISTRIBUTION
# =============================================================================
print("-- Session Distribution --")
print(f"  {'Session':<14} {'Executed':>9} {'Zone-rej':>9} {'Sess-rej':>9}")
all_sessions = sorted(set(r.get("session","?") for r in all_setups))
for sess in all_sessions:
    e = sum(1 for r in executed    if r.get("session") == sess)
    z = sum(1 for r in zone_rejects if r.get("session") == sess)
    s = sum(1 for r in sess_rejects if r.get("session") == sess)
    print(f"  {sess:<14} {e:>9} {z:>9} {s:>9}")
print()

# =============================================================================
# SECTION 4: RISK SCORE COMPARISON
# =============================================================================
print("-- Risk Score at Approval (soft-confirmation fusion score S) --")
print(f"  {'Component':<22} {'Exec mean':>10} {'Zone mean':>10} {'Sess mean':>10}")
for field in ["risk_score_final", "risk_score_sweep", "risk_score_breakout",
              "risk_score_retest", "risk_score_time", "risk_score_decay"]:
    label = field.replace("risk_score_", "")
    e_s = _stat(executed,     field)
    z_s = _stat(zone_rejects, field)
    s_s = _stat(sess_rejects, field)
    print(f"  {label:<22} {_safe(e_s['mean']):>10} {_safe(z_s['mean']):>10} {_safe(s_s['mean']):>10}")
print()

# =============================================================================
# SECTION 5: FEATURE COMPARISON
# =============================================================================
# Notes on feature availability in state.cached_features (crt_engine_v2.py:737-744):
#   PRESENT:  retest_depth, body_ratio, disp_strength, double_sweep, session, retest_index
#   ABSENT:   momentum_score, volume_ratio, volume_spike, sweep_detected
#   DERIVED:  candles_since_retest (from engine state, not cached_features)
print("-- Canonical Feature Comparison --")
print(f"  {'Feature':<24} {'Exec mean':>10} {'Zone mean':>10} {'Sess mean':>10}  source")
_feat_source = {
    "retest_depth":         "cached",
    "disp_strength":        "cached",
    "body_ratio":           "cached",
    "candles_since_retest": "state",
    "double_sweep":         "cached",
    "momentum_score":       "absent",
    "volume_ratio":         "absent",
    "volume_spike":         "absent",
    "sweep_detected":       "absent",
}
features_to_compare = list(_feat_source.keys())
for feat in features_to_compare:
    e_s = _stat(executed,     feat)
    z_s = _stat(zone_rejects, feat)
    s_s = _stat(sess_rejects, feat)
    src = _feat_source.get(feat, "?")
    print(f"  {feat:<24} {_safe(e_s['mean']):>10} {_safe(z_s['mean']):>10} {_safe(s_s['mean']):>10}  [{src}]")
print()

# =============================================================================
# SECTION 6: PER-SETUP TABLE (all 14)
# =============================================================================
print("-- All Approved Setups (all 14 RETEST entries) --")
header = f"  {'Timestamp':<21} {'Dir':<6} {'Filter':<10} {'Intent':<12} {'Zone_pct':>8} {'Session':<14} {'RS_final':>8} {'Ret_dep':>7}"
print(header)
for r in sorted(all_setups, key=lambda x: x.get("timestamp") or ""):
    ts    = str(r.get("timestamp","?"))[:19]
    ftype = r.get("filter_type", "?")
    print(f"  {ts:<21} {r.get('direction','?'):<6} {ftype:<10} "
          f"{r.get('intent','?'):<12} {_fmt(r.get('zone_pct')):>8} "
          f"{r.get('session','?'):<14} {_fmt(r.get('risk_score_final')):>8} "
          f"{_fmt(r.get('retest_depth')):>7}")
print()

# =============================================================================
# SECTION 7: EXECUTED SETUP DETAIL
# =============================================================================
if executed:
    print("-- Executed Setups (full detail) --")
    for i, r in enumerate(executed, 1):
        print(f"  [{i}] {r.get('timestamp','?')[:19]}")
        print(f"      trade_id : {r.get('trade_id','?')}")
        print(f"      dir      : {r.get('direction','?')}")
        print(f"      intent   : {r.get('intent','?')}")
        print(f"      session  : {r.get('session','?')}")
        print(f"      zone_pct : {_fmt(r.get('zone_pct'))}")
        print(f"      RS final : {_fmt(r.get('risk_score_final'))}")
        print(f"      RS comp  : sweep={_fmt(r.get('risk_score_sweep'))} "
              f"brkout={_fmt(r.get('risk_score_breakout'))} "
              f"retest={_fmt(r.get('risk_score_retest'))} "
              f"time={_fmt(r.get('risk_score_time'))}")
        print(f"      retest_d : {_fmt(r.get('retest_depth'))}")
        print(f"      disp_str : {_fmt(r.get('disp_strength'))}")
        print(f"      body_rt  : {_fmt(r.get('body_ratio'))}")
        print(f"      csr      : {r.get('candles_since_retest','?')}")
        print(f"      vol_rat  : {_fmt(r.get('volume_ratio'))}")
        print(f"      risk_pct : {r.get('risk_pct','?')}")
        print()

# =============================================================================
# VERDICT
# =============================================================================
print("-- Verdict --")
if len(all_setups) != 14:
    print(f"  WARNING: Expected 14 approved setups, captured {len(all_setups)}.")
    print("  Patch may have missed some setups. Check BEGIN_SOFT_CONF count in JSONL.")
else:
    # Check for distinguishing patterns
    exec_sessions = set(r.get("session","?") for r in executed)
    rej_sessions  = set(r.get("session","?") for r in _rejected_setups)
    exec_intents  = collections.Counter(r.get("intent","?") for r in executed)
    rej_intents   = collections.Counter(r.get("intent","?") for r in _rejected_setups)

    # Zone position separation
    exec_zone_pcts = [r["zone_pct"] for r in executed if r.get("zone_pct") is not None]
    rej_zone_pcts  = [r["zone_pct"] for r in _rejected_setups if r.get("zone_pct") is not None]
    if exec_zone_pcts and rej_zone_pcts:
        zone_sep = abs(statistics.mean(exec_zone_pcts) - statistics.mean(rej_zone_pcts))
        print(f"  Zone position separation (|exec_mean - rej_mean|): {zone_sep:.3f}")
        if zone_sep > 0.10:
            print("  -> Executed setups are significantly more centered in the zone.")
        elif zone_sep > 0.05:
            print("  -> Modest zone position difference. Zone is a partial predictor.")
        else:
            print("  -> Minimal zone position difference. Zone is not the distinguishing factor.")

    # Session overlap
    exec_only_sessions  = exec_sessions - rej_sessions
    if exec_only_sessions:
        print(f"  Sessions exclusive to executed setups: {exec_only_sessions}")
    else:
        print(f"  Session overlap: executed sessions = {exec_sessions}")

    # Risk score comparison
    exec_rs  = [r["risk_score_final"] for r in executed if r.get("risk_score_final") is not None]
    rej_rs   = [r["risk_score_final"] for r in _rejected_setups if r.get("risk_score_final") is not None]
    if exec_rs and rej_rs:
        rs_diff = statistics.mean(exec_rs) - statistics.mean(rej_rs)
        print(f"  Risk score difference (exec - rej): {rs_diff:+.4f}")
        if abs(rs_diff) < 0.02:
            print("  -> Score indistinguishable. Execution filters are geometric, not score-based.")
        else:
            print(f"  -> {'Executed' if rs_diff > 0 else 'Rejected'} setups had higher risk scores.")

print()
print(f"[P4] Captured : {len(executed)} executed + {len(_rejected_setups)} rejected = {len(all_setups)} total")
print(SEP)
