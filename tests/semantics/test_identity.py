"""Parameterization identity: bearing values only. Producer is representation, not instance."""

from __future__ import annotations

import pytest

from semantics.identity import (
    InstanceKey,
    RepresentationIdentity,
    SemanticIdentity,
    instance_id,
    parameterization_id,
)


def test_window_is_identity_bearing():
    five = parameterization_id("MKT-C04", {"k": 2, "window": 5}, ("k", "window"))
    ten = parameterization_id("MKT-C04", {"k": 2, "window": 10}, ("k", "window"))
    assert five != ten


def test_non_identity_setting_does_not_change_the_id():
    base = parameterization_id(
        "MKT-C04", {"k": 2, "window": 5, "note": "left"}, ("k", "window"),
    )
    changed = parameterization_id(
        "MKT-C04", {"k": 2, "window": 5, "note": "right"}, ("k", "window"),
    )
    assert base == changed


def test_producer_changes_representation_id_not_instance_id():
    semantic = SemanticIdentity(
        "MKT-E01", "EVENT", "MKT-L01 founding", "M15", "bar_close", "bar_close",
    )
    param = parameterization_id(
        "MKT-E01", {"founding": "swing_pivot", "tie": "strict"}, ("founding", "tie"),
    )
    engine = RepresentationIdentity(semantic, param, "crt_engine", "object", "1")
    resolver = RepresentationIdentity(semantic, param, "crt_state_resolver", "object", "1")
    assert engine.id != resolver.id
    key = InstanceKey(anchor="5", side="UPPER")
    assert instance_id(semantic, param, key) == instance_id(semantic, param, key)


def test_missing_identity_bearing_parameter_raises():
    with pytest.raises(KeyError, match="k"):
        parameterization_id("MKT-C01", {"window": 5}, ("k",))
