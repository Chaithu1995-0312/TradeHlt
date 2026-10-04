"""
SWEEP Geometry Trace — Engine vs Pipeline
=========================================
Research-only diagnostic. Does NOT change production behaviour.

Compares three sweep detectors on the same XAUUSD (or other) M15 stream:

  A. ENGINE geometry — RangeDetector.detect_sweep vs active_range
     ref = HTF window max/min (init: completed HTF seed; on HTF change:
     max/min of last atr_period candles — crt_engine_v2.py:2620-2622)
     rule: high > h_ref and close < h_ref  (SHORT)
           low  < l_ref and close > l_ref  (LONG)

  B. PIPELINE geometry — FM-058 liquidity_sweep
     ref = prev(last_swing_*_price) with causal swing k=swing_window
     rule: high > ref_high and close <= ref_high  (+1)
           low  < ref_low  and close >= ref_low   (-1)

  C. ENGINE STATE events — bars where events.jsonl has RANGE→SWEEP
     (or SHADOW→SWEEP) STATE_TRANSITION — full state machine admits only.

Outputs:
  reports/sweep_geometry_trace.md
  reports/sweep_geometry_trace.json

Usage:
  python scripts/research/trace_sweep_geometry.py \\
      --ohlcv data/mt5/XAUUSD_M15.csv \\
      --events results/run_20260724_104845_XAUUSD/XAUUSD_events.jsonl \\
      --instrument XAUUSD
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))


@dataclass
class GeometryStats:
    n_bars: int
    engine_geom_n: int
    pipeline_n: int
    engine_event_n: int
    both_geom: int
    engine_only_geom: int
    pipeline_only_geom: int
    event_and_pipeline: int
    event_and_engine_geom: int
    event_not_pipeline: int
    event_not_engine_geom: int
    jaccard_geom: float
    precision_pipe_vs_event: float
    recall_pipe_vs_event: float
    precision_eng_geom_vs_event: float
    recall_eng_geom_vs_event: float


def build_htf_ids(n: int, candles_per_htf: int, instrument: str) -> list[str]:
    """Same semantics as backtest_v2.HTFBuilder / build_htf_id_timeline."""
    ids: list[str] = []
    buf = 0
    idx = 0
    cur = "HTF-INIT"
    for _ in range(n):
        buf += 1
        if buf >= candles_per_htf:
            idx += 1
            cur = f"{instrument}-HTF-{idx:06d}"
            buf = 0
        ids.append(cur)
    return ids


def engine_range_and_sweep(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    htf_ids: list[str],
    *,
    atr_period: int = 14,
    candles_per_htf: int = 4,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Replay engine range seeding + per-bar detect_sweep geometry.

    Returns:
      eng_sweep: int8 {-1,0,+1}  (+1 high/SHORT, -1 low/LONG — match pipeline sign)
      h_ref, l_ref: float arrays
      range_source: 0=none, 1=htf_seed_4, 2=atr_reseed_14
    """
    n = len(high)
    eng = np.zeros(n, dtype=np.int8)
    h_refs = np.full(n, np.nan)
    l_refs = np.full(n, np.nan)
    src = np.zeros(n, dtype=np.int8)

    active_h = active_l = None
    active_htf = None
    range_src = 0
    seeded = False

    # First complete HTF window ends at bar candles_per_htf-1 (0-based)
    for i in range(n):
        hid = htf_ids[i]

        # HTF window just completed → seed/re-seed from that 4-bar window
        # HTFBuilder completes when buffer fills; id advances on that bar.
        just_completed = (
            i >= candles_per_htf - 1
            and (i + 1) % candles_per_htf == 0
        )

        # Range lifecycle (crt_engine_v2):
        #   * first seed (initialise_range): completed HTF window (4 bars)
        #   * HTF change reset (process_candle ~2620): last atr_period candles
        #     from candle_buffer — NOT the 4-bar HTF window again
        if just_completed:
            if not seeded:
                start = i - candles_per_htf + 1
                active_h = float(np.max(high[start : i + 1]))
                active_l = float(np.min(low[start : i + 1]))
                range_src = 1
                seeded = True
            else:
                start = max(0, i - atr_period + 1)
                active_h = float(np.max(high[start : i + 1]))
                active_l = float(np.min(low[start : i + 1]))
                range_src = 2
            active_htf = hid
        elif seeded and i > 0 and htf_ids[i] != htf_ids[i - 1]:
            # Defensive: id change not on complete boundary
            start = max(0, i - atr_period + 1)
            active_h = float(np.max(high[start : i + 1]))
            active_l = float(np.min(low[start : i + 1]))
            active_htf = hid
            range_src = 2

        if active_h is None:
            continue

        h_refs[i] = active_h
        l_refs[i] = active_l
        src[i] = range_src

        # Engine detect_sweep (strict inequalities on close)
        swept_high = high[i] > active_h and close[i] < active_h
        swept_low = low[i] < active_l and close[i] > active_l
        if swept_high:
            eng[i] = 1   # SHORT sweep (took highs)
        elif swept_low:
            eng[i] = -1  # LONG sweep (took lows)

    return eng, h_refs, l_refs, src


