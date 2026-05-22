# -*- coding: utf-8 -*-
"""
P1 Diagnostic - Persist last_sweep_direction across StateMachine.reset_to_range.

Hypothesis: double_confirmed is structurally always False because reset_to_range()
clears state.sweep_event before detect_sweep() can read it on the next RANGE candle.
If we persist direction across the reset (Class-B memory), double_confirmed should fire
on candles where a sweep in the opposite direction follows a prior sweep.

Patches applied (NO source files modified):
  Patch 1 -- StateMachine.reset_to_range: save sweep direction before clearing Class-A.
  Patch 2 -- CRTEngine.process_candle: inject synthetic prev_sweep stub using the
             persisted direction, restore to None if no real sweep fired.

Usage:
    cd D:\\Tradelatest
    python scripts\\analysis\\p1_sweep_memory_diag.py

Baseline (htf=4, ETHUSDT M15):
    double_confirmed sweeps : 0
    SWEEP -> DISP           : 357
    DISP -> EXPANSION       : 15
    Trades                  : 4
    PnL (net R)             : +1.57R
"""

import sys
import os
import json
import time
import collections
from pathlib import Path

# Force UTF-8 stdout on Windows to avoid cp1252 UnicodeEncodeError
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ── sys.path setup ────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parents[2]
_SRC  = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
os.chdir(_ROOT)

# ── Import CRT classes before patching ───────────────────────────────────────
from config_layer.crt_engine_v2 import (
    StateMachine, CRTEngine, SweepEvent, Direction, CRTState,
)

print("[P1] Applying monkeypatches...")

# =============================================================================
# PATCH 1 -- StateMachine.reset_to_range
# Before Class-A memory wipe, persist sweep direction into state._last_sweep_dir
# =============================================================================
_orig_reset = StateMachine.reset_to_range

def _reset_with_memory(self, state, reason, candle=None, ev_logger=None):
    # Persist direction into Class-B memory before clearing Class-A
    if getattr(state, "sweep_event", None) is not None:
        state._last_sweep_dir = state.sweep_event.direction   # survives reset
    _orig_reset(self, state, reason, candle, ev_logger)

StateMachine.reset_to_range = _reset_with_memory
print("[P1] Patch 1 active: StateMachine.reset_to_range -> persists _last_sweep_dir")

# =============================================================================
# PATCH 2 -- CRTEngine.process_candle
# Inject synthetic stub into state.sweep_event so detect_sweep sees a non-None
# prev_sweep and can compute double_confirmed correctly.
# =============================================================================
_orig_process = CRTEngine.process_candle

def _process_with_memory(self, candle, htf_candle_id):
    # Only inject when: RANGE state, no current sweep_event, persistent dir exists
    last_dir = getattr(self.state, "_last_sweep_dir", None)
    if (
        self.state.current_state == CRTState.RANGE
        and self.state.sweep_event is None
        and last_dir is not None
    ):
        # Synthetic stub -- only `direction` matters for double_confirmed check:
        #   double_confirmed = prev_sweep is not None and prev_sweep.direction != direction
        stub = SweepEvent(
            direction=last_dir,
            price=0.0,
            candle=candle,
            candle_index=self.state.current_candle_index,
        )
        self.state.sweep_event = stub           # visible to detect_sweep via self.state
        result = _orig_process(self, candle, htf_candle_id)
        # Restore: if no real sweep fired, detect_sweep returned None and the stub
        # was never replaced by try_range_to_sweep -- clear it so it does not bleed.
        if self.state.sweep_event is stub:
            self.state.sweep_event = None
        return result
    return _orig_process(self, candle, htf_candle_id)

CRTEngine.process_candle = _process_with_memory
print("[P1] Patch 2 active: CRTEngine.process_candle -> injects sweep direction stub")

# ── Now import and run BacktestRunner (picks up patched classes) ──────────────
from runtime.backtest_v2 import (
    BacktestRunner, BacktestConfig, CandleLoader,
    load_prod_config_from_registry, PROD_VERSION, MultiInstrumentRunner,
)

CSV_PATH   = str(_ROOT / "data" / "ETHUSDT_M15.csv")
INSTRUMENT = "ETHUSDT"
OUTPUT_DIR = str(_ROOT / "results")

print(f"\n[P1] Running backtest: {CSV_PATH}")
print(f"     instrument : {INSTRUMENT}")
print(f"     output_dir : {OUTPUT_DIR}")
print(f"     prod_ver   : {PROD_VERSION}\n")

# Build config exactly as backtest_v2.py main() does
crt_cfg = load_prod_config_from_registry(PROD_VERSION, INSTRUMENT)
cfg = BacktestConfig.from_prod_config(crt_config=crt_cfg)
cfg.instrument = INSTRUMENT
cfg.pip_size = MultiInstrumentRunner.INSTRUMENT_PIP.get(INSTRUMENT, 0.0001)

loader = CandleLoader(CSV_PATH, INSTRUMENT)
runner = BacktestRunner(cfg, csv_path=CSV_PATH, overrides={"diagnostic": "P1_sweep_memory"})

_t0 = time.time()
metrics = runner.run(loader.stream(), loader.count(), OUTPUT_DIR)
_elapsed = time.time() - _t0
print(f"\n[P1] Backtest complete in {_elapsed:.1f}s")

