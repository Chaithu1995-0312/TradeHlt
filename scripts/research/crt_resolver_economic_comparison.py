"""
CRT Resolver vs Engine — Economic Comparison (F-069 follow-up, relaxed trigger)
==================================================================================
READ-ONLY / observe-only w.r.t. `src/`. Grants no authority to modify
CRTStateResolver, the CRT engine, or any production config regardless of the
numbers below (§6.5 Authority Ladder).

TRIGGER RULE DIVERGENCE (stated up front — this is the single most important
fact for reading this script's output correctly)
------------------------------------------------------------------------------
  Engine arm:    the real production trigger — RETEST -> EXECUTION via
                 `CRTEngine.try_retest_to_execution` (crt_engine_v2.py).
  Resolver arm:  EXPANSION-entry transition — a DIFFERENT, RELAXED rule, not a
                 replay of the engine's strategy.

CRTStateResolver's own EXECUTION branch is structurally unreachable on any real
39-dim feature vector (F-069, `docs/current-findings.md`): `_continuous_gates_pass`
requires a `score`/`risk_score`/`crt_score` feature that does not exist in
`CANONICAL_FEATURES` (`src/features/feature_schema.py`) — confirmed empirically
in every measurement this program has taken (baseline, all 33 F-069 Stage-A
candidates, Stage B: resolver EXECUTION count is always 0). This is a deductive
fact from source, not something this script re-measures. Since a strict
same-trigger comparison is a foregone conclusion (0 vs whatever the engine
produces), this script instead triggers resolver-side trades on EXPANSION-entry
(the resolver's most-populated non-trivial state) as an explicitly different,
illustrative proxy — never silently presented as "the same strategy."

PREDICTION (frozen before running; falsifiable)
------------------------------------------------------------------------------
  1. Engine arm: n=1 (the corpus's only real trade, from an existing
     BacktestRunner run current against the committed engine code/config),
     net_rr ~= -0.038, INSUFFICIENT for any economic conclusion (MIN_CELL_N=15
     precedent, `scripts/analysis/blind_label_score.py`).
  2. Resolver arm (EXPANSION-entry, relaxed): low tens of signals expected
     (sticky-dwell collapses ~1,500-4,600 EXPANSION-occupancy bars into far
     fewer distinct entry transitions) — still almost certainly INSUFFICIENT.
  3. No promotable economic conclusion is expected in either direction. The
     only decisive, non-statistical finding is structural: the engine CAN
     trade under its own rule; CRTStateResolver's OWN rule structurally
     cannot. Falsifier for (3): either arm clearing n>=15 with a stable,
     non-degenerate profit factor would warrant a closer look (not expected).

SIMPLIFICATIONS (stated, not hidden)
------------------------------------------------------------------------------
  - Resolver-arm SL mirrors the engine's shape (displacement-candle-anchored,
    `sl_atr_buffer` from the active config) but TP is a single flat TP1
    multiplier only — no per-intent classification (resolver memory carries no
    `cached_features`/intent equivalent), no TP1-partial + breakeven-trail +
    TP2 two-leg structure. This is an illustrative single-leg proxy, not a
    byte-exact replay of `ExecutionEngine.build_trade()`.
  - Direction is read from the resolver's own `CRTStateMemory.displacement_direction`
    (already tracked at DISPLACEMENT/SWEEP entry, carried into EXPANSION) — the
    principled, already-existing source, not a newly invented rule.
  - Cost model: both arms are reported under TWO columns — the engine's own
    native cost (`pnl_rr_net` from its stochastic ATR-slippage+spread
    simulation) and a flat 12bps `DEFAULT_COST_MODEL` applied identically to
    both arms via `EdgeAggregator`. These are NOT numerically equivalent
    models; they are never blended into one number.

A NOTE ON A CONCURRENT DOCUMENT
------------------------------------------------------------------------------
`reports/crt_state_resolver_vs_backtest_runner_report.md` (written by a
concurrent session, correctly cites this program's F-069 finding) contains a
FABRICATED worked example (entry=2352.10, sl=2350.21) that does not match the
real trade row in `XAUUSD_trades.csv` (entry_raw=2318.21, sl=2317.4565714285714).
This script reads the trades CSV directly and does not reuse any number from
that document.

USAGE
-----
    python scripts/research/crt_resolver_economic_comparison.py
    python scripts/research/crt_resolver_economic_comparison.py --force-fresh-run
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "scripts" / "research"))

CERT_VERSION = "1.0.0"

DEFAULT_OHLCV = _ROOT / "data" / "mt5" / "XAUUSD_M15.csv"
DEFAULT_ENGINE_RUN_DIR = _ROOT / "results" / "run_20260805_105350_XAUUSD"
DEFAULT_MAX_FORWARD = 40
DEFAULT_N_BOOT = 10_000
DEFAULT_ALPHA = 0.05
MIN_CELL_N = 15  # precedent: scripts/analysis/blind_label_score.py


# ── Engine-side ledger ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class EngineTrade:
    trade_id: str
    direction: str          # "long" | "short" (lowered from CSV's LONG/SHORT)
    entry_raw: float
    sl: float
    tp1: float
    pnl_rr_net: float
    pnl_rr_raw: float
    exit_reason: str
    duration_candles: int
    opened_at: str
    candle_idx: int


def load_engine_trades(trades_csv: Path) -> list[EngineTrade]:
    trades: list[EngineTrade] = []
    with trades_csv.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            trades.append(EngineTrade(
                trade_id=row["trade_id"],
                direction=row["direction"].lower(),
                entry_raw=float(row["entry_raw"]),
                sl=float(row["sl"]),
                tp1=float(row["tp1"]),
                pnl_rr_net=float(row["pnl_rr_net"]),
                pnl_rr_raw=float(row["pnl_rr_raw"]),
                exit_reason=row["exit_reason"],
                duration_candles=int(row["duration_candles"]),
                opened_at=row["opened_at"],
                candle_idx=int(row["candle_idx"]),
            ))
    return trades


def resolve_engine_ledger(
    *,
    engine_run_dir: Path = DEFAULT_ENGINE_RUN_DIR,
    force_fresh: bool = False,
    ohlcv_path: Path = DEFAULT_OHLCV,
    instrument: str = "XAUUSD",
) -> tuple[list[EngineTrade], dict[str, Any]]:
    """Reuse an existing BacktestRunner run by default (verified this session:
    the current run dir's trade CSV postdates the engine code/config it was
    produced from — it is current, trustworthy ground truth). `force_fresh`
    re-runs BacktestRunner via the `detection_sweep.py:71-79` idiom.
    """
    if not force_fresh:
        trades_csv = engine_run_dir / f"{instrument}_trades.csv"
        if trades_csv.exists():
            trades = load_engine_trades(trades_csv)
            return trades, {
                "mode": "reuse", "engine_run_dir": str(engine_run_dir),
                "trades_csv": str(trades_csv), "n_trades": len(trades),
            }

    from config_layer.config_builder import ConfigBuilder
    from runtime.backtest_v2 import BacktestConfig, BacktestRunner, CandleLoader, MultiInstrumentRunner

    crt_cfg = ConfigBuilder.build(instrument)
    cfg = BacktestConfig.from_prod_config(crt_config=crt_cfg)
    cfg.instrument = instrument
    cfg.pip_size = MultiInstrumentRunner.INSTRUMENT_PIP.get(instrument, 0.01)
    loader = CandleLoader(str(ohlcv_path), instrument)
    out_dir = (_ROOT / "results" / "analysis" / "crt_resolver_econ_compare_fresh_run").resolve()
    runner = BacktestRunner(
        cfg, csv_path=str(ohlcv_path),
        overrides={"diagnostic": "crt_resolver_economic_comparison", "instrument": instrument},
    )
    runner.run(loader.stream(), loader.count(), str(out_dir))
    matches = list(out_dir.glob(f"run_*_{instrument}/{instrument}_trades.csv"))
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly 1 trades.csv under {out_dir}, found {matches}")
    trades = load_engine_trades(matches[0])
    return trades, {"mode": "fresh_run", "trades_csv": str(matches[0]), "n_trades": len(trades)}


# ── Resolver-side EXPANSION-entry adapter ───────────────────────────────────

@dataclass(frozen=True)
class ExpansionEntrySignal:
    entry_index: int    # raw CSV row index — matches CandleLoader Candle.index
    direction: str       # "long" | "short"
    entry: float
    sl_raw: float
    tp1_raw: float
    atr_abs: float
    meta: dict = field(default_factory=dict)


def drive_resolver_with_memory(
    ohlcv_path: Path,
    config_path: Optional[Path] = None,
    *,
    htf_mode: str = "engine",
    instrument: str = "XAUUSD",
) -> tuple[list[str], list[Any], list[float], list[float], list[int], Any]:
    """Mirrors `crt_state_confusion_matrix.build_resolver_timeline`'s per-bar
    loop, but ALSO captures a `resolver.memory` snapshot (a fresh dataclass
    copy per the property's own definition), `resolver._atr_abs(fv)`, and the
    bar's `trend_bias` feature after every `resolve()` call — needed for
    direction inference (see finding below) and absolute ATR, none of which
    the upstream function exposes (it returns only state-name strings).
    Duplicated rather than modifying `build_resolver_timeline` (frozen,
    F-069-committed) or `CRTStateResolver` (no modification authority for
    this program).

    DIRECTION-SOURCE FINDING (empirically verified, not assumed): at every
    real EXPANSION-entry bar in this corpus, BOTH `memory.displacement_direction`
    AND its shadow-preserved fallback `memory.pending_displacement_dir` are
    empty (0 / "NONE"). This is because these entries fire via the
    DECLARATIVE `when: {displacement_flag:[Displacement]}` predicate matching
    the pipeline's own `displacement_flag` feature directly — a path that
    never touches the state-machine memory fields that track direction
    (those are set only inside the SWEEP/DISPLACEMENT state-machine code
    paths, `crt_state_resolver.py:1376-1398`). So `trend_bias` (a feature-
    vector-level signal, already computed by FeaturePipeline) is captured
    here as the ONLY available direction source for these bars — stated
    explicitly in the report, never silently substituted for the memory-based
    field it is not.

    Returns (states, memory_snapshots, atr_abs_list, trend_bias_list, source_indices, raw_df).
    """
    import numpy as np
    import pandas as pd
    from crt_state_confusion_matrix import compute_enriched_frame
    from features.crt_state_resolver import CRTStateResolver, build_htf_id_timeline
    from features.feature_schema import CANONICAL_FEATURES

    df = pd.read_csv(ohlcv_path)
    rename = {c: c.lower() for c in df.columns if c.lower() in
              {"open", "high", "low", "close", "volume", "timestamp", "time"}}
    df = df.rename(columns=rename)
    n_raw = len(df)

    enriched = compute_enriched_frame(ohlcv_path, fp_cfg=None, _df=df)
    source_indices = [int(v) for v in enriched["_src_idx"].tolist()]

    resolver = CRTStateResolver(config_path=config_path)
    thr = resolver._config.get("thresholds", {})
    thr_defaults = {"rsi_overbought": 70.0, "rsi_oversold": 30.0}
    rsi_ob = float(thr.get("rsi_overbought", thr_defaults["rsi_overbought"]))
    rsi_os = float(thr.get("rsi_oversold", thr_defaults["rsi_oversold"]))
    life = thr.get("lifecycle") or {}
    cph = int(life.get("htf_candles_per_range", 4))

    engine_htf_ids = None
    if htf_mode == "engine":
        engine_htf_ids = build_htf_id_timeline(n_raw, candles_per_htf=cph, instrument=instrument)

    first_src = int(source_indices[0]) if source_indices else 0
    if getattr(resolver, "_sweep_geometry", "pipeline_swing") == "htf_range" and first_src > 0:
        raw_o = df["open"].astype(float).tolist()
        raw_h = df["high"].astype(float).tolist()
        raw_l = df["low"].astype(float).tolist()
        raw_c = df["close"].astype(float).tolist()
        for i in range(first_src):
            hid = engine_htf_ids[i] if engine_htf_ids is not None else None
            resolver.seed_ohlc(raw_o[i], raw_h[i], raw_l[i], raw_c[i], htf_id=hid)
        resolver.finalize_seed_range()

    ts_col = None
    for cand in ("timestamp", "time", "datetime"):
        if cand in enriched.columns:
            ts_col = cand
            break
    if ts_col is not None:
        enriched = enriched.copy()
        enriched[ts_col] = pd.to_datetime(enriched[ts_col])

    states: list[str] = []
    memories: list[Any] = []
    atr_abs_list: list[float] = []
    trend_bias_list: list[float] = []
    for row_i, (_, row) in enumerate(enriched.iterrows()):
        fv: dict[str, float] = {}
        for name in CANONICAL_FEATURES:
            if name in enriched.columns:
                val = row[name]
                fv[name] = 0.0 if pd.isna(val) else float(val)
        for name in ("retest_flag", "displacement_flag"):
            if name in enriched.columns:
                val = row[name]
                fv[name] = 0.0 if pd.isna(val) else float(val)
            else:
                fv[name] = 0.0
        rsi = fv.get("rsi_14", 50.0)
        fv["rsi_state"] = 1.0 if rsi > rsi_ob else (-1.0 if rsi < rsi_os else 0.0)
        ts = row[ts_col] if ts_col is not None else None
        if ts is not None and pd.isna(ts):
            ts = None
        src = source_indices[row_i]
        htf_id = (engine_htf_ids[src]
                  if (engine_htf_ids is not None and 0 <= src < len(engine_htf_ids)) else None)

        state = resolver.resolve(fv, timestamp=ts, htf_id=htf_id)
        states.append(state)
        memories.append(resolver.memory)
        atr_abs_list.append(resolver._atr_abs(fv) or 0.0)
        trend_bias_list.append(fv.get("trend_bias", 0.0))

    return states, memories, atr_abs_list, trend_bias_list, source_indices, df


def build_expansion_entry_signals(
    states: list[str],
    memories: list[Any],
    atr_abs_list: list[float],
    trend_bias_list: list[float],
    source_indices: list[int],
    raw_df: Any,
    *,
    sl_atr_buffer: float,
    tp1_atr_multiplier: float,
) -> tuple[list[ExpansionEntrySignal], dict[str, int]]:
    """
    EMPIRICAL FINDING (verified on this corpus, not assumed): every real
    EXPANSION-entry bar has `memory.displacement_direction == 0` AND
    `memory.pending_displacement_dir == "NONE"` AND
    `memory.displacement_candle_index == -1`. These entries fire via the
    DECLARATIVE `when: {displacement_flag:[Displacement]}` predicate matching
    the pipeline's own `displacement_flag` feature directly, a path that never
    touches the state-machine memory fields that track direction/displacement
    geometry (`crt_state_resolver.py:1376-1398`). So this function falls back,
    transparently and with a recorded `direction_source`/`sl_anchor_source`
    tag per signal:
      - direction: memory.displacement_direction -> memory.pending_displacement_dir
        -> sign(trend_bias at the entry bar). All three empty -> skip, counted.
      - SL anchor: memory's displacement candle (when trackable) -> the
        ENTRY bar's OWN low/high (when no displacement candle is trackable,
        i.e. the empirically-common case here) -> same buffer formula, just a
        different reference candle. This changes WHAT the SL is anchored to,
        not the formula shape.
    """
    counters = {
        "entries_found": 0, "skipped_no_direction": 0, "rejected_inverted_sl": 0,
        "direction_source_memory": 0, "direction_source_pending_shadow": 0,
        "direction_source_trend_bias_fallback": 0,
        "sl_anchor_source_displacement_candle": 0, "sl_anchor_source_entry_bar_fallback": 0,
    }
    signals: list[ExpansionEntrySignal] = []
    for i, state in enumerate(states):
        if state != "EXPANSION":
            continue
        if i > 0 and states[i - 1] == "EXPANSION":
            continue  # sticky-dwell occupancy, not an entry transition
        counters["entries_found"] += 1

        mem = memories[i]
        direction_sign = mem.displacement_direction
        direction_source = "memory"
        if direction_sign == 0:
            pending = mem.pending_displacement_dir
            if pending == "LONG":
                direction_sign, direction_source = 1, "pending_shadow"
            elif pending == "SHORT":
                direction_sign, direction_source = -1, "pending_shadow"
            else:
                tb = trend_bias_list[i]
                if tb > 0:
                    direction_sign, direction_source = 1, "trend_bias_fallback"
                elif tb < 0:
                    direction_sign, direction_source = -1, "trend_bias_fallback"
        if direction_sign == 0:
            counters["skipped_no_direction"] += 1
            continue
        counters[f"direction_source_{direction_source}"] += 1
        direction = "long" if direction_sign > 0 else "short"

        entry_src_idx = source_indices[i]
        entry_close = float(raw_df["close"].iloc[entry_src_idx])
        atr_abs = atr_abs_list[i]
        if atr_abs <= 0:
            counters["skipped_no_direction"] += 1  # degenerate ATR — treat as unusable, same bucket
            continue

        disp_idx_1based = mem.displacement_candle_index
        disp_row_i = disp_idx_1based - 1  # candle_index increments BEFORE use (resolver.py:377)
        if disp_idx_1based >= 0 and 0 <= disp_row_i < len(source_indices):
            disp_src_idx = source_indices[disp_row_i]
            anchor_low = float(raw_df["low"].iloc[disp_src_idx])
            anchor_high = float(raw_df["high"].iloc[disp_src_idx])
            counters["sl_anchor_source_displacement_candle"] += 1
        else:
            anchor_low = float(raw_df["low"].iloc[entry_src_idx])
            anchor_high = float(raw_df["high"].iloc[entry_src_idx])
            counters["sl_anchor_source_entry_bar_fallback"] += 1

        if direction == "long":
            sl_raw = anchor_low - sl_atr_buffer * atr_abs
            inverted = sl_raw >= entry_close
        else:
            sl_raw = anchor_high + sl_atr_buffer * atr_abs
            inverted = sl_raw <= entry_close
        if inverted:
            counters["rejected_inverted_sl"] += 1
            continue

        risk_raw = abs(entry_close - sl_raw)
        tp1_raw = (entry_close + tp1_atr_multiplier * risk_raw if direction == "long"
                   else entry_close - tp1_atr_multiplier * risk_raw)

        signals.append(ExpansionEntrySignal(
            entry_index=entry_src_idx, direction=direction, entry=entry_close,
            sl_raw=sl_raw, tp1_raw=tp1_raw, atr_abs=atr_abs,
            meta={"resolver_row_index": i, "direction_source": direction_source,
                  "sl_anchor_source": ("displacement_candle" if disp_idx_1based >= 0
                                        and 0 <= disp_row_i < len(source_indices)
                                        else "entry_bar_fallback")},
        ))
    return signals, counters


# ── Measurement (reuses tested research-layer machinery) ───────────────────

def run_resolver_arm(
    signals: list[ExpansionEntrySignal], candles: list[Any], instrument: str,
    *, max_forward: int = DEFAULT_MAX_FORWARD,
) -> tuple[list, dict[str, int]]:
    from research.contracts import Signal
    from research.measurement.forward_walk import forward_walk

    outcomes = []
    counters = {"future_empty_near_corpus_end": 0}
    for sig in signals:
        future = candles[sig.entry_index + 1: sig.entry_index + 1 + max_forward]
        if not future:
            counters["future_empty_near_corpus_end"] += 1
            continue
        risk_raw = abs(sig.entry - sig.sl_raw)
        reward_raw = abs(sig.tp1_raw - sig.entry)
        research_signal = Signal(
            instrument=instrument, timestamp=candles[sig.entry_index].timestamp,
            entry_index=sig.entry_index, direction=sig.direction, entry=sig.entry,
            sl_atr_mult=risk_raw, tp_atr_mult=reward_raw, atr=1.0,  # raw-price trick
            meta=sig.meta,
        )
        outcomes.append(forward_walk(research_signal, future, max_forward=max_forward,
                                      exit_model="intrabar_fixed"))
    return outcomes, counters


def run_engine_arm(engine_trades: list[EngineTrade], instrument: str) -> list:
    """Wraps each real, already-realized EngineTrade as a synthetic Outcome so
    EdgeAggregator/bootstrap_ci run identically on both arms. Uses GROSS R
    (pnl_rr_raw) so EdgeAggregator's own flat-cost netting isn't double-applied
    on top of the engine's native slippage/spread — the native-cost column is
    reported separately from pnl_rr_net directly.
    """
    from datetime import datetime

    from research.contracts import Outcome, Signal

    outcomes = []
    for t in engine_trades:
        risk_raw = abs(t.entry_raw - t.sl)
        reward_raw = abs(t.tp1 - t.entry_raw)
        sig = Signal(
            instrument=instrument, timestamp=datetime.fromisoformat(t.opened_at),
            entry_index=t.candle_idx, direction=t.direction, entry=t.entry_raw,
            sl_atr_mult=risk_raw, tp_atr_mult=reward_raw, atr=1.0,
            meta={"trade_id": t.trade_id, "native_pnl_rr_net": t.pnl_rr_net},
        )
        outcomes.append(Outcome(
            signal=sig, outcome=("SL_HIT" if t.exit_reason == "STOPPED" else t.exit_reason),
            rr_achieved=t.pnl_rr_raw, mfe=0.0, mae=0.0,
            duration_candles=t.duration_candles, time_to_tp=None,
            time_to_failure=(t.duration_candles if t.exit_reason == "STOPPED" else None),
            reached_1r=False,
        ))
    return outcomes


def compare(resolver_outcomes: list, engine_outcomes: list) -> dict[str, Any]:
    from research.costs import DEFAULT_COST_MODEL
    from research.measurement.bootstrap import bootstrap_ci, seed_from_key
    from research.measurement.metrics import EdgeAggregator

    agg = EdgeAggregator()
    resolver_report = agg.aggregate("crt_resolver_expansion_entry", ["XAUUSD"], resolver_outcomes)
    engine_report = agg.aggregate("backtest_runner_native_execution", ["XAUUSD"], engine_outcomes)

    seed = seed_from_key("crt_resolver_economic_comparison_v1")

    def _net_rrs(outcomes: list) -> list[float]:
        return [
            DEFAULT_COST_MODEL.net_rr(o.rr_achieved, o.signal.entry,
                                       o.signal.sl_atr_mult * o.signal.atr)
            for o in outcomes
        ]

    def _cost_in_r(outcomes: list) -> list[float]:
        # cost_r isolated (not netted) — makes the "cost dominates the trade"
        # finding concrete: this strategy's ATR-based stops are tight relative
        # to price, so a flat bps-of-PRICE model produces a cost several R
        # wide, dwarfing the trade. This is a property of the 12bps model
        # being the wrong tool for THIS geometry, not a real execution cost.
        return [
            DEFAULT_COST_MODEL.cost_r(o.signal.entry, o.signal.sl_atr_mult * o.signal.atr)
            for o in outcomes
        ]

    resolver_gross = [o.rr_achieved for o in resolver_outcomes]
    engine_gross = [o.rr_achieved for o in engine_outcomes]
    resolver_net = _net_rrs(resolver_outcomes)
    engine_net = _net_rrs(engine_outcomes)
    resolver_cost_r = _cost_in_r(resolver_outcomes)
    engine_cost_r = _cost_in_r(engine_outcomes)
    resolver_ci = bootstrap_ci(resolver_net, n_boot=DEFAULT_N_BOOT, alpha=DEFAULT_ALPHA, seed=seed) \
        if resolver_net else None
    engine_ci = bootstrap_ci(engine_net, n_boot=DEFAULT_N_BOOT, alpha=DEFAULT_ALPHA, seed=seed) \
        if engine_net else None
    resolver_gross_ci = bootstrap_ci(resolver_gross, n_boot=DEFAULT_N_BOOT, alpha=DEFAULT_ALPHA, seed=seed) \
        if resolver_gross else None
    engine_gross_ci = bootstrap_ci(engine_gross, n_boot=DEFAULT_N_BOOT, alpha=DEFAULT_ALPHA, seed=seed) \
        if engine_gross else None

    return {
        "resolver": {
            "report": resolver_report, "net_rrs_flat_cost": resolver_net,
            "gross_rrs": resolver_gross, "cost_r_flat": resolver_cost_r,
            "ci_95_flat_cost": resolver_ci, "ci_95_gross": resolver_gross_ci,
            "ci_degenerate": len(resolver_net) <= 1,
            "insufficient": resolver_report.n < MIN_CELL_N,
        },
        "engine": {
            "report": engine_report, "net_rrs_flat_cost": engine_net,
            "gross_rrs": engine_gross, "cost_r_flat": engine_cost_r,
            "ci_95_flat_cost": engine_ci, "ci_95_gross": engine_gross_ci,
            "ci_degenerate": len(engine_net) <= 1,
            "insufficient": engine_report.n < MIN_CELL_N,
            "native_pnl_rr_net": [o.signal.meta.get("native_pnl_rr_net") for o in engine_outcomes],
        },
    }


# ── Report ───────────────────────────────────────────────────────────────────

def _edge_report_row(label: str, d: dict[str, Any]) -> str:
    r = d["report"]
    ci = d["ci_95_flat_cost"]
    ci_str = f"[{ci[0]:+.4f}, {ci[1]:+.4f}]" if ci else "n/a"
    pf = "inf" if r.profit_factor == float("inf") else f"{r.profit_factor:.3f}"
    return (f"| {label} | {r.n} | {r.wins} | {r.losses} | {r.win_rate:.1%} | {pf} | "
            f"{r.expectancy_rr:+.4f} | {r.max_drawdown_rr:.4f} | {ci_str} | "
            f"{'yes' if d['ci_degenerate'] else 'no'} | "
            f"{'INSUFFICIENT' if d['insufficient'] else 'powered'} |")


def write_report(out_path: Path, *, comparison: dict, engine_provenance: dict,
                  resolver_counters: dict, forward_walk_counters: dict,
                  engine_trades: list, corpus_path: Path) -> None:
    lines: list[str] = []
    a = lines.append

    a("# CRT Resolver vs Engine — Economic Comparison (XAUUSD M15)")
    a("")
    a("> Research only (§6.5 Authority Ladder). Grants no authority to modify "
      "CRTStateResolver, the CRT engine, or any production config regardless of "
      "the numbers below.")
    a(f"> cert_version={CERT_VERSION}")
    a("")
    a("## Methodology (read this before the numbers)")
    a("")
    a("**Trigger rule — the two arms use DIFFERENT rules, not the same strategy:**")
    a("")
    a("- **Engine arm**: the real production trigger — RETEST -> EXECUTION via "
      "`CRTEngine.try_retest_to_execution` (`src/config_layer/crt_engine_v2.py`).")
    a("- **Resolver arm**: EXPANSION-entry transition — a relaxed proxy. "
      "`CRTStateResolver`'s own EXECUTION branch is structurally unreachable "
      "(F-069): `_continuous_gates_pass` requires a `score`/`risk_score`/"
      "`crt_score` feature absent from `CANONICAL_FEATURES` "
      "(`src/features/feature_schema.py`) — confirmed 0 in every measurement "
      "this program has taken. A strict same-trigger comparison is therefore a "
      "foregone conclusion (0 trades) before any numbers are computed.")
    a("")
    a("**SL/TP construction:** engine = `ExecutionEngine.build_trade()` "
      "(displacement-candle-anchored SL, per-intent TP1/TP2). Resolver arm "
      "mirrors the SL anchor formula (`sl_atr_buffer` read from the active "
      "config, not hardcoded) but uses a **single flat TP1 multiplier only** — "
      "no per-intent classification, no TP1-partial/breakeven-trail/TP2 "
      "two-leg structure. This is an illustrative single-leg proxy.")
    a("")
    a("**Direction:** tried in order — resolver's own "
      "`CRTStateMemory.displacement_direction` (tracked at DISPLACEMENT/SWEEP "
      "entry), then its shadow-preserved fallback `pending_displacement_dir`, "
      "then `trend_bias` from the feature vector. **Empirical finding on this "
      "corpus:** every real EXPANSION-entry bar has BOTH memory fields empty — "
      "these entries fire via the declarative `displacement_flag` predicate "
      "match, a path that never touches direction-tracking memory — so "
      "`trend_bias` is the source actually used throughout, not memory. "
      "Bars where all three are empty are skipped and counted, never guessed. "
      "**SL anchor** similarly falls back from the displacement candle (never "
      "available here, same root cause) to the entry bar's own low/high — "
      "counted per-signal via `sl_anchor_source`.")
    a("")
    a("**Cost model:** two columns, never blended — the engine's own native "
      "cost (`pnl_rr_net`, its stochastic ATR-slippage+spread simulation) and "
      "a flat 12bps `DEFAULT_COST_MODEL` applied identically to both arms.")
    a("")
    a(f"**Provenance:** engine ledger = `{engine_provenance.get('trades_csv')}` "
      f"(mode: {engine_provenance.get('mode')}). Corpus: `{corpus_path}`. "
      "Resolver config: the current committed `market_crt_states.yaml`, "
      "untouched for this comparison.")
    a("")

    a("## A finding about the cost model, before the table")
    a("")
    eng_cost = comparison["engine"]["cost_r_flat"]
    res_cost = comparison["resolver"]["cost_r_flat"]
    avg_res_cost = sum(res_cost) / len(res_cost) if res_cost else 0.0
    eng_risk_distance = (abs(engine_trades[0].entry_raw - engine_trades[0].sl)
                          if engine_trades else 0.0)
    a("This strategy's stops are ATR-buffer-anchored and genuinely tight relative to "
      "price (a property of the construction, not a measurement artifact). The flat "
      "12bps-of-**price** research cost model (`src/research/costs.py`, designed for "
      "the Edge Discovery program's typically wider stops) converts to an enormous "
      "cost in **R** terms when the risk distance is this small: "
      "`cost_r(entry, risk_distance) = (12bps * entry) / risk_distance`. On the "
      f"engine's real trade, `risk_distance` = {eng_risk_distance:.4f} price units "
      f"(entry ~{engine_trades[0].entry_raw if engine_trades else 0:.2f}) — the flat-"
      f"cost model alone contributes **{eng_cost[0]:+.2f}R** of cost on a trade whose "
      "entire realized result was "
      f"{comparison['engine']['native_pnl_rr_net'][0] if comparison['engine']['native_pnl_rr_net'] else 'n/a'}R "
      "under the engine's OWN (correct) cost model. On the resolver arm, the same "
      f"effect contributes an average of **{avg_res_cost:+.2f}R** per signal. "
      "**This is the 12bps model being the wrong tool for this geometry, not evidence "
      "either arm performed catastrophically** — the GROSS (pre-cost) row below is the "
      "more honest number to read for this strategy, with the flat-cost row kept only "
      "for the apples-to-apples formula comparison the methodology promised, not as "
      "the headline economic verdict.")
    a("")

    a("## Comparison table")
    a("")
    a("**GROSS (pre-cost) — the more honest number given the cost-model mismatch above:**")
    a("")
    a("| Arm | n | mean gross R | 95% CI (gross) |")
    a("|---|---:|---:|---|")
    for label, key in (("Engine (native EXECUTION trigger)", "engine"),
                        ("Resolver (EXPANSION-entry, relaxed)", "resolver")):
        d = comparison[key]
        gross = d["gross_rrs"]
        mean_gross = sum(gross) / len(gross) if gross else 0.0
        ci = d["ci_95_gross"]
        ci_str = f"[{ci[0]:+.4f}, {ci[1]:+.4f}]" if ci else "n/a"
        a(f"| {label} | {len(gross)} | {mean_gross:+.4f} | {ci_str} |")
    a("")
    native = comparison["engine"]["native_pnl_rr_net"]
    if native:
        a(f"Engine's own NATIVE cost model (real stochastic slippage+spread): "
          f"`pnl_rr_net` = {native} — this, not either column below, is the engine "
          "arm's real, governing result.")
        a("")

    a("**Flat-12bps-cost (apples-to-apples formula, degenerate here — see finding above):**")
    a("")
    a("| Arm | n | wins | losses | win rate | PF | expectancy (flat-cost R) | "
      "max DD (R) | 95% CI (flat-cost) | CI degenerate | power |")
    a("|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|")
    a(_edge_report_row("Engine (native EXECUTION trigger)", comparison["engine"]))
    a(_edge_report_row("Resolver (EXPANSION-entry, relaxed)", comparison["resolver"]))
    a("")

    a("### Resolver-arm counters (transparency on what got filtered out)")
    a("")
    a("| Counter | Value |")
    a("|---|---:|")
    for k, v in {**resolver_counters, **forward_walk_counters}.items():
        a(f"| {k} | {v} |")
    a("")

    a("## Epistemic Integrity caveat (Program E-001)")
    a("")
    n_eng = comparison["engine"]["report"].n
    n_res = comparison["resolver"]["report"].n
    a(f"Both arms are reported **INSUFFICIENT** for an economic conclusion "
      f"(n={n_eng} engine, n={n_res} resolver, both below `MIN_CELL_N={MIN_CELL_N}` "
      "— precedent: `scripts/analysis/blind_label_score.py`). Neither win rate, "
      "profit factor, nor expectancy above should be read as evidence that "
      "either arm is economically 'better' — at these sample sizes a single "
      "trade dominates the entire result.")
    a("")
    a("**The only decisive, non-statistical finding is structural**: "
      "`BacktestRunner` can produce a trade under its own native rule; "
      "`CRTStateResolver`'s own native EXECUTION rule structurally cannot "
      "(deductive, F-069, not a sample-size question). The numbers above exist "
      "only under an explicitly different, relaxed resolver-side trigger and "
      "should be read as illustrative, not as a finding in either direction.")
    a("")

    a("## Correction to a concurrent document")
    a("")
    a("`reports/crt_state_resolver_vs_backtest_runner_report.md` (a separate, "
      "descriptive doc, correctly cites this program's F-069 finding) contains "
      "a fabricated worked example (entry=2352.10, sl=2350.21) that does **not** "
      "match the real trade row this report reads directly from "
      f"`{engine_provenance.get('trades_csv')}` "
      f"(entry_raw={engine_trades[0].entry_raw if engine_trades else 'n/a'}, "
      f"sl={engine_trades[0].sl if engine_trades else 'n/a'}). Do not cite that "
      "document's worked-example numbers as real.")
    a("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Report written to {out_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="CRT resolver vs engine economic comparison")
    parser.add_argument("--ohlcv", default=str(DEFAULT_OHLCV))
    parser.add_argument("--engine-run-dir", default=str(DEFAULT_ENGINE_RUN_DIR))
    parser.add_argument("--force-fresh-run", action="store_true")
    parser.add_argument("--instrument", default="XAUUSD")
    parser.add_argument("--max-forward", type=int, default=DEFAULT_MAX_FORWARD)
    parser.add_argument("--output-json", default=str(
        _ROOT / "results" / "analysis" / "crt_resolver_economic_comparison.LATEST.json"
    ))
    parser.add_argument("--output-md", default=str(
        _ROOT / "reports" / "crt_resolver_economic_comparison.md"
    ))
    args = parser.parse_args()

    ohlcv_path = Path(args.ohlcv)
    t0 = time.time()

    print("Loading engine-side trade ledger...")
    engine_trades, engine_provenance = resolve_engine_ledger(
        engine_run_dir=Path(args.engine_run_dir), force_fresh=args.force_fresh_run,
        ohlcv_path=ohlcv_path, instrument=args.instrument,
    )
    print(f"  {engine_provenance}")

    print("Driving resolver with memory capture (this runs FeaturePipeline once)...")
    states, memories, atr_abs_list, trend_bias_list, source_indices, raw_df = drive_resolver_with_memory(
        ohlcv_path, config_path=None, htf_mode="engine", instrument=args.instrument,
    )
    print(f"  n_bars_resolved={len(states)}")

    from config_layer.config_builder import ConfigBuilder
    crt_cfg = ConfigBuilder.build(args.instrument)

    print("Building EXPANSION-entry signals...")
    signals, resolver_counters = build_expansion_entry_signals(
        states, memories, atr_abs_list, trend_bias_list, source_indices, raw_df,
        sl_atr_buffer=crt_cfg.sl_atr_buffer, tp1_atr_multiplier=crt_cfg.tp1_atr_multiplier,
    )
    print(f"  {resolver_counters} -> {len(signals)} usable signals")

    print("Running forward_walk on resolver-side signals...")
    from runtime.backtest_v2 import CandleLoader
    candles = list(CandleLoader(str(ohlcv_path), args.instrument).stream())
    resolver_outcomes, fw_counters = run_resolver_arm(
        signals, candles, args.instrument, max_forward=args.max_forward,
    )
    print(f"  {fw_counters} -> {len(resolver_outcomes)} outcomes")

    engine_outcomes = run_engine_arm(engine_trades, args.instrument)

    print("Comparing arms...")
    comparison = compare(resolver_outcomes, engine_outcomes)

    write_report(
        Path(args.output_md), comparison=comparison, engine_provenance=engine_provenance,
        resolver_counters=resolver_counters, forward_walk_counters=fw_counters,
        engine_trades=engine_trades, corpus_path=ohlcv_path,
    )

    def _report_to_dict(r) -> dict:
        return {
            "hypothesis": r.hypothesis, "instruments": r.instruments, "n": r.n,
            "wins": r.wins, "losses": r.losses, "win_rate": r.win_rate,
            "profit_factor": (None if r.profit_factor == float("inf") else r.profit_factor),
            "profit_factor_is_inf": r.profit_factor == float("inf"),
            "expectancy_rr": r.expectancy_rr, "max_drawdown_rr": r.max_drawdown_rr,
        }

    json_out = {
        "cert_version": CERT_VERSION, "authority": "research_only",
        "engine_provenance": engine_provenance,
        "resolver_counters": resolver_counters, "forward_walk_counters": fw_counters,
        "resolver": {**{k: v for k, v in comparison["resolver"].items() if k != "report"},
                     "report": _report_to_dict(comparison["resolver"]["report"])},
        "engine": {**{k: v for k, v in comparison["engine"].items() if k != "report"},
                   "report": _report_to_dict(comparison["engine"]["report"])},
        "elapsed_s": round(time.time() - t0, 2),
    }
    out_json_path = Path(args.output_json)
    out_json_path.parent.mkdir(parents=True, exist_ok=True)
    out_json_path.write_text(json.dumps(json_out, indent=2, default=str), encoding="utf-8")
    print(f"JSON written to {out_json_path}")

    print(f"\nEngine arm: n={comparison['engine']['report'].n} "
          f"(INSUFFICIENT={comparison['engine']['insufficient']})")
    print(f"Resolver arm: n={comparison['resolver']['report'].n} "
          f"(INSUFFICIENT={comparison['resolver']['insufficient']})")
    print(f"Elapsed: {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
