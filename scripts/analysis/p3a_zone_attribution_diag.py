# -*- coding: utf-8 -*-
"""
P3a Diagnostic - Zone / Session attribution: enhanced FILTER_REJECTED logging.

Goal:
  Compute zone_pct = (entry_price - l_ref) / (h_ref - l_ref) for every
  zone-position reject (Not in discount zone / Not in premium zone) and
  range_size_pct = (h_ref - l_ref) / entry_price for range-width context.
  Current events JSONL carries no range geometry in FILTER_REJECTED events,
  so this diagnostic adds it via two monkeypatches — no filter logic changed.

Why this run first:
  - zone_pct distribution tells us whether zone rejects cluster near 50%
    (conservative threshold, easy to relax) or at 70%+ (structurally bad
    entries; threshold change would be dangerous).
  - P3b (session relax) and P3c (zone relax) should only run after this
    data is in hand.

Patches (observation only — NO execution or filter changes):
  Patch 1: process_candle wrapper — captures range context into _zone_ctx
            dict just before the original fires the zone/session check.
  Patch 2: EventLogger.record wrapper — injects _zone_ctx into metadata
            of FILTER_REJECTED events whose reason contains "zone".

Both patches are read-only with respect to trade decisions.

Baseline (htf=4, ETHUSDT M15):
  FILTER_REJECTED (zone)    : 6  (3 discount + 3 premium)
  FILTER_REJECTED (session) : 4  (3 OFF_SESSION + 1 ASIA)
  Trades                    : 4
  PnL net R                 : +1.57R

Usage:
    cd D:\\Tradelatest
    python scripts\\analysis\\p3a_zone_attribution_diag.py --instrument BTCUSDT
    python scripts\\analysis\\p3a_zone_attribution_diag.py --instrument ETHUSDT
    python scripts\\analysis\\p3a_zone_attribution_diag.py --instrument SOLUSDT --csv data/SOLUSDT_M15.csv
"""

import sys
import os
import json
import time
import copy
import argparse
import collections
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_ROOT = Path(__file__).resolve().parents[2]
_SRC  = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
os.chdir(_ROOT)

# Import before patching
from config_layer.crt_engine_v2 import CRTEngine, EventLogger, Direction

print("[P3a] Applying monkeypatches: zone context capture (observation only)...")

# =============================================================================
# SHARED STATE — zone context buffer (not thread-safe; single-threaded backtest)
# =============================================================================
_zone_ctx: dict = {}

# =============================================================================
# PATCH 1 — CRTEngine.process_candle
# Capture (h_ref, l_ref, entry_price, zone_pct, range_size_pct, direction)
# from state BEFORE the original fires the zone check.
# Active only when a retest_candle and active_range are both present.
# =============================================================================
_orig_process = CRTEngine.process_candle

def _process_zone_logging(self, candle, htf_candle_id):
    rng = self.state.active_range
    ret = getattr(self.state, "retest_candle", None)
    if rng is not None and ret is not None:
        span   = rng.h_ref - rng.l_ref
        entry  = ret.close
        _zone_ctx.clear()
        _zone_ctx.update({
            "h_ref":          round(rng.h_ref, 6),
            "l_ref":          round(rng.l_ref, 6),
            "entry_price":    round(entry, 6),
            "zone_pct":       round((entry - rng.l_ref) / span, 4) if span > 0 else 0.5,
            "range_size_pct": round(span / max(entry, 1e-9), 4),
            "direction":      self.state.direction.value if self.state.direction else None,
        })
    else:
        _zone_ctx.clear()
    return _orig_process(self, candle, htf_candle_id)

CRTEngine.process_candle = _process_zone_logging
print("[P3a] Patch 1: process_candle -> captures zone context into _zone_ctx")

# =============================================================================
# PATCH 2 — EventLogger.record
# Inject _zone_ctx into metadata of FILTER_REJECTED events that mention "zone".
# Session FILTER_REJECTED events are already tagged with session_name; untouched.
# =============================================================================
_orig_record = EventLogger.record

def _record_zone_meta(self, event_type, candle, **kwargs):
    if event_type == "FILTER_REJECTED" and "zone" in kwargs.get("reason", "").lower():
        meta = dict(kwargs.get("metadata") or {})
        meta.update(copy.copy(_zone_ctx))   # shallow copy: all values are scalars
        kwargs["metadata"] = meta
    return _orig_record(self, event_type, candle, **kwargs)

EventLogger.record = _record_zone_meta
print("[P3a] Patch 2: EventLogger.record -> injects zone geometry into FILTER_REJECTED")
print("[P3a] No filter logic changed. Observation only.")

# =============================================================================
# RUN BACKTEST
# =============================================================================
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