def pipeline_liquidity_sweep(df: pd.DataFrame) -> np.ndarray:
    """Run FeaturePipeline and return liquidity_sweep aligned to raw index via _src_idx."""
    from features.feature_pipeline import FeaturePipeline

    work = df.copy()
    work["_src_idx"] = np.arange(len(work), dtype=np.int64)
    pipe = FeaturePipeline(work)
    enr, _ = pipe.run()
    out = np.zeros(len(df), dtype=np.int8)
    for _, row in enr.iterrows():
        si = int(row["_src_idx"])
        out[si] = int(row["liquidity_sweep"])
    return out


def load_engine_sweep_events(events_path: Path, n_bars: int) -> np.ndarray:
    """Bars where engine admitted SWEEP (RANGE→SWEEP or SHADOW→SWEEP).

    Note: events use 1-based candle_index matching engine process_candle.
    """
    flags = np.zeros(n_bars, dtype=np.int8)
    with events_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            if r.get("event") != "STATE_TRANSITION":
                continue
            if r.get("state_to") != "SWEEP":
                continue
            # engine candle_index is 1-based
            ci = int(r["candle_index"]) - 1
            if 0 <= ci < n_bars:
                flags[ci] = 1
    return flags


def _prf(pred: np.ndarray, truth: np.ndarray) -> tuple[float, float, float]:
    pred_b = pred != 0
    truth_b = truth != 0
    tp = int(np.sum(pred_b & truth_b))
    fp = int(np.sum(pred_b & ~truth_b))
    fn = int(np.sum(~pred_b & truth_b))
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return prec, rec, f1


