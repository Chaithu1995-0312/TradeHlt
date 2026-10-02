"""GP-01..GP-06 equality table. Absence of a predicate is False, never a sentinel."""

from __future__ import annotations

import pytest

from semantics.geometry import beyond, directional_impulse, overlap, pierce, pierce_and_reject, reach
from semantics.types import Bias, OhlcBar, Side
from structure import predicates as sp


def _bar(high: float, low: float, close: float, open_: float | None = None, index: int = 0) -> OhlcBar:
    if open_ is None:
        open_ = close
    return OhlcBar(open_, high, low, close, index)


@pytest.mark.parametrize(
    "side,level,high,low,close,want_pierce,want_beyond,want_reach,want_reject",
    [
        # high == L is not a pierce. close == L is reach, not beyond, not GP-04.
        (Side.UPPER, 10.0, 10.0, 9.0, 9.0, False, False, False, False),
        (Side.UPPER, 10.0, 11.0, 9.0, 10.0, True, False, True, False),
        (Side.UPPER, 10.0, 11.0, 9.0, 9.0, True, False, False, True),
        (Side.UPPER, 10.0, 11.0, 9.0, 10.5, True, True, True, False),
        # LOWER mirror: low == L is not a pierce; close == L is reach.
        (Side.LOWER, 10.0, 11.0, 10.0, 11.0, False, False, False, False),
        (Side.LOWER, 10.0, 11.0, 9.0, 10.0, True, False, True, False),
        (Side.LOWER, 10.0, 11.0, 9.0, 10.5, True, False, False, True),
        (Side.LOWER, 10.0, 11.0, 9.0, 9.5, True, True, True, False),
    ],
)
def test_equality_table(side, level, high, low, close, want_pierce, want_beyond, want_reach, want_reject):
    bar = _bar(high, low, close)
    assert pierce(bar, level, side) is want_pierce
    assert beyond(bar, level, side) is want_beyond
    assert reach(bar, level, side) is want_reach
    assert pierce_and_reject(bar, level, side) is want_reject


def test_zero_range_bar_at_the_level():
    """A bar whose open, high, low and close are all L is at the level."""
    level = 10.0
    bar = _bar(level, level, level, level)
    for side in (Side.UPPER, Side.LOWER):
        assert pierce(bar, level, side) is False
        assert beyond(bar, level, side) is False
        assert reach(bar, level, side) is True
        assert pierce_and_reject(bar, level, side) is False


def test_gap_bar_is_evaluated_as_given():
    """A gap that opens and closes beyond L is pierce + beyond + reach, and not a rejection."""
    upper = _bar(high=13.0, low=12.0, close=12.5, open_=12.2)
    assert pierce(upper, 10.0, Side.UPPER) is True
    assert beyond(upper, 10.0, Side.UPPER) is True
    assert reach(upper, 10.0, Side.UPPER) is True
    assert pierce_and_reject(upper, 10.0, Side.UPPER) is False

    lower = _bar(high=8.0, low=7.0, close=7.5, open_=7.8)
    assert pierce(lower, 10.0, Side.LOWER) is True
    assert beyond(lower, 10.0, Side.LOWER) is True
    assert reach(lower, 10.0, Side.LOWER) is True
    assert pierce_and_reject(lower, 10.0, Side.LOWER) is False


def test_overlap_includes_a_shared_edge():
    bar = _bar(high=10.0, low=8.0, close=9.0)
    assert overlap(bar, 10.0, 12.0) is True
    assert overlap(bar, 10.5, 12.0) is False
    with pytest.raises(ValueError):
        overlap(bar, 12.0, 10.0)


def test_directional_impulse_delegates():
    bar = _bar(high=12.0, low=9.0, close=11.0, open_=10.0)
    assert directional_impulse(bar, 9.5, Bias.LONG) is sp.directional_impulse(
        bar.open, bar.close, 9.5, is_long=True,
    )
    assert directional_impulse(bar, 11.5, Bias.SHORT) is sp.directional_impulse(
        bar.open, bar.close, 11.5, is_long=False,
    )
