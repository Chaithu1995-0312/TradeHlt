#!/usr/bin/env python3
"""SECONDLOW-v1 count-only audit on the canonical MT5 corpus."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from research.secondlow_v1.corpus import CANONICAL_XAUUSD_M15
from research.secondlow_v1.detector import (
    DISCOVERY_END,
    DISCOVERY_START,
    detect_independent_events,
    load_ohlcv,
    partition_event_times,
    sha256_prefix,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="SECONDLOW-v1 count-only full corpus audit")
    parser.add_argument(
        "--csv",
        type=Path,
        default=_REPO_ROOT / CANONICAL_XAUUSD_M15,
        help="Canonical MT5 XAUUSD M15 CSV (default: data/XAUUSD_M15.csv)",
    )
    args = parser.parse_args()
    corpus = args.csv.resolve()

    print("=" * 90)
    print("SECONDLOW-v1 Count-Only Full Corpus Audit (trading-day second_low_20d)")
    print("=" * 90)

    df = load_ohlcv(corpus)
    print(f"\nSource: {corpus}")
    print(f"Source SHA256 prefix: {sha256_prefix(corpus)}")
    print(f"Total rows: {len(df)}")
    print(f"Period: {df.index[0]} -> {df.index[-1]}")

    daily = df.groupby(df.index.normalize()).agg(Low=("low", "min"))
    calendar_span = len(
        __import__("pandas").date_range(daily.index.min(), daily.index.max(), freq="D")
    )
    print(f"\nTrading days with bars: {len(daily)}")
    print(f"Calendar days in span:  {calendar_span}")
    print(f"No-bar calendar days:   {calendar_span - len(daily)}")

    raw_mask, events = detect_independent_events(df)
    raw_total = int(raw_mask.sum())
    ind_times = [e.purge_time for e in events]
    ind_total = len(ind_times)

    print(f"\nRAW_EVENTS_TOTAL: {raw_total}")
    print(f"INDEPENDENT_EVENTS_TOTAL: {ind_total}")

    parts = partition_event_times(ind_times)
    pre, disc, post = parts["pre_discovery"], parts["discovery"], parts["post_discovery"]

    print("\n--- Partitioned Counts ---")
    print(f"PRE_DISCOVERY   (< {DISCOVERY_START.date()}): {len(pre)}")
    print(f"DISCOVERY       ({DISCOVERY_START.date()} to {DISCOVERY_END.date()}): {len(disc)}")
    print(f"POST_DISCOVERY  (> {DISCOVERY_END.date()}): {len(post)}")

    print("\n--- Invariants ---")
    print(f"INDEPENDENT_TOTAL == PRE + DISC + POST: {ind_total == len(pre) + len(disc) + len(post)}")

    if pre:
        print(f"\nFirst PRE_DISCOVERY event: {min(pre)}")
        print(f"Last  PRE_DISCOVERY event: {max(pre)}")
    else:
        print("\nNo PRE_DISCOVERY events found.")

    print("\n[Audit Complete]")


if __name__ == "__main__":
    main()