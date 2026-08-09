"""
opportunity_scanner.py
======================
Pipeline B (Research) — generates unbiased ground-truth opportunity logs.

For every candle past warmup, simulates BOTH a long and a short trade with
fixed SL = sl_atr_mult × ATR and TP = tp_atr_mult × ATR. Forward-simulates
up to max_forward_candles bars to record TP_HIT / SL_HIT / TIMEOUT outcomes.

CRT is intentionally NOT consulted. The output is the unbiased ground truth
that breaks the recursive training loop.

Output JSONL (one record per direction per candle):
  {timestamp, instrument, direction, entry, sl, tp, outcome, rr_achieved,
   duration_candles, mfe, mae, features: {...35 canonical features...}}
  rr_achieved spans [-1.0, 2.0] via 0.5R trailing stop (covers all 4 Gaussian classes).

Consumed by: scripts/training/phase5_calibration.py --opportunities
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd

# Allow running as a plain script: prepend src/ to sys.path.
_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from features.feature_pipeline import FeaturePipeline  # noqa: E402
from features.feature_schema import CANONICAL_FEATURES  # noqa: E402

logger = logging.getLogger("OpportunityScanner")


def _load_csv(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df.columns = [c.strip().lower() for c in df.columns]
    if "timestamp" not in df.columns:
        if "date" in df.columns and "time" in df.columns:
            df["timestamp"] = df["date"].astype(str) + " " + df["time"].astype(str)
        elif "date" in df.columns:
            df["timestamp"] = df["date"]
    return df


def _simulate(direction: str, entry: float, sl: float, tp: float,
              forward_bars: pd.DataFrame, risk_distance: float,
              trail_mult: float = 0.5) -> dict:
    """Forward-walk with a trailing stop (trail = trail_mult × risk_distance).

    Trail activates once price moves trail_mult×risk_distance favorably,
    then follows the peak at trail_dist behind.  This populates all 4
    Gaussian classes in rr_achieved:
      class 0 (rr < 0)      — trail/SL hit before trail activation
      class 1 (0 <= rr < 1) — trail triggered after partial favorable run
      class 2 (1 <= rr < 2) — trail triggered after deeper favorable run
      class 3 (rr >= 2)     — TP hit

    Conservative tie-break: if a single bar touches both TP and trail,
    trail (SL) wins — matches existing backtest convention.
    """
    trail_dist = trail_mult * risk_distance
    trail_stop = sl    # starts at original SL price
    peak = entry       # most favorable price seen
    mfe = 0.0
    mae = 0.0
    duration = 0

    for i, bar in enumerate(forward_bars.itertuples(index=False)):
        high = float(bar.high)
        low  = float(bar.low)

        if direction == "long":
            peak = max(peak, high)
            if peak >= entry + trail_dist:          # trail activated
                trail_stop = max(trail_stop, peak - trail_dist)
            unrealized_hi = high - entry
            unrealized_lo = low  - entry
            sl_hit = low  <= trail_stop
            tp_hit = high >= tp
        else:                                        # short
            peak = min(peak, low)
            if peak <= entry - trail_dist:          # trail activated
                trail_stop = min(trail_stop, peak + trail_dist)
            unrealized_hi = entry - low
            unrealized_lo = entry - high
            sl_hit = high >= trail_stop
            tp_hit = low  <= tp

        if unrealized_hi > mfe:
            mfe = unrealized_hi
        if unrealized_lo < mae:
            mae = unrealized_lo
        duration = i + 1

        if sl_hit:
            # If trail_stop has moved past TP, price must have crossed TP first
            # before coming back to hit the trail — honour TP.
            if (direction == "long"  and trail_stop >= tp) or \
               (direction == "short" and trail_stop <= tp):
                rr = (tp - entry) / risk_distance if direction == "long" \
                     else (entry - tp) / risk_distance
                return {
                    "outcome": "TP_HIT",
                    "rr_achieved": float(round(rr, 4)),
                    "duration_candles": duration,
                    "mfe": float(round(mfe, 6)),
                    "mae": float(round(mae, 6)),
                }
            rr = (trail_stop - entry) / risk_distance if direction == "long" \
                 else (entry - trail_stop) / risk_distance
            return {
                "outcome": "SL_HIT",
                "rr_achieved": float(round(rr, 4)),
                "duration_candles": duration,
                "mfe": float(round(mfe, 6)),
                "mae": float(round(mae, 6)),
            }
        if tp_hit:
            rr = (tp - entry) / risk_distance if direction == "long" \
                 else (entry - tp) / risk_distance
            return {
                "outcome": "TP_HIT",
                "rr_achieved": float(round(rr, 4)),
                "duration_candles": duration,
                "mfe": float(round(mfe, 6)),
                "mae": float(round(mae, 6)),
            }

    if len(forward_bars) == 0:
        unrealized = 0.0
    else:
        last_close = float(forward_bars.iloc[-1]["close"])
        unrealized = (last_close - entry) if direction == "long" else (entry - last_close)
    rr = unrealized / risk_distance if risk_distance > 0 else 0.0
    return {
        "outcome": "TIMEOUT",
        "rr_achieved": float(round(rr, 4)),
        "duration_candles": duration,
        "mfe": float(round(mfe, 6)),
        "mae": float(round(mae, 6)),
    }


def scan(csv_path: Path, instrument: str, *, tp_atr_mult: float = 2.0,
         sl_atr_mult: float = 1.0, max_forward_candles: int = 40,
         warmup_candles: int = 30, output_dir: Path = Path("logs"),
         trail_mult: float = 0.5, run_id: str = "") -> Path:
    """Scan csv_path and write opportunities JSONL.

    Output is run-scoped: {output_dir}/{instrument}/{run_id}/opportunities.jsonl
    The first line of the JSONL is a run_header record for downstream inheritance.
    run_id defaults to YYYYMMDD_HHMMSS if not provided.
    """
    import time as _time
    _run_id = run_id or _time.strftime("%Y%m%d_%H%M%S")

    if instrument.upper() == "XAUUSD":
        from data_ingestion.xauusd_phase1_candidate import guard_xauusd_csv_path
        csv_path = Path(guard_xauusd_csv_path(csv_path, instrument))

    df = _load_csv(csv_path)
    pipeline = FeaturePipeline(df)
    enriched_df, _ = pipeline.run()

    if "atr_14_raw" not in enriched_df.columns:
        raise RuntimeError(
            "FeaturePipeline did not produce atr_14_raw; SL/TP cannot be sized."
        )

    run_dir = output_dir / instrument / _run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    out_path = run_dir / "opportunities.jsonl"
    counts = {"long": 0, "short": 0, "TP_HIT": 0, "SL_HIT": 0, "TIMEOUT": 0}

    n = len(enriched_df)
    start = max(int(warmup_candles), 0)

    with out_path.open("w", encoding="utf-8") as fout:
        # First line: run_header — inherited by phase5 and compress_logs
        run_header = {
            "type":       "run_header",
            "run_id":     _run_id,
            "instrument": instrument,
            "started_at": _time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        fout.write(json.dumps(run_header) + "\n")
        for idx in range(start, n - 1):
            row = enriched_df.iloc[idx]
            atr_raw = float(row.get("atr_14_raw", 0.0) or 0.0)
            if atr_raw <= 0 or pd.isna(atr_raw):
                continue
            entry = float(row["close"])
            risk_distance = sl_atr_mult * atr_raw
            reward_distance = tp_atr_mult * atr_raw
            ts = str(row["timestamp"])

            forward_end = min(idx + 1 + int(max_forward_candles), n)
            forward_bars = enriched_df.iloc[idx + 1:forward_end]
            if forward_bars.empty:
                continue

            features = {col: float(row[col]) for col in CANONICAL_FEATURES}

            directions = (
                ("long", entry - risk_distance, entry + reward_distance),
                ("short", entry + risk_distance, entry - reward_distance),
            )
            for direction, sl, tp in directions:
                result = _simulate(direction, entry, sl, tp, forward_bars, risk_distance,
                                   trail_mult=trail_mult)
                record = {
                    "timestamp": ts,
                    "instrument": instrument,
                    "direction": direction,
                    "entry": float(entry),
                    "sl": float(sl),
                    "tp": float(tp),
                    "outcome": result["outcome"],
                    "rr_achieved": result["rr_achieved"],
                    "duration_candles": result["duration_candles"],
                    "mfe": result["mfe"],
                    "mae": result["mae"],
                    "features": features,
                }
                fout.write(json.dumps(record) + "\n")
                counts[direction] += 1
                counts[result["outcome"]] += 1

    logger.info(
        "OpportunityScanner: wrote %s | run_id=%s | long=%d short=%d | TP_HIT=%d SL_HIT=%d TIMEOUT=%d",
        out_path, _run_id, counts["long"], counts["short"],
        counts["TP_HIT"], counts["SL_HIT"], counts["TIMEOUT"],
    )
    return out_path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", required=True, type=Path,
                    help="Path to M15 OHLCV CSV (lowercased headers)")
    ap.add_argument("--instrument", required=True,
                    help="Instrument label embedded in records and filename")
    ap.add_argument("--tp-atr-mult", type=float, default=2.0)
    ap.add_argument("--sl-atr-mult", type=float, default=1.0)
    ap.add_argument("--max-forward-candles", type=int, default=40)
    ap.add_argument("--warmup-candles", type=int, default=30)
    ap.add_argument("--output-dir", type=Path, default=Path("logs"))
    ap.add_argument("--trail-mult", type=float, default=0.5,
                    help="Trailing stop distance as multiple of risk_distance "
                         "(default=0.5; 0.5R trail populates Gaussian classes 1+2)")
    ap.add_argument("--run-id", default=None,
                    help="Run identifier for output scoping. "
                         "Auto-generates YYYYMMDD_HHMMSS if not provided. "
                         "Output: {output-dir}/{instrument}/{run-id}/opportunities.jsonl")
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    import time as _time
    run_id = args.run_id or _time.strftime("%Y%m%d_%H%M%S")
    out_path = scan(
        args.csv, args.instrument,
        tp_atr_mult=args.tp_atr_mult,
        sl_atr_mult=args.sl_atr_mult,
        max_forward_candles=args.max_forward_candles,
        warmup_candles=args.warmup_candles,
        output_dir=args.output_dir,
        trail_mult=args.trail_mult,
        run_id=run_id,
    )
    print(f"OUTPUT:run_id:{run_id}")
    print(f"OUTPUT:opportunities:{out_path.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
