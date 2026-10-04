# Phase 1 audit test. Authority: handoff brief section 3 (V-1..V-12) and the three registries.
from __future__ import annotations

import copy

from semantics.registry import (
    load_concept_contracts,
    load_representation_shards,
    load_terminal_reason_map,
    validate_concepts,
    validate_representations,
    validate_terminal_reasons,
    validate_unmapped_shrink_only,
)


def _concepts():
    return load_concept_contracts()['concepts']


def _shards():
    return copy.deepcopy(load_representation_shards())


def test_a_rep_pointing_at_a_proposed_concept_fails():
    concepts = _concepts()
    assert concepts['GP-07']['status'] == 'PROPOSED'
    shards = _shards()
    shards['crt_engine.yaml']['representations']['SweepEvent']['concept_id'] = 'GP-07'
    problems = validate_representations(concepts, shards)
    assert any('PROPOSED' in p for p in problems)


def test_an_input_referencing_a_higher_layer_fails():
    doc = copy.deepcopy(load_concept_contracts())
    doc['concepts']['GP-01']['inputs'] = ['MKT-L01']
    problems = validate_concepts(doc)
    assert any('I-12' in p for p in problems)


def test_an_accepted_source_that_is_not_git_tracked_fails():
    doc = copy.deepcopy(load_concept_contracts())
    doc['concepts']['GP-01']['authority']['sources'] = ['src/does_not_exist_at_all.py']
    problems = validate_concepts(doc)
    assert any('git-tracked' in p for p in problems)


def test_a_parameter_without_identity_bearing_fails():
    doc = copy.deepcopy(load_concept_contracts())
    del doc['concepts']['MKT-C01']['parameterization']['k']['identity_bearing']
    problems = validate_concepts(doc)
    assert any('identity_bearing' in p for p in problems)


def test_a_legacy_value_without_divergence_ref_fails():
    concepts = _concepts()
    shards = _shards()
    rep = shards['crt_engine.yaml']['representations']['SweepEvent']
    rep['parameterization']['tie'] = 'inclusive'
    rep.pop('divergence_ref', None)
    problems = validate_representations(concepts, shards)
    assert any('inclusive' in p for p in problems)


def test_adding_a_slot_to_an_unmapped_ratchet_fails():
    shards = _shards()
    pinned = {shard['producer_id']: list(shard.get('unmapped') or []) for shard in shards.values()}
    assert validate_unmapped_shrink_only(shards, pinned) == []
    shards['feature_pipeline.yaml']['unmapped']['brand_new_slot'] = 'growth'
    problems = validate_unmapped_shrink_only(shards, pinned)
    assert any('brand_new_slot' in p for p in problems)


def test_deleting_a_terminal_entry_a_reset_literal_needs_fails():
    doc = copy.deepcopy(load_terminal_reason_map())
    doc['entries'] = [e for e in doc['entries'] if e.get('reason') != 'Sweep expired']
    problems = validate_terminal_reasons(doc)
    assert any('Sweep expired' in p for p in problems)
