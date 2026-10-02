"""MKT-E02 fires once per onset. MKT-E01 is a strict tie and refuses a future level."""

from __future__ import annotations

import numpy as np
import pytest

from semantics.identity import parameterization_id
from semantics.market.conditions import (
    StructuralPosition,
    two_sided_sweep,
    structural_position,
)
from semantics.market.events import (
    extension_reach,
    retrace_breach,
    structure_breaks,
    sweep,
    zone_touch,
    zone_touches,
)
from semantics.market.levels import Level, extension, retracement
from semantics.types import Bias, LevelStatus, OhlcBar, Side

# First 40 bars of the frozen XAUUSD M15 book, 2024-05-22 01:00 through 10:45.
# Copied into the test so it does not open the corpus.
_XAU_HL_C = (
    (2421.93, 2420.9, 2421.21), (2421.98, 2421.17, 2421.37), (2422.29, 2421.29, 2421.63),
    (2422.32, 2421.22, 2422.05), (2422.05, 2421.47, 2421.57), (2421.87, 2421.47, 2421.7),
    (2422.2, 2421.33, 2421.98), (2422.25, 2421.39, 2421.79), (2423.11, 2421.64, 2421.91),
    (2423.2, 2421.91, 2422.35), (2422.92, 2420.79, 2421.75), (2422.43, 2420.46, 2420.6),
    (2423.03, 2419.93, 2422.17), (2423.4, 2421.11, 2421.52), (2421.52, 2419.39, 2419.94),
    (2422.87, 2419.83, 2422.04), (2426.54, 2422.02, 2425.51), (2425.94, 2423.82, 2424.17),
    (2424.73, 2420.67, 2421.96), (2421.96, 2416.0, 2417.85), (2419.6, 2417.36, 2419.11),
    (2419.52, 2417.46, 2418.78), (2419.11, 2415.75, 2416.33), (2416.48, 2412.64, 2414.22),
    (2414.94, 2412.36, 2412.93), (2416.08, 2412.48, 2415.76), (2416.18, 2413.13, 2413.15),
    (2413.9, 2412.19, 2412.93), (2414.23, 2412.52, 2413.26), (2415.23, 2411.6, 2413.85),
    (2414.41, 2411.91, 2413.34), (2417.45, 2412.39, 2417.16), (2417.95, 2415.57, 2415.6),
    (2416.32, 2413.79, 2414.15), (2417.09, 2413.99, 2415.97), (2418.14, 2415.25, 2417.14),
    (2417.39, 2415.32, 2417.14), (2418.49, 2412.84, 2412.97), (2416.98, 2412.35, 2416.6),
    (2418.21, 2416.07, 2417.31),
)


def _onsets(values) -> list[int]:
    prev = None
    hits = []
    for i, value in enumerate(values):
        if value is not None and value is not StructuralPosition.INSIDE and value != prev:
            hits.append(i)
        prev = value
    return hits


def _assert_onset_once(position) -> None:
    events = structure_breaks(position)
    fired = [i for i, event in enumerate(events) if event is not None]
    assert fired == _onsets(position.values)
    prev = None
    for i, value in enumerate(position.values):
        if events[i] is not None:
            assert value in (
                StructuralPosition.ABOVE_LAST_SWING_HIGH,
                StructuralPosition.BELOW_LAST_SWING_LOW,
            )
            assert value != prev
        elif value is not None and value is not StructuralPosition.INSIDE and value == prev:
            assert events[i] is None
        prev = value


def test_fixed_position_path_fires_on_each_onset_only():
    values = (
        None,
        StructuralPosition.INSIDE,
        StructuralPosition.ABOVE_LAST_SWING_HIGH,
        StructuralPosition.ABOVE_LAST_SWING_HIGH,
        StructuralPosition.INSIDE,
        StructuralPosition.ABOVE_LAST_SWING_HIGH,
        StructuralPosition.BELOW_LAST_SWING_LOW,
        StructuralPosition.BELOW_LAST_SWING_LOW,
    )
    from semantics.market.conditions import ConditionSeries

    series = ConditionSeries(
        "MKT-C01",
        parameterization_id("MKT-C01", {"k": 2}, ("k",)),
        values,
        parameters=(("k", 2),),
    )
    events = structure_breaks(series)
    assert [i for i, event in enumerate(events) if event is not None] == [2, 5, 6]
    assert events[2].side is Side.UPPER
    assert events[6].side is Side.LOWER
    assert events[3] is None and events[7] is None


def test_structure_break_property_on_generated_paths():
    rng = np.random.default_rng(20261002)
    for n, k in ((40, 2), (60, 3), (25, 5)):
        close = 100.0 + np.cumsum(rng.normal(0.0, 0.4, n))
        spread = np.abs(rng.normal(0.3, 0.1, n))
        high = close + spread
        low = close - spread
        _assert_onset_once(structural_position(high, low, close, k=k))