_ap = argparse.ArgumentParser(description="P3a zone/session attribution diagnostic")
_ap.add_argument("--instrument", required=True,
                 help="Symbol to run, e.g. BTCUSDT, SOLUSDT, ETHUSDT")
_ap.add_argument("--csv",        default=None,
                 help="Explicit path to data file (CSV). Auto-resolved if omitted.")
_ap.add_argument("--output-dir", default=str(_ROOT / "results"),
                 help="Directory for backtest run output (default: results)")
args = _ap.parse_args()

INSTRUMENT = args.instrument
CSV_PATH   = _resolve_data_file(args.instrument, args.csv)
OUTPUT_DIR = args.output_dir

print(f"\n[P3a] Running backtest: {CSV_PATH}")
print(f"      instrument : {INSTRUMENT}")
print(f"      prod_ver   : {PROD_VERSION}\n")

crt_cfg = load_prod_config_from_registry(PROD_VERSION, INSTRUMENT)
cfg = BacktestConfig.from_prod_config(crt_config=crt_cfg)
cfg.instrument = INSTRUMENT
cfg.pip_size   = MultiInstrumentRunner.INSTRUMENT_PIP.get(INSTRUMENT, 0.0001)

loader = CandleLoader(CSV_PATH, INSTRUMENT)
runner = BacktestRunner(cfg, csv_path=CSV_PATH, overrides={"diagnostic": "P3a_zone_attribution"})

_t0 = time.time()
metrics = runner.run(loader.stream(), loader.count(), OUTPUT_DIR)
_elapsed = time.time() - _t0
print(f"\n[P3a] Backtest complete in {_elapsed:.1f}s")

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
    print("[P3a] ERROR: events JSONL not found")
    sys.exit(1)

events_path = candidates[0]
print(f"[P3a] Parsing: {events_path}\n")

with open(events_path, encoding="utf-8") as f:
    events = [json.loads(line) for line in f if line.strip()]

# =============================================================================
# PARSE FILTER_REJECTED
# =============================================================================
all_rejects   = [e for e in events if e.get("event") == "FILTER_REJECTED"]
zone_rejects  = [e for e in all_rejects if "zone" in e.get("reason", "").lower()]
sess_rejects  = [e for e in all_rejects if "off_session" in e.get("reason", "").lower()]

# Funnel for reference
trans_counts = collections.Counter(
    (e.get("state_from"), e.get("state_to"))
    for e in events if e.get("event") == "STATE_TRANSITION"
    and "state_from" in e and "state_to" in e
)
retest_to_exec = trans_counts.get(("RETEST", "EXECUTION"), 0)

# Trade metrics
trades   = metrics.approved_trades     if metrics else "?"
pnl_net  = round(metrics.total_pnl_rr_net, 4) if metrics else "?"
avg_rr   = round(metrics.total_pnl_rr_net / max(metrics.approved_trades, 1), 4) if metrics else "?"

# =============================================================================
# ZONE POSITION ANALYSIS
# =============================================================================
zone_pcts = []
for r in zone_rejects:
    m = r.get("metadata", {}) or {}
    if "zone_pct" in m:
        zone_pcts.append({
            "ts":             r.get("timestamp", "?")[:19],
            "reason":         r.get("reason", "?"),
            "direction":      m.get("direction", "?"),
            "zone_pct":       m.get("zone_pct", 0),
            "range_size_pct": m.get("range_size_pct", 0),
            "entry_price":    m.get("entry_price", 0),
            "h_ref":          m.get("h_ref", 0),
            "l_ref":          m.get("l_ref", 0),
        })

# Bucket zone_pct into sensitivity bands
def _bucket(pct, direction):
    """Which relaxation threshold would admit this setup?"""
    if direction == "LONG":
        pos = pct          # LONG: zone_pct = (entry - l_ref) / span; lower = deeper discount
        if pos <= 0.50: return "passes_baseline (<=50%)"
        if pos <= 0.55: return "passes_at_55%"
        if pos <= 0.60: return "passes_at_60%"
        if pos <= 0.67: return "passes_at_67%"
        return "blocked_above_67%"
    else:
        # SHORT: entry must be ABOVE mid; zone_pct = (entry - l_ref) / span
        # SHORT rejection means entry < mid, i.e., zone_pct < 0.50
        pos = 1.0 - pct    # distance from top; higher = deeper premium
        if pos <= 0.50: return "passes_baseline (>=50%)"
        if pos <= 0.55: return "passes_at_55%"
        if pos <= 0.60: return "passes_at_60%"
        if pos <= 0.67: return "passes_at_67%"
        return "blocked_above_67%"

bucket_counts = collections.Counter()
for z in zone_pcts:
    b = _bucket(z["zone_pct"], z["direction"])
    bucket_counts[b] += 1

