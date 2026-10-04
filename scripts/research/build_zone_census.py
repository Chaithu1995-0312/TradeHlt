#!/usr/bin/env python3
"""CLI: full-corpus HistoricalZoneMapper census (occupancy / dwell / transitions)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Zone geometry census over OHLCV corpus")
    ap.add_argument(
        "--csv",
        default="data/mt5/XAUUSD_M15.csv",
        help="OHLCV CSV (default: Phase-1 XAUUSD M15)",
    )
    ap.add_argument("--instrument", default="XAUUSD")
    ap.add_argument(
        "--out-dir",
        default="results/zone_maps",
        help="Output directory for census JSON/MD",
    )
    ap.add_argument("--stem", default="xauusd_phase1_zone_census")
    ap.add_argument(
        "--guard-xauusd",
        action="store_true",
        default=True,
        help="Fail-closed Phase-1 XAUUSD path guard (default on)",
    )
    ap.add_argument("--no-guard-xauusd", action="store_true")
    args = ap.parse_args()

    csv_path = args.csv
    if not args.no_guard_xauusd and args.instrument.upper() == "XAUUSD":
        from data_ingestion.xauusd_phase1_candidate import guard_xauusd_csv_path

        csv_path = str(guard_xauusd_csv_path(csv_path, "XAUUSD"))

    from research.zone_mapping.build_corpus_zone_map import (
        map_corpus_frame,
        write_census_artifacts,
    )

    print(f"Mapping corpus {csv_path} …", flush=True)
    _records, census = map_corpus_frame(csv_path, instrument=args.instrument)
    paths = write_census_artifacts(census, args.out_dir, stem=args.stem)
    print(f"n_bars={census['n_bars']} passed_pct={census['passed_threshold_pct']:.2f}")
    for z, row in (census.get("per_zone") or {}).items():
        print(
            f"  {z}: n={row['n_bars']} cov={row['coverage_pct']:.2f}% "
            f"mean_score={row['mean_cluster_score']} mean_dwell={row['mean_dwell_length']}"
        )
    print(f"wrote {paths['json']}")
    if "md" in paths:
        print(f"wrote {paths['md']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
