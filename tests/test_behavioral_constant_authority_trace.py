"""
Guard tests for SUR-008 / IC-007 behavioral constant authority trace
+ Active CRT Behavioral-Constant Closure Pass.

Observational only — no remediation, no plan implementation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = _ROOT / "scripts" / "governance"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import behavioral_constant_authority_trace as trace  # noqa: E402

JSON_PATH = trace.JSON_PATH
MD_PATH = trace.MD_PATH
AM_PATH = _ROOT / "active_models.yaml"

ALLOWED_SEM = frozenset(
    {
        "PROVEN_SAME_SEMANTIC",
        "PROVEN_DIFFERENT_SEMANTIC",
        "PROVEN_PARTIAL_SEMANTIC_OVERLAP",
        "UNPROVEN",
    }
)
ALLOWED_VERDICT = frozenset(
    {
        "PROVEN_HOW_CANDIDATE",
        "PROVEN_WHAT_FORMULA_COMPONENT",
        "PROVEN_CODE_INVARIANT",
        "PROVEN_DUPLICATE_RUNTIME_AUTHORITY",
        "PROVEN_MISSING_CODE_IMPLEMENTATION",
        "UNPROVEN",
    }
)


@pytest.fixture(scope="module")
def live_doc() -> dict:
    return trace.scan()


@pytest.fixture(scope="module")
def frozen_doc() -> dict:
    assert JSON_PATH.is_file(), f"missing {JSON_PATH}"
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


def test_artifacts_exist():
    assert JSON_PATH.is_file()
    assert MD_PATH.is_file()


def test_scope_rule_frozen_before_classification(frozen_doc):
    rule = frozen_doc["behavioral_constant_scope_rule"]
    assert rule["frozen_before_classification"] is True
    assert rule["rule_id"] == "BEHAVIORAL_CONSTANT_SCOPE_RULE"


def test_closure_pass_id_present(frozen_doc):
    assert frozen_doc.get("pass_id") == "ACTIVE_CRT_BEHAVIORAL_CONSTANT_CLOSURE_PASS"
    assert frozen_doc["schema"].startswith("behavioral_constant_authority_trace")


def test_spine_expanded_beyond_crt_engine_v2(frozen_doc):
    mods = frozen_doc["spine_modules"]
    assert len(mods) >= 10
    joined = " ".join(mods)
    assert "crt_engine_v2.py" in joined
    assert "scoring_engine.py" in joined
    assert "engine_runner.py" in joined
    assert "execution_planner.py" in joined
    assert "ultron_risk_gate.py" in joined
    assert "market_router.py" in joined


def test_scanner_covers_literal_forms(live_doc):
    contexts = {c.get("AST_context") for c in live_doc["raw_candidates"]}
    assert "inline_constant" in contexts
    assert contexts & {
        "ann_assign_default",
        "assign_name",
        "assign_attr",
        "container_literal",
        "function_default",
        "function_default_container",
    }


def test_sur008_known_examples_present(frozen_doc):
    assert frozen_doc["population_summary"]["SUR008_ANCHORS_FOUND"] is True


def test_enumeration_not_limited_to_sur008(frozen_doc):
    assert frozen_doc["population_summary"]["RAW_CONSTANT_CANDIDATE_COUNT"] > 100
    assert frozen_doc["population_summary"]["IN_SCOPE_BEHAVIORAL_CONSTANT_COUNT"] >= 10


def test_closure_resolves_all_spine_scope_candidates(frozen_doc):
    """Closure requirement: no residual UNPROVEN scope on spine scan set."""
    ps = frozen_doc["population_summary"]
    assert ps["UNPROVEN_SCOPE_COUNT"] == 0
    assert ps["CLOSURE_SCOPE_RESOLVED"] is True
    for c in frozen_doc["raw_candidates"]:
        assert c["scope_status"] in {"IN_SCOPE", "OUT_OF_SCOPE"}, c["candidate_id"]


def test_every_in_scope_fully_adjudicated(frozen_doc):
    ps = frozen_doc["population_summary"]
    assert ps["EVERY_IN_SCOPE_ADJUDICATED"] is True
    assert ps["FULLY_ADJUDICATED_IN_SCOPE_COUNT"] == ps["IN_SCOPE_BEHAVIORAL_CONSTANT_COUNT"]
    in_ids = {c["candidate_id"] for c in frozen_doc["raw_candidates"] if c["scope_status"] == "IN_SCOPE"}
    adj_ids = {a["candidate_id"] for a in frozen_doc["authority_adjudications"]}
    assert in_ids == adj_ids
    for a in frozen_doc["authority_adjudications"]:
        assert a["verdict"] in ALLOWED_VERDICT
        assert a.get("rationale")
        assert a.get("priority") in {"P0", "P1", "P2", "P3"}


def test_every_in_scope_has_behavior_effect(frozen_doc):
    for c in frozen_doc["raw_candidates"]:
        if c["scope_status"] != "IN_SCOPE":
            continue
        assert c.get("behavior_effect") in {
            "DIRECT",
            "CONDITIONAL",
            "INVARIANT_ONLY",
            "NO_EFFECT_PROVEN",
            "UNPROVEN",
        }


def test_authority_search_covers_surfaces(frozen_doc):
    surfaces = {m["surface"] for m in frozen_doc["authority_matches"]}
    assert {"WHAT", "WHO", "HOW", "CODE"} <= surfaces


def test_semantic_taxonomy_and_proof(frozen_doc):
    for r in frozen_doc["semantic_relationships"]:
        assert r["classification"] in ALLOWED_SEM
        assert r.get("proof_basis")
    # dual-path partial overlap must be recorded
    classes = {r["classification"] for r in frozen_doc["semantic_relationships"]}
    assert "PROVEN_PARTIAL_SEMANTIC_OVERLAP" in classes
    assert "PROVEN_DIFFERENT_SEMANTIC" in classes


def test_surplus_preserved(frozen_doc):
    assert frozen_doc["declaration_surplus_records"]
    for s in frozen_doc["declaration_surplus_records"]:
        assert s.get("preserve") is True


def test_plans_recertified_or_revised(frozen_doc):
    assert frozen_doc["population_summary"]["PLANS_RECERTIFIED_OR_REVISED"] is True
    plans = {p["plan_id"]: p for p in frozen_doc["implementation_plans"]}
    assert set(plans) >= {"PLAN-001", "PLAN-002", "PLAN-003"}
    # Lifecycle: RECERTIFIED → IMPLEMENTED (PLAN-001 shipped 2026-07-11 as
    # CH-plan001-retest-min-depth-how); an implemented plan must carry its change_id.
    assert plans["PLAN-001"]["recertification_status"] == "IMPLEMENTED"
    assert plans["PLAN-001"]["implementation_change_id"] == "CH-plan001-retest-min-depth-how"
    assert plans["PLAN-002"]["recertification_status"] in ("REVISED", "IMPLEMENTED")
    assert plans["PLAN-003"]["recertification_status"] == "REVISED"
    # PLAN-002 must mention dual path
    assert "dual" in plans["PLAN-002"]["revision_notes"].lower() or "scoring_engine" in plans[
        "PLAN-002"
    ]["revision_notes"].lower()


def test_implementation_plans_have_required_fields(frozen_doc):
    required = [
        "plan_id",
        "current_behavior",
        "target_authority",
        "existing_destination_surface",
        "required_tests",
        "required_parity_checks",
        "required_backtests",
        "expected_behavior_change",
        "rollback_condition",
        "stop_condition",
        "recommended_order",
        "recertification_status",
    ]
    for p in frozen_doc["implementation_plans"]:
        for k in required:
            assert p.get(k) is not None, f"{p.get('plan_id')} missing {k}"
        assert p["expected_behavior_change"] in {"NONE", "INTENTIONAL", "UNKNOWN"}
        assert "EXECUTED" not in p.get("plan_status", "")


def test_how_candidates_have_destination(frozen_doc):
    plans = {p["plan_id"]: p for p in frozen_doc["implementation_plans"]}
    for a in frozen_doc["authority_adjudications"]:
        if a["verdict"] != "PROVEN_HOW_CANDIDATE":
            continue
        pid = a.get("plan_id")
        if not pid:
            continue
        assert pid in plans
        assert plans[pid]["target_authority"] == "HOW"
        assert plans[pid].get("existing_destination_surface")


def test_no_fourth_yaml_and_non_effects(frozen_doc):
    inv = frozen_doc["invariants"]
    assert inv["NO_FOURTH_YAML"] is True
    assert inv["RUNTIME_CODE_UNCHANGED"] is True
    assert inv["YAML_UNCHANGED"] is True
    assert inv["PRODUCTION_CONFIG_UNCHANGED"] is True
    assert inv["FORMULAS_UNCHANGED"] is True
    assert inv["STATE_CONTRACTS_UNCHANGED"] is True
    assert inv["PHASE_TOPOLOGY_UNCHANGED"] is True
    assert inv["IC001_IC002_NOT_EXECUTED"] is True
    assert inv["PLANS_NOT_IMPLEMENTED"] is True
    assert inv["IC007_REMEDIATION_NOT_EXECUTED"] is True


def test_state_contracts_untouched():
    am = yaml.safe_load(AM_PATH.read_text(encoding="utf-8"))
    sc = am["crt"]["runtime"]["state_contracts"]
    allowed = {"required_fm", "config_keys", "eligible_models"}
    for sid, body in sc.items():
        assert set(body.keys()) <= allowed


def test_unproven_verdict_preserve_policy(frozen_doc):
    for a in frozen_doc["authority_adjudications"]:
        if a["verdict"] == "UNPROVEN":
            assert "PRESERVE" in a.get("disposition", "").upper()


def test_md_mentions_closure_and_plans():
    text = MD_PATH.read_text(encoding="utf-8")
    assert "Closure" in text or "CLOSURE" in text
    assert "PLAN-001" in text
    assert "RECERTIFIED" in text or "REVISED" in text


def test_live_matches_frozen_closure_gates(frozen_doc, live_doc):
    for key in (
        "UNPROVEN_SCOPE_COUNT",
        "CLOSURE_SCOPE_RESOLVED",
        "EVERY_IN_SCOPE_ADJUDICATED",
        "PLANS_RECERTIFIED_OR_REVISED",
    ):
        assert frozen_doc["population_summary"][key] == live_doc["population_summary"][key]
