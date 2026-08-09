#!/usr/bin/env python3
"""build_g001_consumer_attribution.py â€” semantic correctness vs economic contribution.

Permanent ledger: each *consumer* (decision path / engine / gate) is attributed
separately for:

  1. SEMANTIC â€” does it use correctly validated FM math?
  2. ECONOMIC â€” has Î”G001 been measured for this consumer?
  3. AUTHORITY â€” may it influence production? (ladder; default NONE)

Invariant (CLAUDE.md Â§6.5): evidence / parity / resolve_fm NEVER auto-grants
G001 authority. Only demonstrated Î”G001 under a pre-registered consumer study can.

Usage:
  python scripts/governance/build_g001_consumer_attribution.py
  python scripts/governance/build_g001_consumer_attribution.py --check
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

_OUT_JSON = ROOT / "docs" / "governance" / "g001_consumer_attribution.json"
_OUT_MD = ROOT / "docs" / "governance" / "g001_consumer_attribution.md"

# Authority ladder levels (CLAUDE.md Â§6.5) â€” string keys so JSON round-trip is stable.
# 0 = information only Â· 1 = economic usefulness measured Â· 2 = authority earned Â· 3 = architecture
_LADDER = {
    "0": "INFORMATION_ONLY",
    "1": "ECONOMIC_USEFULNESS_MEASURED",
    "2": "AUTHORITY_EARNED",
    "3": "ARCHITECTURE_JUSTIFIED",
}

# Hand-maintained consumer ledger. economic_status cites findings where known.
# Update this table when a new shadow A/B or M4 measurement lands â€” never auto-promote.
_CONSUMERS: list[dict] = [
    {
        "consumer_id": "crt_spine_state_machine",
        "path": "src/config_layer/crt_engine_v2.py",
        "description": "CRT state machine â†’ TRADE_OPENED path (primary research spine)",
        "features_or_signals": [
            "FM-002", "FM-010", "FM-027", "FM-028", "structural states via pipeline"
        ],
        "semantic_status": "VALIDATED",
        "semantic_evidence": [
            "tests/test_fm_resolution_phase2.py",
            "tests/test_fc1a_swing_oracle_parity.py",
            "docs/governance/crt_closure_report.md",
        ],
        "economic_status": "MEASURED_NO_STANDALONE_EDGE",
        "economic_evidence": [
            "F-019", "F-021", "F-025", "F-026", "F-027",
            "docs/current-findings.md",
        ],
        "economic_notes": (
            "Multiple M4-style studies under realistic exits: entry-information null "
            "on crypto majors; spine throughput-starved; not a G001-clearing edge."
        ),
        "authority_ladder_level": 0,
        "production_influence_allowed": True,  # already production path; no NEW authority
        "production_influence_scope": "incumbent_crt_path_only",
        "new_authority_from_parity": False,
    },
    {
        "consumer_id": "scoring_engine_crt_composite",
        "path": "src/engines/scoring_engine.py",
        "description": "CRT composite score (sweep/breakout/retest/time); FM-029 rescale",
        "features_or_signals": ["FM-029", "body_ratio", "retest_depth", "sweep flags"],
        "semantic_status": "VALIDATED",
        "semantic_evidence": [
            "tests/test_gd004_gd005_identity_closure.py",
            "tests/test_fm_resolution_phase3.py",
        ],
        "economic_status": "NOT_ISOLATED",
        "economic_evidence": ["F-021"],
        "economic_notes": (
            "Score/zone selection skill not demonstrated under intrabar+12bps "
            "(F-021). No isolated Î”G001 study for FM-029 alone."
        ),
        "authority_ladder_level": 0,
        "production_influence_allowed": True,
        "production_influence_scope": "incumbent_scoring_only",
        "new_authority_from_parity": False,
    },
    {
        "consumer_id": "engine_runner_fusion",
        "path": "src/core/engine_runner.py",
        "description": "Four-engine fusion gate (CRT/Gaussian/Zone/RR)",
        "features_or_signals": ["engine scores", "zone_gate", "rr", "gaussian"],
        "semantic_status": "PARTIAL",
        "semantic_evidence": [
            "F-037", "F-038", "F-060",
            "docs/governance/gaussian_lineage_audit.md",
            "docs/governance/rr_lineage_audit.md",
        ],
        "economic_status": "MEASURED_NON_PIVOTAL_OR_INERT_CHANNELS",
        "economic_evidence": ["F-036", "F-037", "F-060", "F-038"],
        "economic_notes": (
            "Zone non-pivotal (F-036); Gaussian near-constant inert (F-060); "
            "rr_fusion disabled (F-038). Gate-ON modest N change only (F-037)."
        ),
        "authority_ladder_level": 0,
        "production_influence_allowed": True,
        "production_influence_scope": "incumbent_fusion_when_enabled",
        "new_authority_from_parity": False,
    },
    {
        "consumer_id": "zone_gate",
        "path": "src/engines/zone_gate_engine.py",
        "description": "Geometric HARD zone gate",
        "features_or_signals": ["zone registry geometry", "feature vectors for membership"],
        "semantic_status": "AUDITED",
        "semantic_evidence": ["docs/governance/zonegate_lineage_audit.md", "F-041"],
        "economic_status": "MEASURED_NO_MARGINAL_VALUE",
        "economic_evidence": ["F-036", "F-041B"],
        "economic_notes": "Non-pivotal; honest labels show no zone with E>0.",
        "authority_ladder_level": 0,
        "production_influence_allowed": True,
        "production_influence_scope": "incumbent_hard_gate_geometry",
        "new_authority_from_parity": False,
    },
    {
        "consumer_id": "bitnet_gate",
        "path": "src/bitnet/bitnet_inference.py",
        "description": "BitNet hard-reject gate when use_bitnet enabled",
        "features_or_signals": ["38/39-dim canonical vector"],
        "semantic_status": "AUDITED_CONDITIONAL_SKEW",
        "semantic_evidence": ["docs/governance/bitnet_lineage_audit.md", "F-004", "F-050", "F-055"],
        "economic_status": "MEASURED_NO_IMPROVEMENT",
        "economic_evidence": ["F-055"],
        "economic_notes": (
            "Shadow A/B: gate-ON does not improve CRT spine; use_bitnet stays false on active."
        ),
        "authority_ladder_level": 0,
        "production_influence_allowed": False,
        "production_influence_scope": "inert_on_active_config",
        "new_authority_from_parity": False,
    },
    {
        "consumer_id": "rr_fusion",
        "path": "src/config_layer/rr/rr_fusion.py",
        "description": "RR fusion confidence gate over RR engine",
        "features_or_signals": ["rr_model", "gaussian fallback historically"],
        "semantic_status": "AUDITED_GATE_MISSPEC",
        "semantic_evidence": ["F-038", "F-044", "F-045", "F-059"],
        "economic_status": "DISABLED_NO_AUTHORITY",
        "economic_evidence": ["F-038", "F-059"],
        "economic_notes": "rr_fusion enabled:false on active; clean-label KEEP_CANDIDATE research-only.",
        "authority_ladder_level": 0,
        "production_influence_allowed": False,
        "production_influence_scope": "disabled",
        "new_authority_from_parity": False,
    },
    {
        "consumer_id": "session_filter",
        "path": "src/features/session_classifier.py + engine allowed_sessions",
        "description": "Session FEATURE (FM-052) vs session FILTER policy (distinct)",
        "features_or_signals": ["FM-051", "FM-052"],
        "semantic_status": "VALIDATED",
        "semantic_evidence": [
            "tests/test_feature_temporal_context.py",
            "tests/test_session_classifier.py",
        ],
        "economic_status": "MEASURED_NOT_PROMOTABLE_BNB",
        "economic_evidence": ["F-017", "F-021"],
        "economic_notes": "Session policy not a promotable BNB lever under realistic exits + OOS.",
        "authority_ladder_level": 0,
        "production_influence_allowed": True,
        "production_influence_scope": "filter_policy_config",
        "new_authority_from_parity": False,
    },
    {
        "consumer_id": "ultron_risk_gate",
        "path": "src/core/ultron_risk_gate.py",
        "description": "Final risk / min_rr economic gate (owns RR economics post F-048)",
        "features_or_signals": ["execution plan RR", "risk params"],
        "semantic_status": "CONTRACT_DEFINED",
        "semantic_evidence": ["F-048", "tests/test_ultron_risk_gate.py"],
        "economic_status": "LIVE_UNVERIFIED_HEADLINE",
        "economic_evidence": ["F-010"],
        "economic_notes": (
            "Headline ROI backtest-only; live PnL through ExecutionPlanner+Ultron UNVERIFIED (F-010)."
        ),
        "authority_ladder_level": 0,
        "production_influence_allowed": True,
        "production_influence_scope": "incumbent_risk_gate",
        "new_authority_from_parity": False,
    },
    {
        "consumer_id": "feature_state_encoder_shadow",
        "path": "src/features/feature_states.py + crt_state_resolver",
        "description": "Shadow state naming / CRTStateResolver research path",
        "features_or_signals": ["states blocks for vector-bound FMs"],
        "semantic_status": "VALIDATED_MAPPING",
        "semantic_evidence": ["tests/test_feature_states.py"],
        "economic_status": "NOT_ON_TRADING_PATH",
        "economic_evidence": [],
        "economic_notes": "Research/shadow only; cannot earn G001 by definition until wired.",
        "authority_ladder_level": 0,
        "production_influence_allowed": False,
        "production_influence_scope": "shadow_only",
        "new_authority_from_parity": False,
    },
    {
        "consumer_id": "liquidity_sweep_veto",
        "path": "research/H-G001-001 + research/H-G001-001b (post-entry filter on spine)",
        "description": (
            "H-G001-001/H-G001-001b: veto production CRT spine entries when FM-058 "
            "liquidity_sweep != 0 on entry bar (XAUUSD M15, M4 intrabar+12bps; "
            "fusion gate ON and CRT-only lenses measured separately)"
        ),
        "features_or_signals": ["FM-058"],
        "semantic_status": "VALIDATED",
        "semantic_evidence": [
            "tests/test_fc1a_swing_oracle_parity.py",
            "tests/test_feature_structural_states_complex.py",
        ],
        "economic_status": "MEASURED_INSUFFICIENT",
        "economic_evidence": [
            "research/H-G001-001/promotion_decision.md",
            "research/H-G001-001/baseline_results.json",
            "research/H-G001-001/treatment_results.json",
            "research/H-G001-001b/promotion_decision.md",
            "research/H-G001-001b/baseline_results.json",
            "research/H-G001-001b/treatment_results.json",
            "F-029",
            "F-035",
        ],
        "economic_notes": (
            "2026-07-26 H-G001-001: production spine on frozen XAUUSD candidate yielded n=1 "
            "entry (fusion gate ON); treatment identical (0 vetoes on that entry). "
            "REJECT_INSUFFICIENT; no delta_G001 claim. "
            "2026-07-26 H-G001-001b: CRT-only lens also yielded n=1; treatment identical "
            "(0 vetoes). REJECT_INSUFFICIENT. Reopen only with a powered entry set "
            "(n>=30) or alternate instrument/corpus under a new H-id."
        ),
        "authority_ladder_level": 0,
        "production_influence_allowed": False,
        "production_influence_scope": "research_only_rejected_insufficient",
        "new_authority_from_parity": False,
    },
]


def build() -> dict:
    for c in _CONSUMERS:
        if c["new_authority_from_parity"] is not False:
            raise AssertionError(
                f"{c['consumer_id']}: new_authority_from_parity must be False "
                "(parity never grants authority)"
            )
        if str(c["authority_ladder_level"]) not in _LADDER:
            raise AssertionError(f"{c['consumer_id']}: bad ladder level")
        # Guard: no consumer may claim ladder >= 2 without economic MEASURED positive
        if c["authority_ladder_level"] >= 2:
            if "MEASURED_POSITIVE" not in c["economic_status"]:
                raise AssertionError(
                    f"{c['consumer_id']}: ladder>1 requires MEASURED_POSITIVE economic_status"
                )

    return {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "purpose": (
            "Distinguish semantic correctness (FM parity / resolve_fm / audits) from "
            "economic contribution (Î”G001). Authority ladder is explicit and non-automatic."
        ),
        "goal_id": "G001",
        "goal_doc": "docs/architecture/goal.md",
        "authority_ladder": _LADDER,
        "invariants": [
            "new_authority_from_parity is always false",
            "ladder level >= 2 requires economic_status MEASURED_POSITIVE (none today)",
            "incumbent production_influence_allowed does not imply new authority earned",
            "feature-layer parity is tracked in fm_ownership_consumer_matrix.json only",
        ],
        "summary": {
            "consumer_count": len(_CONSUMERS),
            "ladder_gt0_count": sum(
                1 for c in _CONSUMERS if c["authority_ladder_level"] > 0
            ),
            "semantic_validated_count": sum(
                1 for c in _CONSUMERS if c["semantic_status"] == "VALIDATED"
            ),
            "economic_positive_delta_count": sum(
                1
                for c in _CONSUMERS
                if "MEASURED_POSITIVE" in c["economic_status"]
            ),
        },
        "consumers": _CONSUMERS,
    }


def render_md(doc: dict) -> str:
    lines = [
        "# G001 Consumer Attribution",
        "",
        f"> Generated: `{doc['generated_at_utc']}` Â· schema v{doc['schema_version']}",
        ">",
        f"> Goal: **{doc['goal_id']}** Â· see [`goal.md`](../architecture/goal.md)",
        ">",
        "> **This ledger separates semantic correctness from economic contribution.**",
        "> Passing FM parity / resolve_fm / oracle tests does **not** move G001 and does",
        "> **not** grant production authority (CLAUDE.md Â§6.5 Authority Ladder).",
        "",
        "## Authority ladder",
        "",
    ]
    for k in sorted(doc["authority_ladder"].keys(), key=int):
        lines.append(f"- **Level {k}** â€” `{doc['authority_ladder'][k]}`")
    lines += [
        "",
        "## Summary",
        "",
        f"- Consumers: **{doc['summary']['consumer_count']}**",
        f"- Semantic VALIDATED: **{doc['summary']['semantic_validated_count']}**",
        f"- Ladder > 0: **{doc['summary']['ladder_gt0_count']}**",
        f"- Economic MEASURED_POSITIVE Î”G001: **{doc['summary']['economic_positive_delta_count']}**",
        "",
        "## Consumers",
        "",
        "| Consumer | Semantic | Economic | Ladder | Prod influence | New auth from parity |",
        "|---|---|---|---|---|---|",
    ]
    for c in doc["consumers"]:
        lines.append(
            f"| `{c['consumer_id']}` | {c['semantic_status']} | {c['economic_status']} | "
            f"{c['authority_ladder_level']} | {c['production_influence_allowed']} | "
            f"{c['new_authority_from_parity']} |"
        )
    lines += [
        "",
        "### Detail",
        "",
    ]
    for c in doc["consumers"]:
        lines += [
            f"#### `{c['consumer_id']}`",
            "",
            f"- **Path:** `{c['path']}`",
            f"- **Description:** {c['description']}",
            f"- **Signals:** {', '.join(c['features_or_signals'])}",
            f"- **Semantic evidence:** {', '.join(c['semantic_evidence']) or 'â€”'}",
            f"- **Economic evidence:** {', '.join(c['economic_evidence']) or 'â€”'}",
            f"- **Notes:** {c['economic_notes']}",
            f"- **Scope:** `{c['production_influence_scope']}`",
            "",
        ]
    lines += [
        "## How to update",
        "",
        "1. Run a pre-registered consumer A/B (shadow) with `goal_report` / Î”G001 metrics.",
        "2. Edit `_CONSUMERS` in `scripts/governance/build_g001_consumer_attribution.py`.",
        "3. Set `economic_status` / evidence / ladder only from measured results.",
        "4. Regenerate: `python scripts/governance/build_g001_consumer_attribution.py`",
        "5. Never set `new_authority_from_parity=true`.",
        "",
        "## Related",
        "",
        "- Feature ownership: [`fm_ownership_consumer_matrix.md`](fm_ownership_consumer_matrix.md)",
        "- Goal layer topic: [`docs/topics/goal-layer.md`](../topics/goal-layer.md)",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    doc = build()

    if args.check:
        if not _OUT_JSON.is_file():
            print(f"MISSING {_OUT_JSON}", file=sys.stderr)
            return 1
        on_disk = json.loads(_OUT_JSON.read_text(encoding="utf-8"))
        a = {**on_disk, "generated_at_utc": None}
        b = {**doc, "generated_at_utc": None}
        if a != b:
            print("DRIFT: g001_consumer_attribution.json is stale; regenerate.", file=sys.stderr)
            return 1
        print("OK: g001_consumer_attribution.json matches builder")
        return 0

    _OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    _OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    _OUT_MD.write_text(render_md(doc), encoding="utf-8")
    print(f"Wrote {_OUT_JSON.relative_to(ROOT)}")
    print(f"Wrote {_OUT_MD.relative_to(ROOT)}")
    print(
        f"consumers={doc['summary']['consumer_count']} "
        f"ladder_gt0={doc['summary']['ladder_gt0_count']} "
        f"econ_positive={doc['summary']['economic_positive_delta_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

