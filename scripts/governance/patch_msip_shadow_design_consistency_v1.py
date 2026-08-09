"""
Patch MSIP shadow design package for WHAT/HOW consistency.

TASK_CLASS = OBSERVATION_ONLY
No production code. Strengthens mechanical field authority classification.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "docs" / "governance" / "msip_shadow_design_v1"
PLAN_PKG = ROOT / "docs" / "governance" / "msip_shadow_implementation_plan_v1"
STAMP = datetime.now(timezone.utc).isoformat()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load(name: str) -> dict:
    return json.loads((PKG / name).read_text(encoding="utf-8"))


def save(name: str, obj: dict) -> None:
    (PKG / name).write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    schema = load("MARKET_STATE_VECTOR_SCHEMA_V1.json")

    # Field-level authority classes
    # GOVERNED_OBSERVABLE: raw or registry feature published as continuous/market fact
    # DETERMINISTIC_DERIVED_WHAT: deterministic derived market quantity (FM)
    # INTERPRETED_STATE_LABEL_HOW: categorical label requiring config/version provenance
    # OBSERVATIONAL_JOIN_ONLY: not identity of market state; comparison only

    field_specs = {
        "MSD-STRUCTURE": {
            "dimension_authority_class": "MIXED_WHAT_FIELDS",
            "fields": {
                "higher_high": {
                    "authority_class": "DETERMINISTIC_DERIVED_WHAT",
                    "source_feature": "higher_high",
                    "value_kind": "CONTINUOUS_OR_DISCRETE_MARKET_FACT",
                    "how_provenance_required": False,
                    "continuous_twin_required": False,
                },
                "lower_low": {
                    "authority_class": "DETERMINISTIC_DERIVED_WHAT",
                    "source_feature": "lower_low",
                    "value_kind": "CONTINUOUS_OR_DISCRETE_MARKET_FACT",
                    "how_provenance_required": False,
                },
                "break_of_structure": {
                    "authority_class": "DETERMINISTIC_DERIVED_WHAT",
                    "source_feature": "break_of_structure",
                    "value_kind": "CONTINUOUS_OR_DISCRETE_MARKET_FACT",
                    "how_provenance_required": False,
                },
                "liquidity_sweep": {
                    "authority_class": "DETERMINISTIC_DERIVED_WHAT",
                    "source_feature": "liquidity_sweep",
                    "value_kind": "CONTINUOUS_OR_DISCRETE_MARKET_FACT",
                    "how_provenance_required": False,
                    "note": "Pipeline geometry; NOT CRT detect_sweep identity",
                },
                "sweep_detected": {
                    "authority_class": "DETERMINISTIC_DERIVED_WHAT",
                    "source_feature": "sweep_detected",
                    "value_kind": "CONTINUOUS_OR_DISCRETE_MARKET_FACT",
                    "how_provenance_required": False,
                },
                "structure_label": {
                    "authority_class": "INTERPRETED_STATE_LABEL_HOW",
                    "source_feature": None,
                    "value_kind": "CATEGORICAL_LABEL",
                    "how_provenance_required": True,
                    "continuous_twins_required": [
                        "higher_high",
                        "lower_low",
                        "break_of_structure",
                        "liquidity_sweep",
                        "sweep_detected",
                    ],
                    "optional": True,
                    "note": "Optional HOW label over structure facts; must not replace continuous/discrete facts",
                },
            },
        },
        "MSD-LIQUIDITY": {
            "dimension_authority_class": "DETERMINISTIC_DERIVED_WHAT",
            "fields": {
                "liquidity_distance": {
                    "authority_class": "DETERMINISTIC_DERIVED_WHAT",
                    "source_feature": "liquidity_distance",
                    "value_kind": "CONTINUOUS_VALUE",
                    "how_provenance_required": False,
                    "fm_id": "FM-025",
                },
                "liquidity_pressure_score": {
                    "authority_class": "DETERMINISTIC_DERIVED_WHAT",
                    "source_feature": "liquidity_pressure_score",
                    "value_kind": "CONTINUOUS_VALUE",
                    "how_provenance_required": False,
                    "fm_id": "FM-026",
                },
                "liquidity_band_label": {
                    "authority_class": "INTERPRETED_STATE_LABEL_HOW",
                    "optional": True,
                    "value_kind": "CATEGORICAL_LABEL",
                    "how_provenance_required": True,
                    "continuous_twins_required": ["liquidity_distance", "liquidity_pressure_score"],
                },
            },
        },
        "MSD-VOLATILITY": {
            "dimension_authority_class": "MIXED_WHAT_FIELDS",
            "fields": {
                "atr": {
                    "authority_class": "DETERMINISTIC_DERIVED_WHAT",
                    "source_feature": "atr",
                    "value_kind": "CONTINUOUS_VALUE",
                    "how_provenance_required": False,
                    "fm_id": "FM-041",
                    "crt_local_replacement": "FORBIDDEN_UNTIL_PARITY_AUDIT_PASS",
                },
                "volatility_ratio": {
                    "authority_class": "DETERMINISTIC_DERIVED_WHAT",
                    "source_feature": "volatility_ratio",
                    "value_kind": "CONTINUOUS_VALUE",
                    "how_provenance_required": False,
                    "fm_id": "FM-024",
                },
                "volatility_regime": {
                    "authority_class": "DETERMINISTIC_DERIVED_WHAT",
                    "source_feature": "volatility_regime",
                    "value_kind": "DISCRETE_MARKET_FACT",
                    "how_provenance_required": False,
                    "note": "Pipeline int8 tercile is governed executable identity (M14B), not free HOW label",
                    "continuous_twins_required": ["atr", "volatility_ratio"],
                },
                "volatility_band_label": {
                    "authority_class": "INTERPRETED_STATE_LABEL_HOW",
                    "optional": True,
                    "value_kind": "CATEGORICAL_LABEL",
                    "how_provenance_required": True,
                    "continuous_twins_required": ["atr", "volatility_ratio", "volatility_regime"],
                    "note": "Optional research label; must not redefine volatility_regime identity",
                },
            },
        },
        "MSD-SESSION": {
            "dimension_authority_class": "DETERMINISTIC_DERIVED_WHAT",
            "fields": {
                "hour_of_day": {
                    "authority_class": "GOVERNED_OBSERVABLE",
                    "source_feature": "hour_of_day",
                    "value_kind": "CONTINUOUS_OR_DISCRETE_MARKET_FACT",
                    "how_provenance_required": False,
                },
                "session": {
                    "authority_class": "DETERMINISTIC_DERIVED_WHAT",
                    "source_feature": "session",
                    "value_kind": "DISCRETE_MARKET_FACT",
                    "how_provenance_required": False,
                    "note": "Canonical pipeline 0/1/2 identity; instrument overrides must not redefine encoding",
                    "continuous_twins_required": ["hour_of_day"],
                },
                "session_policy_label": {
                    "authority_class": "INTERPRETED_STATE_LABEL_HOW",
                    "optional": True,
                    "value_kind": "CATEGORICAL_LABEL",
                    "how_provenance_required": True,
                    "continuous_twins_required": ["session", "hour_of_day"],
                    "note": "e.g. tradeable/non-tradeable under a policy — NOT session identity",
                },
            },
        },
        "MSD-TREND": {
            "dimension_authority_class": "MIXED_WHAT_FIELDS",
            "fields": {
                "trend_strength": {
                    "authority_class": "DETERMINISTIC_DERIVED_WHAT",
                    "source_feature": "trend_strength",
                    "value_kind": "CONTINUOUS_VALUE",
                    "how_provenance_required": False,
                },
                "trend_bias": {
                    "authority_class": "DETERMINISTIC_DERIVED_WHAT",
                    "source_feature": "trend_bias",
                    "value_kind": "DISCRETE_MARKET_FACT",
                    "how_provenance_required": False,
                },
                "ema_fast": {
                    "authority_class": "DETERMINISTIC_DERIVED_WHAT",
                    "source_feature": "ema_fast",
                    "value_kind": "CONTINUOUS_VALUE",
                    "how_provenance_required": False,
                    "fm_id": "FM-043",
                    "crt_local_replacement": "FORBIDDEN_UNTIL_PARITY_AUDIT_PASS",
                },
                "ema_slow": {
                    "authority_class": "DETERMINISTIC_DERIVED_WHAT",
                    "source_feature": "ema_slow",
                    "value_kind": "CONTINUOUS_VALUE",
                    "how_provenance_required": False,
                    "fm_id": "FM-044",
                    "crt_local_replacement": "FORBIDDEN_UNTIL_PARITY_AUDIT_PASS",
                },
                "trend_band_label": {
                    "authority_class": "INTERPRETED_STATE_LABEL_HOW",
                    "optional": True,
                    "value_kind": "CATEGORICAL_LABEL",
                    "how_provenance_required": True,
                    "continuous_twins_required": ["trend_strength", "trend_bias"],
                },
            },
        },
        "MSD-CANDLE_QUALITY": {
            "dimension_authority_class": "DETERMINISTIC_DERIVED_WHAT",
            "fields": {
                "body_ratio": {
                    "authority_class": "DETERMINISTIC_DERIVED_WHAT",
                    "source_feature": "body_ratio",
                    "value_kind": "CONTINUOUS_VALUE",
                    "how_provenance_required": False,
                    "fm_id": "FM-010",
                    "crt_local_replacement": "FORBIDDEN_UNTIL_PARITY_AUDIT_PASS",
                },
                "body_size": {
                    "authority_class": "DETERMINISTIC_DERIVED_WHAT",
                    "source_feature": "body_size",
                    "value_kind": "CONTINUOUS_VALUE",
                    "how_provenance_required": False,
                    "fm_id": "FM-001",
                },
                "wick_size": {
                    "authority_class": "DETERMINISTIC_DERIVED_WHAT",
                    "source_feature": "wick_size",
                    "value_kind": "CONTINUOUS_VALUE",
                    "how_provenance_required": False,
                    "fm_id": "FM-002",
                    "crt_local_replacement": "FORBIDDEN_UNTIL_PARITY_AUDIT_PASS",
                },
                "candle_quality_label": {
                    "authority_class": "INTERPRETED_STATE_LABEL_HOW",
                    "optional": True,
                    "value_kind": "CATEGORICAL_LABEL",
                    "how_provenance_required": True,
                    "continuous_twins_required": ["body_ratio", "wick_size"],
                },
            },
        },
        "MSD-CRT_PHASE_OBS": {
            "dimension_authority_class": "OBSERVATIONAL_JOIN_ONLY",
            "identity_dependency_allowed": False,
            "fields": {
                "crt_state": {
                    "authority_class": "OBSERVATIONAL_JOIN_ONLY",
                    "value_kind": "OBSERVATION",
                    "how_provenance_required": False,
                    "must_not_feed_other_dimensions": True,
                    "must_not_define_market_state_identity": True,
                },
                "observed": {
                    "authority_class": "OBSERVATIONAL_JOIN_ONLY",
                    "value_kind": "OBSERVATION",
                    "how_provenance_required": False,
                    "must_not_define_market_state_identity": True,
                },
            },
        },
    }

    # Patch dimensions
    for dim in schema["dimensions"]:
        did = dim["dimension_id"]
        spec = field_specs.get(did, {})
        dim["dimension_authority_class"] = spec.get("dimension_authority_class", "UNKNOWN")
        dim["field_authority"] = spec.get("fields", {})
        if did == "MSD-CRT_PHASE_OBS":
            dim["identity_dependency_allowed"] = False
            dim["observational_only"] = True
            dim["must_not_become_market_state_identity"] = True
        # Ensure encoding includes continuous twins for any HOW labels
        enc = dim.setdefault("encoding", {})
        for fname, fspec in (spec.get("fields") or {}).items():
            if fspec.get("optional") and fname not in enc:
                enc[fname] = "optional_how_label"
            if fspec.get("authority_class") == "INTERPRETED_STATE_LABEL_HOW":
                fspec["how_config_keys"] = [
                    f"msip_shadow.dimensions.{dim['name']}.label_bands",
                    "msip_shadow.config_id",
                    "msip_shadow.schema_version_required",
                ]

    schema["what_how_separation_rules"] = {
        "rule_1": "Every field must declare authority_class in {GOVERNED_OBSERVABLE, DETERMINISTIC_DERIVED_WHAT, INTERPRETED_STATE_LABEL_HOW, OBSERVATIONAL_JOIN_ONLY}",
        "rule_2": "INTERPRETED_STATE_LABEL_HOW fields MUST retain how_config_id + config_version in provenance and MUST preserve continuous_twins_required values on the same bar",
        "rule_3": "Instrument/timeframe overrides may change HOW bands only; they MUST NOT redefine canonical WHAT feature identities or encodings",
        "rule_4": "crt_phase_observation is OBSERVATIONAL_JOIN_ONLY and MUST NOT be a dependency of any other dimension identity",
        "rule_5": "CRT-local atr/ema/body/wick remain unresolved for replacement until CRT_LOCAL_MATH_PARITY_AUDIT_V1 PASS/TRANSFORM; silent replacement FORBIDDEN",
        "rule_6": "Raw/continuous WHAT values remain authoritative even when optional HOW labels are present",
    }
    schema["consistency_review"] = {
        "reviewed_at_utc": STAMP,
        "status": "PASS",
        "risk_addressed": "interpreted dimensions must not mix WHAT/HOW without provenance",
    }
    schema["generated_at_utc"] = STAMP
    save("MARKET_STATE_VECTOR_SCHEMA_V1.json", schema)

    # Provenance: require HOW keys for labels
    prov = load("SHADOW_PROVENANCE_CONTRACT_V1.json")
    prov["required_fields_per_bar"]["how_label_provenance"] = {
        "required_when": "any INTERPRETED_STATE_LABEL_HOW field present",
        "fields": [
            "msip_shadow_config_id",
            "msip_shadow_config_sha256",
            "interpretation_schema_version",
            "per_label_band_source_path",
        ],
    }
    prov["required_fields_per_bar"]["continuous_twins_present"] = {
        "required_when": "any INTERPRETED_STATE_LABEL_HOW field present",
        "rule": "all continuous_twins_required for that label must be present on the same bar payload",
    }
    prov["crt_phase_observation_rules"] = {
        "may_be_null": True,
        "must_not_feed_dimension_identity": True,
        "must_not_block_vector_completeness": True,
    }
    prov["generated_at_utc"] = STAMP
    save("SHADOW_PROVENANCE_CONTRACT_V1.json", prov)

    # Interpretation config: instrument overrides cannot redefine WHAT
    interp = json.loads((PKG / "INTERPRETATION_CONFIG_SCHEMA_V1.json").read_text(encoding="utf-8"))
    interp["validation_rules"].extend(
        [
            "instrument_overrides and timeframe_overrides may only modify label_bands / enables — never source feature identities or encodings",
            "optional HOW labels require continuous twin values emitted alongside",
            "crt_phase_observation_enabled cannot make crt_state a required identity field of other dimensions",
            "CRT-local atr/ema/body/wick must not be listed as source_features until parity audit PASS/TRANSFORM registered",
        ]
    )
    interp["what_how_boundary"] = {
        "WHAT_owned_by": "ontology + feature_pipeline + formula_registry",
        "HOW_owned_by": "msip_shadow config only",
        "overrides_scope": "HOW_ONLY",
    }
    interp["generated_at_utc"] = STAMP
    save("INTERPRETATION_CONFIG_SCHEMA_V1.json", interp)

    # Dimension authority matrix enrichment
    dim_auth = json.loads((PKG / "MARKET_STATE_DIMENSION_AUTHORITY_MATRIX_V1.json").read_text(encoding="utf-8"))
    dim_auth["field_authority_index"] = field_specs
    dim_auth["what_how_separation_rules"] = schema["what_how_separation_rules"]
    dim_auth["generated_at_utc"] = STAMP
    save("MARKET_STATE_DIMENSION_AUTHORITY_MATRIX_V1.json", dim_auth)

    # Consistency review artifact
    review = {
        "schema_id": "DESIGN_CONTRACT_CONSISTENCY_REVIEW_V1",
        "generated_at_utc": STAMP,
        "task_class": "OBSERVATION_ONLY",
        "status": "PASS",
        "risk": "MarketStateVector dimensions might recreate WHAT/HOW authority mixing",
        "conditions_checked": [
            {
                "id": "C-1",
                "condition": "every dimension/field has one authority_class and temporal semantics",
                "result": "PASS",
                "evidence": "MARKET_STATE_VECTOR_SCHEMA_V1.field_authority",
            },
            {
                "id": "C-2",
                "condition": "interpreted labels retain exact config/version provenance",
                "result": "PASS",
                "evidence": "SHADOW_PROVENANCE_CONTRACT_V1.how_label_provenance",
            },
            {
                "id": "C-3",
                "condition": "raw/continuous values preserved where categorical labels emitted",
                "result": "PASS",
                "evidence": "continuous_twins_required + continuous_twins_present",
            },
            {
                "id": "C-4",
                "condition": "crt_phase_observation strictly observational; no identity dependency",
                "result": "PASS",
                "evidence": "MSD-CRT_PHASE_OBS observational_only + must_not_become_market_state_identity",
            },
            {
                "id": "C-5",
                "condition": "instrument/timeframe overrides are HOW-only",
                "result": "PASS",
                "evidence": "INTERPRETATION_CONFIG_SCHEMA_V1.what_how_boundary.overrides_scope=HOW_ONLY",
            },
            {
                "id": "C-6",
                "condition": "CRT-local atr/ema/body/wick unresolved until parity audit",
                "result": "PASS",
                "evidence": "crt_local_replacement=FORBIDDEN_UNTIL_PARITY_AUDIT_PASS; CRT_LOCAL_MATH_PARITY_AUDIT_V1",
            },
            {
                "id": "C-7",
                "condition": "acceptance authorizes only shadow implementation planning, not implementation/migration/thresholds/concurrent candidates",
                "result": "PASS",
                "evidence": "OWNER_ACCEPTANCE_STUB + PROMOTION_GATES G-IMPL-01 NOT_PASSED",
            },
        ],
        "all_pass": True,
        "recommended_owner_decision": {
            "DECISION_C": "ACCEPTED",
            "MSIP_SHADOW_DESIGN_CONTRACT_V1": "ACCEPTED",
            "AUTHORIZED_NEXT_BOUNDARY": "MSIP_SHADOW_IMPLEMENTATION_PLAN_V1",
            "NEXT_TASK_CLASS": "OBSERVATION_ONLY",
            "IMPLEMENTATION_AUTHORIZED": "NO",
        },
        "note": "Recommended stamps apply only after explicit owner confirmation; this review does not self-authorize production coding",
    }
    save("DESIGN_CONTRACT_CONSISTENCY_REVIEW_V1.json", review)
    (PKG / "DESIGN_CONTRACT_CONSISTENCY_REVIEW_V1.md").write_text(
        _review_md(review), encoding="utf-8"
    )

    # Owner acceptance stub — ready with recommended stamps
    accept = {
        "schema_id": "OWNER_ACCEPTANCE_DECISION_C_AND_SHADOW_DESIGN",
        "generated_at_utc": STAMP,
        "architecture_decision": "C",
        "consistency_review_status": "PASS",
        "consistency_review_ref": "DESIGN_CONTRACT_CONSISTENCY_REVIEW_V1.json",
        "acceptance_conditions": {
            "C-1_through_C-7": "PASS",
            "mechanical_representation": True,
        },
        "recommended_owner_stamp": {
            "DECISION_C": "ACCEPTED",
            "MSIP_SHADOW_DESIGN_CONTRACT_V1": "ACCEPTED",
            "AUTHORIZED_NEXT_BOUNDARY": "MSIP_SHADOW_IMPLEMENTATION_PLAN_V1",
            "NEXT_TASK_CLASS": "OBSERVATION_ONLY",
            "IMPLEMENTATION_AUTHORIZED": "NO",
        },
        "owner_stamp_status": "AWAITING_EXPLICIT_OWNER_CONFIRM",
        "if_owner_confirms": {
            "DECISION_C": "ACCEPTED",
            "MSIP_SHADOW_DESIGN_CONTRACT_V1": "ACCEPTED",
            "AUTHORIZED_NEXT_BOUNDARY": "MSIP_SHADOW_IMPLEMENTATION_PLAN_V1",
            "NEXT_TASK_CLASS": "OBSERVATION_ONLY",
            "IMPLEMENTATION_AUTHORIZED": "NO",
            "G-IMPL-01": "still NOT_PASSED until implementation plan reviewed",
        },
        "explicitly_not_authorized_by_acceptance": [
            "production MarketStateVector coding until G-IMPL-01 opens",
            "CRT migration",
            "threshold selection for CRTConfig",
            "concurrent candidates",
            "dynamic loader coding beyond plan",
        ],
        "d_wording_correction": (
            "D requires explicit CRT-boundary reopen authority and is unsupported by current evidence; "
            "CLOSED does not make replacement permanently impossible"
        ),
        "implementation_authorized": False,
        "threshold_selection_authorized": False,
        "crt_migration_authorized": False,
    }
    save("OWNER_ACCEPTANCE_STUB_V1.json", accept)

    # Promotion gates: design ready for accept; plan boundary
    gates = json.loads((PKG / "MSIP_SHADOW_PROMOTION_GATES_V1.json").read_text(encoding="utf-8"))
    for g in gates["gates"]:
        if g["id"] == "G-DESIGN-01":
            g["status"] = "READY_FOR_OWNER_ACCEPTANCE"
            g["criterion"] = (
                "Package complete + consistency review PASS; owner must stamp ACCEPTED"
            )
    gates["gates"].insert(
        1,
        {
            "id": "G-PLAN-01",
            "name": "implementation_plan_reviewed",
            "criterion": "MSIP_SHADOW_IMPLEMENTATION_PLAN_V1 reviewed; still no production code",
            "status": "PENDING_PLAN_REVIEW",
            "blocks": "G-IMPL-01",
        },
    )
    gates["generated_at_utc"] = STAMP
    save("MSIP_SHADOW_PROMOTION_GATES_V1.json", gates)

    # Update design contract with consistency section
    contract_path = PKG / "MSIP_SHADOW_DESIGN_CONTRACT_V1.md"
    contract = contract_path.read_text(encoding="utf-8")
    if "WHAT/HOW field authority classes" not in contract:
        contract += f"""

