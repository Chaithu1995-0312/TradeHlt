#!/usr/bin/env python3
"""Session + regime descriptives on incremental events from R2 / R4 — no outcomes."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from research.secondlow_v1.corpus import CANONICAL_XAUUSD_M15
from research.secondlow_v1.detector import (
    _detect_raw_purge_mask,
    _independent_indices,
    compute_trading_day_second_low,
    detect_independent_events,
    load_ohlcv,
    sha256_prefix,
)
from research.secondlow_v1.regime_metrics import regime_metrics_at_purge

OUTPUT = _REPO / "H-SECONDLOW-002_Complete_Package/results/relaxation_count_diagnostic"


def assign_session(ts: pd.Timestamp) -> str:
    h = ts.hour
    if 0 <= h < 7:
        return "ASIA"
    if 7 <= h < 12:
        return "LONDON"
    if 12 <= h < 16:
        return "OVERLAP"
    if 16 <= h < 21:
        return "NY"
    return "LATE"


def independent_times(df: pd.DataFrame, *, lookback: int, spacing: int) -> list[pd.Timestamp]:
    work = df.copy()
    work["sl"] = compute_trading_day_second_low(work, lookback=lookback)
    raw = _detect_raw_purge_mask(work, "sl")
    idx = _independent_indices(work.index, raw, min_spacing_min=spacing)
    return [work.index[i] for i in idx]


def describe_times(df: pd.DataFrame, times: list[pd.Timestamp], events_by_time: dict) -> list[dict]:
    rows = []
    for t in times:
        e = events_by_time.get(t)
        pos = df.index.get_loc(t)
        reg = regime_metrics_at_purge(df, pos)
        row = {
            "purge_time": str(t),
            "session": assign_session(t),
            "purge_depth_atr": round(e.purge_depth_atr, 4) if e else None,
            "pre_2h_return_atr": round(e.pre_2h_return_atr, 4) if e else None,
        }
        if reg:
            row.update(
                {
                    "atr_ratio_14_over_100": round(reg.atr_ratio_14_over_100, 4),
                    "binary_high_atr_ratio_1_2": reg.binary_high_atr_ratio_1_2,
                }
            )
        rows.append(row)
    return rows


def main() -> None:
    corpus = _REPO / CANONICAL_XAUUSD_M15
    df = load_ohlcv(corpus)
    _, events36 = detect_independent_events(df, require_post_window=False)
    by_time = {e.purge_time: e for e in events36}

    baseline_exp = {e.purge_time for e in events36 if e.pre_2h_return_atr <= -1.5 and e.purge_depth_atr >= 1.0}
    r2_exp = {e.purge_time for e in events36 if e.purge_depth_atr >= 1.0}
    r2_incremental = sorted(r2_exp - baseline_exp)

    base_times = set(independent_times(df, lookback=20, spacing=120))
    r4_times = set(independent_times(df, lookback=20, spacing=90))
    r4_incremental = sorted(r4_times - base_times)

    report = {
        "governance": "DESCRIPTIVE_NO_OUTCOMES",
        "corpus_hash_prefix": sha256_prefix(corpus),
        "R2_incremental_exposed": {
            "n": len(r2_incremental),
            "description": "depth>=1.0 but NOT (pre<=-1.5 and depth>=1.0)",
            "events": describe_times(df, r2_incremental, by_time),
        },
        "R4_incremental_independent": {
            "n": len(r4_incremental),
            "description": "independent at 90min spacing but not at 120min baseline",
            "events": describe_times(df, r4_incremental, by_time),
        },
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    out = OUTPUT / "incremental_event_descriptive.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()