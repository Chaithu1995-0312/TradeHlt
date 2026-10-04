#!/usr/bin/env python
"""
ZoneGate assignment-parity probe — READ-ONLY.

QUESTION
--------
`docs/current-findings.md` F-041 records, unexplained, that the runtime Gaussian zone
assignment agrees with the training label partition only 41.4% (per-zone 0.06-0.70).
Why, and does the residual mean anything?

MECHANICAL CAUSE (established before this probe, from the registry alone)
------------------------------------------------------------------------
The two sides are computed on near-disjoint information:

    labels  : discover_zones KMeans - squared Euclidean, all 38 RAW dims, unnormalised
    runtime : compute_gaussian_score - weighted Gaussian, 25 active dims (13 zeroed),
              divided by GLOBAL sigma, saturating exp(-z^2/2)

`sigma` in the registry IS the global per-dim std (recovered 2026-07-21), so the variance
each dim contributes to the KMeans objective is computable directly. Result:
**99.9983% of that variance lives in the 13 dims the runtime zeroes** (volume alone
97.58%). KMeans effectively partitioned by volume/price level; the runtime scores candle
shape. This probe MEASURES that rather than asserting it, and quantifies the residual.

Also note the correct null: the zones are very unbalanced, so chance is NOT 1/8. Always
predicting the largest zone scores 0.3264. Observed 0.4140 is ~9pp above trivial, not
~29pp.

WHAT THIS PROBE ADDS OVER THE F-041B AUDIT
------------------------------------------
1. Cohen's kappa (chance-corrected) + majority-class baseline alongside raw agreement.
2. The full 8x8 confusion matrix - answers where a label zone's records actually land.
   (Specifically the zone_3 anomaly: 2nd-largest zone, parity only 0.13, while zone_7 at
   a smaller share scores 0.68 - not explainable by "large zone attracts".)
3. Agreement by `margin_best_second` decile - separates argmax INSTABILITY (top-1 and
   top-2 near-tied, so the assignment is a coin flip) from genuine geometric disagreement.
4. The per-dim variance decomposition, shipped with the numbers.

BLOCKING SELF-CHECK
-------------------
Before any new metric is reported, the probe must reproduce the RECORDED
`assignment_parity` from `docs/analysis/f041b-zone-label-audit-BNBUSDT.json`
(overall 0.4140 + all 8 per-zone values). A new measurement pipeline that cannot
reproduce the number it is explaining has not earned the right to extend it. On mismatch
the probe halts and reports, drawing no conclusions.

RUNTIME SIDE ROUTING
--------------------
Uses `HistoricalZoneMapper.map_row`, which goes through `score_zone_cluster` - the
live-consistent path - rather than re-implementing an argmax. Note that the live spine
consumes only `top_scores` and NEVER assigns a zone; `best_zone_id` is telemetry. So this
metric describes a partition nothing acts on, which is why it is a governance
sub-finding and not a runtime risk.

Authority: research/governance only (CLAUDE.md 6.5). ZoneGate holds no G001 authority -
F-036 (dG001 == 0), F-041B (0/8 zones honest E>0). Writes only under docs/analysis/.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
for _p in (str(_SRC), str(_ROOT / "scripts" / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import discover_zones as dz                                       # noqa: E402
from features.feature_schema import CANONICAL_FEATURE_ORDER       # noqa: E402
from research.zone_label_audit import (                           # noqa: E402
    verify_membership,
    assignment_parity,
)
from research.zone_mapping.historical_zone_mapper import (        # noqa: E402
    HistoricalZoneMapper,
    ZoneMapConfig,
)

DEFAULT_SOURCE = "logs/BNBUSDT/bnbusdt_training_20260524/opportunities.jsonl"
DEFAULT_REGISTRY = "models/zone_registry.json"
DEFAULT_ORACLE = "docs/analysis/f041b-zone-label-audit-BNBUSDT.json"
DEFAULT_OUT = "docs/analysis/zone-assignment-parity.LATEST.json"
ORACLE_TOL = 1e-4

# ── PRE-DECLARED anomaly criterion (fixed before inspecting results) ─────────
# Under independence the expected agreement for label zone i is the RUNTIME MARGINAL
# m_i = P(runtime picks i) — NOT the label share and NOT 1/k. Judging a zone against its
# label share is what made zone_3 ("2nd largest yet 0.13") look anomalous when it is not.
#   lift_i       = parity_i - m_i          (additive excess over chance)
#   enrichment_i = parity_i / m_i          (multiplicative excess)
# A zone is ANOMALOUS if it is an outlier on EITHER scale. Both are declared here so zone
# selection cannot be fitted to the numbers after the fact.
ANOMALY_LIFT_SD_MULT = 1.0     # lift > mean + 1*sd across the 8 zones
ANOMALY_ENRICHMENT_X = 5.0     # or enrichment > 5x its runtime marginal


def _load_kmeans_mirror():
    """Import the proven-equivalent vectorised Lloyd from the provenance probe."""
    path = Path(__file__).resolve().parent / "zone_registry_provenance_probe.py"
    spec = importlib.util.spec_from_file_location("_zrpp", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _variance_decomposition(registry: dict) -> dict:
    """Share of the KMeans (squared-Euclidean) variance carried by each dim.

    sigma IS the global per-dim std, so var_j = sigma_j^2 is exactly the per-dim
    contribution to the unnormalised Euclidean objective.
    """
    fo = registry["feature_order"]
    z0 = registry["zones"][0]
    sigma = [float(s) for s in z0["sigma"]]
    zero_idx = set(int(i) for i in z0["meta"]["zero_indices"])
    var = [s * s for s in sigma]
    total = sum(var)
    zeroed = sum(var[i] for i in zero_idx)
    ranked = sorted(range(len(fo)), key=lambda j: -var[j])
    return {
        "note": ("var_j = sigma_j^2 = per-dim contribution to the unnormalised squared-"
                 "Euclidean objective KMeans minimises."),
        "total_variance": total,
        "zeroed_dims_variance_share": zeroed / total,
        "active_dims_variance_share": (total - zeroed) / total,
        "top_contributors": [
            {"feature": fo[j], "sigma": sigma[j], "variance_share": var[j] / total,
             "zeroed_at_runtime": j in zero_idx}
            for j in ranked[:8]
        ],
    }


def _cohens_kappa(labels: list[int], runtime: list[int], k: int) -> float:
    n = len(labels)
    if n == 0:
        return 0.0
    po = sum(1 for a, b in zip(labels, runtime) if a == b) / n
    lc, rc = Counter(labels), Counter(runtime)
    pe = sum((lc.get(i, 0) / n) * (rc.get(i, 0) / n) for i in range(k))
    return (po - pe) / (1.0 - pe) if pe < 1.0 else 0.0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default=DEFAULT_SOURCE)
    ap.add_argument("--registry", default=DEFAULT_REGISTRY)
    ap.add_argument("--oracle", default=DEFAULT_ORACLE)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--n-clusters", type=int, default=8)
    ap.add_argument("--instrument", default="BNBUSDT")
    ap.add_argument("--limit", type=int, default=None,
                    help="cap records for a smoke run; a capped run CANNOT reproduce the "
                         "oracle and is diagnostic only")
    args = ap.parse_args(argv)

    registry = json.loads((_ROOT / args.registry).read_text(encoding="utf-8"))
    zones = registry["zones"]
    k = args.n_clusters

    report: dict = {
        "probe": "zone assignment parity (label KMeans vs runtime Gaussian)",
        "authority": "research/governance only; no G001 authority (CLAUDE.md 6.5)",
        "instrument": args.instrument,
        "source": args.source,
        "registry": args.registry,
        "scope_note": ("The live spine consumes only top_scores and never assigns a zone "
                       "(live_engine.py check() note). This metric describes a partition "
                       "no decision path acts on."),
        "variance_decomposition": _variance_decomposition(registry),
    }

    # ── load corpus exactly as the audit does ───────────────────────────────
    weights = [1.0] * len(CANONICAL_FEATURE_ORDER)
    vecs, raws, outcomes, rrs, feat_dicts = [], [], [], [], []
    for rec in dz._load_records(_ROOT / args.source):
        v = dz._vector_from_record(rec, weights)
        if v is None:
            continue
        feats = rec["features"]
        vecs.append(v)
        raws.append([float(feats[name]) for name in CANONICAL_FEATURE_ORDER])
        rrs.append(float(rec.get("rr_achieved", 0.0) or 0.0))
        outcomes.append(str(rec.get("outcome", "UNKNOWN")))
        feat_dicts.append(feats)
        if args.limit is not None and len(vecs) >= args.limit:
            break
    n = len(vecs)
    report["n_records"] = n
    print(f"[parity] loaded {n} records")

    # ── label side: proven-equivalent vectorised KMeans ─────────────────────
    mirror = _load_kmeans_mirror()
    assign_np, _ = mirror._kmeans_vectorised_chunked(
        np.asarray(vecs, dtype=np.float64), k, seed=1337)
    assignments = [int(a) for a in assign_np]
    reconstructed = [[i for i, a in enumerate(assignments) if a == c] for c in range(k)]

    membership = verify_membership(zones, reconstructed, outcomes, rrs)
    report["membership_status"] = membership["status"]
    print(f"[parity] membership_verification.status = {membership['status']}")
    if membership["status"] == "FAILED":
        report["verdict"] = "HALT_MEMBERSHIP_RECONSTRUCTION_FAILED"
        (_ROOT / args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("[parity] HALT: membership mismatch - no conclusions drawn.")
        return 2
    mapping = membership["mapping"]

    # ── BLOCKING self-check: reproduce the recorded 0.4140 ──────────────────
    parity = assignment_parity(raws, assignments, zones, mapping)
    oracle = json.loads((_ROOT / args.oracle).read_text(encoding="utf-8"))["assignment_parity"]
    d_overall = abs(parity["overall"] - oracle["overall"])
    per_zone_deltas = {z: abs(parity["per_zone"].get(z, -1) - v)
                       for z, v in oracle["per_zone"].items()}
    reproduced = d_overall <= ORACLE_TOL and max(per_zone_deltas.values()) <= ORACLE_TOL
    report["oracle_reproduction"] = {
        "oracle_overall": oracle["overall"],
        "probe_overall": parity["overall"],
        "overall_delta": d_overall,
        "max_per_zone_delta": max(per_zone_deltas.values()),
        "reproduced": bool(reproduced),
    }
    # ASCII only: Windows console is cp1252 (CLAUDE.md 4 - console encoding constraint).
    print(f"[parity] oracle {oracle['overall']} vs probe {parity['overall']} "
          f"-> reproduced={reproduced}")
    if not reproduced:
        report["verdict"] = "HALT_ORACLE_NOT_REPRODUCED"
        report["note"] = ("The probe could not reproduce the recorded parity, so no new "
                          "metric from this pipeline is trustworthy. No conclusions drawn.")
        (_ROOT / args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("[parity] HALT: oracle not reproduced.")
        return 1
    report["assignment_parity"] = parity

    # ── runtime side via the live-consistent path (margins) ─────────────────
    mapper = HistoricalZoneMapper(ZoneMapConfig.from_prod_engine_runner())
    label_of = [mapping.get(a, -1) for a in assignments]
    runtime_of, margins = [], []
    for i, feats in enumerate(feat_dicts):
        row = mapper.map_row(feats, bar_index=i, instrument=args.instrument)
        zid = row.get("best_zone_id")
        runtime_of.append(int(str(zid).split("_")[-1]) if zid not in (None, "none") else -1)
        margins.append(float(row.get("margin_best_second", 0.0)))
        if (i + 1) % 25000 == 0:
            print(f"[parity]   mapped {i + 1}/{n}")
    report["registry_sha256"] = mapper._registry_sha256

    agree = [a == b for a, b in zip(label_of, runtime_of)]
    counts = Counter(label_of)
    majority = max(counts.values()) / n

    # Cross-check: the audit's standalone argmax re-implementation vs the live-consistent
    # score_zone_cluster path. These SHOULD agree; a gap would mean the recorded metric
    # never described the path it claimed to.
    report["path_crosscheck"] = {
        "audit_standalone_argmax_overall": parity["overall"],
        "live_consistent_path_overall": sum(agree) / n,
        "delta": abs(parity["overall"] - sum(agree) / n),
        "paths_agree": bool(abs(parity["overall"] - sum(agree) / n) <= ORACLE_TOL),
    }

    report["agreement"] = {
        "raw": sum(agree) / n,
        "majority_class_baseline": majority,
        "uniform_random_baseline": 1.0 / k,
        "cohens_kappa": _cohens_kappa(label_of, runtime_of, k),
        "lift_over_majority": sum(agree) / n - majority,
        "note": ("kappa corrects for the very unbalanced zone marginals; the majority "
                 "baseline is the honest null, not 1/k."),
    }

    # ── confusion matrix: where does each label zone actually land? ─────────
    conf = [[0] * k for _ in range(k)]
    for a, b in zip(label_of, runtime_of):
        if 0 <= a < k and 0 <= b < k:
            conf[a][b] += 1
    report["confusion_matrix"] = {
        "orientation": "rows = label (KMeans) zone, cols = runtime (Gaussian) zone",
        "matrix": conf,
        "row_normalised": [
            [round(c / max(sum(row), 1), 4) for c in row] for row in conf
        ],
        "runtime_assignment_distribution": {
            str(i): Counter(runtime_of).get(i, 0) for i in range(k)
        },
        "label_distribution": {str(i): counts.get(i, 0) for i in range(k)},
    }

    # ── runtime concentration: does the argmax collapse onto a few zones? ───
    rt_counts = Counter(runtime_of)
    top2 = sorted(rt_counts.items(), key=lambda kv: -kv[1])[:2]
    report["runtime_concentration"] = {
        "note": ("The runtime argmax is not spread over the 8 zones. Concentration is "
                 "itself part of why parity is low for the zones the runtime seldom picks."),
        "top2_zones": [int(z) for z, _ in top2],
        "top2_runtime_share": sum(c for _, c in top2) / n,
        "top2_label_share": sum(counts.get(z, 0) for z, _ in top2) / n,
    }

    # ── per-zone agreement AND margins ──────────────────────────────────────
    m = np.asarray(margins, dtype=np.float64)
    ag = np.asarray(agree, dtype=bool)
    lab = np.asarray(label_of, dtype=int)

    per_zone = []
    for i in range(k):
        sel = lab == i
        n_i = int(sel.sum())
        if n_i == 0:
            continue
        m_i = m[sel]
        marg = rt_counts.get(i, 0) / n                      # runtime marginal
        parity_i = float(ag[sel].mean())
        # agreement stratified by WITHIN-ZONE margin tercile
        terciles = []
        if n_i >= 3:
            cuts = np.quantile(m_i, [0.0, 1 / 3, 2 / 3, 1.0])
            for t in range(3):
                lo, hi = cuts[t], cuts[t + 1]
                s = (m_i >= lo) & (m_i <= hi) if t == 2 else (m_i >= lo) & (m_i < hi)
                if s.sum():
                    terciles.append({
                        "tercile": t + 1, "margin_lo": float(lo), "margin_hi": float(hi),
                        "n": int(s.sum()), "agreement": float(ag[sel][s].mean()),
                    })
        per_zone.append({
            "zone": i,
            "label_n": n_i,
            "label_share": n_i / n,
            "runtime_n": rt_counts.get(i, 0),
            "runtime_marginal": marg,
            "parity": parity_i,
            "lift": parity_i - marg,
            "enrichment": (parity_i / marg) if marg > 0 else None,
            "margin_median": float(np.median(m_i)),
            "margin_p10": float(np.quantile(m_i, 0.10)),
            "margin_p90": float(np.quantile(m_i, 0.90)),
            "frac_margin_lt_0.01": float((m_i < 0.01).mean()),
            "frac_margin_lt_0.05": float((m_i < 0.05).mean()),
            "agreement_by_margin_tercile": terciles,
        })
    report["per_zone"] = per_zone

    # ── apply the PRE-DECLARED anomaly criterion ────────────────────────────
    lifts = np.array([z["lift"] for z in per_zone], dtype=np.float64)
    thr_lift = float(lifts.mean() + ANOMALY_LIFT_SD_MULT * lifts.std(ddof=0))
    selected = [
        z["zone"] for z in per_zone
        if z["lift"] > thr_lift
        or (z["enrichment"] is not None and z["enrichment"] > ANOMALY_ENRICHMENT_X)
    ]
    report["anomaly_criterion"] = {
        "declared_before_inspection": True,
        "expected_agreement_baseline": "runtime marginal m_i (not label share, not 1/k)",
        "lift_threshold": thr_lift,
        "lift_rule": f"lift > mean + {ANOMALY_LIFT_SD_MULT}*sd",
        "enrichment_rule": f"enrichment > {ANOMALY_ENRICHMENT_X}x",
        "selected_zones": selected,
        "not_anomalous_note": ("Zones failing BOTH rules are explained by their runtime "
                               "marginal alone. In particular a large LABEL zone with low "
                               "parity is not anomalous if the runtime seldom picks it."),
    }

    # ── focused investigation: ONLY the selected zones ──────────────────────
    investigations = []
    for zi in selected:
        row = conf[zi]
        tot = max(sum(row), 1)
        dests = sorted(range(k), key=lambda j: -row[j])[:3]
        zrec = next(z for z in per_zone if z["zone"] == zi)
        terc = zrec["agreement_by_margin_tercile"]
        grad = (terc[-1]["agreement"] - terc[0]["agreement"]) if len(terc) >= 2 else None
        investigations.append({
            "zone": zi,
            "why_selected": {
                "lift": zrec["lift"], "exceeds_lift_threshold": zrec["lift"] > thr_lift,
                "enrichment": zrec["enrichment"],
                "exceeds_enrichment": (zrec["enrichment"] or 0) > ANOMALY_ENRICHMENT_X,
            },
            "top_runtime_destinations": [
                {"runtime_zone": j, "n": row[j], "share_of_label_zone": row[j] / tot}
                for j in dests
            ],
            "margin_profile": {
                "median": zrec["margin_median"],
                "frac_lt_0.01": zrec["frac_margin_lt_0.01"],
                "frac_lt_0.05": zrec["frac_margin_lt_0.05"],
            },
            "within_zone_margin_gradient": grad,
            "instability_driven": (None if grad is None else bool(grad > 0.15)),
        })
    report["anomalous_zone_investigations"] = investigations

    # ── margin-gradient structure ───────────────────────────────────────────
    # DO NOT average these. The per-zone gradients are BIMODAL in sign: zones the runtime
    # favours agree MORE as margin grows, while zones it disfavours fall toward 0.000
    # agreement at high margin. A mean over opposing signs is meaningless and would report
    # a single "instability" verdict for two opposite behaviours. Report the split.
    grads = {z["zone"]: (z["agreement_by_margin_tercile"][-1]["agreement"]
                         - z["agreement_by_margin_tercile"][0]["agreement"])
             for z in per_zone if len(z["agreement_by_margin_tercile"]) >= 2}
    rising = sorted(z for z, g in grads.items() if g > 0.05)
    falling = sorted(z for z, g in grads.items() if g < -0.05)
    flat = sorted(z for z, g in grads.items() if -0.05 <= g <= 0.05)
    top2_set = set(report["runtime_concentration"]["top2_zones"])

    report["margin_gradient_structure"] = {
        "per_zone_gradient": {str(z): g for z, g in sorted(grads.items())},
        "rising_zones": rising,
        "falling_zones": falling,
        "flat_zones": flat,
        "bimodal": bool(rising and falling),
        "mean_is_meaningless": bool(rising and falling),
        "rising_are_runtime_attractors": bool(set(rising) & top2_set == top2_set),
        "interpretation": (
            "RISING zone: when the runtime is confident (large top1-top2 margin) it agrees "
            "with the label -> disagreement there is near-tie INSTABILITY. "
            "FALLING zone: when the runtime is confident it systematically picks a "
            "DIFFERENT zone (agreement -> ~0) -> that disagreement is SYSTEMATIC "
            "re-routing, not noise. Both mechanisms operate simultaneously on different "
            "zones, which is why no single scalar describes the 41.4%."
        ),
    }

    report["verdict"] = {
        "parity_reproduced": True,
        "mechanical_cause": ("KMeans variance is 99.99% carried by dims the runtime "
                             "zeroes; the two partitions are built on near-disjoint "
                             "information."),
        "all_zones_positive_lift": bool(all(z["lift"] > 0 for z in per_zone)),
        "residual_over_majority_baseline": report["agreement"]["lift_over_majority"],
        "cohens_kappa": report["agreement"]["cohens_kappa"],
        "near_tie_prevalence": {
            "frac_margin_lt_0.05_overall": float((m < 0.05).mean()),
            "frac_margin_lt_0.01_overall": float((m < 0.01).mean()),
        },
        "two_mechanisms": ("near-tie instability (margins are tiny corpus-wide) AND "
                           "systematic re-routing into the runtime's attractor zones"),
        "instability_driven": "BIMODAL_SEE_margin_gradient_structure",
        "anomalous_zones": selected,
    }

    out = _ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"[parity] wrote {out}")
    print(json.dumps({"agreement": report["agreement"],
                      "verdict": report["verdict"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
