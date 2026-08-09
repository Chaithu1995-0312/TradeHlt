"""
Census-specific tests for Three-Authority Declaration Surplus Census.

READ-ONLY vs runtime: does not mutate production behavior. Pins the frozen
ledger under docs/governance/ and re-derives key counts from live sources so
the census cannot silently rot.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = _ROOT / "scripts" / "governance"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import three_authority_surplus_census as census  # noqa: E402

JSON_PATH = census.JSON_PATH
MD_PATH = census.MD_PATH


@pytest.fixture(scope="module")
def live_doc() -> dict:
    return census.scan()


@pytest.fixture(scope="module")
def frozen_doc() -> dict:
    assert JSON_PATH.is_file(), f"missing census artifact: {JSON_PATH}"
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


def test_artifacts_exist():
    assert JSON_PATH.is_file()
    assert MD_PATH.is_file()


def test_schema_and_status(frozen_doc):
    assert frozen_doc["schema"] == census.SCHEMA
    assert frozen_doc["status"] == "CENSUS_ONLY"
    assert frozen_doc["census_id"] == census.CENSUS_ID


def test_freshness_summary_matches_live_scan(frozen_doc, live_doc):
    """Key counts in the committed ledger must match a live re-scan."""
    fs = frozen_doc["summary"]
    ls = live_doc["summary"]
    for key in (
        "detection_default_count",
        "threshold_entry_count",
        "how_drift_count",
        "formula_prose_count",
        "state_contract_count",
        "state_contract_field_violations",
        "contract_config_keys_n",
        "ontology_fm_n",
        "ontology_fm_not_in_contracts_n",
        "topology_yaml_code_equal",
        "surplus_record_count",
    ):
        assert fs[key] == ls[key], f"stale census summary.{key}: frozen={fs[key]} live={ls[key]}"
    assert fs["contract_required_fm"] == ls["contract_required_fm"]


def test_surplus_record_ids_stable(frozen_doc, live_doc):
    f_ids = [r["id"] for r in frozen_doc["surplus_records"]]
    l_ids = [r["id"] for r in live_doc["surplus_records"]]
    assert f_ids == l_ids
    assert f_ids[0] == "SUR-001"
    assert "SUR-011" in f_ids  # clean state_contracts positive control


def test_implementation_candidates_include_p1_and_keep(frozen_doc):
    ids = {c["id"] for c in frozen_doc["implementation_candidate_ledger"]}
    assert "IC-001" in ids
    assert "IC-002" in ids
    assert "IC-008" in ids
    assert "IC-KEEP" in ids
    p1 = [
        c["id"]
        for c in frozen_doc["implementation_candidate_ledger"]
        if c.get("priority") == "P1"
    ]
    assert set(p1) == set(frozen_doc["summary"]["p1_candidates"])


def test_state_contracts_remain_clean_positive_control(live_doc):
    pc = live_doc["positive_controls"]
    assert pc["state_contracts_ids_only"] is True
    assert pc["required_fm_in_ontology"] is True
    assert pc["contract_keys_on_crtconfig"] is True
    assert live_doc["summary"]["state_contract_field_violations"] == 0


def test_detection_defaults_are_surplus_not_runtime_consumed(frozen_doc):
    sur001 = next(r for r in frozen_doc["surplus_records"] if r["id"] == "SUR-001")
    assert sur001["runtime_consumed"] is False
    assert sur001["class"] == "NUMERIC_DEFAULT_IN_WHO"
    assert sur001["count"] >= 1
    assert sur001["implementation_candidate_id"] == "IC-001"


def test_how_drift_keys_are_documented(live_doc):
    """Active HOW≠WHO default is the session-misread class (IC-008)."""
    sur003 = next(r for r in live_doc["surplus_records"] if r["id"] == "SUR-003")
    assert sur003["class"] == "HOW_ACTIVE_VS_WHO_DEFAULT_DRIFT"
    # At least the known params overrides on v2_multi_2026_04 should appear if present
    if sur003["count"] > 0:
        keys = {d["key"] for d in sur003["details"]}
        # production params historically override body_ratio_min etc.
        assert keys  # non-empty detail set when count>0


def test_topology_dual_is_load_bearing_and_equal(live_doc):
    sur006 = next(r for r in live_doc["surplus_records"] if r["id"] == "SUR-006")
    assert sur006["runtime_consumed"] is True
    assert sur006["details"]["transitions_equal"] is True
    assert sur006["details"]["states_equal"] is True
    assert live_doc["summary"]["topology_yaml_code_equal"] is True


def test_no_fourth_yaml_in_candidates(frozen_doc):
    for c in frozen_doc["implementation_candidate_ledger"]:
        blob = json.dumps(c).lower()
        assert "market_state_registry" not in blob
        assert "fourth yaml" not in blob


def test_md_mentions_key_sections():
    text = MD_PATH.read_text(encoding="utf-8")
    assert "Implementation-candidate ledger" in text
    assert "SUR-001" in text
    assert "IC-001" in text
    assert "No fourth YAML" in text


def test_non_effects_declared(frozen_doc):
    ne = frozen_doc["non_effects"]
    assert any("no runtime code change" in x for x in ne)
    assert any("no behavior change" in x for x in ne)
