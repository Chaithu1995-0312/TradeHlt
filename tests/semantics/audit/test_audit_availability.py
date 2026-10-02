# Phase 1 audit test. Authority: invariant I-6, concept_contracts.yaml MKT-E01 / MKT-E06 / MKT-L01 / MKT-Z02.

from __future__ import annotations

import numpy as np
import pytest

from semantics.identity import parameterization_id
from semantics.market.conditions import structural_position
from semantics.market.events import structure_breaks, sweep
from semantics.market.levels import Level, swing_levels
from semantics.market.zones import fvg_views
from semantics.types import LevelStatus, OhlcBar, Side


def _level(available_at):
    pid = parameterization_id("MKT-L01", {"founding": "swing_pivot", "k": 2}, ("founding", "k"))
    return Level("MKT-L01", 10.0, Side.UPPER, "swing_pivot", "M15", "bar_close", 0, available_at, pid,
                 status=LevelStatus.ACTIVE)


def test_no_sweep_against_a_level_with_available_at_in_the_future():
    level = _level(5)
    assert sweep(OhlcBar(10.2, 11.0, 9.0, 9.5, 4), level) is None
    assert sweep(OhlcBar(10.2, 11.0, 9.0, 9.5, 5), level) is not None


def test_swing_level_is_not_available_before_pivot_plus_k():
    rng = np.random.default_rng(11)
    n = 20
    close = 100.0 + np.cumsum(rng.normal(0.0, 0.4, n))
    high = close + 0.5
    low = close - 0.5
    levels = swing_levels(high, low, k=3)
    assert levels
    for level in levels:
        assert level.available_at == level.formed_at + 3


def test_fvg_is_not_available_before_the_close_of_bar_i_plus_1():
    bars = [
        OhlcBar(9.5, 10.0, 9.0, 9.6, 0),
        OhlcBar(10.2, 11.0, 10.0, 10.8, 1),
        OhlcBar(12.2, 12.6, 12.0, 12.4, 2),
    ]
    views = fvg_views(bars)
    assert views[1].present is False
    assert views[2].present is True and views[2].available_at == 2


def _walk(n, seed):
    rng = np.random.default_rng(seed)
    close = 100.0 + np.cumsum(rng.normal(0.0, 0.5, n))
    high = close + np.abs(rng.normal(0.4, 0.1, n))
    low = close - np.abs(rng.normal(0.4, 0.1, n))
    return high, low, close


def test_levels_conditions_and_events_are_prefix_invariant():
    high, low, close = _walk(30, 5)
    k = 3
    full_levels = swing_levels(high, low, k=k)
    full_pos = structural_position(high, low, close, k=k)
    full_events = structure_breaks(full_pos)
    for t in (6, 15, 29):
        prefix_levels = swing_levels(high[: t + 1], low[: t + 1], k=k)
        assert prefix_levels == [lv for lv in full_levels if lv.available_at <= t]
        prefix_pos = structural_position(high[: t + 1], low[: t + 1], close[: t + 1], k=k)
        assert prefix_pos.values == full_pos.values[: t + 1]
        assert structure_breaks(prefix_pos) == full_events[: t + 1]

def test_no_sweep_against_a_level_that_is_no_longer_active():
    # MKT-E01 rule: 'GP-04 on an ACTIVE, already-available MKT-L01.'
    level = _level(0)
    assert level.status is LevelStatus.ACTIVE
    swept = level.with_status(LevelStatus.SWEPT)
    assert sweep(OhlcBar(10.2, 11.0, 9.0, 9.5, 1), swept) is None