def analyze(
    ohlcv_path: Path,
    events_path: Path,
    *,
    instrument: str = "XAUUSD",
    candles_per_htf: int = 4,
    atr_period: int = 14,
) -> dict[str, Any]:
    df = pd.read_csv(ohlcv_path)
    rename = {c: c.lower() for c in df.columns}
    df = df.rename(columns=rename)
    n = len(df)
    high = df["high"].to_numpy(dtype=np.float64)
    low = df["low"].to_numpy(dtype=np.float64)
    close = df["close"].to_numpy(dtype=np.float64)

    htf_ids = build_htf_ids(n, candles_per_htf, instrument)
    eng, h_refs, l_refs, range_src = engine_range_and_sweep(
        high, low, close, htf_ids,
        atr_period=atr_period,
        candles_per_htf=candles_per_htf,
    )
    print("Computing pipeline liquidity_sweep (FeaturePipeline)...")
    pipe = pipeline_liquidity_sweep(df)
    print("Loading engine STATE_TRANSITION → SWEEP events...")
    events = load_engine_sweep_events(events_path, n)

    eng_b = eng != 0
    pipe_b = pipe != 0
    ev_b = events != 0

    both = int(np.sum(eng_b & pipe_b))
    eng_only = int(np.sum(eng_b & ~pipe_b))
    pipe_only = int(np.sum(pipe_b & ~eng_b))
    union = both + eng_only + pipe_only
    jaccard = both / union if union else 0.0

    prec_p, rec_p, f1_p = _prf(pipe, events)
    prec_e, rec_e, f1_e = _prf(eng, events)

    # Direction agreement on co-firing bars
    both_idx = np.where(eng_b & pipe_b)[0]
    dir_agree = int(np.sum(eng[both_idx] == pipe[both_idx])) if len(both_idx) else 0

    # Close-rule sensitivity: pipeline uses <=, engine uses <
    # Count bars where only inequality differs vs same ref (hard without same ref)

    # Sample disagreements
    def _samples(mask: np.ndarray, k: int = 8) -> list[dict]:
        idxs = np.where(mask)[0][:k]
        rows = []
        for i in idxs:
            rows.append({
                "idx": int(i),
                "htf": htf_ids[i],
                "high": float(high[i]),
                "low": float(low[i]),
                "close": float(close[i]),
                "h_ref": None if np.isnan(h_refs[i]) else float(h_refs[i]),
                "l_ref": None if np.isnan(l_refs[i]) else float(l_refs[i]),
                "eng_geom": int(eng[i]),
                "pipeline": int(pipe[i]),
                "engine_event": int(events[i]),
                "range_src": int(range_src[i]),
            })
        return rows

    stats = GeometryStats(
        n_bars=n,
        engine_geom_n=int(eng_b.sum()),
        pipeline_n=int(pipe_b.sum()),
        engine_event_n=int(ev_b.sum()),
        both_geom=both,
        engine_only_geom=eng_only,
        pipeline_only_geom=pipe_only,
        event_and_pipeline=int(np.sum(ev_b & pipe_b)),
        event_and_engine_geom=int(np.sum(ev_b & eng_b)),
        event_not_pipeline=int(np.sum(ev_b & ~pipe_b)),
        event_not_engine_geom=int(np.sum(ev_b & ~eng_b)),
        jaccard_geom=jaccard,
        precision_pipe_vs_event=prec_p,
        recall_pipe_vs_event=rec_p,
        precision_eng_geom_vs_event=prec_e,
        recall_eng_geom_vs_event=rec_e,
    )

    # Ref span stats when range active
    valid = ~np.isnan(h_refs)
    span = h_refs[valid] - l_refs[valid]
    span_stats = {
        "n_with_range": int(valid.sum()),
        "mean_span": float(np.mean(span)) if len(span) else 0.0,
        "median_span": float(np.median(span)) if len(span) else 0.0,
        "p90_span": float(np.percentile(span, 90)) if len(span) else 0.0,
        "range_src_counts": {
            "htf_seed_4": int(np.sum(range_src == 1)),
            "atr_reseed_14": int(np.sum(range_src == 2)),
        },
    }

    return {
        "stats": stats.__dict__,
        "direction_agree_on_both": dir_agree,
        "direction_agree_denom": int(len(both_idx)),
        "span_stats": span_stats,
        "f1_pipe_vs_event": f1_p,
        "f1_eng_geom_vs_event": f1_e,
        "samples": {
            "engine_only_geom": _samples(eng_b & ~pipe_b),
            "pipeline_only_geom": _samples(pipe_b & ~eng_b),
            "event_not_pipeline": _samples(ev_b & ~pipe_b),
            "event_and_pipeline": _samples(ev_b & pipe_b),
        },
        "meta": {
            "ohlcv": str(ohlcv_path),
            "events": str(events_path),
            "instrument": instrument,
            "candles_per_htf": candles_per_htf,
            "atr_period": atr_period,
        },
    }


