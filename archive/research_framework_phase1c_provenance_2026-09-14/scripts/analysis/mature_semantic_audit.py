#!/usr/bin/env python3
"""
mature_semantic_audit.py
=========================
Read-only EVIDENCE EXTRACTOR for the mature-bar semantic audit (XAUUSD M15).

Runs the STANDARD production path -- `FeaturePipeline.run()` INCLUDING `finalize()` -- and
emits every value the audit cites, for a window of fully-mature bars. This script makes NO
judgments: it extracts, verifies primitive geometry against the immutable candle_math scalars,
and writes an evidence table. The audit narrative is authored separately on top of this output,
so every figure quoted there is traceable to a real production value.

Bar numbering: 1-based RAW CSV data rows (bar 1 = first data row after the header), matching
the earlier explainability report. Bars are located in the post-finalize frame BY TIMESTAMP,
because finalize() drops warmup rows and resets the index -- a positional lookup would silently
audit the wrong candles.

Usage:
    PYTHONPATH=src python scripts/analysis/mature_semantic_audit.py
    PYTHONPATH=src python scripts/analysis/mature_semantic_audit.py --start-bar 100 --end-bar 109
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import pandas as pd

from features import candle_math
from features.feature_pipeline import FeaturePipeline
from features.feature_schema import CANONICAL_FEATURES

# Columns the audit cites. Split by audit section so the evidence table mirrors the report.
OHLCV_COLS = ["open", "high", "low", "close", "volume"]

# NOTE: upper_wick / lower_wick / price_position / candle_body are PRODUCTION-COMPUTED but are
# deliberately included here as NON-CANONICAL -- the audit's "missing semantics" section turns
# on the fact that they never reach the 39-dim vector.
PRIMITIVE_COLS = ["body_size", "candle_range", "body_ratio",
                  "upper_wick", "lower_wick", "price_position", "candle_body"]

DERIVED_COLS = ["atr", "atr_14", "atr_14_raw", "true_range", "rsi_14", "rsi_state",
                "ema_fast", "ema_slow", "ema_spread", "macd_line", "macd_signal",
                "macd_hist_raw", "macd_hist_z", "momentum_score", "trend_strength",
                "volatility_ratio", "range_size", "disp_strength",
                "volume_ratio", "volume_spike", "volume_ma20", "volume_range_proxy"]

STRUCTURE_COLS = ["swing_high", "swing_low", "higher_high", "lower_low", "break_of_structure",
                  "liquidity_sweep", "sweep_detected", "double_sweep", "retest_flag",
                  "retest_depth", "liquidity_distance", "candles_since_retest",
                  "volatility_regime", "trend_bias", "session", "hour_of_day",
                  "displacement_flag"]

# Internals the audit cites to EXPLAIN a value (e.g. why BOS latches, why the regime lags).
INTERNAL_COLS = ["prev_close", "last_swing_high_price", "last_swing_low_price",
                 "ma_20", "ma_slope_20", "delta_close"]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _native(v):
    if v is None:
        return None
    if isinstance(v, (np.floating, float)):
        v = float(v)
        return None if (v != v or v in (float("inf"), float("-inf"))) else v
    if isinstance(v, (np.integer, int)):
        return int(v)
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    return str(v)


def _verify_primitive_geometry(row) -> list:
    """Independently recompute geometry from raw OHLCV via the immutable candle_math scalars.

    A mismatch here is a REAL bug, not a rounding artifact -- the pipeline's vectorized numpy
    forms are contractually bound to these scalars (candle_math.py module docstring).
    """
    o, h, l, c = float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])
    checks = [
        ("body_size", candle_math.body_size(o, c), row.get("body_size")),
        ("candle_range", candle_math.candle_range(h, l), row.get("candle_range")),
        ("body_ratio", candle_math.body_ratio(o, h, l, c), row.get("body_ratio")),
        ("upper_wick", candle_math.upper_wick(o, h, c), row.get("upper_wick")),
        ("lower_wick", candle_math.lower_wick(o, l, c), row.get("lower_wick")),
        ("total_wick", candle_math.total_wick(o, h, l, c), None),
    ]
    out = []
    for name, scalar_val, pipeline_val in checks:
        pv = None if pipeline_val is None else float(pipeline_val)
        if pv is None:
            match = None
        else:
            match = abs(float(scalar_val) - pv) <= max(1e-6, 1e-6 * abs(pv))
        out.append({
            "quantity": name,
            "independent_scalar_value": _native(scalar_val),
            "production_column_value": _native(pv),
            "matches": match,
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default="data/mt5/XAUUSD_M15.csv")
    ap.add_argument("--start-bar", type=int, default=100,
                    help="1-based RAW CSV data row (bar 1 = first row after header). Default 100")
    ap.add_argument("--end-bar", type=int, default=109, help="inclusive. Default 109")
    ap.add_argument("--output-dir", default="results/feature_trace")
    args = ap.parse_args()

    csv_path = Path(args.csv) if Path(args.csv).is_absolute() else ROOT / args.csv
    raw = pd.read_csv(csv_path)
    csv_sha = _sha256(csv_path)

    from config_layer.production_config import get_active_version, get_prod_section
    prod_version = get_active_version()
    fp_cfg = get_prod_section("feature_pipeline")

    # ── STANDARD production path: run() INCLUDING finalize(). ──
    pipe = FeaturePipeline(raw.copy(), cfg=fp_cfg)
    df, vectors = pipe.run()
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Locate the requested RAW rows by timestamp (finalize() dropped rows + reset the index).
    raw_ts = pd.to_datetime(raw["timestamp"])
    want_ts = raw_ts.iloc[args.start_bar - 1: args.end_bar].tolist()
    ts_to_pos = {ts: i for i, ts in enumerate(df["timestamp"])}

    missing = [str(t) for t in want_ts if t not in ts_to_pos]
    if missing:
        print(f"ERROR: {len(missing)} requested bar(s) did not survive finalize() (still in "
              f"warmup?): {missing}", file=sys.stderr)
        return 1

    # Trailing ATR percentile — explains volatility_regime's relative-rank behaviour.
    w = int(fp_cfg["volatility_percentile_window"])
    roll_pct = df["atr_14"].rolling(w, min_periods=1).rank(pct=True)

    bars = []
    for offset, ts in enumerate(want_ts):
        bar_number = args.start_bar + offset
        pos = ts_to_pos[ts]
        row = df.iloc[pos]

        def grab(cols):
            return {c: _native(row[c]) for c in cols if c in df.columns}

        prev_swing_high = df["last_swing_high_price"].shift(1).iloc[pos]
        prev_swing_low = df["last_swing_low_price"].shift(1).iloc[pos]

        bars.append({
            "bar_number_raw_csv_1based": bar_number,
            "timestamp": ts.isoformat(),
            "post_finalize_row_index": int(pos),
            "ohlcv": grab(OHLCV_COLS),
            "primitive_geometry": grab(PRIMITIVE_COLS),
            "primitive_geometry_independent_check": _verify_primitive_geometry(row),
            "derived": grab(DERIVED_COLS),
            "structure": grab(STRUCTURE_COLS),
            "internals": {
                **grab(INTERNAL_COLS),
                "prev_last_swing_high_price": _native(prev_swing_high),
                "prev_last_swing_low_price": _native(prev_swing_low),
                "atr_14_trailing_percentile": _native(roll_pct.iloc[pos]),
                "atr_14_percentile_window": w,
                "rows_preceding_in_finalized_frame": int(pos),
            },
            "canonical_vector": [_native(row[c]) for c in CANONICAL_FEATURES],
        })

    # Columns computed by production but absent from the 39-dim vector (missing-semantics basis).
    computed_non_canonical = sorted(
        c for c in df.columns
        if c not in CANONICAL_FEATURES and c != "timestamp"
        and pd.api.types.is_numeric_dtype(df[c])
    )

    payload = {
        "generator": "scripts/analysis/mature_semantic_audit.py",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_csv": str(csv_path),
        "source_csv_sha256": csv_sha,
        "prod_config_version": prod_version,
        "production_path": "FeaturePipeline.run() INCLUDING finalize()",
        "raw_rows": int(len(raw)),
        "post_finalize_rows": int(len(df)),
        "warmup_rows_dropped": int(len(raw) - len(df)),
        "bar_numbering": "1-based RAW CSV data rows; located post-finalize by timestamp",
        "window": {"start_bar": args.start_bar, "end_bar": args.end_bar,
                   "first_timestamp": want_ts[0].isoformat(),
                   "last_timestamp": want_ts[-1].isoformat()},
        "canonical_feature_count": len(CANONICAL_FEATURES),
        "computed_but_non_canonical_columns": computed_non_canonical,
        "bars": bars,
    }

    out_dir = Path(args.output_dir) if Path(args.output_dir).is_absolute() else ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"mature_semantic_audit_evidence_bars_{args.start_bar:04d}_{args.end_bar:04d}"
    json_path = out_dir / f"{stem}.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # Flat CSV companion for eyeballing the window as a table.
    flat = []
    for b in bars:
        rec = {"bar": b["bar_number_raw_csv_1based"], "timestamp": b["timestamp"]}
        rec.update(b["ohlcv"]); rec.update(b["primitive_geometry"])
        rec.update(b["derived"]); rec.update(b["structure"])
        rec["prev_last_swing_high_price"] = b["internals"]["prev_last_swing_high_price"]
        rec["prev_last_swing_low_price"] = b["internals"]["prev_last_swing_low_price"]
        rec["atr_14_trailing_percentile"] = b["internals"]["atr_14_trailing_percentile"]
        flat.append(rec)
    csv_out = out_dir / f"{stem}.csv"
    pd.DataFrame(flat).to_csv(csv_out, index=False)

    # Geometry-verification summary (a mismatch is a real bug, surfaced loudly).
    bad = [(b["bar_number_raw_csv_1based"], chk["quantity"])
           for b in bars for chk in b["primitive_geometry_independent_check"]
           if chk["matches"] is False]
    print(f"Wrote {json_path}")
    print(f"Wrote {csv_out}")
    print(f"Window: bars {args.start_bar}-{args.end_bar} "
          f"({want_ts[0]} -> {want_ts[-1]}), {len(bars)} bars, all present post-finalize.")
    print(f"Post-finalize rows: {len(df)}/{len(raw)} (warmup dropped: {len(raw) - len(df)})")
    print(f"Primitive-geometry independent check: "
          f"{'ALL MATCH' if not bad else f'MISMATCHES {bad}'}")
    print(f"Computed-but-non-canonical numeric columns: {len(computed_non_canonical)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