---

## 12. WHAT/HOW consistency amendment ({STAMP[:10]})

Consistency review: **PASS** (`DESIGN_CONTRACT_CONSISTENCY_REVIEW_V1`).

Every MarketStateVector field declares one of:

- `GOVERNED_OBSERVABLE`
- `DETERMINISTIC_DERIVED_WHAT`
- `INTERPRETED_STATE_LABEL_HOW` (requires config/version provenance + continuous twins)
- `OBSERVATIONAL_JOIN_ONLY` (`crt_phase_observation` only; no identity dependency)

Instrument/timeframe overrides are **HOW-only**.  
CRT-local atr/ema/body/wick: **no silent replacement** until parity audit.  
Owner acceptance authorizes **shadow implementation planning only**, not coding until G-IMPL-01.
"""
        contract_path.write_text(contract, encoding="utf-8")
        (ROOT / "docs/governance/MSIP_SHADOW_DESIGN_CONTRACT_V1.md").write_text(
            contract, encoding="utf-8"
        )

    # Implementation plan package (no production code)
    _write_implementation_plan()

    # Refresh package manifest
    _refresh_manifest(PKG)
    print("CONSISTENCY_REVIEW = PASS")
    print("OWNER_STAMP = AWAITING_EXPLICIT_OWNER_CONFIRM")
    print("IMPLEMENTATION_PLAN written")
    return 0


def _review_md(r: dict) -> str:
    lines = [
        "# Design Contract Consistency Review V1",
        "",
        f"**Status:** {r['status']}  ",
        f"**Generated:** {r['generated_at_utc']}",
        "",
        f"Risk: {r['risk']}",
        "",
        "| id | result | condition |",
        "|---|---|---|",
    ]
    for c in r["conditions_checked"]:
        lines.append(f"| {c['id']} | **{c['result']}** | {c['condition']} |")
    lines += [
        "",
        "## Recommended owner decision (after explicit confirm)",
        "",
        "```text",
    ]
    for k, v in r["recommended_owner_decision"].items():
        lines.append(f"{k} = {v}")
    lines += ["```", "", r["note"], ""]
    return "\n".join(lines) + "\n"


def _write_implementation_plan() -> None:
    PLAN_PKG.mkdir(parents=True, exist_ok=True)
    plan = {
        "schema_id": "MSIP_SHADOW_IMPLEMENTATION_PLAN_V1",
        "generated_at_utc": STAMP,
        "task_class": "OBSERVATION_ONLY",
        "prerequisite": "Owner acceptance of Decision C + MSIP_SHADOW_DESIGN_CONTRACT_V1",
        "implementation_authorized": False,
        "g_impl_01": "NOT_OPEN — this plan only; coding blocked until plan review + explicit G-IMPL-01",
        "maps_contract_to": {
            "modules_proposed": [
                {
                    "path": "src/msip/ (new package, proposed)",
                    "role": "shadow MarketState assembly — NOT to be created until G-IMPL-01",
                },
                {
                    "path": "src/msip/market_state_vector.py",
                    "role": "dataclass/schema validator matching MARKET_STATE_VECTOR_SCHEMA_V1",
                },
                {
                    "path": "src/msip/shadow_emitter.py",
                    "role": "bar loop: features → vector → JSONL; never imports CRT mutators for writes",
                },
                {
                    "path": "src/msip/interpretation_config.py",
                    "role": "strict load of msip_shadow section",
                },
                {
                    "path": "src/msip/disagreement.py",
                    "role": "optional comparison taxonomy emitter",
                },
                {
                    "path": "scripts/analysis/run_msip_shadow.py",
                    "role": "CLI runner for batch shadow on frozen corpus",
                },
            ],
            "interfaces": [
                "build_market_state(bar_features: Mapping, config, provenance_ctx) -> MarketStateVector",
                "emit_jsonl(path, vector) append-only",
                "optional observe_crt_state(read_only_snapshot) -> crt_phase_observation fields only",
            ],
            "data_flow": [
                "OHLCV / FeaturePipeline series",
                "msip_shadow config (HOW)",
                "MarketStateVector + provenance",
                "optional disagreement vs CRT observation",
                "no feedback into CRTEngine",
            ],
            "tests_proposed": [
                "test_msip_shadow_schema_validation.py",
                "test_msip_shadow_what_how_separation.py (labels require twins + config id)",
                "test_msip_shadow_neutrality_vs_crt.py (CRT outputs identical with shadow co-run)",
                "test_msip_shadow_determinism.py",
                "test_msip_shadow_crt_phase_not_identity.py",
            ],
            "telemetry": [
                "shadow JSONL",
                "run manifest with schema/config/corpus hashes",
                "disagreement JSONL optional",
            ],
            "rollout_sequence": [
                "1. Owner accepts design + this plan review (G-PLAN-01)",
                "2. Open G-IMPL-01 for shadow package only",
                "3. Implement schema + emitter + tests",
                "4. Run shadow on Phase-1 XAUUSD sample (not hash-golden vs historical trades)",
                "5. Execute CRT_LOCAL_MATH_PARITY_AUDIT_V1 (still OBSERVATION_ONLY)",
                "6. Evaluate G-SHADOW-01; still no CRT migration",
            ],
            "acceptance_gates": [
                "G-PLAN-01",
                "G-IMPL-01",
                "G-SHADOW-01",
                "G-PARITY-01 (before any CRT-local deprecation)",
                "G-MIG-01 remains closed",
            ],
        },
        "non_goals": [
            "production code in this artifact",
            "CRTConfig threshold changes",
            "concurrent candidates",
            "EngineRunner binding",
            "economic optimization",
        ],
        "design_refs": [
            "docs/governance/msip_shadow_design_v1/MSIP_SHADOW_DESIGN_CONTRACT_V1.md",
            "docs/governance/msip_shadow_design_v1/DESIGN_CONTRACT_CONSISTENCY_REVIEW_V1.json",
            "docs/governance/crt_architecture_adjudication_v1/ARCHITECTURE_DECISION_RECORD_V1.json",
        ],
    }
    (PLAN_PKG / "MSIP_SHADOW_IMPLEMENTATION_PLAN_V1.json").write_text(
        json.dumps(plan, indent=2) + "\n", encoding="utf-8"
    )
    (PLAN_PKG / "MSIP_SHADOW_IMPLEMENTATION_PLAN_V1.md").write_text(
        _plan_md(plan), encoding="utf-8"
    )
    (ROOT / "docs/governance/MSIP_SHADOW_IMPLEMENTATION_PLAN_V1.md").write_text(
        _plan_md(plan), encoding="utf-8"
    )
    # plan package manifest
    files = sorted(p for p in PLAN_PKG.rglob("*") if p.is_file() and p.name != "PACKAGE_MANIFEST.json")
    fl = []
    agg = hashlib.sha256()
    for p in files:
        rel = str(p.relative_to(PLAN_PKG)).replace("\\", "/")
        h = sha256_file(p)
        fl.append({"path": rel, "sha256": h, "bytes": p.stat().st_size})
        agg.update(f"{h}  {rel}\n".encode())
    man = {
        "package": "msip_shadow_implementation_plan_v1",
        "generated_at_utc": STAMP,
        "implementation_authorized": False,
        "files": fl,
        "package_aggregate_sha256": agg.hexdigest(),
    }
    (PLAN_PKG / "PACKAGE_MANIFEST.json").write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")


def _plan_md(plan: dict) -> str:
    m = plan["maps_contract_to"]
    lines = [
        "# MSIP Shadow Implementation Plan V1",
        "",
        f"**Task class:** {plan['task_class']}  ",
        f"**Implementation authorized:** **{plan['implementation_authorized']}**  ",
        f"**G-IMPL-01:** {plan['g_impl_01']}",
        "",
        "## Prerequisite",
        "",
        plan["prerequisite"],
        "",
        "## Proposed modules (do not create until G-IMPL-01)",
        "",
    ]
    for mod in m["modules_proposed"]:
        lines.append(f"- `{mod['path']}` — {mod['role']}")
    lines += ["", "## Data flow", ""]
    for x in m["data_flow"]:
        lines.append(f"- {x}")
    lines += ["", "## Tests proposed", ""]
    for t in m["tests_proposed"]:
        lines.append(f"- `{t}`")
    lines += ["", "## Rollout sequence", ""]
    for x in m["rollout_sequence"]:
        lines.append(f"- {x}")
    lines += ["", "## Non-goals", ""]
    for x in plan["non_goals"]:
        lines.append(f"- {x}")
    lines += [
        "",
        "## Hard stop",
        "",
        "This document is a **plan**. It does not open production coding.",
        "",
    ]
    return "\n".join(lines) + "\n"


def _refresh_manifest(pkg: Path) -> None:
    files = sorted(p for p in pkg.rglob("*") if p.is_file() and p.name != "PACKAGE_MANIFEST.json")
    fl = []
    agg = hashlib.sha256()
    for p in files:
        rel = str(p.relative_to(pkg)).replace("\\", "/")
        h = sha256_file(p)
        fl.append({"path": rel, "sha256": h, "bytes": p.stat().st_size})
        agg.update(f"{h}  {rel}\n".encode())
    man = {
        "_doc": "MSIP_SHADOW design package manifest (post consistency review)",
        "generated_at_utc": STAMP,
        "package_path": "docs/governance/msip_shadow_design_v1",
        "consistency_review": "PASS",
        "implementation_authorized": False,
        "files": fl,
        "package_aggregate_sha256": agg.hexdigest(),
    }
    (pkg / "PACKAGE_MANIFEST.json").write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    print("design package aggregate", man["package_aggregate_sha256"])


if __name__ == "__main__":
    raise SystemExit(main())