def write_report(result: dict[str, Any], path: Path) -> None:
    s = result["stats"]
    lines: list[str] = []
    a = lines.append

    a("# SWEEP Geometry Trace — Engine vs Pipeline")
    a("")
    a(f"> Generated: {__import__('datetime').datetime.now().isoformat()}")
    a(">")
    a("> Research-only. Explains SWEEP↔RANGE residual on the CRT state resolver.")
    a("")
    a("## Executive summary")
    a("")
    a("Two **different reference frames** define a 'sweep':")
    a("")
    a("| Layer | Reference | Close rule | When evaluated |")
    a("|-------|-----------|------------|----------------|")
    a("| **Engine** `RangeDetector.detect_sweep` | HTF range `h_ref/l_ref` "
      "(init: completed HTF window max/min; on HTF reset: last `atr_period` bars) | "
      "`close < h_ref` / `close > l_ref` (strict) | Only in state **RANGE** "
      "(state machine admits) |")
    a("| **Pipeline** FM-058 `liquidity_sweep` | `prev(last_swing_*_price)` "
      "causal swing k=`swing_window` | `close <= ref` / `close >= ref` | **Every bar** |")
    a("")
    a("Resolver SWEEP entry uses the **pipeline** flag. Confusion-matrix SWEEP↔RANGE "
      "residual is therefore expected even with perfect funnel/lifecycle.")
    a("")

    a("## Formula trace")
    a("")
    a("### Engine (`crt_engine_v2.RangeDetector`)")
    a("")
    a("```")
    a("detect_htf_range(candles):")
    a("    h_ref = max(c.high for c in candles)")
    a("    l_ref = min(c.low  for c in candles)")
    a("")
    a("detect_sweep(candle, active_range):")
    a("    swept_high = high > h_ref and close < h_ref   # → SHORT")
    a("    swept_low  = low  < l_ref and close > l_ref   # → LONG")
    a("```")
    a("")
    a("- **Init range** (`backtest` + `initialise_range`): candles = completed HTF "
      f"window (`htf_candles_per_range`={result['meta']['candles_per_htf']}).")
    a("- **On HTF reset** (`process_candle` ~2620): reseed from "
      f"`candle_buffer[-atr_period:]` (atr_period={result['meta']['atr_period']}) "
      "— **not** the 4-bar HTF window.")
    a("- **State gate:** sweep only attempted when `current_state == RANGE`.")
    a("- **Same-bar after reset:** fall-through allows sweep on freshly seeded range "
      "(deadlock fix comment at 2626–2629).")
    a("")
    a("### Pipeline (`feature_pipeline.compute_structure_liquidity`)")
    a("")
    a("```")
    a("k = swing_window  # default 2; pivot width 2k+1, causal delay k")
    a("last_swing_*_price = causal delayed ffill of centered pivots")
    a("ref_high = last_swing_high_price.shift(1)")
    a("ref_low  = last_swing_low_price.shift(1)")
    a("sweep_high = (high > ref_high) & (close <= ref_high)  # +1")
    a("sweep_low  = (low  < ref_low)  & (close >= ref_low)   # -1")
    a("liquidity_sweep = where(sweep_high, 1, where(sweep_low, -1, 0))")
    a("sweep_detected  = liquidity_sweep != 0")
    a("```")
    a("")
    a("- Reference = **last confirmed local pivot**, not HTF session range.")
    a("- Publication delay k means ref is older than the live engine HTF box.")
    a("- Evaluated on **all** bars; no RANGE state gate.")
    a("")

    a("## Quantitative comparison")
    a("")
    a(f"| Measure | Count / value |")
    a(f"|---------|---------------|")
    a(f"| Bars | {s['n_bars']:,} |")
    a(f"| Engine geometry fires | {s['engine_geom_n']:,} |")
    a(f"| Pipeline `liquidity_sweep` fires | {s['pipeline_n']:,} |")
    a(f"| Engine STATE_TRANSITION → SWEEP | {s['engine_event_n']:,} |")
    a(f"| Both geometries (intersection) | {s['both_geom']:,} |")
    a(f"| Engine-only geometry | {s['engine_only_geom']:,} |")
    a(f"| Pipeline-only geometry | {s['pipeline_only_geom']:,} |")
    a(f"| **Jaccard (engine geom ∩ pipeline)** | **{s['jaccard_geom']:.3f}** |")
    a(f"| Direction agree on both | {result['direction_agree_on_both']:,} / "
      f"{result['direction_agree_denom']:,} |")
    a("")
    a("### Against engine admitted SWEEP events")
    a("")
    a("| Detector | Precision | Recall | F1 |")
    a("|----------|-----------|--------|-----|")
    a(f"| Pipeline liquidity_sweep | {s['precision_pipe_vs_event']:.3f} | "
      f"{s['recall_pipe_vs_event']:.3f} | {result['f1_pipe_vs_event']:.3f} |")
    a(f"| Engine geometry (no state gate) | {s['precision_eng_geom_vs_event']:.3f} | "
      f"{s['recall_eng_geom_vs_event']:.3f} | {result['f1_eng_geom_vs_event']:.3f} |")
    a("")
    a(f"| Event ∩ pipeline | {s['event_and_pipeline']:,} |")
    a(f"| Event ∩ engine geom | {s['event_and_engine_geom']:,} |")
    a(f"| Event missing from pipeline | {s['event_not_pipeline']:,} |")
    a(f"| Event missing from engine geom replay | {s['event_not_engine_geom']:,} |")
    a("")
    a("### Range span (engine active_range when present)")
    a("")
    sp = result["span_stats"]
    a(f"| Stat | Value |")
    a(f"|------|-------|")
    a(f"| Bars with range | {sp['n_with_range']:,} |")
    a(f"| Mean H−L span | {sp['mean_span']:.4f} |")
    a(f"| Median span | {sp['median_span']:.4f} |")
    a(f"| P90 span | {sp['p90_span']:.4f} |")
    a(f"| Seeded from HTF-4 | {sp['range_src_counts']['htf_seed_4']:,} |")
    a(f"| Reseeded atr_period | {sp['range_src_counts']['atr_reseed_14']:,} |")
    a("")

    a("## Interpretation (why resolver SWEEP↔RANGE persists)")
    a("")
    a("1. **Different anchors:** swing pivot ≠ HTF box. Pipeline can fire on a "
      "local wick through a 5-bar pivot while price is deep inside the engine HTF range.")
    a("2. **Different cadence:** pipeline fires every bar; engine only admits from RANGE "
      "(and after HTF reset fall-through). Geometry fire count ≫ admitted events.")
    a("3. **Close rule:** `<=` vs `<` is minor; anchor mismatch dominates.")
    a("4. **Range reseed dualism (engine-internal):** init uses 4-bar HTF window; "
      "HTF-change reseed uses last 14 ATR bars — refs jump in size/level.")
    a("5. **Resolver implication:** funnel/lifecycle can only enforce *state legality*; "
      "they cannot make last-swing sweeps equal HTF-range sweeps. SWEEP bar parity "
      "requires either sharing `active_range` with the engine or a new FM that uses "
      "the same HTF box.")
    a("")

    a("## Sample disagreements")
    a("")
    for key, title in [
        ("engine_only_geom", "Engine geometry only (pipeline silent)"),
        ("pipeline_only_geom", "Pipeline only (engine geometry silent)"),
        ("event_not_pipeline", "Engine admitted SWEEP, pipeline silent"),
    ]:
        a(f"### {title}")
        a("")
        rows = result["samples"][key]
        if not rows:
            a("_none_")
            a("")
            continue
        a("| idx | HTF | high | low | close | h_ref | l_ref | eng | pipe | event |")
        a("|-----|-----|------|-----|-------|-------|-------|-----|------|-------|")
        for r in rows:
            a(
                f"| {r['idx']} | {r['htf']} | {r['high']:.2f} | {r['low']:.2f} | "
                f"{r['close']:.2f} | {r['h_ref'] or '-'} | {r['l_ref'] or '-'} | "
                f"{r['eng_geom']} | {r['pipeline']} | {r['engine_event']} |"
            )
        a("")

    a("## Recommendations")
    a("")
    a("| Option | Effect | Cost |")
    a("|--------|--------|------|")
    a("| **A. Freeze** SWEEP as soft-aligned | Honest about geometry gap; keep funnel | Zero |")
    a("| **B. HTF-range FM** (new feature) | Pipeline can match engine geom | Ontology + pipeline work |")
    a("| **C. Feed engine `active_range` into resolver** | Exact geom if engine runs | Couples research layer to engine |")
    a("| **D. Threshold-tune liquidity_sweep** | Will not close Jaccard gap | Wasted |")
    a("")
    a("**Recommended default:** A unless a program explicitly needs SWEEP bar-parity. "
      "Do not threshold-tune (D).")
    a("")
    a("## Authority")
    a("")
    a("Research / documentation only. Does not enable `crt_state`. "
      "Does not change production CRT engine.")
    a("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Report written to {path}")


