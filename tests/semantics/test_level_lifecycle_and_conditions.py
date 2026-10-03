"""MKT-L01 lifecycle walk (events.level_lifecycle) and the MKT-C03 / MKT-C06 implementations."""

from __future__ import annotations

import pandas as pd
import pytest

from semantics.market.conditions import momentum_bias, session
from semantics.market.events import level_lifecycle
from semantics.market.levels import Level
from semantics.types import LevelStatus, OhlcBar, Side


def _level(price, side, available_at):
    return Level("MKT-L01", price, side, "swing_pivot", "M15", "bar_close", available_at, available_at, "pid")


def _bars(*ohlc):
    return [OhlcBar(o, h, l, c, i) for i, (o, h, l, c) in enumerate(ohlc)]


def test_a_swept_level_is_consumed_and_not_swept_again():
    up = _level(110.0, Side.UPPER, 0)
    life = level_lifecycle([up], _bars((100, 111, 99, 105), (105, 112, 104, 106)))
    assert [len(e) for e in life.events] == [1, 0]
    assert life.ended[0] == (LevelStatus.SWEPT, 0)
    assert life.status_before(0, 1) is LevelStatus.SWEPT and life.status_before(0, 0) is LevelStatus.ACTIVE


def test_a_close_beyond_breaks_the_level_and_unavailable_levels_wait():
    up = _level(110.0, Side.UPPER, 0)
    late = _level(90.0, Side.LOWER, 2)
    life = level_lifecycle([up, late], _bars((100, 111, 99, 111), (100, 101, 89, 95), (95, 96, 89, 92)))
    assert life.ended[0] == (LevelStatus.BROKEN, 0) and life.events[0] == ()
    assert life.events[1] == ()                    # 90 not yet available on bar 1
    assert life.ended[1] == (LevelStatus.SWEPT, 2) and life.events[2][0].side is Side.LOWER


def test_two_levels_on_one_bar_are_two_events():
    life = level_lifecycle([_level(110.0, Side.UPPER, 0), _level(90.0, Side.LOWER, 0)],
                           _bars((100, 111, 89, 100)))
    assert sorted(e.side.value for e in life.events[0]) == ["LOWER", "UPPER"]


def test_level_lifecycle_requires_positional_indices():
    with pytest.raises(ValueError):
        level_lifecycle([], [OhlcBar(1, 1, 1, 1, 5)])


def test_two_sided_sweep_counts_one_bar_that_sweeps_both_sides():
    from semantics.market.conditions import two_sided_sweep

    # k=2: swing high 110 (bar 3, available 5), swing low 95 (bar 6, available 8); bar 9 sweeps both
    ohlc = [(100, 101, 99, 100), (100, 102, 99, 101), (101, 104, 100, 103), (103, 110, 102, 108),
            (108, 109, 104, 105), (105, 106, 97, 98), (98, 99, 95, 96), (96, 100, 96, 99),
            (99, 103, 97, 102), (100, 111, 94, 100)]
    _o, h, l, c = zip(*ohlc)
    vals = two_sided_sweep(h, l, c, k=2, window=5).values
    assert vals[:6] == (None,) * 6         # no level available as of bar i-1 before bar 6
    assert vals[8] is False and vals[9] is True


def test_momentum_bias_is_the_ema_sign():
    rising = momentum_bias([float(x) for x in range(1, 40)], fast=9, slow=21).values
    falling = momentum_bias([float(x) for x in range(40, 1, -1)], fast=9, slow=21).values
    assert rising[0] == 0 and set(rising[1:]) == {1} and set(falling[1:]) == {-1}


def test_session_depends_on_the_declared_clock():
    windows = {"ASIA": [0, 9], "LONDON": [7, 16], "NEWYORK": [12, 21]}
    ts = ["2026-07-06 22:00:00"]            # broker 22:00 (CLOSED) = 19:00 UTC (NEWYORK), summer UTC+3
    broker = session(ts, basis="broker_local", windows=windows)
    utc = session(ts, basis="utc_corrected", windows=windows)
    assert broker.values != utc.values and broker.parameterization_id != utc.parameterization_id
    with pytest.raises(ValueError):
        session(ts, basis="local", windows=windows)
    assert len(session(pd.Series(ts * 3), basis="broker_local", windows=windows).values) == 3
