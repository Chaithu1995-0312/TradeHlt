"""zone_label_audit.py — thin driver for the F-041B Phase-5 ZoneGate label audit.

Argparse wrapper only (per CLAUDE.md §3.3): no business logic lives here. Loads the runtime zone
registry + the SOURCE opportunities that built it + the candles, reconstructs the ORIGINAL seeded
KMeans membership by calling `discover_zones._kmeans` VERBATIM (identical geometry), runs
`research.zone_label_audit`, and writes a deterministic report under docs/analysis/.

Usage:
  python scripts/research/zone_label_audit.py \
      --registry models/zone_registry.json \
      --opportunities logs/BNBUSDT/bnbusdt_training_20260524/opportunities.jsonl \
      --candles data/BNBUSDT_M15.csv --instrument BNBUSDT
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
# discover_zones lives beside this driver; import it for the VERBATIM KMeans + vector builder.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import discover_zones as dz                                          # noqa: E402
from features.feature_schema import CANONICAL_FEATURE_ORDER          # noqa: E402
from research import zone_label_audit as zla                         # noqa: E402
from research.zone_label_audit import (                              # noqa: E402
    verify_membership, assignment_parity, audit_zones, classify_verdict,
    build_report, honest_outcome,
)

# candle loader reused verbatim from the proven anatomy substrate
sys.path.insert(0, str(ROOT / "scripts" / "analysis"))
from bnbusdt_trade_anatomy import load_candles                      # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--registry", default="models/zone_registry.json")
    ap.add_argument("--opportunities",
                    default="logs/BNBUSDT/bnbusdt_training_20260524/opportunities.jsonl")
    ap.add_argument("--candles", default="data/BNBUSDT_M15.csv")
    ap.add_argument("--instrument", default="BNBUSDT")
    ap.add_argument("--n-clusters", type=int, default=8)
    ap.add_argument("--out", default=None,
                    help="report path (default docs/analysis/f041b-zone-label-audit-{inst}.json)")
    args = ap.parse_args(argv)

    reg = json.loads((ROOT / args.registry).read_text(encoding="utf-8"))
    zones = reg["zones"]
    n_feat = len(CANONICAL_FEATURE_ORDER)
    weights = [1.0] * n_feat                      # discover_zones default (reproduces the build)

    # ── reconstruct ORIGINAL membership: mirror discover.discover() lines 115-139 verbatim ──
    vecs_weighted: list[list[float]] = []         # KMeans space (× feature_weights)
    vecs_raw: list[list[float]] = []              # runtime Gaussian space (raw 38-vec)
    outcomes: list[str] = []
    rrs: list[float] = []
    opps: list[dict] = []
    for rec in dz._load_records(ROOT / args.opportunities):
        v = dz._vector_from_record(rec, weights)
        if v is None:
            continue
        feats = rec["features"]
        vecs_weighted.append(v)
        vecs_raw.append([float(feats[name]) for name in CANONICAL_FEATURE_ORDER])
        rrs.append(float(rec.get("rr_achieved", 0.0) or 0.0))
        outcomes.append(str(rec.get("outcome", "UNKNOWN")))
        opps.append(rec)
    n = len(vecs_weighted)
    print(f"[audit] loaded {n} valid records ({n_feat}-dim); reconstructing {args.n_clusters}-zone KMeans (seed=1337)")

    assignments, _centers = dz._kmeans(vecs_weighted, args.n_clusters)
    reconstructed = [[i for i, a in enumerate(assignments) if a == c] for c in range(args.n_clusters)]

    # ── gate 0: membership verification (runs FIRST; halt on FAILED) ──
    membership = verify_membership(zones, reconstructed, outcomes, rrs)
    print(f"[audit] membership_verification.status = {membership['status']}")
    for d in membership["detail"]:
        print(f"        {d['stored_zone']}: stored_n={d['stored_n']} recon_n={d['recon_n']} "
              f"mean_ok={d['mean_ok']} sl_ok={d['sl_ok']}")
    out_path = ROOT / (args.out or f"docs/analysis/f041b-zone-label-audit-{args.instrument}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if membership["status"] == "FAILED":
        report = build_report(
            instrument=args.instrument, source_opportunities=args.opportunities,
            registry_path=args.registry, membership=membership,
            parity={"overall": None, "per_zone": {}, "n": n}, audits=[],
            verdict={"verdict": "MEMBERSHIP_RECONSTRUCTION_FAILED",
                     "membership_status": "FAILED"},
            skips={"reason": "count multiset mismatch -- cannot isolate contamination"}, n_records=n)
        out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print(f"[audit] HALT: MEMBERSHIP_RECONSTRUCTION_FAILED -- no verdict emitted. Report: {out_path}")
        return 2

    # ── honest relabel over the RECONSTRUCTED membership (isolates contamination) ──
    candles, ts_to_idx, _closes = load_candles(ROOT / args.candles)
    honest = []
    skips = {"no_candle_or_future": 0}
    for opp in opps:
        o = honest_outcome(opp, candles, ts_to_idx)
        honest.append(o)
        if o is None:
            skips["no_candle_or_future"] += 1
    print(f"[audit] honest relabel done; skips={skips}")

    parity = assignment_parity(vecs_raw, assignments, zones, membership["mapping"])
    print(f"[audit] assignment_parity overall = {parity['overall']}")
    audits = audit_zones(reconstructed, membership["mapping"], zones, honest)
    verdict = classify_verdict(audits, membership["status"])
    print(f"[audit] VERDICT = {verdict['verdict']}  (powered zones={verdict['n_powered_zones']}, "
          f"insufficient={verdict['n_insufficient_zones']})")

    report = build_report(
        instrument=args.instrument, source_opportunities=args.opportunities,
        registry_path=args.registry, membership=membership, parity=parity,
        audits=audits, verdict=verdict, skips=skips, n_records=n)
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"[audit] report -> {out_path}")
    for a in report["zones"]:
        print(f"        {a['zone_id']}: n={a['n']} stored_sl={a['stored_sl_rate']} "
              f"honest_sl={a['honest_sl_rate']} d_sl={a['sl_delta']} "
              f"E_net={a['honest_expectancy']} CI=[{a['ci_low']},{a['ci_high']}] {a['sufficiency']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
