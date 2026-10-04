"""
build_pattern_library.py
========================
Pattern Timing Library — aggregator (Phase 1b, measure-only).

Reads an instrument's opportunity records (the ~140k/instrument Pipeline-B
"ground truth" universe), groups them into clusters, and emits per-cluster
empirical timing + capital-efficiency distributions:

  cluster key = (direction, session, volatility_regime, geometry_bucket)

For each cluster:
  - n, win_rate, expectancy (mean rr), expectancy_per_candle  [CAPITAL EFFICIENCY]
  - reach_rate + p10/p50/p90 of time_to_{025R,05R,1R}
  - median mfe_R / mae_R
  - conditional win-rate decay: "if NOT +0.25R by candle k, win_rate -> X"
    (the early-invalidation / abnormality signal — the PRIMARY consumer contract)

The emitted JSON schema IS the contract the two (dormant, weight-0.0) consumers
read: src/scanner/ranker.py (ranking, Phase 2) and the in-trade management
surface (early-invalidation, Phase 2). This script changes NOTHING live.

Timing fields are read from the record when present (new scans) or reconstructed
offline from the candle CSV (existing files) via replay.timing_reconstructor —
identical numbers either way (shared core).

Usage:
  python scripts/analysis/build_pattern_library.py --instrument ETHUSDT \
      --opportunities logs/ETHUSDT/oos_ETHUSDT/opportunities.jsonl \
      --csv data/ETHUSDT_M15.csv
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from replay.timing_reconstructor import (  # noqa: E402
    R_LEVELS, load_candles, reconstruct_record, iter_jsonl,
)
from replay.timing_advisor import (  # noqa: E402
    geometry_bucket as _geometry_bucket, cluster_key_from_features,
)

logger = logging.getLogger("PatternLibrary")

_LEVEL_KEYS = {0.25: "time_to_025R", 0.5: "time_to_05R", 1.0: "time_to_1R"}
# Conditional-decay checkpoints (candles): the abnormality curve the
# early-invalidation consumer reads.
_DECAY_CANDLES = (1, 2, 3, 5, 8)


def _pctl(sorted_vals, p):
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    k = (len(sorted_vals) - 1) * p
    f = int(k)
    if f + 1 >= len(sorted_vals):
        return float(sorted_vals[f])
    return round(sorted_vals[f] + (sorted_vals[f + 1] - sorted_vals[f]) * (k - f), 2)


def _is_crt_like(features: dict) -> bool:
    """Coarse CRT-geometry filter for the 'this exact setup occurred N x' view:
    a structural break or a detected sweep is present."""
    return bool(
        float(features.get("break_of_structure", 0.0) or 0.0)
        or float(features.get("sweep_detected", 0.0) or 0.0)
        or float(features.get("liquidity_sweep", 0.0) or 0.0)
    )


def _cell_stats(rows: list) -> dict:
    """rows: list of dicts each with rr, dur, mfe_R, mae_R, t025, t05, t1.
    t* are candle counts or None (not reached within the trade's life)."""
    n = len(rows)
    rr = [r["rr"] for r in rows]
    wins = sum(1 for x in rr if x > 0)
    expectancy = sum(rr) / n if n else 0.0
    durs = sorted(r["dur"] for r in rows)
    med_dur = _pctl(durs, 0.5) or 0.0
    epc = (expectancy / med_dur) if med_dur else None

    levels = {}
    for lvl, key in _LEVEL_KEYS.items():
        reached = sorted(r[key] for r in rows if r[key] is not None)
        levels[key] = {
            "reach_rate": round(len(reached) / n, 4) if n else 0.0,
            "p10": _pctl(reached, 0.10),
            "p50": _pctl(reached, 0.50),
            "p90": _pctl(reached, 0.90),
        }

    # Conditional win-rate decay on the +0.25R signal (abnormality curve).
    decay = {}
    for k in _DECAY_CANDLES:
        # "not yet +0.25R by candle k" => time_to_025R is None or > k
        slow = [r for r in rows
                if r["time_to_025R"] is None or r["time_to_025R"] > k]
        fast = [r for r in rows
                if r["time_to_025R"] is not None and r["time_to_025R"] <= k]
        sw = sum(1 for r in slow if r["rr"] > 0)
        fw = sum(1 for r in fast if r["rr"] > 0)
        decay[str(k)] = {
            "n_slow": len(slow),
            "win_rate_if_not_by_k": round(sw / len(slow), 4) if slow else None,
            "n_fast": len(fast),
            "win_rate_if_by_k": round(fw / len(fast), 4) if fast else None,
        }

    mfes = sorted(r["mfe_R"] for r in rows)
    maes = sorted(r["mae_R"] for r in rows)
    return {
        "n": n,
        "win_rate": round(wins / n, 4) if n else 0.0,
        "expectancy_R": round(expectancy, 4),
        "median_resolution_candles": med_dur,
        "expectancy_per_candle": round(epc, 5) if epc is not None else None,
        "time_to": levels,
        "median_mfe_R": _pctl(mfes, 0.5),
        "median_mae_R": _pctl(maes, 0.5),
        "winrate_decay_on_025R": decay,
    }


def build(opp_path: Path, instrument: str, csv_path: "Path | None",
          *, min_cell: int, max_forward_candles: int, trail_mult: float,
          crt_filter: bool) -> dict:
    # Candle arrays only needed to backfill records that lack timing fields.
    highs = lows = closes = None
    ts_index = {}
    if csv_path and csv_path.exists():
        ts, highs, lows, closes = load_candles(csv_path)
        ts_index = {t: i for i, t in enumerate(ts)}

    cells: dict = {}
    overall_rows: list = []
    n_total = 0
    n_filtered = 0
    n_backfilled = 0
    n_skipped = 0

    for rec in iter_jsonl(opp_path):
        feats = rec.get("features", {})
        if crt_filter and not _is_crt_like(feats):
            n_filtered += 1
            continue

        # timing: prefer stored fields; else reconstruct offline.
        if "time_to_025R" in rec:
            t025, t05, t1 = rec.get("time_to_025R"), rec.get("time_to_05R"), rec.get("time_to_1R")
            dur = rec.get("duration_candles", 0)
            rr = float(rec.get("rr_achieved", 0.0))
            mfe = float(rec.get("mfe", 0.0)); mae = float(rec.get("mae", 0.0))
        elif ts_index:
            r = reconstruct_record(rec, highs, lows, closes, ts_index,
                                   max_forward_candles=max_forward_candles,
                                   trail_mult=trail_mult)
            if r is None:
                n_skipped += 1
                continue
            n_backfilled += 1
            t025, t05, t1 = r["time_to_025R"], r["time_to_05R"], r["time_to_1R"]
            dur, rr, mfe, mae = r["duration_candles"], r["rr_achieved"], r["mfe"], r["mae"]
        else:
            n_skipped += 1
            continue

        rd = abs(float(rec["entry"]) - float(rec["sl"]))
        if rd <= 0:
            n_skipped += 1
            continue
        row = {
            "rr": rr, "dur": dur,
            "mfe_R": mfe / rd, "mae_R": mae / rd,
            "time_to_025R": t025, "time_to_05R": t05, "time_to_1R": t1,
        }
        n_total += 1
        overall_rows.append(row)

        key = cluster_key_from_features(rec["direction"], feats)
        cells.setdefault(key, []).append(row)

    cell_out = {k: _cell_stats(v) for k, v in cells.items() if len(v) >= min_cell}
    thin = {k: len(v) for k, v in cells.items() if len(v) < min_cell}

    return {
        "schema": "pattern_timing_v1",
        "instrument": instrument,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(opp_path),
        "params": {
            "min_cell": min_cell,
            "max_forward_candles": max_forward_candles,
            "trail_mult": trail_mult,
            "crt_filter": crt_filter,
            "r_levels": list(R_LEVELS),
            "decay_candles": list(_DECAY_CANDLES),
        },
        "counts": {
            "n_records": n_total,
            "n_backfilled": n_backfilled,
            "n_crt_filtered_out": n_filtered,
            "n_skipped": n_skipped,
            "n_cells": len(cell_out),
            "n_thin_cells_below_min": len(thin),
        },
        "overall": _cell_stats(overall_rows) if overall_rows else {},
        "cells": cell_out,
        "thin_cells": thin,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--instrument", required=True)
    ap.add_argument("--opportunities", type=Path, default=None,
                    help="opportunities.jsonl path (file or dir). "
                         "Default: logs/{INSTRUMENT}/**/opportunities.jsonl (first found)")
    ap.add_argument("--csv", type=Path, default=None,
                    help="M15 candle CSV for offline timing backfill. "
                         "Default: data/{INSTRUMENT}_M15.csv")
    ap.add_argument("--output", type=Path, default=None,
                    help="Default: results/analysis/pattern_library_{INSTRUMENT}.json")
    ap.add_argument("--min-cell", type=int, default=30)
    ap.add_argument("--max-forward-candles", type=int, default=40)
    ap.add_argument("--trail-mult", type=float, default=0.5)
    ap.add_argument("--crt-filter", action="store_true",
                    help="Restrict to CRT-like geometry (BOS / sweep present).")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    opp = args.opportunities
    if opp is None:
        base = Path("logs") / args.instrument
        found = sorted(base.rglob("opportunities.jsonl")) if base.exists() else []
        if not found:
            ap.error(f"No opportunities.jsonl under {base}; pass --opportunities")
        opp = found[0]
    elif opp.is_dir():
        found = sorted(opp.rglob("opportunities.jsonl"))
        if not found:
            ap.error(f"No opportunities.jsonl under {opp}")
        opp = found[0]

    csv_path = args.csv or (Path("data") / f"{args.instrument}_M15.csv")
    out = args.output or (Path("results/analysis") /
                          f"pattern_library_{args.instrument}.json")
    out.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Building pattern library: instrument=%s opp=%s csv=%s",
                args.instrument, opp, csv_path)
    lib = build(opp, args.instrument, csv_path,
                min_cell=args.min_cell,
                max_forward_candles=args.max_forward_candles,
                trail_mult=args.trail_mult, crt_filter=args.crt_filter)
    out.write_text(json.dumps(lib, indent=2), encoding="utf-8")
    c = lib["counts"]
    logger.info("Wrote %s | n=%d cells=%d backfilled=%d skipped=%d",
                out, c["n_records"], c["n_cells"], c["n_backfilled"], c["n_skipped"])
    o = lib["overall"]
    logger.info("OVERALL win_rate=%.3f expectancy_R=%.3f exp/candle=%s "
                "median_res=%s", o.get("win_rate"), o.get("expectancy_R"),
                o.get("expectancy_per_candle"), o.get("median_resolution_candles"))
    print(f"OUTPUT:pattern_library:{out.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
