"""
discover_zones.py
=================
Pipeline B (Research) — clusters opportunity records into "zones" of similar
market context, producing a simple zone registry consumable by the runtime
zone-gate engine.

Pure-stdlib KMeans (lightweight; uses only numpy if present, else nested
Python loops). LLM-tunable hyperparameters:
  --n-clusters       integer number of zones (default 8)
  --min-samples      drop clusters with fewer than this many points (default 15)
  --feature-weights  comma-separated weight per CANONICAL_FEATURE_ORDER position
                     (default: uniform 1.0)

Reads `logs/opportunities_*.jsonl` (one record per long/short/candle) and
writes a JSON registry: {"version": ..., "zones": [...]}.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from features.feature_schema import CANONICAL_FEATURE_ORDER  # noqa: E402

logger = logging.getLogger("DiscoverZones")


def _load_records(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _vector_from_record(rec: dict, weights: list[float]) -> list[float] | None:
    feats = rec.get("features")
    if not isinstance(feats, dict):
        return None
    out: list[float] = []
    for i, name in enumerate(CANONICAL_FEATURE_ORDER):
        if name not in feats:
            return None
        try:
            v = float(feats[name])
        except (TypeError, ValueError):
            return None
        out.append(v * weights[i])
    return out


def _kmeans(points: list[list[float]], k: int, max_iter: int = 30,
            seed: int = 1337) -> tuple[list[int], list[list[float]]]:
    rng = random.Random(seed)
    n = len(points)
    if n == 0 or k <= 0:
        return [], []
    dim = len(points[0])
    centers = [points[rng.randrange(n)][:] for _ in range(k)]
    assignments = [0] * n
    for _ in range(max_iter):
        changed = False
        for i, p in enumerate(points):
            best = 0
            best_d = float("inf")
            for c_idx, c in enumerate(centers):
                d = sum((p[j] - c[j]) ** 2 for j in range(dim))
                if d < best_d:
                    best_d = d
                    best = c_idx
            if assignments[i] != best:
                assignments[i] = best
                changed = True
        # Recompute centers
        sums = [[0.0] * dim for _ in range(k)]
        counts = [0] * k
        for i, p in enumerate(points):
            a = assignments[i]
            counts[a] += 1
            for j in range(dim):
                sums[a][j] += p[j]
        for c_idx in range(k):
            if counts[c_idx] > 0:
                centers[c_idx] = [s / counts[c_idx] for s in sums[c_idx]]
        if not changed:
            break
    return assignments, centers


def discover(opportunities: list[Path], *, n_clusters: int, min_samples: int,
             feature_weights: list[float], subsample: int = 1) -> dict:
    """
    subsample: keep every Nth record (1 = all records; 5 = 20% of data).
    Subsampling is deterministic (index % subsample == 0) so results are
    reproducible across runs on the same JSONL.
    """
    if len(feature_weights) != len(CANONICAL_FEATURE_ORDER):
        raise ValueError(
            f"feature_weights length {len(feature_weights)} != "
            f"CANONICAL_FEATURE_ORDER length {len(CANONICAL_FEATURE_ORDER)}"
        )
    vectors: list[list[float]] = []
    rr_values: list[float] = []
    outcomes: list[str] = []
    _rec_idx = 0
    for path in opportunities:
        for rec in _load_records(path):
            if subsample > 1 and _rec_idx % subsample != 0:
                _rec_idx += 1
                continue
            _rec_idx += 1
            v = _vector_from_record(rec, feature_weights)
            if v is None:
                continue
            vectors.append(v)
            rr_values.append(float(rec.get("rr_achieved", 0.0) or 0.0))
            outcomes.append(str(rec.get("outcome", "UNKNOWN")))

    if not vectors:
        raise ValueError("No usable feature vectors found in inputs.")
    logger.info(
        "loaded %d vectors from %d files (subsample=%d); clustering into %d zones",
        len(vectors), len(opportunities), subsample, n_clusters,
    )

    assignments, centers = _kmeans(vectors, n_clusters)

    zones = []
    for c_idx, center in enumerate(centers):
        member_idx = [i for i, a in enumerate(assignments) if a == c_idx]
        if len(member_idx) < min_samples:
            continue
        zone_rr = [rr_values[i] for i in member_idx]
        zone_tp = sum(1 for i in member_idx if outcomes[i] == "TP_HIT")
        zone_sl = sum(1 for i in member_idx if outcomes[i] == "SL_HIT")
        mean_rr = sum(zone_rr) / len(zone_rr)
        zones.append({
            "zone_id":     c_idx,
            "center":      [round(c, 6) for c in center],
            "n_samples":   len(member_idx),
            "mean_rr":     round(mean_rr, 4),
            "tp_hit_rate": round(zone_tp / len(member_idx), 4),
            "sl_hit_rate": round(zone_sl / len(member_idx), 4),
        })

    return {
        "schema_version":  "zone_v1",
        "feature_order":   list(CANONICAL_FEATURE_ORDER),
        "feature_weights": feature_weights,
        "n_clusters_requested": n_clusters,
        "min_samples":     min_samples,
        "zones":           zones,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--opportunities", nargs="+", required=True,
                    help="One or more opportunity JSONL paths")
    ap.add_argument("--output", required=True, type=Path,
                    help="Canonical output path (e.g. models/zone_registry.json). "
                         "Always written when --promote (default). Also used as "
                         "fallback filename base when --version is omitted.")
    ap.add_argument("--n-clusters", type=int, default=8)
    ap.add_argument("--min-samples", type=int, default=15)
    ap.add_argument("--feature-weights", default="",
                    help="Comma-separated weights aligned with "
                         "CANONICAL_FEATURE_ORDER (length 35)")
    ap.add_argument("--version", default=None,
                    help="Version key for zone_gate_registry.json "
                         "(auto-generates YYYYMM_v1 if omitted)")
    ap.add_argument("--subsample", type=int, default=1, metavar="N",
                    help="Keep every Nth record (default 1 = all). "
                         "Use 5-10 on large JSONL files to speed up the pure-Python KMeans.")
    ap.add_argument("--no-promote", dest="promote", action="store_false", default=True,
                    help="Skip promoting this version as active (useful for experiments)")
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    if args.feature_weights:
        weights = [float(x) for x in args.feature_weights.split(",") if x.strip()]
    else:
        weights = [1.0] * len(CANONICAL_FEATURE_ORDER)

    paths = [Path(p) for p in args.opportunities]
    result = discover(paths, n_clusters=args.n_clusters,
                      min_samples=args.min_samples, feature_weights=weights,
                      subsample=args.subsample)

    # ── versioned save ──────────────────────────────────────────────────────
    import time as _time
    version = args.version or _time.strftime("%Y%m_v1")

    # Derive versioned filename alongside the canonical output path
    versioned_path = args.output.parent / f"zone_registry_{version}.json"
    versioned_path.parent.mkdir(parents=True, exist_ok=True)
    versioned_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    logger.info("Saved versioned zone registry -> %s (%d zones)",
                versioned_path, len(result["zones"]))
    print(f"Versioned file: {versioned_path}")

    # ── register in zone_gate_registry.json ────────────────────────────────
    try:
        from core.model_registry import register_zone_gate, promote_zone_gate
        register_zone_gate(
            version=version,
            model_file=str(versioned_path),
            n_zones=len(result["zones"]),
            n_clusters_requested=args.n_clusters,
            feature_order=result.get("feature_order", []),
        )
        logger.info("Registered in zone_gate_registry: %s", version)
    except Exception as e:
        logger.warning("Zone gate registry update failed (non-fatal): %s", e)

    # ── promote: also write to canonical --output for runtime compatibility ─
    if args.promote:
        try:
            from core.model_registry import promote_zone_gate
            ok, reason = promote_zone_gate(version)
            logger.info("Promote: %s", reason)
        except Exception as e:
            logger.warning("promote_zone_gate failed (non-fatal): %s", e)
        # Write canonical file so engine_runner / config-driven paths still work
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        logger.info("Canonical zone registry updated -> %s", args.output)
        print(f"Canonical file: {args.output}")
    else:
        logger.info("--no-promote set; canonical %s NOT updated", args.output)

    print(f"Version: {version}  Zones: {len(result['zones'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