# ── Find the events JSONL just written ────────────────────────────────────────
results_root = Path(OUTPUT_DIR)
candidates = sorted(
    results_root.glob(f"run_*_{INSTRUMENT}/{INSTRUMENT}_events.jsonl"),
    key=lambda p: p.stat().st_mtime,
    reverse=True,
)
if not candidates:
    print("[P1] ERROR: could not find events JSONL -- aborting analysis")
    sys.exit(1)

events_path = candidates[0]
print(f"[P1] Parsing: {events_path}\n")

with open(events_path, encoding="utf-8") as f:
    events = [json.loads(line) for line in f if line.strip()]

# ── Count double_confirmed sweeps ─────────────────────────────────────────────
double_events = [
    e for e in events
    if e.get("event") == "SWEEP" and e.get("metadata", {}).get("double_confirmed")
]
all_sweeps = [e for e in events if e.get("event") == "SWEEP"]

# ── Funnel counts ─────────────────────────────────────────────────────────────
transitions = [
    (e["state_from"], e["state_to"])
    for e in events if e.get("event") == "STATE_TRANSITION"
    and "state_from" in e and "state_to" in e
]
trans_counts = collections.Counter(transitions)

range_to_sweep = trans_counts.get(("RANGE",       "SWEEP"),        0)
sweep_to_disp  = trans_counts.get(("SWEEP",       "DISPLACEMENT"), 0)
disp_to_exp    = trans_counts.get(("DISPLACEMENT","EXPANSION"),     0)
exp_to_retest  = trans_counts.get(("EXPANSION",   "RETEST"),       0)
retest_to_exec = trans_counts.get(("RETEST",      "EXECUTION"),    0)
exec_to_res    = trans_counts.get(("EXECUTION",   "RESOLUTION"),   0)

trades   = metrics.approved_trades     if metrics else "?"
pnl_net  = round(metrics.total_pnl_rr_net, 4) if metrics else "?"
win_rate = round(metrics.win_rate, 4)          if metrics else "?"
max_dd   = round(getattr(metrics, "max_drawdown_pct", 0.0) or 0.0, 4) if metrics else "?"

# ── Report ────────────────────────────────────────────────────────────────────
SEP = "-" * 64

print(SEP)
print("P1 DIAGNOSTIC RESULTS - persist last_sweep_dir across reset")
print(SEP)
print()

print("-- Sweep memory --")
print(f"  Total sweeps detected    : {len(all_sweeps)}")
print(f"  double_confirmed = True  : {len(double_events)}   <- KEY METRIC")
if len(all_sweeps) > 0:
    pct = len(double_events) / len(all_sweeps) * 100
    print(f"  double rate              : {pct:.1f}%")
print()

print("-- Funnel (P1) vs Baseline (htf=4) --")
print(f"  {'Transition':<30} {'P1':>8}  {'Baseline':>8}")
print(f"  {'RANGE -> SWEEP':<30} {range_to_sweep:>8}  {'1,726':>8}")
print(f"  {'SWEEP -> DISPLACEMENT':<30} {sweep_to_disp:>8}  {'357':>8}")
print(f"  {'DISPLACEMENT -> EXPANSION':<30} {disp_to_exp:>8}  {'15':>8}")
print(f"  {'EXPANSION -> RETEST':<30} {exp_to_retest:>8}  {'14':>8}")
print(f"  {'RETEST -> EXECUTION':<30} {retest_to_exec:>8}  {'4':>8}")
print(f"  {'EXECUTION -> RESOLUTION':<30} {exec_to_res:>8}  {'4':>8}")
print()

print("-- Trade metrics (P1) vs Baseline --")
print(f"  Trades          : {str(trades):>6}   (baseline: 4)")
print(f"  PnL net R       : {str(pnl_net):>6}   (baseline: +1.57R)")
print(f"  Win rate        : {str(win_rate):>6}   (baseline: ~0.75)")
print(f"  Max DD          : {str(max_dd):>6}   (baseline: unknown)")
print()

if double_events:
    print("-- double_confirmed sweeps (sample, first 5) --")
    for ev in double_events[:5]:
        ts   = ev.get("timestamp", "?")[:19]
        dir_ = ev.get("direction", "?")
        px   = ev.get("price", 0)
        print(f"  {ts}  dir={dir_:<5}  price={px:.4f}")
    if len(double_events) > 5:
        print(f"  ... and {len(double_events) - 5} more")
    print()

print("-- Verdict --")
if len(double_events) == 0:
    print("  double_confirmed = 0")
    print("  Structural impossibility is deeper than reset lifecycle. Re-examine detect_sweep call-site.")
elif isinstance(trades, int) and trades > 4 and isinstance(pnl_net, float) and pnl_net >= 1.57:
    print("  PASS: double_confirmed fires, trades UP, PnL >= baseline.")
    print("  Memory fix is ROI-positive => proceed to P2 (permanent Class-B memory).")
elif isinstance(trades, int) and trades > 4 and isinstance(pnl_net, float) and pnl_net < 1.57:
    print("  MIXED: double_confirmed fires, trades UP, but PnL degraded.")
    print("  Signal adds noise. Do NOT implement without further investigation.")
elif isinstance(trades, int) and trades == 4:
    print("  INFORMATIONAL: double_confirmed fires but trade count unchanged.")
    print("  Bonus fires but not gating. Evaluate marginal risk impact only.")
else:
    print("  INCONCLUSIVE -- review funnel changes above.")

print()
print(f"[P1] Events JSONL : {events_path}")
print(f"[P1] Total events : {len(events)}")
print(SEP)