def test_structure_break_property_on_xauusd_prefix():
    """A real XAUUSD M15 prefix, not a constructed walk."""
    highs = [row[0] for row in _XAU_HL_C]
    lows = [row[1] for row in _XAU_HL_C]
    closes = [row[2] for row in _XAU_HL_C]
    position = structural_position(highs, lows, closes, k=5)
    assert position.values[0] is None
    _assert_onset_once(position)


def _level(price: float, side: Side, available_at: int) -> Level:
    pid = parameterization_id("MKT-L01", {"founding": "swing_pivot", "k": 2}, ("founding", "k"))
    return Level(
        "MKT-L01", price, side, "swing_pivot", "M15", "bar_close",
        0, available_at, pid, status=LevelStatus.ACTIVE,
    )


def test_sweep_strict_tie():
    level = _level(10.0, Side.UPPER, 0)
    # close == L is at the level: pierced, not rejected.
    at_level = OhlcBar(10.0, 11.0, 9.0, 10.0, 0)
    assert sweep(at_level, level) is None
    # high == L is not a pierce.
    touch = OhlcBar(9.5, 10.0, 9.0, 9.5, 0)
    assert sweep(touch, level) is None
    rejected = OhlcBar(10.2, 11.0, 9.0, 9.5, 0)
    event = sweep(rejected, level)
    assert event is not None
    assert event.implied_bias is Bias.SHORT
    assert event.side is Side.UPPER

    lower = _level(10.0, Side.LOWER, 0)
    long_sweep = sweep(OhlcBar(10.5, 11.0, 9.0, 10.5, 1), lower)
    assert long_sweep is not None and long_sweep.implied_bias is Bias.LONG


def test_no_sweep_of_a_level_that_is_not_yet_available():
    level = _level(10.0, Side.UPPER, available_at=5)
    bar = OhlcBar(10.2, 11.0, 9.0, 9.5, 4)
    assert sweep(bar, level) is None
    later = OhlcBar(10.2, 11.0, 9.0, 9.5, 5)
    assert sweep(later, level) is not None


@pytest.mark.parametrize("status", [LevelStatus.SWEPT, LevelStatus.BROKEN, LevelStatus.EXPIRED])
def test_only_an_active_level_can_be_swept(status):
    # MKT-E01 rule: "GP-04 on an ACTIVE, already-available MKT-L01."
    bar = OhlcBar(10.2, 11.0, 9.0, 9.5, 1)
    assert sweep(bar, _level(10.0, Side.UPPER, 0)) is not None
    assert sweep(bar, _level(10.0, Side.UPPER, 0).with_status(status)) is None


def test_zone_touch_is_the_first_overlapping_bar_only():
    # MKT-E06: "The first bar after a zone becomes available whose range overlaps it."
    bars = [OhlcBar(9.0, 9.5, 8.5, 9.0, i) for i in range(2)] + [
        OhlcBar(10.5, 11.0, 10.2, 10.6, 2),   # overlaps [10, 11]: the touch
        OhlcBar(10.5, 10.9, 10.1, 10.4, 3),   # overlaps again: not a second MKT-E06
    ]
    events = zone_touches(bars, zone_low=10.0, zone_high=11.0, available_at=0, reference="z")
    assert [e.bar if e else None for e in events] == [None, None, 2, None]
    assert zone_touch(bars[3], zone_low=10.0, zone_high=11.0, available_at=0, reference="z",
                      already_touched=True) is None


def test_retrace_and_extension_use_their_own_parameterization():
    retr = retracement(10.0, 12.0, 0.5, anchor="move-1", formed_at=0, available_at=0)
    ext = extension(10.0, 12.0, 1.618, anchor="move-1", formed_at=0, available_at=0)
    breach = retrace_breach(OhlcBar(11.2, 11.2, 10.5, 10.8, 1), retr, Bias.LONG)
    reached = extension_reach(OhlcBar(13.4, 14.0, 13.0, 13.4, 1), ext, Bias.LONG)
    assert breach is not None and breach.parameterization_id != retr.parameterization_id
    assert reached is not None and reached.parameterization_id != ext.parameterization_id
    assert breach.parameterization_id == parameterization_id("MKT-E10", {}, ())
    assert reached.parameterization_id == parameterization_id("MKT-E11", {}, ())


def test_two_sided_sweep_is_absent_until_a_reference_exists():
    n = 6
    series = two_sided_sweep([10.0] * n, [9.0] * n, [9.5] * n, k=3, window=5)
    assert series.values[0] is None
    assert all(value is None for value in series.values)
