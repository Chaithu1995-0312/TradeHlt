#!/usr/bin/env python3
"""
Descriptive purge-depth metric comparison on all 36 independent events.

GOVERNANCE: No close_disp_atr or outcome-linked metrics. No sealed-21-only mining.
Purpose: compare depth metric distributions before any new hypothesis prereg.
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
from research.secondlow_v1.detector import (
    DISCOVERY_START,
    detect_independent_events,
    load_ohlcv,
    partition_event_times,
    sha256_prefix,
)

THRESHOLD = 1.0
OUTPUT = _REPO / "H-SECONDLOW-002_Complete_Package/results/depth_metric_descriptive"
MANIFEST = _REPO / "H-SECONDLOW-002_Complete_Package/data/sealed_evaluation_set_v1.json"


def summarize(series: pd.Series) -> dict:
    s = series.dropna()
    if s.empty:
        return {"n": 0}
    return {
        "n": int(len(s)),
        "mean": float(s.mean()),
        "median": float(s.median()),
        "std": float(s.std(ddof=1)) if len(s) > 1 else 0.0,
        "min": float(s.min()),
        "max": float(s.max()),
        "pct_ge_threshold": float((s >= THRESHOLD).mean()),
    }


def main() -> None:
    corpus = _REPO / CANONICAL_XAUUSD_M15
    df = load_ohlcv(corpus)
    raw_mask, events = detect_independent_events(df, require_post_window=False)
    assert len(events) == 36, f"expected 36 independent events, got {len(events)}"

    sealed = set(pd.to_datetime(json.loads(MANIFEST.read_text())["purge_times"]))
    parts = partition_event_times([e.purge_time for e in events])

    rows = []
    for e in events:
        pos = df.index.get_loc(e.purge_time)
        m = depth_metrics_at_purge(df, pos)
        if m is None:
            continue
        rows.append(
            {
                "purge_time": m.purge_time,
                "partition": (
                    "pre_discovery" if m.purge_time < DISCOVERY_START
                    else "discovery"
                ),
                "in_sealed_21": m.purge_time in sealed,
                "atr_14": round(m.atr_14, 4),
                "atr_100": round(m.atr_100, 4),
                "regime_factor_atr14_over_atr100": round(m.atr_14 / m.atr_100, 4),
                "baseline_depth_atr": round(m.baseline_depth_atr, 4),
                "lowest_low_depth_atr": round(m.lowest_low_depth_atr, 4),
                "regime_normalized_depth_atr": round(m.regime_normalized_depth_atr, 4)
                if np.isfinite(m.regime_normalized_depth_atr)
                else None,
                "rolling_min_zscore": round(m.rolling_min_zscore, 4)
                if m.rolling_min_zscore is not None
                else None,
            }
        )

    table = pd.DataFrame(rows)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUTPUT / "depth_metrics_36_events.csv", index=False)

    metrics = [
        "baseline_depth_atr",
        "lowest_low_depth_atr",
        "regime_normalized_depth_atr",
    ]
    summary = {m: summarize(table[m]) for m in metrics}
    summary["correlation_baseline_vs_regime_norm"] = float(
        table[["baseline_depth_atr", "regime_normalized_depth_atr"]].dropna().corr().iloc[0, 1]
    )
    summary["correlation_baseline_vs_regime_factor"] = float(
        table[["baseline_depth_atr", "regime_factor_atr14_over_atr100"]].dropna().corr().iloc[0, 1]
    )

    def threshold_flips(col: str) -> dict:
        base = table["baseline_depth_atr"] >= THRESHOLD
        alt = table[col] >= THRESHOLD
        return {
            "baseline_ge_threshold": int(base.sum()),
            f"{col}_ge_threshold": int(alt.sum()),
            "flip_to_exposed_by_depth_only": int((~base & alt).sum()),
            "flip_to_reference_by_depth_only": int((base & ~alt).sum()),
        }

    summary["threshold_1.0_comparison"] = {
        "lowest_low": threshold_flips("lowest_low_depth_atr"),
        "regime_normalized": threshold_flips("regime_normalized_depth_atr"),
    }

    sealed5 = table[table["in_sealed_21"] & (table["baseline_depth_atr"] >= 1.0) & (table["partition"] == "pre_discovery")]
    summary["sealed_pre_baseline_exposed_n"] = int(
        ((table["in_sealed_21"]) & (table["partition"] == "pre_discovery") & (table["baseline_depth_atr"] >= 1.0)).sum()
    )
    summary["sealed_pre_regime_factor_for_baseline_depth_ge_1"] = (
        sealed5["regime_factor_atr14_over_atr100"].describe().to_dict()
        if len(sealed5)
        else {}
    )

    report = {
        "study": "depth_metric_descriptive_v0.1",
        "corpus_sha256_prefix": sha256_prefix(corpus),
        "n_independent_events": len(table),
        "n_pre_discovery": len(parts["pre_discovery"]),
        "n_discovery": len(parts["discovery"]),
        "no_outcome_metrics_computed": True,
        "threshold_atr": THRESHOLD,
        "summary": summary,
    }
    (OUTPUT / "depth_metric_descriptive_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    print(json.dumps(report, indent=2))
    print(f"\nWrote {OUTPUT}")


if __name__ == "__main__":
    main()