#!/usr/bin/env python3
"""
Descriptive volatility-regime analysis on 36 independent SECONDLOW events.

GOVERNANCE: No close_disp_atr. No outcome-linked claims on sealed 21.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from research.secondlow_v1.corpus import CANONICAL_XAUUSD_M15
from research.secondlow_v1.depth_metrics import depth_metrics_at_purge
from research.secondlow_v1.detector import detect_independent_events, load_ohlcv, sha256_prefix
from research.secondlow_v1.regime_metrics import compute_regime_series

OUTPUT = _REPO / "H-SECONDLOW-002_Complete_Package/results/regime_descriptive"
DEPTH_THRESHOLD = 1.0


def summarize(series: pd.Series) -> dict:
    s = series.dropna()
    return {
        "n": int(len(s)),
        "mean": float(s.mean()),
        "median": float(s.median()),
        "std": float(s.std(ddof=1)) if len(s) > 1 else 0.0,
        "min": float(s.min()),
        "max": float(s.max()),
    }


def main() -> None:
    corpus = _REPO / CANONICAL_XAUUSD_M15
    df = load_ohlcv(corpus)
    _, events = detect_independent_events(df, require_post_window=False)
    assert len(events) == 36

    regime_df = compute_regime_series(df)
    rows = []
    for e in events:
        pos = df.index.get_loc(e.purge_time)
        d = depth_metrics_at_purge(df, pos)
        atr14 = float(regime_df["atr_14"].iloc[pos])
        atr100 = float(regime_df["atr_100"].iloc[pos])
        atr200 = float(regime_df["atr_200"].iloc[pos])
        pk20 = float(regime_df["parkinson_vol_20"].iloc[pos])
        pk100 = float(regime_df["parkinson_vol_100"].iloc[pos])
        above_p70 = bool(regime_df["atr_percentile_proxy"].iloc[pos] == 1.0)
        if not all(np.isfinite(v) and v > 0 for v in [atr14, atr100, atr200, pk20, pk100]):
            continue
        if d is None:
            continue
        atr_r100 = atr14 / atr100
        atr_r200 = atr14 / atr200
        pk_ratio = pk20 / pk100
        rows.append(
            {
                "purge_time": e.purge_time,
                "atr_ratio_14_over_100": round(atr_r100, 4),
                "atr_ratio_14_over_200": round(atr_r200, 4),
                "parkinson_ratio_20_over_100": round(pk_ratio, 4),
                "binary_high_atr_p70_200": above_p70,
                "binary_high_atr_ratio_1_2": atr_r100 > 1.2,
                "baseline_depth_atr": round(d.baseline_depth_atr, 4),
                "depth_ge_1.0": d.baseline_depth_atr >= DEPTH_THRESHOLD,
            }
        )

    table = pd.DataFrame(rows)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUTPUT / "regime_metrics_36_events.csv", index=False)

    deep = table[table["depth_ge_1.0"]]
    report = {
        "study": "regime_descriptive_v0.1",
        "corpus_sha256_prefix": sha256_prefix(corpus),
        "n_events": len(table),
        "no_outcome_metrics": True,
        "distributions": {
            "atr_ratio_14_over_100": summarize(table["atr_ratio_14_over_100"]),
            "atr_ratio_14_over_200": summarize(table["atr_ratio_14_over_200"]),
            "parkinson_ratio_20_over_100": summarize(table["parkinson_ratio_20_over_100"]),
        },
        "correlations": {
            "atr100_vs_atr200_ratio": float(
                table[["atr_ratio_14_over_100", "atr_ratio_14_over_200"]].corr().iloc[0, 1]
            ),
            "atr_ratio_vs_parkinson_ratio": float(
                table[["atr_ratio_14_over_100", "parkinson_ratio_20_over_100"]].corr().iloc[0, 1]
            ),
            "atr_ratio_vs_depth": float(
                table[["atr_ratio_14_over_100", "baseline_depth_atr"]].corr().iloc[0, 1]
            ),
        },
        "binary_high_vol_fractions": {
            "atr_ratio_gt_1.2": float(table["binary_high_atr_ratio_1_2"].mean()),
            "atr_p70_200": float(table["binary_high_atr_p70_200"].mean()),
        },
        "deep_breaks_depth_ge_1.0": {
            "n": int(len(deep)),
            "atr_ratio_mean": float(deep["atr_ratio_14_over_100"].mean()) if len(deep) else None,
            "fraction_high_vol_ratio_1.2": float(deep["binary_high_atr_ratio_1_2"].mean())
            if len(deep)
            else None,
            "fraction_high_vol_p70_200": float(deep["binary_high_atr_p70_200"].mean())
            if len(deep)
            else None,
        },
        "lookback_stability": {
            "mean_abs_diff_ratio100_vs_ratio200": float(
                (table["atr_ratio_14_over_100"] - table["atr_ratio_14_over_200"]).abs().mean()
            ),
        },
    }
    (OUTPUT / "regime_descriptive_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"\nWrote {OUTPUT}")


if __name__ == "__main__":
    main()