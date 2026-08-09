"""Two-namespace floor — canonical stays frozen, candidate stays free and unauthoritative.

The point of the candidate namespace is that research features can change without
re-identifying an episode and without touching the production feature contract. These
tests pin exactly that, so a future refactor cannot quietly couple the two again.
"""
from __future__ import annotations

from dataclasses import replace

from research.episodes import protocol as P
from research.episodes.builder import build_episode
from research.episodes.schema import EntrySnapshot
from research.episodes.store import from_dict, read_episodes, to_dict, write_episodes


class Bar:
    def __init__(self, i):
        self.index = i
        self.open, self.high, self.low, self.close, self.volume = 100.0 + i, 101.0 + i, 99.0 + i, 100.5 + i, 1.0
        self.timestamp = f"2026-01-01 {i // 4:02d}:{(i % 4) * 15:02d}:00"


CANDLES = [Bar(i) for i in range(10)]
ENTRY = EntrySnapshot(bar_index=0, timestamp="2026-01-01 00:00:00", direction="long",
                      entry_price=100.0, sl_price=98.0, tp_price=104.0)


def _ep(entry=ENTRY):
    return build_episode(instrument="T", population="DETECTION_STREAM",
                         entry=entry, candles=CANDLES, max_forward=5)


# ── protocol declaration ──────────────────────────────────────────────────
def test_protocol_declares_both_namespaces():
    assert P.FEATURE_NAMESPACES == ("canonical", "candidate")
    assert P.CANONICAL_NAMESPACE_IS_FROZEN is True
    assert P.CANDIDATE_NAMESPACE_AUTHORITY == "none"


def test_freeze_block_records_the_namespace_contract():
    ns = P.freeze_block()["feature_namespaces"]
    assert ns["canonical_is_frozen"] is True
    assert ns["candidate_authority"] == "none"
    assert ns["candidate_excluded_from_content_hash"] is True


# ── the load-bearing property: candidacy never re-identifies an episode ──
def test_adding_candidate_features_does_not_change_content_hash():
    bare = _ep()
    annotated = _ep(replace(ENTRY, candidate_features={"my_new_idea": 1.23}))
    assert annotated.content_hash() == bare.content_hash()


def test_changing_or_dropping_candidates_does_not_change_content_hash():
    a = _ep(replace(ENTRY, candidate_features={"x": 1.0}))
    b = _ep(replace(ENTRY, candidate_features={"x": 999.0, "y": 2.0, "z": 3.0}))
    c = _ep(replace(ENTRY, candidate_features={}))
    assert a.content_hash() == b.content_hash() == c.content_hash() == _ep().content_hash()


def test_canonical_geometry_still_does_change_the_hash():
    """Guard against the exclusion being over-broad — real entry fields must count."""
    a = _ep()
    b = _ep(replace(ENTRY, sl_price=97.0))
    assert a.content_hash() != b.content_hash()


# ── they must still be carried, just not identifying ─────────────────────
def test_candidate_features_survive_serialization_round_trip():
    feats = {"pressure_ratio": 0.42, "sweep_age": 7.0}
    ep = _ep(replace(ENTRY, candidate_features=feats))
    assert from_dict(to_dict(ep)).entry.candidate_features == feats


def test_candidate_features_survive_the_store(tmp_path):
    feats = {"experimental_a": -1.5}
    manifest = write_episodes([_ep(replace(ENTRY, candidate_features=feats))], tmp_path)
    back = list(read_episodes(manifest["path"]))
    assert back[0].entry.candidate_features == feats


def test_default_is_none_so_nothing_is_forced_to_carry_them():
    assert _ep().entry.candidate_features is None


def test_a_variable_length_namespace_needs_no_dimension_constant():
    """The structural fix for the 38->39 class: no count to assert, so none to drift."""
    for n in (0, 1, 5, 50):
        ep = _ep(replace(ENTRY, candidate_features={f"f{i}": float(i) for i in range(n)}))
        assert len(ep.entry.candidate_features) == n
        assert ep.content_hash() == _ep().content_hash()


# ── the frozen side is untouched ──────────────────────────────────────────
def test_production_canonical_contract_is_unchanged():
    from features.feature_schema import CANONICAL_FEATURE_DIM, CANONICAL_FEATURES

    assert CANONICAL_FEATURE_DIM == 39
    assert len(CANONICAL_FEATURES) == 39


def test_episodes_still_store_no_canonical_vector():
    """Features join by bar_index; episodes stay dimension-agnostic (substrate §7)."""
    assert _ep().entry.feature_vector is None
