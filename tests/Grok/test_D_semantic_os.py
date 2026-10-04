"""D. Semantic OS — fail-closed identity, relations, journeys, provenance.

The closed environment must refuse unknown ownership/concept/boundary claims
instead of fabricating a record. Complements tests/test_semantic_grounding.py
with auditor-specific substitutions (empty joins, invented journeys, object paths).
"""
from __future__ import annotations

import pytest

from governance.semantic_grounding import (
    AMBIGUOUS,
    GROUNDED,
    UNANSWERABLE,
    UNKNOWN,
    SemanticGrounder,
)
from governance.semantic_os import SemanticOSRegistry


@pytest.fixture(scope="module")
def grounder() -> SemanticGrounder:
    return SemanticGrounder.load()


@pytest.fixture(scope="module")
def registry() -> SemanticOSRegistry:
    return SemanticOSRegistry.load()


def test_unknown_ownership_relation_does_not_invent_an_edge(grounder: SemanticGrounder):
    """Fail-closed: a live concept does not own a live-but-unrelated boundary.

    Source: SemanticGrounder.ground_relationship / _relation_holds
    Failure mode: missing owner_boundary treated as true.
    """
    hit = grounder.ground(
        "RELATIONSHIP",
        "owns",
        source="CN-001",
        target="BD-001",
    )
    # Either GROUNDED (if the registry really joins them) or UNKNOWN (join absent).
    # Never a fabricated record_id that is not one of the endpoints/relation.
    assert hit.status in {GROUNDED, UNKNOWN}
    if hit.status == UNKNOWN:
        assert hit.record_id is None
        assert any("do not invent" in c.lower() or "join" in c.lower() for c in hit.caveats)


def test_invented_relation_is_unanswerable_not_a_new_kind(grounder: SemanticGrounder):
    hit = grounder.ground(
        "RELATIONSHIP",
        "causes_edge",
        source="CN-001",
        target="BD-001",
    )
    assert hit.status == UNANSWERABLE
    assert hit.record_id is None


def test_relationship_without_endpoints_is_unknown(grounder: SemanticGrounder):
    hit = grounder.ground("RELATIONSHIP", "owns")
    assert hit.status == UNKNOWN
    assert hit.record_id is None


def test_ungrounded_endpoint_fails_closed(grounder: SemanticGrounder):
    hit = grounder.ground(
        "RELATIONSHIP",
        "owns",
        source="CN-001",
        target="FloobyBoundary",
    )
    assert hit.status == UNKNOWN
    assert hit.record_id is None


def test_empty_noun_is_unknown(grounder: SemanticGrounder):
    hit = grounder.ground("NOUN", "")
    assert hit.status == UNKNOWN
    assert hit.record_id is None


def test_implementation_missing_file_is_unknown(grounder: SemanticGrounder):
    hit = grounder.ground("IMPLEMENTATION", "src/does_not_exist_semantic_audit.py")
    assert hit.status == UNKNOWN
    assert hit.record_id is None


def test_evidence_does_not_upgrade_a_typo_finding(grounder: SemanticGrounder):
    """F-48 (wrong width) is not F-048."""
    hit = grounder.ground("EVIDENCE", "F-48")
    assert hit.status == UNKNOWN
    assert hit.record_id is None


def test_registry_journeys_do_not_declare_illegal_crt_hops(registry: SemanticOSRegistry):
    """If a Semantic OS journey talks about CRT states, it must not invent hops
    outside VALID_TRANSITIONS. Unknown / non-CRT journeys are ignored.

    Source: docs/governance/semantic_os/journeys.yaml + state_identity.VALID_TRANSITIONS
    """
    from config_layer.state_identity import CRTState, VALID_TRANSITIONS

    legal = {s.name: {t.name for t in ts} for s, ts in VALID_TRANSITIONS.items()}
    crt_names = set(legal)
    invented = []
    for rec in registry.journeys.values():
        steps = rec.get("steps") or rec.get("journey_steps") or []
        names = []
        for step in steps:
            if isinstance(step, str):
                names.append(step)
            elif isinstance(step, dict):
                names.append(str(step.get("state") or step.get("name") or ""))
        crt_steps = [n for n in names if n in crt_names]
        for a, b in zip(crt_steps, crt_steps[1:]):
            if b not in legal[a]:
                invented.append((rec.get("id"), a, b))
    assert invented == [], f"SOS journey declares illegal CRT hops: {invented}"


def test_file_identity_unknown_path_is_not_grounded(grounder: SemanticGrounder):
    hit = grounder.ground("NOUN", "src/governance/this_file_is_not_real.py")
    assert hit.status == UNKNOWN


def test_grounding_payload_never_contains_fabricated_fm_id(grounder: SemanticGrounder):
    hit = grounder.ground("NOUN", "FM-999")
    assert hit.status == UNKNOWN
    assert "FM-999" not in str(hit.payload)
    assert hit.payload == {} or hit.payload.get("id") is None


def test_denominator_fm041_and_atr_abs_are_distinct_nouns(grounder: SemanticGrounder):
    """Provenance: FM-041 grounds; the local name atr_abs is not an ontology id.

    Source: EngineState.atr_abs comment (crt_engine_v2.py:244-248) + grounder
    Failure mode: treating atr_abs as FM-041 because both are called 'atr'.
    """
    fm = grounder.ground("NOUN", "FM-041")
    abs_name = grounder.ground("NOUN", "atr_abs")
    assert fm.status == GROUNDED
    # atr_abs may be UNKNOWN or resolve to a text alias — it must not share FM-041's id
    if abs_name.status == GROUNDED:
        assert abs_name.record_id != "FM-041"
    else:
        assert abs_name.status in {UNKNOWN, AMBIGUOUS, UNANSWERABLE}
