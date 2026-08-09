"""Feature Specification Schema floor — ontology v1.4.

`market_ontology.yaml` is a FEATURE SPECIFICATION SYSTEM, not merely a formula registry: every
entry must answer what it is, why it exists, how it is computed, what it means, what states it can
express, which config influences it, and what it depends on. This module is the floor that keeps it
that way — without it, the next entry someone adds carries a formula and nothing else, and the
system silently degrades back into a formula registry.

Complements, does not duplicate:
  - test_feature_lineage.py    — the CHAIN (ontology -> registry -> impl -> parity -> vector) and,
                                 since v1.4, the reverse vector -> ontology coverage ratchet.
  - test_ontology_config_parity.py — declared `config_key`s match what the code actually reads.
  - THIS FILE                  — the SPEC CONTRACT: is each entry self-describing?

The strongest assertion here is `test_vector_index_matches_feature_schema`: the ontology's claim
about WHERE a feature sits in the 39-dim vector is checked against FEATURE_INDEX_MAP rather than
trusted. A stale index is otherwise invisible — and schema v4.0's MACD split shifted the entire
v3.0 tail by +1, which is exactly how such a claim goes stale.
"""
from __future__ import annotations

import pytest

from features.registry import load_ontology, validate_registry, _iter_entries
from features.feature_schema import CANONICAL_FEATURES, FEATURE_INDEX_MAP

# Blocks every entry must carry. `states` is included deliberately: its EMPTY form is meaningful
# (the feature is continuous), so absence and emptiness are different statements.
_REQUIRED_BLOCKS = ("taxonomy", "semantics", "states", "lineage")
_REQUIRED_SEMANTICS = ("description", "why_it_exists", "interpretation")
_REQUIRED_LINEAGE = ("derivation_depth", "produced_by", "consumed_by", "vector_key", "vector_index")
_REQUIRED_STATE_FIELDS = ("name", "value", "condition", "description")


@pytest.fixture(scope="module")
def ont():
    return load_ontology()


@pytest.fixture(scope="module")
def entries(ont):
    return list(_iter_entries(ont))


def test_validate_registry_is_clean(ont):
    """The runtime validator — which now enforces the spec schema — reports nothing."""
    assert validate_registry(ont) == []


def test_spec_schema_block_exists(ont):
    schema = ont.get("spec_schema")
    assert schema, "ontology is missing its `spec_schema` contract block"
    assert schema.get("category_vocabulary"), "spec_schema.category_vocabulary is empty"
    assert schema.get("knowledge_class_vocabulary"), "spec_schema.knowledge_class_vocabulary is empty"
    assert schema.get("frozen_runtime_keys"), (
        "spec_schema.frozen_runtime_keys is empty — this list is the record of WHICH keys may "
        "never be nested (they are read flat, at import time, by fm_resolve/derived_registry)"
    )


def test_every_entry_carries_all_spec_blocks(entries):
    missing = [
        f"{section}.{name}: {block}"
        for section, name, spec in entries
        for block in _REQUIRED_BLOCKS
        if block not in spec
    ]
    assert not missing, "entries missing required spec blocks:\n  " + "\n  ".join(missing)


def test_semantics_are_populated(entries):
    """A present-but-empty semantics block is the failure mode this catches."""
    bad = [
        f"{section}.{name}: semantics.{field}"
        for section, name, spec in entries
        for field in _REQUIRED_SEMANTICS
        if not (spec.get("semantics") or {}).get(field)
    ]
    assert not bad, "empty semantics fields:\n  " + "\n  ".join(bad)


def test_lineage_fields_present(entries):
    bad = [
        f"{section}.{name}: lineage.{field}"
        for section, name, spec in entries
        for field in _REQUIRED_LINEAGE
        if field not in (spec.get("lineage") or {})
    ]
    assert not bad, "missing lineage fields:\n  " + "\n  ".join(bad)


def test_vocabularies_are_closed(ont, entries):
    """Free-text categories would make the taxonomy unqueryable — the point of having one."""
    schema = ont["spec_schema"]
    categories = set(schema["category_vocabulary"])
    knowledge = set(schema["knowledge_class_vocabulary"])
    bad = []
    for section, name, spec in entries:
        tax = spec.get("taxonomy") or {}
        if tax.get("category") not in categories:
            bad.append(f"{section}.{name}: category {tax.get('category')!r}")
        if tax.get("knowledge_class") not in knowledge:
            bad.append(f"{section}.{name}: knowledge_class {tax.get('knowledge_class')!r}")
    assert not bad, "values outside the closed vocabularies:\n  " + "\n  ".join(bad)


def test_empty_collections_are_lists_never_null(entries):
    """YAML `null` deserializes to None, so `spec.get("states", [])` returns None and the caller's
    default never fires — the next iteration raises TypeError. Absent-means-empty is a trap;
    empty-means-empty is the contract."""
    bad = []
    for section, name, spec in entries:
        if not isinstance(spec.get("states"), list):
            bad.append(f"{section}.{name}: states is {type(spec.get('states')).__name__}, not list")
        consumed = (spec.get("lineage") or {}).get("consumed_by")
        if not isinstance(consumed, list):
            bad.append(
                f"{section}.{name}: lineage.consumed_by is {type(consumed).__name__}, not list"
            )
    assert not bad, "null/scalar where a list is required:\n  " + "\n  ".join(bad)


