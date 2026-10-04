"""
e1_retest_depth_max_probe.py
=============================
Phase E1 of the "CRT single source of truth" plan (2026-08-31 session).

Isolated, un-confounded probe of `thresholds.retest_depth_max` at exactly the 3 values the E1
adjudication needs to compare: 0.08 (current market_crt_states.yaml value / what the resolver
reads today), 0.15 (what crt_engine_v2 actually runs, per Phase A's census), and 0.25 (the bare
CRTConfig code default). Research-only (CLAUDE.md Section 6.5 Authority Ladder) -- this
measures the resolver's semantic parity against the ENGINE, it does not touch or gate any
production decision.

Why a new tiny script instead of re-running crt_parity_sweep.py directly
    F-069's own recorded sweep (results/analysis/crt_parity_sweep/ledger.jsonl, iterations
    28-30) already tested retest_depth_max, but CONFOUNDED with two other simultaneously-changed
    params (thresholds.body_ratio_min=0.55, thresholds.max_expansion_age_candles=250) -- so it
    answers "does retest_depth_max matter GIVEN those two other changes", not "does it matter
    against the unmodified baseline", and it tested {0.02, 0.04, 0.25}, not {0.08, 0.15, 0.25}.
    `crt_parity_sweep.py`'s own `main()` only runs its hardcoded 33-candidate STAGE_A_GROUPS list
    -- there is no CLI surface for an arbitrary single-parameter probe. This script is NOT a new
    harness: it imports and calls that module's own `evaluate_candidate` / `materialize_candidate`
    / `anti_simpson_ok` functions directly (same engine-comparison kernel, same confusion-matrix
    machinery, same anti-Simpson guard), just without going through the fixed candidate list.
    Writes to its OWN scratch root (results/analysis/e1_retest_depth_max_probe/), never touching
    or appending to F-069's established sweep_root/ledger.jsonl.

Existing evidence already checked (read before writing this script, not re-derived blind)
    reports/crt_semantic_parity_report.md + results/analysis/crt_parity_sweep/iters/iter_00{18,
    28,29,30}.json: at retest_depth_max in {0.02, 0.04, 0.25} (confounded as above), RETEST's
    resolver_n is EXACTLY 0 in every case -- the resolver classifies ZERO of 47,197 bars as
    RETEST regardless of the threshold value. Baseline (iter 1, unconfounded) shows the same:
    engine_n=17, resolver_n=0, recall=0.00%. This probe exists to confirm that holds at the
    THREE VALUES E1 actually needs, unconfounded, before treating "retest_depth_max is
    non-pivotal" as established for the adjudication.

Usage
    python scripts/research/e1_retest_depth_max_probe.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "scripts" / "research"))

import crt_state_confusion_matrix as cm  # noqa: E402
from crt_parity_sweep import (  # noqa: E402
    DEFAULT_BASE_CONFIG,
    DEFAULT_EVENTS,
    DEFAULT_OHLCV,
    anti_simpson_ok,
    evaluate_candidate,
    materialize_candidate,
    per_state_summary,
)

PROBE_ROOT = _ROOT / "results" / "analysis" / "e1_retest_depth_max_probe"
OUT_JSON = PROBE_ROOT / "e1_retest_depth_max_probe.json"

#: The 3 values E1 must compare, each with its own meaning.
CANDIDATES = [
    ("current (YAML today)", {}),  # empty delta == market_crt_states.yaml as-is == 0.08
    ("engine-resolved (params)", {"thresholds.retest_depth_max": 0.15}),
    ("code default", {"thresholds.retest_depth_max": 0.25}),
]


def main() -> int:
    import yaml

    print(f"Preparing engine context ({DEFAULT_OHLCV}, {DEFAULT_EVENTS})...")
    engine_ctx = cm.prepare_engine_context(DEFAULT_OHLCV, DEFAULT_EVENTS)
    print(f"  n_bars={engine_ctx.n_bars} transitions={engine_ctx.timeline.n_transitions}")
    enriched = cm.compute_enriched_frame(engine_ctx.ohlcv_path)
    base_cfg = yaml.safe_load(DEFAULT_BASE_CONFIG.read_text(encoding="utf-8"))

    PROBE_ROOT.mkdir(parents=True, exist_ok=True)

    records = []
    baseline_per_state = None
    baseline_agreement = 0
    baseline_total = 0

    for i, (label, delta) in enumerate(CANDIDATES, start=1):
        cand_path = materialize_candidate(base_cfg, delta, PROBE_ROOT) if delta else None
        record = evaluate_candidate(
            engine_ctx, iter_num=i, stage="E1", delta=delta, cand_path=cand_path,
            enriched=enriched,
            baseline_agreement=baseline_agreement, baseline_total=baseline_total,
            best_agreement=baseline_agreement,
        )
        record["label"] = label
        if baseline_per_state is None:
            baseline_per_state = record["per_state"]
            baseline_agreement = record["agreement"]
            baseline_total = record["total"]
            record["anti_simpson_ok"] = True
            record["anti_simpson_violations"] = []
        else:
            ok, violations = anti_simpson_ok(baseline_per_state, record["per_state"])
            record["anti_simpson_ok"] = ok
            record["anti_simpson_violations"] = violations
        records.append(record)

        ret = record["per_state"].get("RETEST", {})
        print(
            f"\n[{label}] retest_depth_max delta={delta or '(baseline, 0.08)'}"
            f"\n  agreement: {record['agreement_rate']:.4%} "
            f"({record['delta_vs_baseline_pp']:+.2f}pp vs candidate-1 baseline)"
            f"\n  RETEST:    engine_n={ret.get('engine_n')} resolver_n={ret.get('resolver_n')} "
            f"tp={ret.get('tp')} recall={ret.get('recall')}"
            f"\n  anti_simpson: {'OK' if record['anti_simpson_ok'] else 'VIOLATED: ' + '; '.join(record['anti_simpson_violations'])}"
        )

    out = {
        "purpose": "Phase E1 adjudication probe: retest_depth_max at {0.08, 0.15, 0.25}, "
                   "unconfounded (no other threshold changed)",
        "records": records,
    }
    OUT_JSON.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(f"\nwrote {OUT_JSON.relative_to(_ROOT)}")

    agreements = {r["label"]: r["agreement_rate"] for r in records}
    retest_recalls = {r["label"]: r["per_state"].get("RETEST", {}).get("recall")
                       for r in records}
    print("\n" + "=" * 68)
    print("E1 SUMMARY")
    for label in agreements:
        print(f"  {label:28s} agreement={agreements[label]:.4%}  "
              f"RETEST recall={retest_recalls[label]}")
    all_same_agreement = len(set(agreements.values())) == 1
    all_same_retest = len(set(retest_recalls.values())) == 1
    print(f"\n  All 3 candidates identical agreement: {all_same_agreement}")
    print(f"  All 3 candidates identical RETEST recall: {all_same_retest}")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
