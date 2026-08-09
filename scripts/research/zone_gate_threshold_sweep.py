# -*- coding: utf-8 -*-
"""Threshold sweep over zone_gate scores.jsonl (no re-score).

Usage:
  python scripts/research/zone_gate_threshold_sweep.py
  python scripts/research/zone_gate_threshold_sweep.py --scores results/analysis/zone_gate_xauusd_trace/scores.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[2]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--scores",
        type=Path,
        default=_ROOT / "results" / "analysis" / "zone_gate_xauusd_trace" / "scores.jsonl",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=_ROOT / "results" / "analysis" / "zone_gate_xauusd_trace" / "threshold_sweep.json",
    )
    args = ap.parse_args(argv)

    scores_path = args.scores if args.scores.is_absolute() else _ROOT / args.scores
    out_path = args.out if args.out.is_absolute() else _ROOT / args.out

    rows = []
    with scores_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))

    scores = np.array([float(r["cluster_score"]) for r in rows], dtype=float)
    n = len(scores)
    print(f"source: {scores_path}")
    print(f"n_rows_jsonl: {n} (stride subsample of full corpus)")
    print(
        f"score min/med/mean/max: "
        f"{scores.min():.4f} / {float(np.median(scores)):.4f} / "
        f"{scores.mean():.4f} / {scores.max():.4f}"
    )

    thresholds = [
        0.0, 0.25, 0.30, 0.40, 0.50, 0.60, 0.65, 0.70,
        0.75, 0.80, 0.85, 0.90, 0.95, 1.0,
    ]

    print()
    header = f"{'thr':>6} {'pass':>7} {'block':>7} {'pass%':>8} {'block%':>8}"
    print(header)
    print("-" * len(header))

    results = []
    for thr in thresholds:
        passed = int((scores >= thr).sum())
        blocked = n - passed
        pr = 100.0 * passed / n
        br = 100.0 * blocked / n
        results.append(
            {
                "threshold": thr,
                "n": n,
                "pass_n": passed,
                "block_n": blocked,
                "pass_rate": passed / n,
                "block_rate": blocked / n,
            }
        )
        mark = "  <-- active default" if thr == 0.25 else ""
        print(f"{thr:6.2f} {passed:7d} {blocked:7d} {pr:7.2f}% {br:7.2f}%{mark}")

    print()
    print("percentiles (jsonl subsample):")
    percentiles = {}
    for pct in (0, 1, 5, 10, 25, 50, 75, 90, 95, 99, 100):
        val = float(np.percentile(scores, pct))
        percentiles[f"p{pct}"] = val
        print(f"  p{pct:3d}: {val:.4f}")

    print()
    print("threshold for target pass rates (empirical quantile):")
    thr_for_pass = {}
    for target in (0.99, 0.95, 0.90, 0.75, 0.50, 0.25, 0.10, 0.05, 0.01):
        thr_t = float(np.quantile(scores, 1.0 - target))
        thr_for_pass[f"pass_{int(target * 100)}pct"] = thr_t
        print(f"  pass_rate ~ {target * 100:5.1f}%  =>  thr ~ {thr_t:.4f}")

    print()
    print(f"first block appears above thr: {float(scores.min()):.4f}")
    print(f"thr for >=1% block rate:  {float(np.quantile(scores, 0.01)):.4f}")
    print(f"thr for >=5% block rate:  {float(np.quantile(scores, 0.05)):.4f}")
    print(f"thr for >=50% block rate: {float(np.quantile(scores, 0.50)):.4f}")

    out = {
        "source": str(scores_path).replace("\\", "/"),
        "n_jsonl": n,
        "note": (
            "scores.jsonl is every 10th bar (jsonl_stride=10) of the full 50,091 scored bars; "
            "rates approximate the full corpus (full-run min was 0.3987, med 0.7537 — same regime)."
        ),
        "score_stats": {
            "min": float(scores.min()),
            "median": float(np.median(scores)),
            "mean": float(scores.mean()),
            "max": float(scores.max()),
        },
        "sweep": results,
        "percentiles": percentiles,
        "thr_for_pass_rate": thr_for_pass,
        "authority": "none — research observation only; no config/promotion change",
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print()
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
