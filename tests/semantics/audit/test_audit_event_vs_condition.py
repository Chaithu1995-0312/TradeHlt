# Phase 1 audit test. Authority: invariant I-1, concept_contracts.yaml MKT-C01 / MKT-E02.

from __future__ import annotations

import pytest

from semantics.identity import parameterization_id
from semantics.market.conditions import (
    ConditionSeries,
    StructuralPosition,
    structural_position,
)
from semantics.market.events import structure_breaks


def _series(values):
    return ConditionSeries(
        "MKT-C01",
        parameterization_id("MKT-C01", {"k": 2}, ("k",)),
        tuple(values),
        parameters=(("k", 2),),
    )


def test_break_fires_on_the_onset_bar_only_while_the_position_persists():
    series = _series([None, StructuralPosition.INSIDE, StructuralPosition.ABOVE_LAST_SWING_HIGH,
                      StructuralPosition.ABOVE_LAST_SWING_HIGH, StructuralPosition.ABOVE_LAST_SWING_HIGH])
    events = structure_breaks(series)
    assert [i for i, e in enumerate(events) if e is not None] == [2]
    assert events[3] is None and events[4] is None
    assert series.values[3] is StructuralPosition.ABOVE_LAST_SWING_HIGH


def test_a_second_break_on_a_different_level_on_the_next_bar_is_legal():
    series = _series([None, StructuralPosition.INSIDE,
                      StructuralPosition.ABOVE_LAST_SWING_HIGH, StructuralPosition.BELOW_LAST_SWING_LOW])
    events = structure_breaks(series)
    assert [i for i, e in enumerate(events) if e is not None] == [2, 3]
    assert events[2].side.value == "UPPER"
    assert events[3].side.value == "LOWER"


def test_undefined_position_is_none_not_inside_and_not_zero():
    n = 8
    values = structural_position([10.0] * n, [9.0] * n, [9.5] * n, k=2)
    assert values.values[0] is None
    assert values.values[0] is not StructuralPosition.INSIDE
    assert values.values[5] is StructuralPosition.INSIDE


def test_once_per_level_is_proposed_and_refused():
    series = _series([None, StructuralPosition.ABOVE_LAST_SWING_HIGH])
    with pytest.raises(ValueError):
        structure_breaks(series, consumption="once_per_level")