# Session breakdown
sess_by_name = collections.Counter(
    e.get("metadata", {}).get("session_name", "UNKNOWN")
    for e in sess_rejects
)
sess_by_hour = collections.Counter(
    e.get("timestamp", "?")[11:13]   # HH from "YYYY-MM-DDTHH:MM:SS"
    for e in sess_rejects
)

# =============================================================================
# REPORT
# =============================================================================
SEP = "-" * 68

print(SEP)
print("P3a DIAGNOSTIC RESULTS - Zone / Session Attribution")
print(SEP)
print()

print("-- FILTER_REJECTED totals --")
print(f"  Total FILTER_REJECTED  : {len(all_rejects)}  (baseline: 10)")
print(f"  Zone-position rejects  : {len(zone_rejects)}  (baseline: 6)")
print(f"  Off-session rejects    : {len(sess_rejects)}  (baseline: 4)")
print()

print("-- Funnel reference --")
print(f"  RETEST -> EXECUTION    : {retest_to_exec}  (baseline: 4)")
print(f"  Trades                 : {trades}  (baseline: 4)")
print(f"  PnL net R              : {pnl_net}  (baseline: +1.57R)")
print()

print("-- Zone position breakdown --")
print(f"  {'Timestamp':<20} {'Reason':<28} {'Dir':<6} {'zone_pct':>8} {'range_size_pct':>14}")
for z in zone_pcts:
    print(f"  {z['ts']:<20} {z['reason']:<28} {str(z['direction']):<6} "
          f"{z['zone_pct']:>8.3f} {z['range_size_pct']:>14.4f}")
print()

print("-- Zone sensitivity buckets --")
print("  (Which threshold level would admit each rejected setup?)")
for bucket_label in [
    "passes_baseline (<=50%)",
    "passes_at_55%",
    "passes_at_60%",
    "passes_at_67%",
    "blocked_above_67%",
    "passes_baseline (>=50%)",
]:
    count = bucket_counts.get(bucket_label, 0)
    if count:
        print(f"  {bucket_label:<35} : {count}")
if not any(bucket_counts.values()):
    print("  (no zone_pct data — patch may not have fired; check retest state presence)")
print()

print("-- Session breakdown --")
print(f"  By session name:")
for name, cnt in sess_by_name.most_common():
    print(f"    {name:<15} : {cnt}")
print(f"  By UTC hour:")
for hour in sorted(sess_by_hour.keys()):
    print(f"    {hour}:xx UTC         : {sess_by_hour[hour]}")
print()

# =============================================================================
# VERDICT
# =============================================================================
print("-- Verdict / next step --")
if not zone_pcts:
    print("  ERROR: no zone_pct data captured. Patches may not have fired.")
    print("  Verify that RETEST -> EXECUTION path was reached (check retest_to_exec > 0).")
else:
    near_mid    = sum(1 for z in zone_pcts if abs(z["zone_pct"] - 0.5) <= 0.10)
    above_67    = sum(1 for z in zone_pcts
                      if (z["direction"] == "LONG"  and z["zone_pct"] > 0.67) or
                         (z["direction"] == "SHORT" and z["zone_pct"] < 0.33))
    total_zone  = len(zone_pcts)

    if near_mid == total_zone:
        print("  All zone rejects within 10% of midpoint (0.40-0.60).")
        print("  Zone threshold is conservative. P3c at 55-60% likely captures most.")
        print("  -> Run P3b (session relax) then P3c(60%).")
    elif above_67 > 0:
        print(f"  {above_67}/{total_zone} zone rejects above 67% from range edge.")
        print("  Structurally unfavourable entries. Zone filter may be doing real work.")
        print("  -> Proceed cautiously to P3c; evaluate quality first.")
    else:
        print("  Zone rejects mix of tight (near-mid) and moderate (50-67%) positions.")
        print("  -> Run P3b then P3c(60%) with full quality metrics.")

    # Session verdict
    off_sess_count = sess_by_name.get("OFF_SESSION", 0)
    asia_count     = sess_by_name.get("ASIA", 0)
    if off_sess_count > asia_count:
        print(f"\n  Session: OFF_SESSION dominates ({off_sess_count} vs ASIA {asia_count}).")
        print("  OFF_SESSION setups occur outside defined session windows entirely.")
        print("  -> Check UTC hour distribution above before relaxing all sessions.")
    elif asia_count > 0:
        print(f"\n  Session: ASIA ({asia_count}) present. Lower liquidity / wider spreads expected.")
        print("  -> P3b session relax worthwhile; track quality separately for ASIA trades.")
print()
print(f"[P3a] Events JSONL : {events_path}")
print(f"[P3a] Total events : {len(events)}")
print(SEP)
