"""Structural floor for configs/research/market_story_ontology.yaml.

Enforces the invariants that keep the semantic ontology mechanically honest and coupled to the real
executable substrate: the CRT-bridge rule, feature-name discipline (rejects the historical drift
names), valid CRT walks for active families, and well-formed engine bands.
"""
from __future__ import annotations

import pytest

from config_layer.state_identity import CRTState
from features.feature_schema import CANONICAL_FEATURES
from research.synthetic.ontology import StoryOntology, crt_path_is_legal, load_raw

_RAW = load_raw()
_ONTO = StoryOntology(_RAW)
_CANON = set(CANONICAL_FEATURES)
_CRT_NAMES = {s.name for s in CRTState}
_LAYER_IDS = {ly["id"] for ly in _RAW["layers"]}
_STATES = _RAW["market_states"]


def test_authority_is_descriptive_only():
    assert _RAW["authority"] == "user_approved"


def test_every_state_belongs_to_a_declared_layer():
    for st in _STATES:
        assert st["layer"] in _LAYER_IDS, st


def test_crt_bridge_rule_only_structure_states_map_to_crt():
    """Mechanical invariant: ONLY structure-layer states carry a crt_state_map; all others null."""
    for st in _STATES:
        if st["layer"] == "structure":
            assert st["crt_state_map"] in _CRT_NAMES, st
        else:
            assert st.get("crt_state_map") is None, st


def test_all_feature_signatures_are_canonical():
    for st in _STATES:
        for feat in st.get("feature_signature", []):
            assert feat in _CANON, f"{st['id']}: '{feat}' not in CANONICAL_FEATURES"


def test_family_key_features_are_canonical():
    for fam in _RAW["families"]:
        for feat in fam.get("key_features", []):
            assert feat in _CANON, f"{fam['id']}: '{feat}' not canonical"


def test_drift_names_are_rejected_everywhere():
    """The exact historical drift names must never appear (ema_long / displacement_strength / volatility)."""
    banned = {"ema_long", "displacement_strength", "volatility"}
    names = set()
    for st in _STATES:
        names.update(st.get("feature_signature", []))
    for fam in _RAW["families"]:
        names.update(fam.get("key_features", []))
    assert banned.isdisjoint(names), banned & names


def test_active_families_have_valid_crt_walk():
    structure = {st["id"]: st for st in _STATES if st["layer"] == "structure"}
    for fam in _RAW["families"]:
        if fam.get("status") != "active":
            continue
        seq = fam["canonical_state_sequence"]
        for sid in seq:
            assert sid in structure, f"{fam['id']}: state '{sid}' is not a structure state"
        crt_path = [structure[sid]["crt_state_map"] for sid in seq]
        legal, msg = crt_path_is_legal(crt_path)
        assert legal, f"{fam['id']}: illegal CRT walk — {msg}"


def test_four_active_families():
    active = [f for f in _RAW["families"] if f.get("status") == "active"]
    assert len(active) == 4
    assert len(_RAW["families"]) == 12  # 12 defined (room to grow)


def test_engine_bands_well_formed():
    bands = _RAW["engine_signature_bands"]
    for eng in ("crt", "gaussian", "zone"):
        assert bands[eng]["high"] > bands[eng]["low"]
    assert bands["rr"]["strong"] > bands["rr"]["weak"]


@pytest.mark.parametrize("bad_path", [["RANGE", "RETEST"], ["SWEEP", "RESOLUTION"]])
def test_crt_path_checker_rejects_illegal_edges(bad_path):
    legal, _ = crt_path_is_legal(bad_path)
    assert legal is False
