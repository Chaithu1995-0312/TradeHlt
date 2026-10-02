"""Grounding the v2 meaning plane (SEMANTIC_OS_V2_MEANING_PLANE.md §15, G-1..G-6)."""

from __future__ import annotations

import copy

import pytest

from governance.concept_grounding import MeaningPlane
from governance.semantic_grounding import (
    AMBIGUOUS, GROUNDED, REFUSED, UNKNOWN, SemanticGrounder,
)
from semantics.consumers import _matches, _ModuleFacts, consumers_by_concept
from semantics.registry import load_concept_contracts, validate_proposed_unbound, validate_proposed_unbound_source


@pytest.fixture(scope="module")
def grounder() -> SemanticGrounder:
    # CONCEPT / REPRESENTATION / meaning relations never touch the v1 registry or index.
    return SemanticGrounder(registry=None, index=None)


def test_a_concept_grounds_by_id_name_and_alias(grounder):
    by_id = grounder.ground("CONCEPT", "MKT-E01")
    by_name = grounder.ground("CONCEPT", "SWEEP")
    alias = grounder.ground("CONCEPT", "retest_entry")
    assert by_id.status == by_name.status == GROUNDED and by_name.record_id == "MKT-E01"
    assert alias.status == GROUNDED and alias.record_id == "MKT-E09"
    assert by_id.payload["status"] == "ACCEPTED" and "configs/formulas/concept_contracts.yaml" in by_id.artifacts
    assert grounder.ground("CONCEPT", "MKT-P01.SWEPT").record_id == "MKT-P01.SWEPT"


def test_a_concept_payload_lists_representations_and_heuristic_consumers(grounder):
    hit = grounder.ground("CONCEPT", "DEX-09")
    assert "crt_engine:Trade.pnl" in hit.payload["representations"]
    assert hit.payload["consumers_evidence_class"] == "HEURISTIC"
    assert "src/config_layer/crt_engine_v2.py" in hit.payload["consumers"]
    assert any("HEURISTIC" in c for c in hit.caveats)


def test_g1_a_proposed_concept_grounds_with_a_caveat(grounder):
    hit = grounder.ground("CONCEPT", "MKT-E03")
    assert hit.status == GROUNDED and hit.payload["status"] == "PROPOSED"
    assert "PROPOSED" in hit.caveats[0] and hit.payload["representations"] == []


def test_unknown_and_ambiguous_concepts_fail_closed():
    assert MeaningPlane.load() is not None
    grounder = SemanticGrounder(registry=None, index=None)
    assert grounder.ground("CONCEPT", "not_a_concept").status == UNKNOWN
    plane = MeaningPlane.load()
    concepts = copy.deepcopy(plane.concepts)
    concepts["TRS-01"]["aliases"] = ["sweep"]
    clash = MeaningPlane(concepts, plane.shards)
    from governance.concept_grounding import ground_concept
    hit = ground_concept(clash, "sweep")
    assert hit.status == AMBIGUOUS and hit.record_id is None


def test_g2_representation_mapped_unmapped_deprecated(grounder):
    hit = grounder.ground("REPRESENTATION", "crt_engine:Trade.pnl")
    assert hit.status == GROUNDED and hit.payload["concept_id"] == "DEX-09"
    assert hit.payload["divergence_ref"] == "DEX-09 Trade.pnl"
    unmapped = grounder.ground("REPRESENTATION", "Trade.partial_pnl")
    assert unmapped.status == UNKNOWN and "unmapped" in unmapped.ungrounded_reason
    dead = grounder.ground("REPRESENTATION", "SweepEvent.double_confirmed")
    assert dead.status == REFUSED and "I-13" in dead.ungrounded_reason
    assert grounder.ground("REPRESENTATION", "crt_engine:No.such").status == UNKNOWN


def test_meaning_relations(grounder):
    ok = grounder.ground("RELATIONSHIP", "", relation="represents", source="crt_engine:Trade.pnl", target="DEX-09")
    wrong = grounder.ground("RELATIONSHIP", "", relation="represents", source="crt_engine:Trade.pnl", target="TRS-08")
    feeds = grounder.ground("RELATIONSHIP", "", relation="input_of", source="TRS-07", target="DEX-09")
    nope = grounder.ground("RELATIONSHIP", "", relation="input_of", source="DEX-09", target="TRS-07")
    assert (ok.status, wrong.status, feeds.status, nope.status) == (GROUNDED, UNKNOWN, GROUNDED, UNKNOWN)


def test_g3_noun_never_falls_through_to_v2():
    hit = SemanticGrounder.load().ground("NOUN", "MKT-E01")
    assert hit.status == UNKNOWN


def test_g4_consumer_matching_rules():
    facts = _ModuleFacts()
    facts.pairs.add(("CRTState", "SWEEP"))
    facts.names.add("Trade")
    facts.attrs.update({"pnl", "status"})
    facts.strings.update({"sweep_detected", "RESET"})
    assert _matches("crt_engine", "CRTState.SWEEP", facts)
    assert not _matches("crt_engine", "CRTState.RETEST", facts)
    assert _matches("crt_engine", "Trade.pnl", facts)
    assert _matches("crt_engine", "events.RESET", facts)
    assert _matches("feature_pipeline", "sweep_detected", facts)
    assert _matches("crt_engine", "Trade.tp1_price[liq_sweep]", facts) is False
    orphan = _ModuleFacts()
    orphan.attrs.add("pnl")   # .pnl without the owner named is not a Trade.pnl consumer
    assert not _matches("crt_engine", "Trade.pnl", orphan)


def test_consumers_exclude_the_semantics_package():
    for modules in consumers_by_concept().values():
        assert not any(m.startswith("src/semantics/") for m in modules)


def test_v19_proposed_ids_are_never_bound_in_semantics_code():
    concepts = load_concept_contracts()["concepts"]
    assert validate_proposed_unbound(concepts) == []
    bad = validate_proposed_unbound_source('X = "MKT-E03"\n', {"MKT-E03"}, name="x.py")
    assert bad and "I-18" in bad[0]
    assert validate_proposed_unbound_source('"""mentions MKT-E03 in prose"""\n', {"MKT-E03"}, name="x.py") == []
