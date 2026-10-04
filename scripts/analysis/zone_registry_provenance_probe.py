#!/usr/bin/env python
"""
Zone-registry provenance probe — READ-ONLY.

QUESTION
--------
`models/zone_registry.json` declares `source: "discover_zones_v1_converted_to_gaussian"`
and `weight_strategy: "scale_free_v1"`, but no script in the repository emits the
`v2_gaussian` schema. The converter is absent. Is the artifact reproducible from the
`zone_v1` trainer plus a deterministic rule, or is its provenance lost?

HYPOTHESIS UNDER TEST
---------------------
  mu        = discover_zones KMeans centroid (k=8, seed=1337), rounded to 6dp
  sigma     = GLOBAL per-dim std over the whole corpus, floored at 0.01, rounded to 6dp
              (identical vector on every zone — NOT per-cluster; the initial
              per-cluster-std hypothesis was tested and refuted, see sigma_check)
  weights   = uniform 1/n_active over dims NOT in `zero_indices`; 0.0 elsewhere
  threshold = constant 0.3 (value known, derivation not found in repo)

PRIOR WORK REUSED
-----------------
F-041B (`docs/analysis/f041b-zone-label-audit-BNBUSDT.json`) already established
`membership_verification.status = VERIFIED` — re-running `discover_zones._kmeans`
verbatim reproduces every stored zone's n_samples / mean_rr / sl_hit_rate to 4dp under
an identity cluster mapping. This probe does NOT re-litigate membership; it treats the
stored `n_samples` vector as a membership oracle and asks the narrower question of
whether `mu` and `sigma` follow from that membership.

WHY THE KMEANS IS VECTORISED
----------------------------
`discover_zones._kmeans` is pure-Python and O(n·k·dim·iters) — ~1.3e9 inner operations
on this corpus. This probe reimplements the SAME Lloyd iteration in numpy (identical
seed/init draw, identical first-wins tie-breaking, identical empty-cluster handling,
identical convergence test) and then VERIFIES equivalence two ways before trusting it:

  1. `--verify-subsample N` runs both implementations on the first N records and
     asserts identical assignments.
  2. On the full corpus, the resulting cluster sizes must match the artifact's stored
     `n_samples` exactly. Membership is an integer partition — an exact match on all 8
     counts is not something an incorrect partition produces by chance.

If either check fails the probe reports it and makes no reconstruction claim.

Authority: research/governance only. Writes nothing outside `docs/analysis/`. Does not
modify, regenerate, or promote the registry (CLAUDE.md §6.5 — ZoneGate has no G001
authority; see F-036 / F-041B).
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
# discover_zones is the v1 trainer — import it for the VERBATIM kmeans + vector builder.
_RESEARCH = _ROOT / "scripts" / "research"
if str(_RESEARCH) not in sys.path:
    sys.path.insert(0, str(_RESEARCH))

import discover_zones as dz                                    # noqa: E402
from features.feature_schema import CANONICAL_FEATURE_ORDER    # noqa: E402

DEFAULT_SOURCE = "logs/BNBUSDT/bnbusdt_training_20260524/opportunities.jsonl"
DEFAULT_REGISTRY = "models/zone_registry.json"
DEFAULT_OUT = "docs/analysis/zone-registry-provenance-probe.LATEST.json"
ROUND_DP = 6
SIGMA_FLOOR = 0.01   # recovered: the converter floors sigma before rounding


# ── vectorised Lloyd, mirroring dz._kmeans step for step ─────────────────────

def _kmeans_vectorised(points: np.ndarray, k: int, max_iter: int = 30, seed: int = 1337):
    """numpy mirror of discover_zones._kmeans. Same init draw, same tie-break, same stop."""
    import random as _random

    rng = _random.Random(seed)
    n, dim = points.shape
    if n == 0 or k <= 0:
        return np.array([], dtype=int), np.zeros((0, dim))
    # dz: centers = [points[rng.randrange(n)][:] for _ in range(k)] — same draw order.
    centers = np.array([points[rng.randrange(n)] for _ in range(k)], dtype=np.float64)
    assignments = np.zeros(n, dtype=int)

    for _ in range(max_iter):
        # squared euclidean; argmin returns FIRST minimum, matching dz's strict `d < best_d`
        d2 = ((points[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        new_assign = d2.argmin(axis=1)
        changed = bool((new_assign != assignments).any())
        assignments = new_assign

        # recompute centers; empty clusters retain their previous center (as dz does)
        for c in range(k):
            mask = assignments == c
            if mask.any():
                centers[c] = points[mask].mean(axis=0)
        if not changed:
            break
    return assignments, centers


def _kmeans_vectorised_chunked(points: np.ndarray, k: int, max_iter: int = 30,
                               seed: int = 1337, chunk: int = 20000):
    """Same as above but chunked over rows to bound peak memory on large corpora."""
    import random as _random

    rng = _random.Random(seed)
    n, dim = points.shape
    centers = np.array([points[rng.randrange(n)] for _ in range(k)], dtype=np.float64)
    assignments = np.zeros(n, dtype=int)

    for _ in range(max_iter):
        new_assign = np.empty(n, dtype=int)
        for s in range(0, n, chunk):
            blk = points[s:s + chunk]
            d2 = ((blk[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
            new_assign[s:s + chunk] = d2.argmin(axis=1)
        changed = bool((new_assign != assignments).any())
        assignments = new_assign
        for c in range(k):
            mask = assignments == c
            if mask.any():
                centers[c] = points[mask].mean(axis=0)
        if not changed:
            break
    return assignments, centers


# ── data loading (reuses the trainer's own record→vector contract) ───────────

def _load_vectors(source: Path, limit: int | None = None) -> np.ndarray:
    weights = [1.0] * len(CANONICAL_FEATURE_ORDER)   # artifact feature_weights are all 1.0
    out: list[list[float]] = []
    for rec in dz._load_records(source):
        v = dz._vector_from_record(rec, weights)
        if v is None:
            continue
        out.append(v)
        if limit is not None and len(out) >= limit:
            break
    return np.asarray(out, dtype=np.float64)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default=DEFAULT_SOURCE)
    ap.add_argument("--registry", default=DEFAULT_REGISTRY)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--n-clusters", type=int, default=8)
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--verify-subsample", type=int, default=3000,
                    help="rows used to prove the vectorised kmeans == dz._kmeans (0 = skip)")
    ap.add_argument("--limit", type=int, default=None,
                    help="cap records (diagnostic only — a capped run cannot be decisive)")
    args = ap.parse_args(argv)

    registry = json.loads(Path(args.registry).read_text(encoding="utf-8"))
    zones = registry["zones"]
    stored_n = [int(z["weight"]) for z in zones]
    stored_mu = np.array([z["mu"] for z in zones], dtype=np.float64)
    stored_sigma = np.array([z["sigma"] for z in zones], dtype=np.float64)
    stored_weights = np.array([z["weights"] for z in zones], dtype=np.float64)
    zero_idx = sorted(int(i) for i in zones[0]["meta"]["zero_indices"])

    report: dict = {
        "probe": "zone-registry-provenance (converter reconstruction)",
        "authority": "research/governance only; no G001 authority (CLAUDE.md 6.5)",
        "source": str(args.source),
        "registry": str(args.registry),
        "hypothesis": {
            "mu": "kmeans centroid (k=8, seed=1337), round 6dp",
            "sigma": f"round(max(GLOBAL per-dim std ddof=0, {SIGMA_FLOOR}), 6) — one vector, all zones",
            "weights": "uniform 1/n_active over non-zero_indices dims",
            "threshold": "constant 0.3",
        },
        "prior_work_reused": "F-041B membership_verification=VERIFIED",
    }

    # ── weights hypothesis: pure arithmetic, no corpus needed ────────────────
    n_active = len(CANONICAL_FEATURE_ORDER) - len(zero_idx)
    expected_w = np.zeros(len(CANONICAL_FEATURE_ORDER))
    for i in range(len(CANONICAL_FEATURE_ORDER)):
        if i not in zero_idx:
            expected_w[i] = round(1.0 / n_active, ROUND_DP)
    weights_exact = bool(np.allclose(stored_weights, expected_w[None, :], atol=1e-12))
    report["weights_check"] = {
        "n_active": n_active,
        "expected_uniform_weight": round(1.0 / n_active, ROUND_DP),
        "identical_mask_across_zones": bool(
            len({tuple(z["meta"]["zero_indices"]) for z in zones}) == 1
        ),
        "all_zones_match_hypothesis": weights_exact,
        "zeroed_features": [CANONICAL_FEATURE_ORDER[i] for i in zero_idx],
    }

    # ── threshold: constant? ────────────────────────────────────────────────
    thresholds = sorted({float(z["threshold"]) for z in zones})
    report["threshold_check"] = {
        "distinct_values": thresholds,
        "is_constant": len(thresholds) == 1,
        "derivation": "UNKNOWN — not emitted by discover_zones; no source found in repo",
    }

    # ── equivalence proof for the vectorised kmeans ─────────────────────────
    if args.verify_subsample:
        sub = _load_vectors(Path(args.source), limit=args.verify_subsample)
        a_ref, _ = dz._kmeans(sub.tolist(), args.n_clusters, seed=args.seed)
        a_vec, _ = _kmeans_vectorised(sub, args.n_clusters, seed=args.seed)
        equiv = bool(np.array_equal(np.asarray(a_ref), a_vec))
        report["kmeans_equivalence"] = {
            "rows": int(sub.shape[0]),
            "identical_assignments": equiv,
        }
        if not equiv:
            report["verdict"] = "INCONCLUSIVE_KMEANS_MIRROR_DIVERGED"
            report["note"] = ("The vectorised mirror does not match dz._kmeans on the "
                              "subsample, so full-corpus results would not be trustworthy.")
            Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report, indent=2))
            return 1

    # ── full corpus ─────────────────────────────────────────────────────────
    pts = _load_vectors(Path(args.source), limit=args.limit)
    report["n_vectors"] = int(pts.shape[0])
    report["n_records_expected"] = sum(stored_n)

    assign, centers = _kmeans_vectorised_chunked(pts, args.n_clusters, seed=args.seed)
    counts = [int((assign == c).sum()) for c in range(args.n_clusters)]
    report["membership_check"] = {
        "reconstructed_counts": counts,
        "stored_counts": stored_n,
        "counts_match_exactly": sorted(counts) == sorted(stored_n),
        "identity_order_match": counts == stored_n,
    }

    if sorted(counts) != sorted(stored_n):
        report["verdict"] = "INCONCLUSIVE_MEMBERSHIP_MISMATCH"
        report["note"] = ("Cluster sizes do not match the artifact, so mu/sigma cannot be "
                          "attributed. Does not by itself disprove the hypothesis — the "
                          "corpus or record filter may differ from the original run.")
        Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 1

    # map reconstructed cluster -> stored zone by count (F-041B found identity)
    order = list(range(args.n_clusters))
    if counts != stored_n:
        remaining = list(range(args.n_clusters))
        order = []
        for target in stored_n:
            match = next(c for c in remaining if counts[c] == target)
            remaining.remove(match)
            order.append(match)

    tol = 1e-6

    # ── mu: per-cluster centroid ────────────────────────────────────────────
    mu_deltas, sigma_percluster_deltas = [], []
    for zi, c in enumerate(order):
        members = pts[assign == c]
        mu_hat = np.round(members.mean(axis=0), ROUND_DP)
        mu_deltas.append(float(np.abs(mu_hat - stored_mu[zi]).max()))
        sig_pc = np.round(members.std(axis=0, ddof=0), ROUND_DP)
        sigma_percluster_deltas.append(float(np.abs(sig_pc - stored_sigma[zi]).max()))
    mu_ok = max(mu_deltas) <= tol
    report["mu_check"] = {
        "max_abs_delta_per_zone": mu_deltas,
        "worst": max(mu_deltas),
        "matches_hypothesis": mu_ok,
    }

    # ── sigma: refuted per-cluster, then global, then global+floor ──────────
    sigma_is_global = bool(len({tuple(np.asarray(z["sigma"])) for z in zones}) == 1)
    g_raw = pts.std(axis=0, ddof=0)
    d_global = float(np.abs(np.round(g_raw, ROUND_DP) - stored_sigma[0]).max())
    floored = np.round(np.maximum(g_raw, SIGMA_FLOOR), ROUND_DP)
    d_floor = float(np.abs(floored - stored_sigma[0]).max())
    below_floor = [
        {"index": int(i), "feature": CANONICAL_FEATURE_ORDER[int(i)],
         "raw_std": float(g_raw[int(i)]), "stored": float(stored_sigma[0][int(i)])}
        for i in np.where(g_raw < SIGMA_FLOOR)[0]
    ]
    sigma_ok = d_floor <= tol
    report["sigma_check"] = {
        "identical_across_zones": sigma_is_global,
        "per_cluster_std_max_delta_per_zone": sigma_percluster_deltas,
        "per_cluster_std_matches": bool(max(sigma_percluster_deltas) <= tol),
        "global_std_max_delta": d_global,
        "global_std_matches": bool(d_global <= tol),
        "global_std_floored_max_delta": d_floor,
        "global_std_floored_matches": sigma_ok,
        "floor": SIGMA_FLOOR,
        "dims_below_floor": below_floor,
        "which": ("global_ddof0_floored" if sigma_ok
                  else "global_ddof0" if d_global <= tol else "NEITHER"),
        "note": ("sigma is a single GLOBAL vector replicated on every zone, not a "
                 "per-cluster dispersion — the per-cluster hypothesis is refuted above."),
    }

    if mu_ok and sigma_ok and weights_exact:
        report["verdict"] = "RECONSTRUCTED_EXACT"
    elif mu_ok and weights_exact:
        report["verdict"] = "RECONSTRUCTED_PARTIAL_SIGMA_UNEXPLAINED"
    else:
        report["verdict"] = "IRRECOVERABLE"

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
