"""Enforcement floor for the Canonical Market Ontology Evolution Contract (2026-07-25).

Guards the non-frozen semantic sections (spec_schema.semantic_registry) via
features.registry.validate_semantic_registry, and asserts the frozen runtime path is untouched.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from features.registry import (            # noqa: E402
    load_ontology,
    validate_registry,
    validate_semantic_registry,
)


@pytest.fixture(scope="module")
def ont():
    return load_ontology()


# ── the live ontology satisfies both contracts ───────────────────────────────────────────────
def test_semantic_registry_is_clean(ont):
    assert validate_semantic_registry(ont) == []


def test_frozen_registry_unchanged(ont):
    # The contract is additive: the frozen feature-math path must be unaffected.
    assert validate_registry(ont) == []


# ── spec_schema declares the contract vocabularies (ontology-first) ───────────────────────────
def test_spec_schema_declares_contract(ont):
    sr = ont["spec_schema"]["semantic_registry"]
    assert set(sr["knowledge_status_ladder"]) >= {"UNKNOWN", "OBSERVED", "STABLE"}
    assert "ExecutionBehaviour" in sr["semantic_category_vocabulary"]
    assert "Unknown" in sr["semantic_category_vocabulary"]
    assert "canonical_unknowns" in sr["sections"]
    assert len(sr["semantic_node_required_fields"]) >= 20


# ── the seed nodes from this session are present + well-formed ────────────────────────────────
def test_seed_nodes_present(ont):
    ids = {}
    for sec in ("execution_behaviours", "invariants", "canonical_unknowns"):
        for name, spec in (ont.get(sec) or {}).items():
            ids[spec["id"]] = spec["knowledge_status"]
    assert ids.get("SEM-001") == "OBSERVED"          # EXPANSION_DWELL_DIVERGENCE
    assert ids.get("SEM-002") == "CHARACTERIZED"     # HTF_PROTECTION
    assert ids.get("SEM-003") == "MATHEMATICALLY_DEFINED"  # STATE_OCCUPANCY_VS_DWELL_SPAN
    assert ids.get("UNK-001") == "UNKNOWN"           # unknown mechanism


def test_no_duplicate_ids_across_all_sections(ont):
    # FM-0NN (frozen) + SEM-/UNK- (semantic) must share one global id namespace.
    seen = {}
    sr = ont["spec_schema"]["semantic_registry"]
    frozen = ("primitives", "feature_compositions", "derived_metrics", "rolling_indicators",
              "temporal_context", "structural_states")
    for sec in frozen + tuple(sr["sections"]):
        for name, spec in (ont.get(sec) or {}).items():
            fid = spec.get("id")
            if fid:
                assert fid not in seen, f"duplicate id {fid}: {name} and {seen[fid]}"
                seen[fid] = name


# ── negative cases: the validator actually catches contract violations ────────────────────────
def _mutate(ont, section, node, **changes):
    o = copy.deepcopy(ont)
    o[section][node].update(changes)
    return o


def test_missing_required_field_is_caught(ont):
    o = copy.deepcopy(ont)
    del o["execution_behaviours"]["htf_protection"]["evidence"]
    probs = validate_semantic_registry(o)
    assert any("missing required field 'evidence'" in p for p in probs)


def test_bad_knowledge_status_is_caught(ont):
    o = _mutate(ont, "execution_behaviours", "htf_protection", knowledge_status="MOSTLY_DONE")
    assert any("knowledge_status" in p for p in validate_semantic_registry(o))


def test_bad_category_is_caught(ont):
    o = _mutate(ont, "invariants", "state_occupancy_vs_dwell_span", semantic_category="Vibe")
    assert any("semantic_category" in p for p in validate_semantic_registry(o))


def test_evidence_required_above_unknown(ont):
    o = _mutate(ont, "execution_behaviours", "expansion_dwell_divergence", evidence="UNKNOWN")
    assert any("evidence must be non-empty" in p for p in validate_semantic_registry(o))


def test_canonical_unknown_cannot_be_high_status(ont):
    o = _mutate(ont, "canonical_unknowns",
                "unknown_expansion_occupancy_gap_mechanism",
                knowledge_status="VALIDATED", evidence=["x"], origin="x")
    assert any("canonical_unknowns node must be UNKNOWN/OBSERVED" in p
               for p in validate_semantic_registry(o))


def test_null_list_field_is_caught(ont):
    o = _mutate(ont, "execution_behaviours", "htf_protection", consumers=None)
    assert any("consumers is null" in p for p in validate_semantic_registry(o))


def test_duplicate_id_with_frozen_fm_is_caught(ont):
    o = _mutate(ont, "invariants", "state_occupancy_vs_dwell_span", id="FM-002")
    assert any("duplicate id 'FM-002'" in p for p in validate_semantic_registry(o))


# ── epistemic-block discipline (separate epistemic levels) ────────────────────────────────────
_UNK_NODE = "unknown_expansion_occupancy_gap_mechanism"


def test_unknown_node_carries_epistemic_block(ont):
    epi = ont["canonical_unknowns"][_UNK_NODE]["epistemic"]
    assert set(epi) >= {"known_invariants", "unknown_mechanism", "candidate_hypotheses",
                        "resolution_metric", "falsification_conditions"}
    assert isinstance(epi["falsification_conditions"], list) and epi["falsification_conditions"]


def test_unknown_status_requires_epistemic_block(ont):
    o = copy.deepcopy(ont)
    del o["canonical_unknowns"][_UNK_NODE]["epistemic"]
    assert any("requires an `epistemic` block" in p for p in validate_semantic_registry(o))


def test_incomplete_epistemic_block_is_caught(ont):
    o = copy.deepcopy(ont)
    del o["canonical_unknowns"][_UNK_NODE]["epistemic"]["falsification_conditions"]
    assert any("epistemic.falsification_conditions missing" in p
               for p in validate_semantic_registry(o))


def test_null_epistemic_list_is_caught(ont):
    o = copy.deepcopy(ont)
    o["canonical_unknowns"][_UNK_NODE]["epistemic"]["candidate_hypotheses"] = None
    assert any("epistemic.candidate_hypotheses is null" in p
               for p in validate_semantic_registry(o))
