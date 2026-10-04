#!/usr/bin/env python
"""
Convert a `discover_zones` v1 registry into the `v2_gaussian` runtime schema.

RECOVERED ARTIFACT — 2026-07-21
-------------------------------
`models/zone_registry.json` declares `source: "discover_zones_v1_converted_to_gaussian"`
and `weight_strategy: "scale_free_v1"`, but the script that produced it was absent from
the repository. This file is a RECONSTRUCTION, not the original. It is admitted on
evidence, not on authorship: `scripts/analysis/zone_registry_provenance_probe.py`
verified every component against the live artifact on the original corpus
(`logs/BNBUSDT/bnbusdt_training_20260524/opportunities.jsonl`, 139,942 records):

    membership  8/8 cluster sizes exact, identity order
    mu          max abs delta 0.0 across 38 dims x 8 zones
    sigma       38/38 dims exact
    weights     8/8 zones exact

The conversion (`zone_v1` -> `v2_gaussian`):

    mu        = the v1 cluster `center` (KMeans centroid, k=8, seed=1337), round 6dp
    sigma     = round(max(GLOBAL per-dim std ddof=0 over the WHOLE corpus, 0.01), 6)
                — a single vector replicated onto every zone. NOT a per-cluster
                dispersion; the per-cluster hypothesis was tested and refuted. The
                0.01 floor is load-bearing: `atr`'s true std is 0.00237, and the
                artifact stores exactly 0.010000 for it.
    weights     "scale_free_v1" = 0.0 on every dim carrying an absolute price/volume
                unit, uniform 1/n_active on the rest (25 active -> 0.04 each).
                `zero_indices` is the same mask on every zone.
    threshold = 0.3 on every zone. Value reproduced; its DERIVATION was not found in
                the repository and is not derived here — it is a declared constant.
                (It is inert on the live path anyway: the spine reads only
                `top_scores`, never the per-zone threshold. See F-041 / the
                `live_engine.check()` note.)
    meta      = v1 `n_samples` / `mean_rr` / `tp_hit_rate` / `sl_hit_rate` copied
                verbatim. NOTE these labels are F-022-contaminated (F-041B: honest
                forward_walk re-derive gives SL ~0.65 vs the stored ~0.98). They are
                descriptive only — `compute_gaussian_score` never reads them.

Because sigma is a global corpus statistic, this converter needs the ORIGINAL
opportunities stream, not just the v1 JSON. That is why it could not be a pure
JSON->JSON transform, and is the likely reason the original was run ad hoc and lost.

SCOPE: this script exists to make the artifact reproducible. Running it is NOT a
promotion. It does not write `models/zone_registry.json` unless `--output` explicitly
names that path, and ZoneGate holds no G001 authority regardless (CLAUDE.md 6.5;
F-036 dG001 == 0; F-041B 0/8 zones honest E>0).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import discover_zones as dz                                    # noqa: E402
from features.feature_schema import CANONICAL_FEATURE_ORDER    # noqa: E402

ROUND_DP = 6
SIGMA_FLOOR = 0.01
DEFAULT_THRESHOLD = 0.3

# "scale_free_v1": dims carrying an absolute price or volume unit are zero-weighted so
# that raw instrument scale cannot drive the Gaussian similarity. The 25 survivors are
# ratios / normalised quantities.
ABSOLUTE_SCALE_FEATURES = (
    "open", "high", "low", "close", "volume",
    "ema_fast", "ema_slow", "ema_spread",
    "momentum_score", "macd_line", "macd_signal",
    "body_size",
    # Same quantity under two schema versions: v3 called it `wick_size`, the v4
    # ALIGNMENT_REMAP renamed it `candle_range` (numerically inert then, because the
    # dim was already zero-weighted). BOTH names are listed so this converter keeps
    # reproducing the v3 artifact exactly while still zeroing the dim on v4+ schemas.
    # Name-only omission here would silently re-admit a price-unit dim to the score.
    "wick_size", "candle_range",
    # `macd_hist_raw` (= macd_line - macd_signal) is also a price-unit quantity. It is
    # not listed because the v5 retrain EXCLUDES it from the trained vector entirely
    # (discover_zones --exclude-feature); if it is ever trained, add it here.
)


def scale_free_weights(feature_order) -> tuple[list[float], list[int]]:
    """Return (weights, zero_indices) under the scale_free_v1 rule."""
    zero_idx = [i for i, name in enumerate(feature_order)
                if name in ABSOLUTE_SCALE_FEATURES]
    n_active = len(feature_order) - len(zero_idx)
    if n_active <= 0:
        raise ValueError("scale_free_v1: no active features remain")
    w = round(1.0 / n_active, ROUND_DP)
    weights = [0.0 if i in set(zero_idx) else w for i in range(len(feature_order))]
    return weights, zero_idx


def global_sigma(vectors: np.ndarray) -> list[float]:
    """round(max(global std ddof=0, SIGMA_FLOOR), 6) — one vector for all zones."""
    raw = vectors.std(axis=0, ddof=0)
    return [float(x) for x in np.round(np.maximum(raw, SIGMA_FLOOR), ROUND_DP)]


def convert(v1: dict, vectors: np.ndarray, *, threshold: float = DEFAULT_THRESHOLD) -> dict:
    feature_order = list(v1["feature_order"])
    weights, zero_idx = scale_free_weights(feature_order)
    sigma = global_sigma(vectors)
    n_active = len(feature_order) - len(zero_idx)

    zones = []
    for z in v1["zones"]:
        zones.append({
            "id":        f"zone_{z['zone_id']}",
            "mu":        [round(float(c), ROUND_DP) for c in z["center"]],
            "sigma":     sigma,
            "weights":   weights,
            "threshold": threshold,
            "weight":    int(z["n_samples"]),
            "meta": {
                "n_samples":         int(z["n_samples"]),
                "mean_rr":           z["mean_rr"],
                "tp_hit_rate":       z["tp_hit_rate"],
                "sl_hit_rate":       z["sl_hit_rate"],
                "source":            "discover_zones_v1_converted",
                "weight_strategy":   "scale_free_v1",
                "zero_indices":      zero_idx,
                "n_active_features": n_active,
            },
        })

    return {
        "schema_version":  "v2_gaussian",
        "feature_order":   feature_order,
        "feature_weights": list(v1["feature_weights"]),
        "source":          "discover_zones_v1_converted_to_gaussian",
        "zones":           zones,
    }


def _load_vectors(source: Path) -> np.ndarray:
    weights = [1.0] * len(CANONICAL_FEATURE_ORDER)
    out = []
    for rec in dz._load_records(source):
        v = dz._vector_from_record(rec, weights)
        if v is not None:
            out.append(v)
    if not out:
        raise ValueError(f"no usable feature vectors in {source}")
    return np.asarray(out, dtype=np.float64)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--v1-registry", required=True,
                    help="zone_v1 JSON emitted by discover_zones.py")
    ap.add_argument("--source", required=True,
                    help="opportunities JSONL the v1 registry was trained on (sigma is global)")
    ap.add_argument("--output", required=True)
    ap.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    ap.add_argument("--compare", default=None,
                    help="existing v2_gaussian registry to diff against (verification mode)")
    args = ap.parse_args(argv)

    v1 = json.loads(Path(args.v1_registry).read_text(encoding="utf-8"))
    if v1.get("schema_version") != "zone_v1":
        raise SystemExit(f"expected schema_version 'zone_v1', got {v1.get('schema_version')!r}")

    vectors = _load_vectors(Path(args.source))
    out = convert(v1, vectors, threshold=args.threshold)

    if args.compare:
        ref = json.loads(Path(args.compare).read_text(encoding="utf-8"))
        same = json.dumps(ref, sort_keys=True) == json.dumps(out, sort_keys=True)
        print(f"compare vs {args.compare}: {'IDENTICAL' if same else 'DIFFERS'}")
        if not same:
            for zi, (a, b) in enumerate(zip(ref["zones"], out["zones"])):
                for field in ("mu", "sigma", "weights"):
                    d = max(abs(x - y) for x, y in zip(a[field], b[field]))
                    if d > 0:
                        print(f"  zone {zi} {field}: max abs delta {d}")
            return 1

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"wrote {args.output} ({len(out['zones'])} zones)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
