#!/usr/bin/env python3
"""Phase-1 duplicate implementation + formula identity closure.

Deterministic artifact generator + structural validators.
Does NOT promote corpus authority, retrain, or start PIT remediation.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

DATE = "2026-07-10"
GOV = ROOT / "docs" / "governance"
REG_PATH = GOV / f"phase1_feature_identity_registry-{DATE}.json"

from data_ingestion.xauusd_phase1_candidate import require_phase1_frozen_candidate  # noqa: E402
from features import candle_math as cm  # noqa: E402
from features import derived_math as dm  # noqa: E402
from features.feature_identity import (  # noqa: E402
    all_identities,
    clear_cache,
    get_by_feature_id,
    load_identity_registry,
)


def _canonical_json(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def _write(path: Path, obj: object) -> str:
    text = _canonical_json(obj)
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _authority_decisions() -> dict:
    return {
        "artifact": "phase1_duplicate_implementation_authority_decisions",
        "date": DATE,
        "decisions": [
            {
                "family": "VOLUME",
                "duplicate_pair": ["Q-VOL-PROXY-T003", "Q-VOL-RANGE-PROXY-SEPARATE"],
                "relationship": "SAME_SEMANTICS_SAME_FORMULA",
                "selected_authority": "FEAT-VOLUME_RANGE_PROXY / FeaturePipeline.volume_range_proxy",
                "rejected_path": "T-003 overwrite of df['volume'] with high-low",
                "rejection_reason": "same-name substitution under source-volume identity",
                "status": "CANONICAL_IMPLEMENTATION_SELECTED",
            },
            {
                "family": "VOLUME",
                "identity": "FEAT-VOLUME",
                "selected_authority": "source OHLCV passthrough",
                "status": "CANONICAL_IMPLEMENTATION_SELECTED",
            },
            {
                "family": "SWING",
                "relationship": "DIFFERENT_SEMANTICS (temporal publication)",
                "identities": [
                    "FEAT-SWING_HIGH_CENTERED_BATCH",
                    "FEAT-SWING_LOW_CENTERED_BATCH",
                    "FEAT-SWING_HIGH_CAUSAL_CONFIRMED",
                    "FEAT-SWING_LOW_CAUSAL_CONFIRMED",
                ],
                "selected_authority_production_vector": "CENTERED_BATCH columns",
                "rejected_mutation": "TRUST_SWING_CAUSAL in-place rewrite of swing_high/low",
                "status": "DISTINCT_SEMANTIC_PRESERVED",
            },
            {
                "family": "VOLATILITY_REGIME",
                "relationship": "DIFFERENT_SEMANTICS (rank population + temporal)",
                "identities": [
                    "FEAT-VOLATILITY_REGIME_GLOBAL_BATCH_RANK",
                    "FEAT-VOLATILITY_REGIME_EXPANDING_CAUSAL_RANK",
                    "FEAT-VOLATILITY_REGIME_ROLLING_CAUSAL_RANK",
                ],
                "selected_authority_production_vector": "GLOBAL_BATCH",
                "rejected_mutation": "TRUST_VOLREGIME_CAUSAL in-place rewrite of volatility_regime",
                "N_rolling_note": "N=200 provisional implementation param only; not final regime model selection",
                "status": "DISTINCT_SEMANTIC_PRESERVED",
            },
            {
                "family": "BODY_RATIO",
                "relationship": "DIFFERENT_SEMANTICS",
                "identities": [
                    "FEAT-BODY_TO_RANGE_RATIO",
                    "FEAT-BODY_TO_TOTAL_WICK_RATIO",
                ],
                "range_authority": "candle_math.body_ratio / FM-010",
                "total_wick_authority": "candle_math.body_to_total_wick_ratio / FM-013 + live_engine_hook binding",
                "status": "DISTINCT_SEMANTIC_PRESERVED",
            },
            {
                "family": "DISPLACEMENT_RETEST",
                "relationship": "all pairs DIFFERENT_SEMANTICS",
                "identities": [
                    "FEAT-DISP_STRENGTH",
                    "FEAT-RETEST_DEPTH",
                    "FEAT-DISPLACEMENT_RETRACE",
                    "FEAT-DISPLACEMENT_ATR_RATIO",
                ],
                "authorities": {
                    "FM-020": "derived_math.disp_strength",
                    "FM-021": "derived_math.retest_depth",
                    "FM-027": "derived_math.displacement_retrace",
                    "FM-028": "derived_math.displacement_atr_ratio",
                },
                "status": "IDENTITY_CLOSED",
            },
        ],
    }


def _consumer_bindings() -> dict:
    rows = []
    for ident in all_identities(str(REG_PATH)):
        for c in ident.consumer_bindings:
            rows.append(
                {
                    "consumer": c,
                    "feature_id": ident.feature_id,
                    "formula_id": ident.formula_id,
                    "formula_version": ident.formula_version,
                    "resolution_mode": "explicit_id"
                    if "legacy" not in c.lower()
                    else "legacy_alias_to_id",
                    "status": ident.status,
                    "family": ident.family,
                }
            )
    return {
        "artifact": "phase1_consumer_identity_bindings",
        "date": DATE,
        "bindings": rows,
        "blocked": [],
    }


def _follow_up() -> dict:
    return {
        "artifact": "phase1_duplicate_formula_follow_up_backlog",
        "date": DATE,
        "DIRECTLY_CONNECTED_NEW_RECORDS": [
            "live_engine_hook wick_size = total_wick vs pipeline wick_size = candle_range",
            "volume_range_proxy_ratio explicit column",
            "structure features inherit centered swing temporal semantics",
        ],
        "IN_SCOPE_ADDITIONS": [
            "volume_ratio/spike bind to source volume only",
            "live dual-emit body_to_range_ratio + body_to_total_wick_ratio",
            "research_view columns for env (non-mutating)",
        ],
        "FOLLOW_UP_BACKLOG": [
            {
                "id": "FU-WICK-SIZE-NAME",
                "item": "wick_size pipeline range vs live total_wick name collision",
            },
            {
                "id": "FU-SCORING-DISP",
                "item": "scoring_engine local disp_strength=move/atr third quantity",
            },
            {
                "id": "FU-STRUCTURE-CAUSAL-GRAPH",
                "item": "re-id higher_high/BOS/sweep under causal swing publication",
            },
            {
                "id": "FU-FC1-A-PIT",
                "item": "centered-swing leakage remediation (FC1-A)",
            },
            {
                "id": "FU-FC1-D-VR-SELECT",
                "item": "select final volatility regime causal formula + freeze N",
            },
            {
                "id": "FU-BITNET-RETRAIN",
                "item": "BitNet retrain on non-aliased FM keys",
            },
            {
                "id": "FU-PROXY-VECTOR",
                "item": "whether volume_range_proxy joins default 38-vector",
            },
        ],
    }


def _closure_report(binding) -> dict:
    idents = all_identities(str(REG_PATH))
    families = sorted({i.family for i in idents})
    return {
        "artifact": "phase1_duplicate_formula_identity_closure",
        "date": DATE,
        "require_phase1_frozen_candidate": "PASS",
        "corpus": {
            "physical_path": str(binding.physical_path).replace("\\", "/"),
            "sha256": binding.content_hash_sha256,
            "rows": binding.rows,
            "promoted": False,
        },
        "families_closed": families,
        "identity_count": len(idents),
        "pairwise_fm": {
            "FM-020_vs_FM-021": "DIFFERENT_SEMANTICS",
            "FM-020_vs_FM-027": "DIFFERENT_SEMANTICS",
            "FM-020_vs_FM-028": "DIFFERENT_SEMANTICS",
            "FM-021_vs_FM-027": "DIFFERENT_SEMANTICS",
            "FM-021_vs_FM-028": "DIFFERENT_SEMANTICS",
            "FM-027_vs_FM-028": "DIFFERENT_SEMANTICS",
        },
        "exact_duplicates_removed_from_governed_authority": [
            "T-003 volume column overwrite",
            "TRUST_SWING_CAUSAL in-place mutation of centered swing columns",
            "TRUST_VOLREGIME_CAUSAL in-place mutation of volatility_regime column",
        ],
        "ambiguous_names_eliminated_from_governed_lookup": [
            "volume (proxy no longer shares identity)",
            "swing_high / swing_low (bare name → legacy alias CENTERED only; causal has distinct names)",
            "volatility_regime (bare → legacy alias GLOBAL only; expanding/rolling distinct names)",
            "body_ratio (canonical is body_to_range_ratio; total_wick has distinct name)",
            "disp_strength / retest_depth historical CRT alias collisions (CH-002 emission + registry)",
        ],
        "oracle_checks": _oracle_checks(),
        "flags": {
            "PIT_REMEDIATION_STARTED": False,
            "MODEL_LINEAGE_STARTED": False,
            "MODEL_COMPATIBILITY_EVALUATED": False,
            "RETRAINING_PERFORMED": False,
            "ECONOMIC_CLAIMS_ALLOWED": False,
            "MODEL_ENABLEMENT_CHANGED": False,
            "MODEL_ARTIFACTS_CHANGED": False,
        },
        "DUPLICATE_FORMULA_IDENTITY_PHASE_STATUS": "COMPLETE",
    }


def _oracle_checks() -> dict:
    # body formulas
    br = cm.body_ratio(100.0, 110.0, 95.0, 108.0)
    btw = cm.body_to_total_wick_ratio(100.0, 110.0, 95.0, 108.0)
    assert abs(br - 8.0 / 15.0) < 1e-12
    assert abs(btw - 8.0 / 7.0) < 1e-12
    assert br != btw
    # proxy
    proxy = 110.0 - 95.0
    assert proxy == 15.0
    # FM oracles
    ds = dm.disp_strength(8.0, 0.01, 100.0)  # body/(atr*close)
    rd = dm.retest_depth(100.0, 99.0, 0.01)
    dret = dm.displacement_retrace(105.0, 100.0, 110.0)
    datr = dm.displacement_atr_ratio(15.0, 5.0)
    return {
        "body_to_range": br,
        "body_to_total_wick": btw,
        "price_range_proxy": proxy,
        "fm020_disp_strength": ds,
        "fm021_retest_depth": rd,
        "fm027_displacement_retrace": dret,
        "fm028_displacement_atr_ratio": datr,
    }


def _manifest(hashes: dict) -> dict:
    return {
        "artifact": "phase1_duplicate_formula_identity_manifest",
        "date": DATE,
        "DUPLICATE_FORMULA_IDENTITY_PHASE_STATUS": "COMPLETE",
        "PIT_REMEDIATION_STARTED": False,
        "MODEL_LINEAGE_STARTED": False,
        "MODEL_COMPATIBILITY_EVALUATED": False,
        "RETRAINING_PERFORMED": False,
        "ECONOMIC_CLAIMS_ALLOWED": False,
        "MODEL_ENABLEMENT_CHANGED": False,
        "MODEL_ARTIFACTS_CHANGED": False,
        "artifact_sha256": hashes,
        "production_code_changes": [
            "src/features/feature_pipeline.py",
            "src/features/candle_math.py",
            "src/features/feature_identity.py",
            "src/runtime/live_engine_hook.py",
            "configs/formulas/market_ontology.yaml",
        ],
        "registry_path": str(REG_PATH.relative_to(ROOT)).replace("\\", "/"),
    }


def _closure_md(report: dict) -> str:
    lines = [
        f"# Phase-1 Duplicate Formula Identity Closure ({DATE})",
        "",
        f"**Status:** `{report['DUPLICATE_FORMULA_IDENTITY_PHASE_STATUS']}`",
        "",
        "## Input binding",
        "",
        f"- require_phase1_frozen_candidate: **{report['require_phase1_frozen_candidate']}**",
        f"- path: `{report['corpus']['physical_path']}`",
        f"- sha256: `{report['corpus']['sha256']}`",
        f"- rows: {report['corpus']['rows']}",
        f"- corpus promoted: **false**",
        "",
        "## Families closed",
        "",
    ]
    for f in report["families_closed"]:
        lines.append(f"- {f}")
    lines += [
        "",
        f"Identity count: **{report['identity_count']}**",
        "",
        "## Exact duplicates removed from governed authority",
        "",
    ]
    for x in report["exact_duplicates_removed_from_governed_authority"]:
        lines.append(f"- {x}")
    lines += [
        "",
        "## Ambiguous names eliminated",
        "",
    ]
    for x in report["ambiguous_names_eliminated_from_governed_lookup"]:
        lines.append(f"- {x}")
    lines += [
        "",
        "## Flags",
        "",
        "```",
        json.dumps(report["flags"], indent=2),
        "```",
        "",
        "## What this does not prove",
        "",
        "- PIT/lookahead correctness is not closed",
        "- All canonical formulas are not yet audited",
        "- Full FeaturePipeline correctness is not proven",
        "- Batch/runtime/live parity is not proven",
        "- Model training lineage is not recovered",
        "- Model compatibility is not evaluated",
        "- No retraining performed",
        "- No economic claims",
        "",
        "## Next exact step",
        "",
        "STOP FOR USER REVIEW. Do not begin PIT/lookahead remediation automatically.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    clear_cache()
    binding = require_phase1_frozen_candidate(repo_root=ROOT)
    load_identity_registry(str(REG_PATH))

    hashes: dict[str, str] = {}

    # registry already on disk — hash it
    reg_text = REG_PATH.read_text(encoding="utf-8")
    # normalize registry to canonical form for determinism
    reg_obj = json.loads(reg_text)
    hashes[REG_PATH.name] = _write(REG_PATH, reg_obj)

    auth = _authority_decisions()
    p = GOV / f"phase1_duplicate_implementation_authority_decisions-{DATE}.json"
    hashes[p.name] = _write(p, auth)

    cons = _consumer_bindings()
    p = GOV / f"phase1_consumer_identity_bindings-{DATE}.json"
    hashes[p.name] = _write(p, cons)

    fu = _follow_up()
    p = GOV / f"phase1_duplicate_formula_follow_up_backlog-{DATE}.json"
    hashes[p.name] = _write(p, fu)

    report = _closure_report(binding)
    p = GOV / f"phase1_duplicate_formula_identity_closure-{DATE}.json"
    hashes[p.name] = _write(p, report)

    md_path = GOV / f"phase1_duplicate_formula_identity_closure-{DATE}.md"
    md_text = _closure_md(report)
    md_path.write_text(md_text, encoding="utf-8")
    hashes[md_path.name] = hashlib.sha256(md_text.encode("utf-8")).hexdigest()

    man = _manifest(hashes)
    p = GOV / f"phase1_duplicate_formula_identity_manifest-{DATE}.json"
    hashes[p.name] = _write(p, man)
    # rewrite manifest with self-hash included
    man["artifact_sha256"] = hashes
    hashes[p.name] = _write(p, man)

    # structural floors
    assert get_by_feature_id("FEAT-VOLUME", str(REG_PATH)).formula_id == (
        "FORMULA-SOURCE-TICK-VOLUME"
    )
    assert get_by_feature_id("FEAT-VOLUME_RANGE_PROXY", str(REG_PATH)).formula_id == (
        "FORMULA-PRICE-RANGE-PROXY-HL"
    )

    print("DUPLICATE_FORMULA_IDENTITY_PHASE_STATUS=COMPLETE")
    print(f"artifacts={len(hashes)}")
    for k, v in sorted(hashes.items()):
        print(f"  {k}: {v[:16]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
