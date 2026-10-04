# -*- coding: utf-8 -*-
"""
build_resampled_data.py — Program 3 data prep: M15 -> {H1, H4} for the crypto majors.

Thin CLI. Reads each major's M15 CSV via the PROVEN `CandleLoader` (so the dataset
integrity/sequence guards run), aggregates with the deterministic `research.resample`
resampler, and writes `data/resampled/{INST}_{TF}.csv` in the canonical OHLCV schema
that `CandleLoader` re-reads. No statistics, no spine, no wall-clock in file content
(byte-comparable across runs).

This only produces INPUT DATA for Program 3's higher-timeframe qualification — it
touches no live-spine or research-measurement module.

Usage:
    python scripts/research/build_resampled_data.py
    python scripts/research/build_resampled_data.py --tf H1 H4 --out data/resampled
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from research.resample import resample, write_csv     # noqa: E402
from utils.console_safe import safe_print              # noqa: E402

MAJORS = ["BNBUSDT", "ETHUSDT", "BTCUSDT", "SOLUSDT"]   # same universe as qualify_majors


def _load_m15(csv_path: Path, instrument: str) -> list:
    from runtime.backtest_v2 import CandleLoader        # reuse the proven loader
    return list(CandleLoader(str(csv_path), instrument).stream())


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="build_resampled_data",
        description="Resample crypto-major M15 CSVs to higher timeframes (Program 3 prep)")
    p.add_argument("--data-dir", default="data", help="source dir holding {INST}_M15.csv")
    p.add_argument("--out", default="data/resampled", help="destination dir for {INST}_{TF}.csv")
    p.add_argument("--tf", nargs="+", default=["H1", "H4"], choices=["H1", "H4"],
                   help="target timeframes")
    p.add_argument("--instruments", nargs="+", default=MAJORS)
    args = p.parse_args(argv)

    data_dir = Path(args.data_dir)
    out_dir = Path(args.out)
    safe_print(f"build_resampled_data: {sorted(args.instruments)} -> {args.tf}  ({data_dir} -> {out_dir})\n")

    for inst in sorted(args.instruments):
        src = data_dir / f"{inst}_M15.csv"
        if not src.exists():
            raise SystemExit(f"missing source CSV: {src}")
        m15 = _load_m15(src, inst)
        for tf in args.tf:
            htf = resample(m15, tf)
            dst = out_dir / f"{inst}_{tf}.csv"
            write_csv(htf, dst)
            safe_print(f"  {inst:8s} M15 {len(m15):>7d} -> {tf} {len(htf):>6d}  {dst}")
    safe_print(f"\n-> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
