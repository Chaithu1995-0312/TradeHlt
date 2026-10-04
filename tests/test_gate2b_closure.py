"""F-049 Gate-2B closure invariants — machine-checked against the frozen Census-v3 governed ID set.

Gate 2B cannot be complete unless: adjudicated ids == frozen governed ids (no missing / foreign /
duplicate), and every record carries semantic relation, family, variant, zero-range policy, all six
reachability dimensions (with evidence), hypothesis comparison, contradiction + Gate-5 status fields.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_CENSUS = _REPO / "docs" / "governance" / "geometry_census.jsonl"
_ADJ = _REPO / "docs" / "governance" / "geometry_semantic_adjudication.jsonl"
_FAM = _REPO / "docs" / "governance" / "geometry_family_registry.json"

_RELATIONS = {"CANONICAL_EQUIVALENT", "MATHEMATICALLY_EQUIVALENT_VARIANT", "DOMAIN_POLICY_VARIANT",
              "NON_EQUIVALENT_SAME_NAME", "SAME_MATH_DIFFERENT_NAME",
              "SUBEXPRESSION_OF_GOVERNED_QUANTITY", "INDEPENDENT_UNGOVERNED_QUANTITY",
              "TEST_ORACLE", "NO_GOVERNED_COUNTERPART", "UNKNOWN"}
_REACH_DIMS = ("runtime_reachable", "decision_reachable", "research_reachable",
               "training_reachable", "artifact_reachable", "test_only")
_REACH_VALUES = {"YES", "NO", "UNKNOWN", "NOT_APPLICABLE"}


def _load():
    if not (_CENSUS.exists() and _ADJ.exists()):
        pytest.skip("gate-2B artifacts not generated")
    cen = [json.loads(l) for l in _CENSUS.read_text(encoding="utf-8").splitlines() if l.strip()]
    adj = [json.loads(l) for l in _ADJ.read_text(encoding="utf-8").splitlines() if l.strip()]
    return cen, adj


def test_closure_ids_exact():
    cen, adj = _load()
    governed = sorted(r["occurrence_id"] for r in cen if r["derivation_id_or_null"])
    adjudicated = sorted(r["occurrence_id"] for r in adj)
    assert len(adjudicated) == len(set(adjudicated)), "duplicate adjudication records"
    missing = set(governed) - set(adjudicated)
    foreign = set(adjudicated) - set(governed)
    assert not missing, f"MISSING governed records: {sorted(missing)[:5]} (+{max(0,len(missing)-5)})"
    assert not foreign, f"FOREIGN adjudication records: {sorted(foreign)[:5]}"
    assert adjudicated == governed


def test_every_record_complete():
    _cen, adj = _load()
    for r in adj:
        assert r["semantic_relation"] in _RELATIONS, f'{r["derivation_id"]}: bad relation'
        assert str(r["semantic_family_id"]).strip(), f'{r["derivation_id"]}: no family'
        assert str(r["implementation_variant"]).strip(), f'{r["derivation_id"]}: no variant'
        assert str(r["zero_range_policy"]).strip(), f'{r["derivation_id"]}: no zero policy'
        for dim in _REACH_DIMS:
            assert r.get(dim) in _REACH_VALUES, f'{r["derivation_id"]}: bad {dim}={r.get(dim)}'
        assert str(r["reachability_evidence"]).strip()
        assert str(r["evidence"]).strip()
        assert r["hypothesis_comparison"].split(" ")[0].split("_")[0] in ("HYPOTHESIS", "UNKNOWN")
        assert "contradiction_status" in r and "gate5_followup" in r


def test_unknowns_carry_gate5_or_reason():
    """artifact/training UNKNOWNs are admissible; they must be Gate-5-deferrable by design."""
    _cen, adj = _load()
    for r in adj:
        if r["artifact_reachable"] == "UNKNOWN":
            assert ("Gate-5" in r["reachability_evidence"]) or r["gate5_followup"] or \
                   ("Gate-5" in r["evidence"]), f'{r["derivation_id"]}: artifact UNKNOWN without Gate-5 pointer'


def test_family_registry_consistent():
    _cen, adj = _load()
    fam = json.loads(_FAM.read_text(encoding="utf-8"))
    member_ids = {i for d in fam["families"].values() for i in d["member_site_ids"]}
    adj_fam_ids = {r["derivation_id"] for r in adj if r["semantic_family_id"] != "-"}
    assert member_ids == adj_fam_ids, "family registry membership != adjudication family assignments"


def test_preserved_contradictions_present():
    """The mandated contradiction seeds must be preserved, not remediated away."""
    _cen, adj = _load()
    text = json.dumps(adj)
    for marker in ("GD-001", "GD-002", "F-050", "CS-2", "FAM-04-TABLE3-FLOORED-WICK"):
        assert marker in text, f"mandated contradiction seed missing from adjudication: {marker}"
