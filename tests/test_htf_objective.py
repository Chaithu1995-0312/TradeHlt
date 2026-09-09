"""CH-htf-state-objective — ObjectiveStatus from C3 bias + C1 range."""

from __future__ import annotations

from config_layer.htf_state import (
    ObjectiveStatus,
    activation_allows,
    resolve_objective,
)
from config_layer.parent_crt import ParentRange
from config_layer.state_identity import Direction


def test_none_without_bias():
    rng = ParentRange(h_ref=110, l_ref=100, formed_at_index=0)
    obj = resolve_objective(Direction.NONE, rng, 105.0)
    assert obj.status is ObjectiveStatus.NONE
    assert obj.direction is Direction.NONE


def test_long_exists_inside_range():
    rng = ParentRange(h_ref=110, l_ref=100, formed_at_index=0)
    obj = resolve_objective(Direction.LONG, rng, 105.0)
    assert obj.status is ObjectiveStatus.EXISTS
    assert obj.target == 110
    assert obj.invalidate_at == 100


def test_long_achieved_at_or_above_href():
    rng = ParentRange(h_ref=110, l_ref=100, formed_at_index=0)
    assert resolve_objective(Direction.LONG, rng, 110.0).status is ObjectiveStatus.ACHIEVED
    assert resolve_objective(Direction.LONG, rng, 111.0).status is ObjectiveStatus.ACHIEVED


def test_long_invalidated_below_lref():
    rng = ParentRange(h_ref=110, l_ref=100, formed_at_index=0)
    assert resolve_objective(Direction.LONG, rng, 99.9).status is ObjectiveStatus.INVALIDATED


def test_short_exists_achieved_invalidated():
    rng = ParentRange(h_ref=110, l_ref=100, formed_at_index=0)
    assert resolve_objective(Direction.SHORT, rng, 105.0).status is ObjectiveStatus.EXISTS
    assert resolve_objective(Direction.SHORT, rng, 100.0).status is ObjectiveStatus.ACHIEVED
    assert resolve_objective(Direction.SHORT, rng, 110.1).status is ObjectiveStatus.INVALIDATED


def test_activation_allows_exists_only():
    assert activation_allows(ObjectiveStatus.EXISTS, "allow_exists_only") is True
    assert activation_allows(ObjectiveStatus.NONE, "allow_exists_only") is False
    assert activation_allows(ObjectiveStatus.ACHIEVED, "allow_exists_only") is False
    assert activation_allows(ObjectiveStatus.INVALIDATED, "allow_exists_only") is False
