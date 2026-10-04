#!/usr/bin/env python3
"""Count-only relaxation diagnostic on 36 independent events — no outcomes."""

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
    compute_true_range_atr,
    detect_independent_events,
    load_ohlcv,
    sha256_prefix,
)

MANIFEST = _REPO / "H-SECONDLOW-002_Complete_Package/data/sealed_evaluation_set_v1.json"
OUTPUT = _REPO / "H-SECONDLOW-002_Complete_Package/results/relaxation_count_diagnostic"


def exposed_count(events, *, pre_a: float, depth_b: float, mode: str) -> int:
    n = 0
    for e in events:
        pre_ok = e.pre_2h_return_atr <= pre_a
        dep_ok = e.purge_depth_atr >= depth_b
        if mode == "and" and pre_ok and dep_ok:
            n += 1
        elif mode == "depth_only" and dep_ok:
            n += 1
        elif mode == "or" and (pre_ok or dep_ok):
            n += 1
    return n


def count_independent(df: pd.DataFrame, *, lookback: int, spacing: int) -> tuple[int, int]:
    work = df.copy()
    work["atr"] = compute_true_range_atr(work)
    work["sl"] = compute_trading_day_second_low(work, lookback=lookback)
    raw = _detect_raw_purge_mask(work, "sl")
    ind = len(_independent_indices(work.index, raw, min_spacing_min=spacing))
    return int(raw.sum()), ind


def main() -> None:
    corpus = _REPO / CANONICAL_XAUUSD_M15
    df = load_ohlcv(corpus)
    _, events36 = detect_independent_events(df, require_post_window=False)

    baseline = exposed_count(events36, pre_a=-1.5, depth_b=1.0, mode="and")
    exposure_rows = [
        {
            "id": "baseline",
            "rule": "pre_2h<=-1.5 AND depth>=1.0",
            "n_exposed": baseline,
            "delta": 0,
        },
        {
            "id": "R1",
            "rule": "pre_2h<=-1.5 AND depth>=0.75",
            "n_exposed": exposed_count(events36, pre_a=-1.5, depth_b=0.75, mode="and"),
        },
        {
            "id": "R2",
            "rule": "depth>=1.0 only",
            "n_exposed": exposed_count(events36, pre_a=-1.5, depth_b=1.0, mode="depth_only"),
        },
        {
            "id": "R5",
            "rule": "depth>=0.75 OR pre_2h<=-1.5",
            "n_exposed": exposed_count(events36, pre_a=-1.5, depth_b=0.75, mode="or"),
        },
    ]
    for row in exposure_rows[1:]:
        row["delta"] = row["n_exposed"] - baseline

    raw20, ind20 = count_independent(df, lookback=20, spacing=120)
    detector_rows = [
        {"id": "baseline", "lookback": 20, "spacing_min": 120, "raw": raw20, "independent": ind20, "delta_ind": 0},
    ]
    for lb in (10, 15):
        raw, ind = count_independent(df, lookback=lb, spacing=120)
        detector_rows.append({"id": f"R3_lb{lb}", "lookback": lb, "spacing_min": 120, "raw": raw, "independent": ind, "delta_ind": ind - ind20})
    for sp in (60, 90):
        raw, ind = count_independent(df, lookback=20, spacing=sp)
        detector_rows.append({"id": f"R4_sp{sp}", "lookback": 20, "spacing_min": sp, "raw": raw, "independent": ind, "delta_ind": ind - ind20})

    sealed = {pd.Timestamp(t) for t in json.loads(MANIFEST.read_text())["purge_times"]}
    ev21 = [e for e in events36 if e.purge_time in sealed]
    b21 = exposed_count(ev21, pre_a=-1.5, depth_b=1.0, mode="and")
    sealed_rows = [{"id": "baseline", "n_exposed": b21, "delta": 0}]
    for rid, dep, mode in [("R1", 0.75, "and"), ("R2", 1.0, "depth_only"), ("R5", 0.75, "or")]:
        n = exposed_count(ev21, pre_a=-1.5, depth_b=dep, mode=mode)
        sealed_rows.append({"id": rid, "n_exposed": n, "delta": n - b21})

    report = {
        "governance": "COUNT_ONLY_NO_OUTCOMES",
        "corpus": str(corpus),
        "corpus_hash_prefix": sha256_prefix(corpus),
        "n_independent_events": len(events36),
        "exposure_relaxations_36": exposure_rows,
        "detector_relaxations": detector_rows,
        "exposure_relaxations_sealed21": sealed_rows,
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    out = OUTPUT / "relaxation_counts.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()