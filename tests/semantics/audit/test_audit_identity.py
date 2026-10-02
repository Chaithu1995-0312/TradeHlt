# Phase 1 audit test. Authority: SEMANTIC_OS_V2_MEANING_PLANE.md section 5 (identity contract)
# and invariant I-17. Written from the contracts only.

from __future__ import annotations

import pytest

from semantics.identity import (
    InstanceKey,
    RepresentationIdentity,
    SemanticIdentity,
    instance_id,
    parameterization_id,
)


def test_window_is_identity_bearing_even_when_one_value_is_configured():
    five = parameterization_id("MKT-C04", {"window": 5}, ("window",))
    ten = parameterization_id("MKT-C04", {"window": 10}, ("window",))
    assert five != ten


def test_tie_rule_is_identity_bearing_strict_vs_inclusive():
    strict = parameterization_id("MKT-E01", {"founding": "swing_pivot", "tie": "strict"}, ("founding", "tie"))
    inclusive = parameterization_id("MKT-E01", {"founding": "swing_pivot", "tie": "inclusive"}, ("founding", "tie"))
    assert strict != inclusive


def test_non_identity_setting_change_keeps_the_id():
    a = parameterization_id("MKT-C04", {"window": 5, "note": "settings-hash-a"}, ("window",))
    b = parameterization_id("MKT-C04", {"window": 5, "note": "settings-hash-b"}, ("window",))
    assert a == b


def test_producer_changes_representation_id_but_never_instance_id():
    semantic = SemanticIdentity("MKT-E01", "EVENT", "MKT-L01 founding", "M15", "bar_close", "bar_close")
    param = parameterization_id("MKT-E01", {"founding": "swing_pivot", "tie": "strict"}, ("founding", "tie"))
    engine = RepresentationIdentity(semantic, param, "crt_engine", "object", "1")
    resolver = RepresentationIdentity(semantic, param, "crt_state_resolver", "object", "1")
    assert engine.id != resolver.id
    key = InstanceKey(anchor="5", side="UPPER")
    assert instance_id(semantic, param, key) == instance_id(semantic, param, key)


def test_missing_identity_bearing_parameter_raises_and_never_defaults():
    with pytest.raises(KeyError):
        parameterization_id("MKT-C01", {"window": 5}, ("k",))


def test_two_values_coexisting_are_two_representation_identities():
    semantic = SemanticIdentity("MKT-C04", "CONDITION", "MKT-E01 swing_pivot", "M15", "bar_close", "bar_close")
    p5 = parameterization_id("MKT-C04", {"k": 2, "window": 5}, ("k", "window"))
    p10 = parameterization_id("MKT-C04", {"k": 2, "window": 10}, ("k", "window"))
    assert p5 != p10
    r5 = RepresentationIdentity(semantic, p5, "feature_pipeline", "bool_int8", "6.0")
    r10 = RepresentationIdentity(semantic, p10, "feature_pipeline", "bool_int8", "6.0")
    assert r5.id != r10.id