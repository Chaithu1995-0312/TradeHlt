"""shape_statistics_survey.py — CLI wrapper for the Historical Statistics layer.

Thin wrapper per conventions: all logic lives in src/research/shape_statistics.py.

Usage:
    python scripts/research/shape_statistics_survey.py --csv data/XAUUSD_W2026-03-23-to-2026-05-21.csv \
        --horizons 4 8 20 --min-samples 30 [--out results/research/shape_stats_xauusd.json]

Output is DESCRIPTIVE ONLY (Authority-Ladder Level ≤ 1). An interesting cell is a reason to run
the M4 qualification gate — never a reason to touch production.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src"))

import pandas as pd  # noqa: E402

from research.shape_statistics import ShapeStatisticsBuilder  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", required=True, help="OHLCV CSV with a timestamp column")
    ap.add_argument("--horizons", required=True, type=int, nargs="+",
                    help="forward horizons in bars, strictly increasing (e.g. 4 8 20)")
    ap.add_argument("--min-samples", required=True, type=int,
                    help="cell floor below which insufficient=True (repo convention: 30)")
    ap.add_argument("--out", default=None, help="optional JSON output path")
    args = ap.parse_args()

    raw = pd.read_csv(args.csv)
    profile = ShapeStatisticsBuilder().profile(
        raw, horizons=tuple(args.horizons), min_samples=args.min_samples
    )

    d = profile.to_dict()
    print(f"bars_raw={d['bars_raw']} usable={d['bars_usable']} "
          f"excluded={d['excluded']} x_marker_bars={d['x_marker_bars']}")
    for h in profile.horizons:
        print(f"\n== horizon {h} bars (ATR units; * = insufficient n<{profile.min_samples}) ==")
        rows = []
        for fam, cells in profile.by_family.items():
            if h not in cells:
                continue
            c = cells[h]
            rows.append((fam, c))
        rows.sort(key=lambda r: -r[1].n)
        print(f"  {'family':22s} {'n':>5s} {'fwd_mean':>9s} {'pct_pos':>8s} "
              f"{'up_exc':>7s} {'dn_exc':>7s}")
        for fam, c in rows:
            star = "*" if c.insufficient else " "
            print(f"  {fam:22s} {c.n:5d}{star} {c.fwd_ret_mean:+9.4f} {c.pct_positive:8.3f} "
                  f"{c.up_exc_mean:7.3f} {c.down_exc_mean:7.3f}")

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(d, indent=2), encoding="utf-8")
        print(f"\nwritten -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