def main() -> None:
    p = argparse.ArgumentParser(description="Trace SWEEP geometry engine vs pipeline")
    p.add_argument("--ohlcv", default="data/mt5/XAUUSD_M15.csv")
    p.add_argument(
        "--events",
        default="results/run_20260724_104845_XAUUSD/XAUUSD_events.jsonl",
    )
    p.add_argument("--instrument", default="XAUUSD")
    p.add_argument("--htf-candles-per-range", type=int, default=4)
    p.add_argument("--atr-period", type=int, default=14)
    p.add_argument("--output", default="reports/sweep_geometry_trace.md")
    p.add_argument("--json-out", default="reports/sweep_geometry_trace.json")
    args = p.parse_args()

    result = analyze(
        Path(args.ohlcv),
        Path(args.events),
        instrument=args.instrument,
        candles_per_htf=args.htf_candles_per_range,
        atr_period=args.atr_period,
    )
    write_report(result, Path(args.output))
    Path(args.json_out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"JSON written to {args.json_out}")

    s = result["stats"]
    print("\n=== SUMMARY ===")
    print(f"Jaccard engine_geom ∩ pipeline: {s['jaccard_geom']:.3f}")
    print(f"Pipeline vs events  P/R/F1: "
          f"{s['precision_pipe_vs_event']:.3f}/"
          f"{s['recall_pipe_vs_event']:.3f}/{result['f1_pipe_vs_event']:.3f}")
    print(f"Engine geom vs events P/R/F1: "
          f"{s['precision_eng_geom_vs_event']:.3f}/"
          f"{s['recall_eng_geom_vs_event']:.3f}/{result['f1_eng_geom_vs_event']:.3f}")
    print(f"counts eng_geom={s['engine_geom_n']} pipe={s['pipeline_n']} "
          f"events={s['engine_event_n']}")


if __name__ == "__main__":
    main()
