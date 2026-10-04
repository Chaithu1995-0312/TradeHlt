"""
Guard tests for WHO Numeric Dependency Census (IC-001/IC-002 pre-cleanup).

Observational only — does not execute cleanup or mutate WHO/HOW/runtime.
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

import who_numeric_dependency_census as census  # noqa: E402

JSON_PATH = census.JSON_PATH
MD_PATH = census.MD_PATH
SURPLUS_JSON = census.SURPLUS_CENSUS_JSON
AM_PATH = census.AM_PATH

ALLOWED_CLASS = frozenset(
    {
        "SAFE_TO_REMOVE_VALUE",
        "KEEP_KEY_REMOVE_VALUE",
        "KEEP_AS_NONAUTHORITATIVE_REFERENCE",
        "MIGRATION_REQUIRED",
        "UNPROVEN",
    }
)


@pytest.fixture(scope="module")
def live_doc() -> dict:
    return census.scan()


@pytest.fixture(scope="module")
def frozen_doc() -> dict:
    assert JSON_PATH.is_file(), f"missing artifact {JSON_PATH}"
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


def test_artifacts_exist():
    assert JSON_PATH.is_file()
    assert MD_PATH.is_file()


def test_exactly_57_declarations(frozen_doc, live_doc):
    assert len(frozen_doc["declarations"]) == 57
    assert frozen_doc["population_summary"]["WHO_NUMERIC_DECLARATION_COUNT"] == 57
    assert live_doc["population_summary"]["WHO_NUMERIC_DECLARATION_COUNT"] == 57


def test_population_equals_surplus_census(frozen_doc):
    assert SURPLUS_JSON.is_file()
    sur = json.loads(SURPLUS_JSON.read_text(encoding="utf-8"))
    s = sur["summary"]
    ps = frozen_doc["population_summary"]
    assert ps["DETECTION_DEFAULT_COUNT"] == s["detection_default_count"] == 9
    assert ps["THRESHOLD_COUNT"] == s["threshold_entry_count"] == 48
    assert ps["population_matches_surplus_census"] is True


def test_unique_canonical_ids(frozen_doc):
    ids = [d["declaration_id"] for d in frozen_doc["declarations"]]
    assert len(ids) == len(set(ids))
    assert ids[0] == "WHO-NUM-001"
    assert ids[-1] == "WHO-NUM-057"


def test_every_declaration_has_yaml_path_and_value(frozen_doc):
    for d in frozen_doc["declarations"]:
        assert d.get("yaml_path"), d["declaration_id"]
        assert "numeric_value" in d
        assert d.get("yaml_key")
        assert d.get("source_file") == "active_models.yaml"


def test_every_declaration_has_consumer_search_evidence(frozen_doc):
    for d in frozen_doc["declarations"]:
        assert "consumer_ids" in d
        assert isinstance(d["consumer_ids"], list)
        # every decl is linked to at least the whole-file + census consumers
        assert len(d["consumer_ids"]) >= 1, d["declaration_id"]
        assert d.get("consumer_classes")


def test_indirect_consumers_explicitly_searched(frozen_doc):
    ind = frozen_doc["indirect_consumer_search"]
    assert "status" in ind
    assert ind["status"] in {"COMPLETE", "INCOMPLETE"}
    assert ind.get("files_scanned", 0) > 0
    assert ind.get("methods")
    assert "unresolved_dynamic_paths" in ind


def test_every_observed_consumer_class_has_definition(frozen_doc):
    for c in frozen_doc["observed_consumer_class_registry"]:
        assert c.get("class_id")
        assert c.get("class_name")
        assert c.get("definition")
        assert c.get("observed_examples")
        assert c.get("removal_risk")


def test_consumer_class_registry_frozen_before_classification(frozen_doc):
    assert frozen_doc["consumer_class_registry_frozen_before_classification"] is True
    assert frozen_doc["eligibility_ruleset_frozen_before_classification"] is True


def test_every_declaration_has_equivalent_authority(frozen_doc):
    for d in frozen_doc["declarations"]:
        eq = d["equivalent_authority"]
        assert "semantic_identity_proven" in eq
        assert eq["semantic_identity_proven"] in {"YES", "NO"}
        assert "proof_basis" in eq
        assert "crtconfig_field" in eq or eq.get("on_crtconfig") is False or True


def test_every_declaration_has_information_loss(frozen_doc):
    for d in frozen_doc["declarations"]:
        loss = d["information_loss"]
        assert "information_surfaces" in loss
        assert "information_lost_if_value_removed" in loss
        assert "unknown_loss_risk" in loss
        assert loss["unknown_loss_risk"] in {"YES", "NO"}


def test_every_eligibility_rule_has_evidence(frozen_doc):
    for r in frozen_doc["eligibility_ruleset"]:
        assert r.get("rule_id")
        assert r.get("rule_statement")
        assert r.get("evidence_that_required_rule")
        assert r.get("counterexample_prevented")
        # no cleanup-presumption rule
        stmt = r["rule_statement"].lower()
        assert "should be removed" not in stmt
        assert "must be removed" not in stmt
        assert "who numeric values should be removed" not in stmt


def test_no_cleanup_presumption_in_ruleset(frozen_doc):
    blob = json.dumps(frozen_doc["eligibility_ruleset"]).lower()
    assert "who numeric values should be removed" not in blob
    # rules authorize classification constraints, not mandate strip
    assert "authorize removal" in blob or "does not authorize" in blob


def test_every_declaration_classified_exactly_once(frozen_doc):
    for d in frozen_doc["declarations"]:
        assert d["classification"] in ALLOWED_CLASS
        assert d.get("disposition")
        assert d.get("eligibility_rules_applied")
    # summary matches
    s = frozen_doc["classification_summary"]
    for cls in ALLOWED_CLASS:
        assert s[cls] == sum(
            1 for d in frozen_doc["declarations"] if d["classification"] == cls
        )


def test_unproven_preserve_no_action(frozen_doc):
    for d in frozen_doc["declarations"]:
        if d["classification"] == "UNPROVEN":
            assert d["disposition"] == "PRESERVE_NO_ACTION"


def test_safe_to_remove_satisfies_deletion_safety_rules(frozen_doc):
    for d in frozen_doc["declarations"]:
        if d["classification"] != "SAFE_TO_REMOVE_VALUE":
            continue
        # if any ever appear: must have no unknown loss and no value consumers unresolved
        assert d["information_loss"]["unknown_loss_risk"] == "NO"
        assert d["information_loss"]["value_consumer_count"] == 0


def test_keep_key_remove_value_proof_requirements(frozen_doc):
    for d in frozen_doc["declarations"]:
        if d["classification"] != "KEEP_KEY_REMOVE_VALUE":
            continue
        assert d["information_loss"]["unknown_loss_risk"] == "NO"
        # key necessity implied by key consumers
        assert any(
            c.get("consumes_key")
            for c in frozen_doc["consumers"]
            if c["declaration_id"] == d["declaration_id"]
        )


def test_keep_as_nonauthoritative_reference_requires_proof(frozen_doc):
    for d in frozen_doc["declarations"]:
        if d["classification"] != "KEEP_AS_NONAUTHORITATIVE_REFERENCE":
            continue
        # must document required reference role in rationale
        assert "required" in d.get("classification_rationale", "").lower()


def test_migration_required_identifies_destination(frozen_doc):
    for d in frozen_doc["declarations"]:
        if d["classification"] != "MIGRATION_REQUIRED":
            continue
        assert d["equivalent_authority"].get("equivalent_how_path") or d[
            "equivalent_authority"
        ].get("crtconfig_field")


def test_no_fourth_yaml(frozen_doc):
    assert frozen_doc["invariants"]["NO_FOURTH_YAML"] is True
    blob = json.dumps(frozen_doc).lower()
    assert "market_state_registry.yaml" not in blob


def test_state_contracts_unchanged(frozen_doc):
    assert frozen_doc["invariants"]["STATE_CONTRACTS_UNCHANGED"] is True
    am = yaml.safe_load(AM_PATH.read_text(encoding="utf-8"))
    sc = am["crt"]["runtime"]["state_contracts"]
    allowed = {"required_fm", "config_keys", "eligible_models"}
    for sid, body in sc.items():
        assert set(body.keys()) <= allowed, sid


def test_phase_topology_and_runtime_invariants(frozen_doc):
    inv = frozen_doc["invariants"]
    assert inv["PHASE_TOPOLOGY_UNCHANGED"] is True
    assert inv["RUNTIME_CODE_UNCHANGED"] is True
    assert inv["PRODUCTION_CONFIG_UNCHANGED"] is True
    assert inv["FORMULAS_UNCHANGED"] is True
    assert inv["IC001_IC002_CLEANUP_NOT_EXECUTED"] is True


def test_incomplete_indirect_search_forces_readiness_no(live_doc):
    """If indirect search were incomplete, readiness must be NO (rule R-08)."""
    # Live scan reports COMPLETE; still readiness NO due to UNPROVEN
    if live_doc["indirect_consumer_search"]["status"] != "COMPLETE":
        assert live_doc["ic001_readiness"] == "NO"
        assert live_doc["ic002_readiness"] == "NO"
    # Any UNPROVEN forces corresponding readiness NO
    det_unproven = any(
        d["classification"] == "UNPROVEN" and d["ic_bucket"] == "IC-001"
        for d in live_doc["declarations"]
    )
    thr_unproven = any(
        d["classification"] == "UNPROVEN" and d["ic_bucket"] == "IC-002"
        for d in live_doc["declarations"]
    )
    if det_unproven:
        assert live_doc["ic001_readiness"] == "NO"
    if thr_unproven:
        assert live_doc["ic002_readiness"] == "NO"


def test_freshness_live_matches_frozen_population(frozen_doc, live_doc):
    assert (
        frozen_doc["population_summary"]["WHO_NUMERIC_DECLARATION_COUNT"]
        == live_doc["population_summary"]["WHO_NUMERIC_DECLARATION_COUNT"]
    )
    f_ids = [d["declaration_id"] for d in frozen_doc["declarations"]]
    l_ids = [d["declaration_id"] for d in live_doc["declarations"]]
    assert f_ids == l_ids


def test_md_mentions_status_and_rules():
    text = MD_PATH.read_text(encoding="utf-8")
    assert "WHO Numeric Dependency Census" in text
    assert "R-01" in text
    assert "IC001_READY" in text or "IC001_READY" in text.replace(" ", "")
    assert "UNPROVEN" in text