def test_structural_states_declare_their_states(ont):
    """The whole reason `structural_states` is its own section: the legal VALUES are not the
    knowledge — what each value MEANS is."""
    bad = []
    for name, spec in (ont.get("structural_states") or {}).items():
        states = spec.get("states") or []
        if not states:
            bad.append(f"{name}: no states declared")
            continue
        for st in states:
            for field in _REQUIRED_STATE_FIELDS:
                if field not in st:
                    bad.append(f"{name}: state {st.get('name', '?')!r} missing {field!r}")
    assert not bad, "structural_states with incomplete state definitions:\n  " + "\n  ".join(bad)


def test_enumerated_domains_have_states(entries):
    """`bounds: "{0, 1, 2}"` enumerates values, so each carries meaning and must be named.
    `bounds: "[0, 100]"` is a RANGE — rsi_14 has no per-value semantics and needs no states."""
    bad = [
        f"{section}.{name}: bounds {spec['bounds']!r} but states is empty"
        for section, name, spec in entries
        if str(spec.get("bounds") or "").strip().startswith("{") and not spec.get("states")
    ]
    assert not bad, "enumerated domains without state definitions:\n  " + "\n  ".join(bad)


def test_state_values_are_unique_within_a_feature(entries):
    bad = []
    for section, name, spec in entries:
        values = [st.get("value") for st in (spec.get("states") or [])]
        if len(values) != len(set(values)):
            bad.append(f"{section}.{name}: duplicate state values {values}")
    assert not bad, "\n  ".join(bad)


def test_vector_index_matches_feature_schema(entries):
    """The ontology's claim about vector position, checked rather than trusted.

    This is the assertion that would have caught schema v4.0's tail shift: the MACD split moved
    every v3.0 index >= 18 by +1, and a hand-written `vector_index` has no other way to be found
    wrong. (One such stale claim was found and fixed during the v1.4 backfill: FM-025
    liquidity_distance's note said index 35; it is 36.)
    """
    bad = []
    for section, name, spec in entries:
        lin = spec.get("lineage") or {}
        key, idx = lin.get("vector_key"), lin.get("vector_index")
        if not isinstance(key, str) or not key:
            # Unbound: both must be empty, so a slot cannot be half-claimed.
            assert not idx or idx == [], (
                f"{section}.{name}: vector_index {idx!r} declared without a vector_key"
            )
            continue
        if key not in FEATURE_INDEX_MAP:
            bad.append(f"{section}.{name}: vector_key {key!r} is not in CANONICAL_FEATURES")
        elif FEATURE_INDEX_MAP[key] != idx:
            bad.append(
                f"{section}.{name}: vector_index {idx} but CANONICAL_FEATURES has "
                f"{key!r} at {FEATURE_INDEX_MAP[key]}"
            )
    assert not bad, "ontology vector bindings disagree with feature_schema:\n  " + "\n  ".join(bad)


def test_vector_keys_are_unique(entries):
    """Two entries claiming the same slot means one of them is wrong about what it emits."""
    seen: dict[str, str] = {}
    bad = []
    for section, name, spec in entries:
        key = (spec.get("lineage") or {}).get("vector_key")
        if isinstance(key, str) and key:
            if key in seen:
                bad.append(f"{key!r} claimed by both {seen[key]} and {name}")
            seen[key] = name
    assert not bad, "duplicate vector_key claims:\n  " + "\n  ".join(bad)


def test_depends_on_is_referentially_intact(ont, entries):
    """Set inclusion only — the acyclic/grounded property is owned by test_feature_lineage.py."""
    known = {name for _s, name, _sp in entries} | set(ont.get("base_inputs") or ())
    bad = [
        f"{section}.{name}: depends_on {dep!r}"
        for section, name, spec in entries
        for dep in (spec.get("depends_on") or ())
        if dep not in known
    ]
    assert not bad, "unresolvable dependencies:\n  " + "\n  ".join(bad)


def test_canonical_coverage_is_near_complete(entries, ont):
    """Coverage is a number worth pinning: v1.4 took it from 23/39 to 37/39; 2026-08-01 (FM-064
    trend_strength + FM-065 candles_since_retest registered) closed the gap to 39/39 -- full
    coverage, matching _UNREGISTERED_VECTOR_SLOTS now being empty in test_feature_lineage.py."""
    known = {name for _s, name, _sp in entries} | set(ont.get("base_inputs") or ())
    covered = [f for f in CANONICAL_FEATURES if f in known]
    assert len(covered) == 39, (
        f"canonical coverage changed: {len(covered)}/{len(CANONICAL_FEATURES)}. "
        "Raising this is the goal (see _UNREGISTERED_VECTOR_SLOTS in test_feature_lineage.py); "
        "lowering it means an identity was withdrawn — update this pin deliberately."
    )
