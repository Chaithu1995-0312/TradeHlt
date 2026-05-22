# -*- coding: utf-8 -*-
"""
P2 Diagnostic - DISPLACEMENT state exemption from HTF resets.

Hypothesis:
  259 of 342 DISPLACEMENT kills (75.7%) are caused by HTF range reseeding,
  which fires BEFORE try_displacement_to_expansion in process_candle.
  EXPANSION and RETEST are already exempt from HTF resets (should_reset line 1386).
  DISPLACEMENT is not. Extending the exemption gives each DISPLACEMENT episode
  1-4 more candles to produce an expansion candle.

Patch:
  One monkeypatch on ResetLogic.should_reset — adds CRTState.DISPLACEMENT to
  the HTF-exempt states. Retrace (73 episodes) and extension (9 episodes) resets
  remain fully active.

Baseline (htf=4, ETHUSDT M15):
  DISP -> EXP  :  15 / 357  (4.2%)
  DISP median  :  1 candle
  HTF kills    :  259 / 342 (75.7%)
  Retrace kills:  73 / 342  (21.3%)
  Trades       :  4
  PnL net R    :  +1.57R

Metrics collected post-run:
  - DISP median/p95 episode duration
  - HTF kill share after exemption (target: < 25%)
  - DISP -> EXP conversion rate (target: > 4.2%)
  - Retrace kill share (target: <= 50%)
  - ATR drift during surviving DISP episodes (target: < 20% median)
  - HTF distance at EXPANSION (target: <= 1 HTF boundary crossed)
  - DISP age at EXPANSION p95 (target: <= 4 candles)
  - avg_R, MaxDD

Usage:
    cd D:\\Tradelatest
    python scripts\\analysis\\p2_disp_exemption_diag.py
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

# Import before patching
from config_layer.crt_engine_v2 import ResetLogic, CRTState

print("[P2] Applying monkeypatch: DISPLACEMENT exemption from HTF resets...")

# =============================================================================
# PATCH -- ResetLogic.should_reset
# Extend HTF exempt states from [EXPANSION, RETEST] to
# [DISPLACEMENT, EXPANSION, RETEST].
# Retrace and extension logic falls through to original (unchanged).
# =============================================================================
_orig_should_reset = ResetLogic.should_reset

def _should_reset_with_disp_exemption(self, state, current_candle, current_htf_id):
    if state.active_range is None:
        return False, ""
    # Protect active trades (unchanged from original)
    if state.active_trade and state.active_trade.status in ("OPEN", "TP1"):
        return False, ""
    # HTF exemption: extended to include DISPLACEMENT
    if current_htf_id != state.active_range.htf_candle_id:
        if state.current_state in (CRTState.DISPLACEMENT, CRTState.EXPANSION, CRTState.RETEST):
            return False, ""   # <- only change vs original: DISPLACEMENT added
        return True, f"HTF changed: {state.active_range.htf_candle_id} -> {current_htf_id}"
    # Retrace and extension: pass through to original (retrace/extension guards unchanged)
    return _orig_should_reset(self, state, current_candle, current_htf_id)

ResetLogic.should_reset = _should_reset_with_disp_exemption
print("[P2] Patch active: DISPLACEMENT now exempt from HTF resets")
print("[P2] Retrace (50%) and extension (1.618x) guards remain active")

# Import and run backtest
from runtime.backtest_v2 import (
    BacktestRunner, BacktestConfig, CandleLoader,
    load_prod_config_from_registry, PROD_VERSION, MultiInstrumentRunner,
)

CSV_PATH   = str(_ROOT / "data" / "ETHUSDT_M15.csv")
INSTRUMENT = "ETHUSDT"
OUTPUT_DIR = str(_ROOT / "results")

print(f"\n[P2] Running backtest: {CSV_PATH}")
print(f"     instrument : {INSTRUMENT}")
print(f"     prod_ver   : {PROD_VERSION}\n")

crt_cfg = load_prod_config_from_registry(PROD_VERSION, INSTRUMENT)
cfg = BacktestConfig.from_prod_config(crt_config=crt_cfg)
cfg.instrument = INSTRUMENT
cfg.pip_size = MultiInstrumentRunner.INSTRUMENT_PIP.get(INSTRUMENT, 0.0001)

loader = CandleLoader(CSV_PATH, INSTRUMENT)
runner = BacktestRunner(cfg, csv_path=CSV_PATH, overrides={"diagnostic": "P2_disp_exemption"})

_t0 = time.time()
metrics = runner.run(loader.stream(), loader.count(), OUTPUT_DIR)
_elapsed = time.time() - _t0
print(f"\n[P2] Backtest complete in {_elapsed:.1f}s")

# Find events JSONL
results_root = Path(OUTPUT_DIR)
candidates = sorted(
    results_root.glob(f"run_*_{INSTRUMENT}/{INSTRUMENT}_events.jsonl"),
    key=lambda p: p.stat().st_mtime,
    reverse=True,
)
if not candidates:
    print("[P2] ERROR: events JSONL not found")
    sys.exit(1)

events_path = candidates[0]
print(f"[P2] Parsing: {events_path}\n")

with open(events_path, encoding="utf-8") as f:
    events = [json.loads(line) for line in f if line.strip()]

# ============================================================
# EPISODE RECONSTRUCTION
# ============================================================
events_sorted = sorted(events, key=lambda e: (e.get("candle_index", 0), e.get("timestamp", "")))

episodes = []
in_disp = False
disp_start_idx = None
disp_start_ts  = None

for e in events_sorted:
    ev  = e.get("event", "")
    idx = e.get("candle_index", 0)
    ts  = e.get("timestamp", "")

    if ev == "STATE_TRANSITION" and e.get("state_from") == "SWEEP" and e.get("state_to") == "DISPLACEMENT":
        in_disp = True
        disp_start_idx = idx
        disp_start_ts  = ts

    elif in_disp and ev == "STATE_TRANSITION" and e.get("state_from") == "DISPLACEMENT" and e.get("state_to") == "EXPANSION":
        dur = idx - disp_start_idx
        episodes.append({
            "start": disp_start_idx, "end": idx, "duration": dur,
            "outcome": "EXPANSION", "reason": e.get("reason", ""),
            "start_ts": disp_start_ts, "end_ts": ts,
        })
        in_disp = False

    elif in_disp and ev == "RESET" and e.get("state_from") == "DISPLACEMENT":
        reason = e.get("reason", "")
        if "HTF" in reason:
            outcome = "HTF_RESET"
        elif "retrace" in reason.lower() or "50%" in reason:
            outcome = "RETRACE"
        elif "1.618" in reason:
            outcome = "EXTENSION"
        else:
            outcome = "OTHER"
        dur = idx - disp_start_idx
        episodes.append({
            "start": disp_start_idx, "end": idx, "duration": dur,
            "outcome": outcome, "reason": reason,
            "start_ts": disp_start_ts, "end_ts": ts,
        })
        in_disp = False

# ============================================================
# FUNNEL
# ============================================================
trans_counts = collections.Counter(
    (e["state_from"], e["state_to"])
    for e in events if e.get("event") == "STATE_TRANSITION"
    and "state_from" in e and "state_to" in e
)

range_to_sweep  = trans_counts.get(("RANGE",        "SWEEP"),        0)
sweep_to_disp   = trans_counts.get(("SWEEP",        "DISPLACEMENT"), 0)
disp_to_exp     = trans_counts.get(("DISPLACEMENT", "EXPANSION"),    0)
exp_to_retest   = trans_counts.get(("EXPANSION",    "RETEST"),       0)
retest_to_exec  = trans_counts.get(("RETEST",       "EXECUTION"),    0)
exec_to_res     = trans_counts.get(("EXECUTION",    "RESOLUTION"),   0)

# ============================================================
# EPISODE METRICS
# ============================================================
by_outcome = collections.defaultdict(list)
for ep in episodes:
    by_outcome[ep["outcome"]].append(ep["duration"])

n_ep   = len(episodes)
n_exp  = len(by_outcome["EXPANSION"])
n_htf  = len(by_outcome["HTF_RESET"])
n_ret  = len(by_outcome["RETRACE"])
n_ext  = len(by_outcome["EXTENSION"])
n_oth  = len(by_outcome["OTHER"])
n_dead = n_ep - n_exp

# Duration stats helpers
def pct(lst, p):
    if not lst: return 0
    s = sorted(lst)
    return s[int(len(s) * p / 100)]

exp_durs = sorted(by_outcome["EXPANSION"])
all_durs = sorted(ep["duration"] for ep in episodes)

disp_median = pct(all_durs, 50)
disp_p95    = pct(all_durs, 95)
exp_disp_p95 = pct(exp_durs, 95) if exp_durs else 0

htf_share  = n_htf / max(n_dead, 1) * 100
ret_share  = n_ret / max(n_dead, 1) * 100
conv_rate  = n_exp / max(n_ep, 1) * 100

# Trade metrics
trades   = metrics.approved_trades     if metrics else "?"
pnl_net  = round(metrics.total_pnl_rr_net, 4) if metrics else "?"
win_rate = round(metrics.win_rate, 4)          if metrics else "?"
avg_rr   = round(metrics.total_pnl_rr_net / max(metrics.approved_trades, 1), 4) if metrics else "?"
max_dd   = round(getattr(metrics, "max_drawdown_pct", 0.0) or 0.0, 4) if metrics else "?"

# ============================================================
# ATR DRIFT for surviving DISPLACEMENT episodes (episodes ending in EXPANSION)
# We measure: how many of those have duration > 1 (multi-candle survival)?
# ATR drift cannot be computed directly from events JSONL (no ATR in events).
# We report duration distribution as a proxy for staleness.
# ============================================================
exp_episodes = [ep for ep in episodes if ep["outcome"] == "EXPANSION"]
multi_candle_exp = [ep for ep in exp_episodes if ep["duration"] > 1]

# HTF distance: count HTF_RESET events that occurred WHILE in DISPLACEMENT in P2
# (these would have reset in baseline but are now survived). Proxy: n_htf_resets
# that still fired (those that are RETRACE/EXTENSION post-boundary).
# Real HTF boundary crossings during DISP = episodes where HTF changed but DISP survived.
# We can't directly count this from JSONL without per-candle HTF tracking.
# Report as: episodes lasting > 1 candle = survived at least one HTF boundary.
survived_htf = [ep for ep in episodes if ep["duration"] > 1]

# ============================================================
# REPORT
# ============================================================
SEP = "-" * 68

print(SEP)
print("P2 DIAGNOSTIC RESULTS - DISPLACEMENT exemption from HTF resets")
print(SEP)
print()

print("-- Funnel (P2) vs Baseline --")
print(f"  {'Transition':<32} {'P2':>8}  {'Baseline':>8}  {'Delta':>8}")
print(f"  {'RANGE -> SWEEP':<32} {range_to_sweep:>8}  {'1,726':>8}  {range_to_sweep-1726:>+8}")
print(f"  {'SWEEP -> DISPLACEMENT':<32} {sweep_to_disp:>8}  {'357':>8}  {sweep_to_disp-357:>+8}")
print(f"  {'DISPLACEMENT -> EXPANSION':<32} {disp_to_exp:>8}  {'15':>8}  {disp_to_exp-15:>+8}  <- KEY")
print(f"  {'EXPANSION -> RETEST':<32} {exp_to_retest:>8}  {'14':>8}  {exp_to_retest-14:>+8}")
print(f"  {'RETEST -> EXECUTION':<32} {retest_to_exec:>8}  {'4':>8}  {retest_to_exec-4:>+8}")
print(f"  {'EXECUTION -> RESOLUTION':<32} {exec_to_res:>8}  {'4':>8}  {exec_to_res-4:>+8}")
print()

print("-- DISPLACEMENT episode breakdown --")
print(f"  Total episodes      : {n_ep}  (baseline: 357)")
print(f"  -> EXPANSION        : {n_exp}  (baseline: 15)  conversion={conv_rate:.1f}%  (baseline: 4.2%)")
print(f"  -> HTF_RESET        : {n_htf}  (baseline: 259)  share={htf_share:.1f}%  (target: <25%)")
print(f"  -> RETRACE          : {n_ret}  (baseline: 73)   share={ret_share:.1f}%  (target: <=50%)")
print(f"  -> EXTENSION        : {n_ext}  (baseline: 9)")
print(f"  -> OTHER            : {n_oth}  (baseline: 1)")
print()

print("-- Episode duration (all outcomes) --")
print(f"  Median              : {disp_median}  (baseline: 1)")
print(f"  p95                 : {disp_p95}  (baseline: 1)")
print()

print("-- Expansion episode quality --")
print(f"  EXPANSION episodes  : {n_exp}")
print(f"  Multi-candle EXP    : {len(multi_candle_exp)} (survived >1 candle before expansion)")
if exp_durs:
    print(f"  EXP age median      : {pct(exp_durs, 50)}  (baseline: 1)")
    print(f"  EXP age p95         : {exp_disp_p95}  (target: <=4)")
print(f"  Episodes dur>1      : {len(survived_htf)}  (survived HTF boundary)")
print()

print("-- Trade metrics (P2) vs Baseline --")
print(f"  Trades          : {str(trades):>6}   (baseline: 4)")
print(f"  PnL net R       : {str(pnl_net):>6}   (baseline: +1.57R)")
print(f"  avg R per trade : {str(avg_rr):>6}   (baseline: +0.39R)")
print(f"  Win rate        : {str(win_rate):>6}   (baseline: 0.5)")
print(f"  Max DD          : {str(max_dd):>6}   (baseline: 0.011)")
print()

# ============================================================
# CRITERIA CHECK
# ============================================================
print("-- Success criteria check --")
criteria = [
    ("DISP median duration > 1",              disp_median > 1,                  f"median={disp_median}"),
    ("DISP->EXP conversion > 4.2%",           conv_rate > 4.2,                  f"{conv_rate:.1f}%"),
    ("HTF kill share < 25%",                  htf_share < 25.0,                 f"{htf_share:.1f}%"),
    ("Retrace kill share <= 50%",             ret_share <= 50.0,                f"{ret_share:.1f}%"),
    ("DISP age at EXP p95 <= 4 candles",      exp_disp_p95 <= 4,               f"p95={exp_disp_p95}"),
    ("avg_R >= baseline (0.39R)",             isinstance(avg_rr, float) and avg_rr >= 0.39, f"{avg_rr}"),
    ("MaxDD <= baseline x1.2 (0.0132)",       isinstance(max_dd, float) and max_dd <= 0.0132, f"{max_dd}"),
]
for label, passed, val in criteria:
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {label:<42} {val}")
print()

# ============================================================
# VERDICT
# ============================================================
print("-- Verdict --")
all_pass = all(p for _, p, _ in criteria)
exp_up   = isinstance(disp_to_exp, int) and disp_to_exp > 15
pnl_ok   = isinstance(pnl_net, float) and pnl_net >= 1.57

if not exp_up:
    print("  EXPANSION = 15 (unchanged). Retrace threshold is the actual governor.")
    print("  Next: investigate retrace_reset_pct config.")
elif exp_up and pnl_ok and all_pass:
    print("  PASS: EXPANSION up, PnL >= baseline, all criteria met.")
    print("  DISP exemption is ROI-positive -> proceed to guarded source fix.")
    print("  Add protect_disp_from_htf_reset: bool = False to CRTConfig.")
elif exp_up and not pnl_ok:
    print("  MIXED: EXPANSION up but PnL degraded.")
    print("  More setups but lower quality. HTF freshness was a quality governor.")
    print("  REJECT source promotion.")
else:
    print("  PARTIAL: review criteria table above for specific failures.")

print()
print(f"[P2] Events JSONL : {events_path}")
print(f"[P2] Total events : {len(events)}")
print(SEP)
