#!/usr/bin/env python3
"""Purged event k-fold worked example — 50 independent events (EXPLORATORY only)."""

from __future__ import annotations

import json
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from research.secondlow_v1.corpus import CANONICAL_XAUUSD_M15
from research.secondlow_v1.detector import (
    DISCOVERY_END,
    DISCOVERY_START,
    POST_WINDOW_BARS,
    detect_independent_events,
    load_ohlcv,
    sha256_prefix,
)

DEPTH_V02 = 1.0
K_FOLDS = 3
N_MIN_EXPOSED = 3
N_BOOT = 5000
SEED = 42
WINDOW_MIN = POST_WINDOW_BARS * 15  # 120
EMBARGO_MIN = 120
OUTPUT = _REPO / "H-SECONDLOW-002_Complete_Package/results/purged_kfold_worked_example"


def event_window(t: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    return t - timedelta(minutes=WINDOW_MIN), t + timedelta(minutes=WINDOW_MIN)


def windows_overlap(t1: pd.Timestamp, t2: pd.Timestamp) -> bool:
    a0, a1 = event_window(t1)
    b0, b1 = event_window(t2)
    return a0 <= b1 and b0 <= a1


def bootstrap_median_diff(exposed: np.ndarray, reference: np.ndarray) -> dict:
    if len(exposed) == 0 or len(reference) == 0:
        return {"observed": None, "ci_95": [None, None]}
    rng = np.random.default_rng(SEED)
    obs = float(np.median(exposed) - np.median(reference))
    boots = np.empty(N_BOOT)
    for i in range(N_BOOT):
        e = rng.choice(exposed, size=len(exposed), replace=True)
        r = rng.choice(reference, size=len(reference), replace=True)
        boots[i] = np.median(e) - np.median(r)
    return {
        "observed": round(obs, 4),
        "ci_95": [round(float(np.percentile(boots, 2.5)), 4), round(float(np.percentile(boots, 97.5)), 4)],
    }


def fold_metrics(events: list) -> dict:
    exposed = [e for e in events if e.purge_depth_atr >= DEPTH_V02]
    reference = [e for e in events if e.purge_depth_atr < DEPTH_V02]
    exp_y = np.array([e.close_disp_atr for e in exposed], dtype=float)
    ref_y = np.array([e.close_disp_atr for e in reference], dtype=float)
    boot = bootstrap_median_diff(exp_y, ref_y)
    n_exp = len(exposed)
    verdict = "INSUFFICIENT" if n_exp < N_MIN_EXPOSED else "DESCRIPTIVE"
    return {
        "n_events": len(events),
        "n_exposed": n_exp,
        "n_reference": len(reference),
        "median_exposed": round(float(np.median(exp_y)), 4) if n_exp else None,
        "median_reference": round(float(np.median(ref_y)), 4) if len(ref_y) else None,
        "median_diff": boot["observed"],
        "bootstrap_ci_95": boot["ci_95"],
        "verdict": verdict,
        "event_times": [str(e.purge_time) for e in events],
        "exposed_times": [str(e.purge_time) for e in exposed],
    }


def partition_label(t: pd.Timestamp) -> str:
    if t < DISCOVERY_START:
        return "pre_discovery"
    if t <= DISCOVERY_END:
        return "discovery"
    return "post_discovery"


def main() -> None:
    corpus = _REPO / CANONICAL_XAUUSD_M15
    df = load_ohlcv(corpus)
    _, events = detect_independent_events(df, require_post_window=True)
    if len(events) != 50:
        raise SystemExit(f"Expected 50 events, got {len(events)}")

    events = sorted(events, key=lambda e: e.purge_time)
    n = len(events)
    sizes = [n // K_FOLDS + (1 if i < n % K_FOLDS else 0) for i in range(K_FOLDS)]
    blocks: list[list] = []
    start = 0
    for sz in sizes:
        blocks.append(events[start : start + sz])
        start += sz

    folds = []
    for f in range(K_FOLDS):
        test = blocks[f]
        test_times = {e.purge_time for e in test}
        train = [e for i, b in enumerate(blocks) if i != f for e in b]

        purged_overlap = []
        kept_train = []
        for e in train:
            if any(windows_overlap(e.purge_time, t) for t in test_times):
                purged_overlap.append(e)
            else:
                kept_train.append(e)

        min_test_time = min(test_times)
        embargo_cut = min_test_time - timedelta(minutes=EMBARGO_MIN)
        embargo_dropped = [e for e in kept_train if embargo_cut < e.purge_time < min_test_time]
        kept_train = [e for e in kept_train if e not in embargo_dropped]

        metrics = fold_metrics(test)
        folds.append(
            {
                "fold": f + 1,
                "test_block_index": f,
                "test_time_range": [str(test[0].purge_time), str(test[-1].purge_time)],
                "test_partition_counts": {
                    "pre_discovery": sum(1 for e in test if partition_label(e.purge_time) == "pre_discovery"),
                    "discovery": sum(1 for e in test if partition_label(e.purge_time) == "discovery"),
                    "post_discovery": sum(1 for e in test if partition_label(e.purge_time) == "post_discovery"),
                },
                "train_before_purge": len(train),
                "train_purged_overlap": len(purged_overlap),
                "train_embargo_dropped": len(embargo_dropped),
                "train_final_n": len(kept_train),
                "purged_overlap_times": [str(e.purge_time) for e in purged_overlap],
                "embargo_dropped_times": [str(e.purge_time) for e in embargo_dropped],
                "test_metrics": metrics,
            }
        )

    eligible = [f for f in folds if f["test_metrics"]["verdict"] != "INSUFFICIENT"]
    if eligible:
        weights = np.array([f["test_metrics"]["n_exposed"] for f in eligible], dtype=float)
        weights /= weights.sum()
        pooled_diff = sum(
            w * f["test_metrics"]["median_diff"]
            for w, f in zip(weights, eligible)
            if f["test_metrics"]["median_diff"] is not None
        )
    else:
        pooled_diff = None

    report = {
        "governance": "EXPLORATORY_ROBUSTNESS_NOT_V02_CONFIRMATORY",
        "framework": "historical-robustness-framework-v1.md",
        "corpus": str(corpus),
        "corpus_hash_prefix": sha256_prefix(corpus),
        "n_events": 50,
        "exposure_rule": f"purge_depth_atr >= {DEPTH_V02}",
        "endpoint": "close_disp_atr +120m",
        "estimand": "median(EXPOSED) - median(REFERENCE)",
        "k_folds": K_FOLDS,
        "block_sizes": sizes,
        "purge_rule": f"drop train if event window overlaps any test window (±{WINDOW_MIN}m)",
        "embargo_minutes": EMBARGO_MIN,
        "n_min_exposed_per_fold": N_MIN_EXPOSED,
        "bootstrap": {"n_boot": N_BOOT, "seed": SEED},
        "folds": folds,
        "pooled_median_diff_eligible_folds_only": round(pooled_diff, 4) if pooled_diff is not None else None,
        "n_eligible_folds": len(eligible),
        "note": "PRE/discovery folds are exploratory; v0.2 confirmatory evidence remains prospective ledger only.",
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    out = OUTPUT / "purged_kfold_50_events.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Purged k-fold worked example (50 events, k=3)",
        "",
        f"Corpus hash: `{report['corpus_hash_prefix']}`",
        "",
        "| Fold | Test range | n | EXPOSED | Median diff | 95% CI | Verdict |",
        "|------|------------|--:|--------:|------------:|--------|---------|",
    ]
    for f in folds:
        m = f["test_metrics"]
        ci = m["bootstrap_ci_95"]
        ci_s = f"[{ci[0]}, {ci[1]}]" if ci[0] is not None else "—"
        lines.append(
            f"| {f['fold']} | {f['test_time_range'][0][:10]} → {f['test_time_range'][1][:10]} | "
            f"{m['n_events']} | {m['n_exposed']} | {m['median_diff']} | {ci_s} | {m['verdict']} |"
        )
    lines.append("")
    lines.append(f"Pooled median diff (eligible folds only): **{report['pooled_median_diff_eligible_folds_only']}**")
    (OUTPUT / "purged_kfold_50_events_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()