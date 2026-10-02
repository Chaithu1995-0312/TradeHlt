"""V-1..V-5 on concept_contracts.yaml, plus the mutation cases from the slice-1 brief."""

from __future__ import annotations

import copy

import pytest

from semantics.registry import (
    DuplicateKeyError,
    load_concept_contracts,
    load_representation_shards,
    parse_registry,
    validate_concepts,
    validate_representations,
)


def test_shipped_contracts_pass_v1_through_v5():
    assert validate_concepts(load_concept_contracts()) == []


def test_duplicate_concept_id_fails():
    # V-1: plain yaml.safe_load would silently keep the second record.
    text = "concepts:\n  GP-01: {layer: GEOMETRY}\n  GP-01: {layer: MARKET}\n"
    with pytest.raises(DuplicateKeyError, match="GP-01"):
        parse_registry(text)


def test_missing_required_field_fails():
    doc = copy.deepcopy(load_concept_contracts())
    del doc["concepts"]["MKT-E01"]["absence"]
    problems = validate_concepts(doc)
    assert any("MKT-E01" in item and "absence" in item for item in problems), problems


def test_higher_layer_input_fails():
    doc = copy.deepcopy(load_concept_contracts())
    doc["concepts"]["GP-01"]["inputs"] = ["MKT-L01"]
    problems = validate_concepts(doc)
    assert any("I-12" in item for item in problems), problems


def test_untracked_source_fails():
    doc = copy.deepcopy(load_concept_contracts())
    doc["concepts"]["GP-01"]["authority"]["sources"] = ["src/does_not_exist_semantics.py"]
    problems = validate_concepts(doc)
    assert any("not git-tracked" in item for item in problems), problems


def test_missing_identity_bearing_flag_fails():
    doc = copy.deepcopy(load_concept_contracts())
    del doc["concepts"]["MKT-C01"]["parameterization"]["k"]["identity_bearing"]
    problems = validate_concepts(doc)
    assert any("identity_bearing" in item for item in problems), problems


def test_measurement_without_units_fails():
    doc = copy.deepcopy(load_concept_contracts())
    doc["concepts"]["GP-01"]["kind"] = "MEASUREMENT"
    doc["concepts"]["GP-01"]["units"] = {}
    problems = validate_concepts(doc)
    assert any("MEASUREMENT" in item for item in problems), problems


def test_accepted_with_trading_knowledge_evidence_fails():
    doc = copy.deepcopy(load_concept_contracts())
    doc["concepts"]["GP-01"]["authority"]["evidence"] = ["TK"]
    problems = validate_concepts(doc)
    assert any("evidence" in item for item in problems), problems


def test_proposed_concept_bound_to_a_representation_fails():
    concepts = load_concept_contracts()["concepts"]
    shards = copy.deepcopy(load_representation_shards())
    crt = shards["crt_engine.yaml"]
    crt["representations"]["SweepEvent"]["concept_id"] = "GP-07"
    problems = validate_representations(concepts, shards)
    assert any("PROPOSED" in item for item in problems), problems
