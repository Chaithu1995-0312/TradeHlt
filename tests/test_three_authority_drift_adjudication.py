"""
IC-008 adjudication artifact guards.

Observational only — does not mutate runtime, WHO YAML, production JSON,
state_contracts, or execute IC-001/IC-002 cleanup.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_GOV = _ROOT / "docs" / "governance"
JSON_PATH = _GOV / "three_authority_drift_adjudication-2026-07-11.json"
MD_PATH = _GOV / "three_authority_drift_adjudication-2026-07-11.md"
CENSUS_JSON = _GOV / "three_authority_declaration_surplus_census-2026-07-11.json"
ACTIVE_MODELS = _ROOT / "active_models.yaml"

ALLOWED_CLASSIFICATIONS = frozenset(
    {
        "PROVEN_SAME_SEMANTIC",
        "PROVEN_DIFFERENT_SEMANTIC",
        "PROVEN_WHO_RUNTIME_AUTHORITY",
        "PROVEN_HOW_RUNTIME_AUTHORITY",
        "PROVEN_DUAL_RUNTIME_AUTHORITY",
        "UNPROVEN",
    }
)
ALLOWED_DISPOSITIONS = frozenset(
    {
        "PRESERVE_NO_ACTION",
        "ELIGIBLE_FOR_FUTURE_WHO_CLEANUP",
        "KEEP_DISTINCT",
        "REQUIRES_REMEDIATION",
    }
)


@pytest.fixture(scope="module")
def doc() -> dict:
    assert JSON_PATH.is_file(), f"missing adjudication artifact: {JSON_PATH}"
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def census() -> dict:
    assert CENSUS_JSON.is_file(), f"missing census artifact: {CENSUS_JSON}"
    return json.loads(CENSUS_JSON.read_text(encoding="utf-8"))


def test_artifacts_exist():
    assert JSON_PATH.is_file()
    assert MD_PATH.is_file()


def test_exactly_six_drift_records(doc):
    drifts = doc["drifts"]
    assert len(drifts) == 6
    assert doc["summary"]["total_drifts"] == 6


def test_every_census_drift_represented_exactly_once(doc, census):
    sur003 = next(r for r in census["surplus_records"] if r["id"] == "SUR-003")
    assert sur003["class"] == "HOW_ACTIVE_VS_WHO_DEFAULT_DRIFT"
    census_keys = [d["key"] for d in sur003["details"]]
    assert len(census_keys) == 6
    adj_keys = [d["census_key"] for d in doc["drifts"]]
    assert sorted(adj_keys) == sorted(census_keys)
    assert len(set(adj_keys)) == 6  # no duplicates


def test_no_extra_drift_records(doc, census):
    sur003 = next(r for r in census["surplus_records"] if r["id"] == "SUR-003")
    census_key_set = {d["key"] for d in sur003["details"]}
    adj_key_set = {d["census_key"] for d in doc["drifts"]}
    assert adj_key_set == census_key_set


def test_every_record_has_who_path_and_value(doc):
    for d in doc["drifts"]:
        assert d.get("who_path"), d["drift_id"]
        assert "who_value" in d, d["drift_id"]  # may be null for session_windows


def test_every_record_has_how_path_and_value(doc):
    for d in doc["drifts"]:
        assert d.get("how_path"), d["drift_id"]
        assert "active_how_value" in d, d["drift_id"]
        assert "how_value" in d, d["drift_id"]


def test_every_record_has_runtime_consumption_evidence(doc):
    for d in doc["drifts"]:
        assert d["who_runtime_consumed"] in {"YES", "NO"}, d["drift_id"]
        assert d["how_runtime_consumed"] in {"YES", "NO"}, d["drift_id"]
        assert d.get("runtime_loader"), d["drift_id"]
        assert d.get("runtime_consumer_files"), d["drift_id"]
        assert d.get("runtime_consumer_lines"), d["drift_id"]
        assert d.get("evidence"), d["drift_id"]


def test_every_record_has_classification_and_disposition(doc):
    for d in doc["drifts"]:
        assert d["classification"] in ALLOWED_CLASSIFICATIONS, d["drift_id"]
        assert d["disposition"] in ALLOWED_DISPOSITIONS, d["drift_id"]


def test_eligible_cleanup_requires_who_not_runtime_consumed(doc):
    """ELIGIBLE_FOR_FUTURE_WHO_CLEANUP ⇒ who_runtime_consumed == NO."""
    for d in doc["drifts"]:
        if d["disposition"] == "ELIGIBLE_FOR_FUTURE_WHO_CLEANUP":
            assert d["who_runtime_consumed"] == "NO", d["drift_id"]


def test_unproven_uses_preserve_no_action(doc):
    """UNPROVEN must result in PRESERVE_NO_ACTION (proof-only rule)."""
    for d in doc["drifts"]:
        if d["classification"] == "UNPROVEN":
            assert d["disposition"] == "PRESERVE_NO_ACTION", d["drift_id"]


def test_summary_counts_match_records(doc):
    drifts = doc["drifts"]
    s = doc["summary"]
    for cls in ALLOWED_CLASSIFICATIONS:
        assert s[cls] == sum(1 for d in drifts if d["classification"] == cls), cls
    for disp in ALLOWED_DISPOSITIONS:
        assert s[disp] == sum(1 for d in drifts if d["disposition"] == disp), disp


def test_who_runtime_numeric_authority_gate(doc):
    if any(d["who_runtime_consumed"] == "YES" for d in doc["drifts"]):
        assert doc["summary"]["WHO_RUNTIME_NUMERIC_AUTHORITY_FOUND"] == "YES"
    else:
        assert doc["summary"]["WHO_RUNTIME_NUMERIC_AUTHORITY_FOUND"] == "NO"


def test_how_runtime_authority_gate(doc):
    how_yes = sum(1 for d in doc["drifts"] if d["how_runtime_consumed"] == "YES")
    if how_yes == 6:
        assert doc["summary"]["HOW_RUNTIME_AUTHORITY_CONFIRMED"] == "YES"
    elif how_yes == 0:
        assert doc["summary"]["HOW_RUNTIME_AUTHORITY_CONFIRMED"] == "NO"
    else:
        assert doc["summary"]["HOW_RUNTIME_AUTHORITY_CONFIRMED"] == "PARTIAL"


def test_ic_readiness_blocked_without_eligible_cleanup(doc):
    """IC001/IC002 may be YES only if cleanup eligibility is proven — not here by default."""
    s = doc["summary"]
    if s["ELIGIBLE_FOR_FUTURE_WHO_CLEANUP"] == 0 or s["UNPROVEN"] > 0:
        assert s["IC001_READY"] == "NO"
        assert s["IC002_READY"] == "NO"


def test_state_contracts_remain_unchanged_by_adjudication(doc):
    """Adjudication must not introduce state_contracts mutation claims."""
    assert doc["summary"]["STATE_CONTRACTS_UNCHANGED"] is True
    assert doc["non_effects"]
    assert any("state_contracts" in x for x in doc["non_effects"])
    # Live WHO: state_contracts still only allowed structural fields
    import yaml

    am = yaml.safe_load(ACTIVE_MODELS.read_text(encoding="utf-8"))
    sc = am["crt"]["runtime"]["state_contracts"]
    allowed = {"required_fm", "config_keys", "eligible_models"}
    for sid, body in sc.items():
        assert set(body.keys()) <= allowed, sid


def test_no_fourth_yaml_introduced(doc):
    assert doc["summary"]["NO_FOURTH_YAML"] is True
    blob = json.dumps(doc).lower()
    assert "market_state_registry" not in blob
    assert "fourth yaml" not in blob or "no fourth yaml" in blob
    # MD must not invent a new peer authority file
    md = MD_PATH.read_text(encoding="utf-8").lower()
    assert "no fourth yaml" in md


def test_md_mentions_ic008_and_six_drifts():
    text = MD_PATH.read_text(encoding="utf-8")
    assert "IC-008" in text
    assert "DRIFT-001" in text
    assert "DRIFT-006" in text
    assert "PROVEN_HOW_RUNTIME_AUTHORITY" in text
    assert "PRESERVE_NO_ACTION" in text


def test_runtime_behavior_unchanged_declared(doc):
    assert doc["summary"]["RUNTIME_BEHAVIOR_UNCHANGED"] is True
    assert any("no runtime" in x.lower() for x in doc["non_effects"])


def test_adjudication_does_not_execute_ic001_ic002(doc):
    assert doc.get("ic") == "IC-008"
    assert any("IC-001" in x and "IC-002" in x for x in doc["non_effects"])
