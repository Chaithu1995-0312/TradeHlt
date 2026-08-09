"""validate_fm030_bands.py — CLI for behavioral validation of FM-030 band thresholds (A2a).

Thin wrapper (CLAUDE.md §3.3): all logic lives in src/research/band_validation.py.

Decides whether candidate FM-030 (ema_spread_atr) band thresholds correspond to STABLE BEHAVIORAL
REGIMES — persistence, transition structure, forward-return characteristics — BEFORE any ontology
freeze. Quantiles alone never freeze (user directive 2026-07-24). DESCRIPTIVE ONLY, no authority.

Usage:
    python scripts/research/validate_fm030_bands.py --csv data/mt5/XAUUSD_M15.csv \
        --horizon 8 [--out results/research/fm030_band_validation.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from research.band_validation import (  # noqa: E402
    BandSpec, BandValidationParams, prepare_fm030_series, validate_partitions,
)
from research.shape_statistics import BootstrapSpec  # noqa: E402

_Q5 = ("StrongBear", "WeakBear", "Neutral", "WeakBull", "StrongBull")
_Q3 = ("Bear", "Neutral", "Bull")


def _candidate_partitions(values: np.ndarray) -> list[BandSpec]:
    finite = values[np.isfinite(values)]
    p2, p98 = float(np.percentile(finite, 2)), float(np.percentile(finite, 98))
    eq = tuple(round(p2 + (p98 - p2) * i / 5.0, 6) for i in range(1, 5))   # equal-width interior cuts
    return [
        BandSpec("quintile", (-0.466786, -0.069504, 0.288226, 0.708429), _Q5),
        BandSpec("tercile", (-0.20185, 0.402123), _Q3),
        BandSpec("zero_centered", (-0.59, -0.18, 0.18, 0.59), _Q5),
        BandSpec("equal_width", eq, _Q5),
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", required=True, help="OHLCV CSV with a timestamp column")
    ap.add_argument("--horizon", required=True, type=int, help="forward-return horizon in bars")
    ap.add_argument("--n-perm", type=int, default=2000, help="permutation-null iterations")
    ap.add_argument("--out", default=None, help="optional JSON output path")
    args = ap.parse_args()

    raw = pd.read_csv(args.csv)
    values, fwd, years = prepare_fm030_series(raw, horizon=args.horizon)

    params = BandValidationParams(
        k_persist=4, fwd_horizon=args.horizon, n_perm=args.n_perm, alpha=0.05,
        rho_min=0.6, stab_min=0.3, min_cell=30,
        ci=BootstrapSpec(n_boot=2000, alpha=0.05, seed=1), seed=7,
    )
    report = validate_partitions(values, fwd, years, _candidate_partitions(values), params)
    d = report.to_dict()

    print(f"bars={d['n_bars']} horizon={d['fwd_horizon']} recommended={d['recommended']}")
    for p in d["partitions"]:
        fr = p["forward_return"]
        print(f"\n== {p['name']:14s} -> {p['verdict']}  ({p['reason']}) ==")
        print(f"   persistence p={p['persistence']['p']:.4f} real={p['persistence']['real_rate']:.3f} "
              f"null={p['persistence']['null_mean']:.3f}")
        print(f"   transition  p={p['transition']['p']:.4f} dist={p['transition']['real_mean_distance']:.3f} "
              f"null={p['transition']['null_mean_distance']:.3f} adj={p['transition']['adjacency_fraction']:.3f}")
        print(f"   fwd monotonic_rho={fr['spearman_rho']} stability_rho={fr['stability_rho']} "
              f"supported_edges={p['supported_edges']}")
        for b, s in fr["per_band"].items():
            star = "*" if s["insufficient"] else " "
            lo = f"{s['ci_lo']:+.4f}" if s["ci_lo"] == s["ci_lo"] else "  nan "
            hi = f"{s['ci_hi']:+.4f}" if s["ci_hi"] == s["ci_hi"] else "  nan "
            print(f"      {b:12s} n={s['n']:6d}{star} mean={s['mean']:+.4f} CI=[{lo},{hi}]")
    print("\nDESCRIPTIVE ONLY - licenses the semantic LABEL, not a trading edge (M4 owns that).")

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(d, indent=2), encoding="utf-8")
        print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
