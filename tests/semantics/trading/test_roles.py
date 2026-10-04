"""TRS-02. ACHIEVED is inclusive (GP-03). INVALIDATED is strict (GP-02). The level is not written."""

from __future__ import annotations

import pytest

from semantics.market.levels import range_levels
from semantics.trading.roles import Invalidation, breach, objective_role
from semantics.types import Bias, LevelStatus, OhlcBar


def _range(high, low, *, formed=0, available=0):
    return range_levels(
        high, low, founding="parent_candle", formed_at=formed, available_at=available,
        timeframe="H4", clock="htf_period",
    )


def test_objective_achieved_is_inclusive_and_invalidated_is_strict():
    upper, lower = _range(110.0, 100.0)
    assert upper.status is LevelStatus.ACTIVE
    long_at_target = objective_role(upper, lower, Bias.LONG, 110.0, 5)
    assert long_at_target.status == "ACHIEVED"
    assert long_at_target.target == upper.price
    assert long_at_target.available_at >= 5
    assert objective_role(upper, lower, Bias.LONG, 100.0, 5).status == "EXISTS"
    assert objective_role(upper, lower, Bias.LONG, 99.9, 5).status == "INVALIDATED"
    short_at_target = objective_role(upper, lower, Bias.SHORT, 100.0, 5)
    assert short_at_target.status == "ACHIEVED"
    assert short_at_target.target == lower.price
    # The same upper level is the LONG objective and the SHORT invalidation edge.
    assert objective_role(upper, lower, Bias.SHORT, upper.price, 5).status == "EXISTS"
    assert objective_role(upper, lower, Bias.SHORT, upper.price + 0.1, 5).status == "INVALIDATED"
    assert upper.status is LevelStatus.ACTIVE
    assert lower.status is LevelStatus.ACTIVE


def test_one_level_is_the_long_objective_and_the_short_invalidation_edge():
    upper, lower = _range(110.0, 100.0)
    assert upper.status is LevelStatus.ACTIVE
    long_objective = objective_role(upper, lower, Bias.LONG, upper.price, 5)
    assert long_objective.status == "ACHIEVED"
    assert long_objective.level is upper
    invalidation = Invalidation("TRS-03", "pid", upper.available_at, 0.5, upper)
    beyond = OhlcBar(109.0, 112.0, 108.0, upper.price + 0.1, 6)
    assert breach(invalidation, beyond, Bias.SHORT) is not None
    on_the_level = OhlcBar(109.0, 112.0, 108.0, upper.price, 6)
    assert breach(invalidation, on_the_level, Bias.SHORT) is None
    assert upper.status is LevelStatus.ACTIVE
    assert long_objective.level.status is LevelStatus.ACTIVE


def test_objective_does_not_read_a_level_that_is_not_available_yet():
    upper, lower = _range(110.0, 100.0, formed=10, available=10)
    early = objective_role(upper, lower, Bias.LONG, 110.0, 5)
    assert early.status == "NONE"
    assert early.target is None
    assert early.available_at >= upper.available_at
    assert upper.status is LevelStatus.ACTIVE


def test_m15_objective_scope_is_not_bound():
    upper, lower = _range(110.0, 100.0)
    with pytest.raises(ValueError, match="PROPOSED"):
        objective_role(upper, lower, Bias.LONG, 105.0, 5, scope="m15")
