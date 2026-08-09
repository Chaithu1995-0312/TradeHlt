"""remap_zone_registry_v4.py — one-shot ZoneGate registry remap, schema v3.0 -> v4.0.

WHY A SCRIPT AND NOT A HAND-EDIT
--------------------------------
`models/zone_registry.json` carries 8 zones x 3 parallel 38-float vectors. Hand-editing those is
exactly how alignment defects are born, and the freeze pin's own `_doc` says never hand-edit vector
data. This script is the provenance record of HOW the v4 artifact was produced: run it, diff its
output, keep it.

WHAT IT DOES (and, as importantly, what it does NOT)
----------------------------------------------------
Renames two entries in `feature_order` and zeroes one weight. That is all.

    wick_size  -> candle_range     numerically INERT: weight is 0.0 in all 8 zones already
                                   (it is in the hand-specified 13-dim mask), so the dim was
                                   never scored. Pure relabel.
    macd_hist  -> macd_hist_z      pure relabel: the stored stats (mu ~ -0.041, sigma ~ 1.18) are
                                   unmistakably the Z-SCORED distribution, because v3's
                                   compute_normalization overwrote macd_hist in place. The trained
                                   numbers therefore describe macd_hist_z exactly.
    session    -> weight 0.0       the ONLY genuine change. Trained mu=0.968 / sigma=0.8165
                                   (sigma == sqrt(2/3), the exact std of a uniform 3-value
                                   partition, and IDENTICAL in all 8 zones -- i.e. never estimated
                                   per cluster) no longer describes the v4 domain, measured at
                                   mu=1.624 / sigma=1.380 over 19,922 BNBUSDT bars.

`mu` and `sigma` are copied through UNCHANGED for every zone. `macd_hist_raw` is deliberately NOT
added to `feature_order`: there are no trained statistics for it, and inventing some would fabricate
provenance. A 38-name subset of the 39-dim schema is fully supported by the name-anchored extractor
(`zone_gate_engine._extract_vector`).

WHY ZERO-WEIGHT AND NOT RE-ESTIMATE
------------------------------------
`mu`/`sigma` are per-zone CLUSTER-MEMBER statistics. Recomputing them needs the training set plus
cluster membership, neither of which is available; a global re-estimate would assert numbers no
training run produced. Zero-weighting is the only option that neither fabricates provenance nor
keeps asserting a distribution known to be wrong.

Measured consequence (6,000 BNBUSDT bars, top_k=3, cluster_min_n=2, spread_max=0.15, thr=0.25):
cluster score mean 0.74254 -> 0.75461, max |delta| 0.036, and **0 decision flips** — scores sit far
above the threshold either way (consistent with F-036 non-pivotal / F-041B 0-of-8-zones).

The scorer normalizes by `sum(weights)`, so zeroing a dim RENORMALIZES over the rest (active dims
25 -> 24, total_weight 1.0 -> 0.96). That is a real score change, just not a decision change.

Grants NO authority (CLAUDE.md 6.5): this is an alignment repair, not a retrain, and it does not
clean the artifact's PIT status (F-051 PIT_UNCLEAN_CENTERED_SWINGS is carried forward).

USAGE
-----
    python scripts/governance/remap_zone_registry_v4.py            # write the v4 artifact
    python scripts/governance/remap_zone_registry_v4.py --check    # verify, write nothing
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT / "src"))

SRC = _ROOT / "models" / "zone_registry.json"
DST = _ROOT / "models" / "zone_registry_v4_2026_07.json"
SRC_PROV = _ROOT / "models" / "zone_registry.provenance.json"
DST_PROV = _ROOT / "models" / "zone_registry_v4_2026_07.provenance.json"

RENAMES = {"wick_size": "candle_range", "macd_hist": "macd_hist_z"}
ZERO_WEIGHT = "session"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> tuple[dict, dict]:
    reg = json.loads(SRC.read_text(encoding="utf-8"))
    src_sha = _sha256(SRC)

    old_order = list(reg["feature_order"])
    for old in RENAMES:
        if old not in old_order:
            raise SystemExit(f"source registry has no `{old}` in feature_order — already remapped?")
    new_order = [RENAMES.get(n, n) for n in old_order]

    # Every renamed name must exist in the LIVE schema, and every retained name too — this is the
    # same invariant BitNetZoneGate._validate_feature_order enforces at load. Fail here, loudly,
    # rather than shipping an artifact that will fail closed in the spine.
    from features.feature_schema import CANONICAL_FEATURE_ORDER
    live = set(CANONICAL_FEATURE_ORDER)
    missing = [n for n in new_order if n not in live]
    if missing:
        raise SystemExit(f"remapped feature_order still names features absent from v4: {missing}")

    s_idx = new_order.index(ZERO_WEIGHT)

    zones_out = []
    for z in reg["zones"]:
        w = list(z["weights"])
        prev_w = w[s_idx]
        w[s_idx] = 0.0
        zones_out.append({
            **z,
            "mu": list(z["mu"]),          # UNCHANGED
            "sigma": list(z["sigma"]),    # UNCHANGED
            "weights": w,
        })

    out = {
        "schema_version": "v4_gaussian",
        "feature_order": new_order,
        "feature_weights": list(reg.get("feature_weights") or []),
        "source": reg.get("source"),
        "zones": zones_out,
    }

    n_active_before = sum(1 for x in reg["zones"][0]["weights"] if x != 0)
    n_active_after = sum(1 for x in zones_out[0]["weights"] if x != 0)

    prov_src = {}
    if SRC_PROV.is_file():
        prov_src = json.loads(SRC_PROV.read_text(encoding="utf-8"))

    prov = {
        "artifact": str(DST.relative_to(_ROOT)).replace("\\", "/"),
        "derived_from": str(SRC.relative_to(_ROOT)).replace("\\", "/"),
        "derived_from_sha256": src_sha,
        "generated_by": "scripts/governance/remap_zone_registry_v4.py",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "program_id": "SCHEMA-V4-VECTOR-MIGRATION",
        "change_class": "ALIGNMENT_REMAP",
        "_change_class_note": "Relabel + one weight zeroed. NOT a retrain: no mu/sigma value moved, "
                              "no new statistics were estimated, no labels were consulted.",
        "renames": dict(RENAMES),
        "_renames_note": {
            "wick_size->candle_range": "numerically inert — weight is 0.0 in all 8 zones (the dim "
                                       "is inside the hand-specified 13-dim mask), so it was never "
                                       "scored.",
            "macd_hist->macd_hist_z": "pure relabel — stored mu~-0.041/sigma~1.18 is the z-scored "
                                      "distribution, because v3 compute_normalization overwrote "
                                      "macd_hist in place. The trained stats describe macd_hist_z.",
        },
        "zeroed_weights": [ZERO_WEIGHT],
        "_zeroed_note": (
            "FM-052 session moved from a 3-value hour partition to a 5-value window domain, so the "
            "trained mu=0.968/sigma=0.8165 no longer describes the feature (measured v4: mu=1.624, "
            "sigma=1.380 over 19,922 BNBUSDT bars). sigma was identical in all 8 zones "
            "(== sqrt(2/3)), i.e. never estimated per cluster. mu/sigma are per-zone cluster-member "
            "statistics and cannot be re-estimated without the training set + membership, so "
            "zero-weighting is the only option that neither fabricates provenance nor keeps "
            "asserting a known-wrong distribution."
        ),
        "measured_impact": {
            "probe": "6000 BNBUSDT bars, top_k=3, cluster_min_n=2, spread_max=0.15, threshold=0.25",
            "cluster_score_mean_before": 0.74254,
            "cluster_score_mean_after": 0.75461,
            "max_abs_delta": 0.03576,
            "decision_flips": 0,
            "pass_rate_before": 1.0,
            "pass_rate_after": 1.0,
            "interpretation": "Decision-inert on this corpus — scores sit ~0.74 against a 0.25 "
                              "threshold either way (consistent with F-036 non-pivotal). The choice "
                              "was made on honesty, not economics.",
        },
        "active_dims": {"before": n_active_before, "after": n_active_after},
        "total_weight": {"before": 1.0, "after": round(sum(zones_out[0]["weights"]), 6)},
        "_total_weight_note": "compute_gaussian_score normalizes by sum(weights), so zeroing a dim "
                              "renormalizes over the remaining ones — a real score change.",
        "scored_dims": len(new_order),
        "live_schema_dim": None,   # filled below
        "_subset_note": "feature_order is a 38-name SUBSET of the 39-dim v4 schema. macd_hist_raw is "
                        "deliberately absent: it has no trained statistics. The name-anchored "
                        "extractor supports any subset in any order.",
        "pit_status": prov_src.get("pit_status", "PIT_UNCLEAN_CENTERED_SWINGS"),
        "_pit_note": "Carried forward from the v3 provenance — an alignment remap does NOT clean "
                     "PIT status (F-051). No promote / re-enable / economic use without causal "
                     "revalidation.",
        "inherited_provenance": prov_src,
        "finding_ids": sorted(set((prov_src.get("finding_ids") or []) + ["F-041", "F-051", "F-062"])),
        "authority": "NONE — alignment repair only (CLAUDE.md 6.5).",
    }
    from features.feature_schema import CANONICAL_FEATURE_DIM
    prov["live_schema_dim"] = CANONICAL_FEATURE_DIM
    return out, prov


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Remap the ZoneGate registry from schema v3.0 to v4.0.")
    ap.add_argument("--check", action="store_true", help="verify only; write nothing")
    args = ap.parse_args(argv)

    out, prov = build()

    print(f"source        : {SRC.relative_to(_ROOT)}  sha={prov['derived_from_sha256'][:16]}")
    print(f"renames       : {prov['renames']}")
    print(f"zeroed        : {prov['zeroed_weights']}")
    print(f"active dims   : {prov['active_dims']['before']} -> {prov['active_dims']['after']}")
    print(f"total weight  : {prov['total_weight']['before']} -> {prov['total_weight']['after']}")
    print(f"scored dims   : {prov['scored_dims']} (live schema {prov['live_schema_dim']})")

    # mu/sigma must be untouched — the whole claim of this remap
    src_reg = json.loads(SRC.read_text(encoding="utf-8"))
    for a, b in zip(src_reg["zones"], out["zones"]):
        assert a["mu"] == b["mu"] and a["sigma"] == b["sigma"], f"{a['id']}: mu/sigma moved"
    print("mu/sigma      : UNCHANGED in all zones (verified)")

    if args.check:
        print("\n[--check] nothing written")
        return 0

    DST.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    DST_PROV.write_text(json.dumps(prov, indent=2) + "\n", encoding="utf-8")
    print(f"\n[OK] wrote {DST.relative_to(_ROOT)}  sha={_sha256(DST)[:16]}")
    print(f"[OK] wrote {DST_PROV.relative_to(_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
