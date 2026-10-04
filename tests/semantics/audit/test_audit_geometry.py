# Phase 1 audit test. Authority: SEMANTIC_OS_V2_MEANING_PLANE.md section 4 and
# configs/formulas/concept_contracts.yaml GP-01..GP-07. Written from the contracts only.

from __future__ import annotations

import inspect

import pytest

import semantics.geometry as geo
from semantics.types import Bias, OhlcBar, Side

L = 10.0


def _bar(high, low, close, open_=None, index=0):
    if open_ is None:
        open_ = close
    return OhlcBar(open_, high, low, close, index)


def _mirror(bar):
    return OhlcBar(2 * L - bar.open, 2 * L - bar.low, 2 * L - bar.high, 2 * L - bar.close, bar.index)


UPPER_TABLE = [
    (10.0, 9.0, 9.0, False, False, False, False),
    (11.0, 9.0, 10.0, True, False, True, False),
    (11.0, 9.0, 9.0, True, False, False, True),
    (11.0, 9.0, 10.5, True, True, True, False),
    (11.0, 9.0, 11.0, True, True, True, False),
]


@pytest.mark.parametrize("high,low,close,w_pierce,w_beyond,w_reach,w_reject", UPPER_TABLE)
def test_upper_equality_table(high, low, close, w_pierce, w_beyond, w_reach, w_reject):
    bar = _bar(high, low, close)
    assert geo.pierce(bar, L, Side.UPPER) == w_pierce
    assert geo.beyond(bar, L, Side.UPPER) == w_beyond
    assert geo.reach(bar, L, Side.UPPER) == w_reach
    assert geo.pierce_and_reject(bar, L, Side.UPPER) == w_reject


@pytest.mark.parametrize("high,low,close,w_pierce,w_beyond,w_reach,w_reject", UPPER_TABLE)
def test_lower_mirrors_upper(high, low, close, w_pierce, w_beyond, w_reach, w_reject):
    m = _mirror(_bar(high, low, close))
    assert geo.pierce(m, L, Side.LOWER) == w_pierce
    assert geo.beyond(m, L, Side.LOWER) == w_beyond
    assert geo.reach(m, L, Side.LOWER) == w_reach
    assert geo.pierce_and_reject(m, L, Side.LOWER) == w_reject


def test_close_exactly_at_the_level():
    bar = _bar(11.0, 9.0, L)
    assert geo.beyond(bar, L, Side.UPPER) == False
    assert geo.reach(bar, L, Side.UPPER) == True
    assert geo.pierce_and_reject(bar, L, Side.UPPER) == False
    m = _mirror(bar)
    assert geo.beyond(m, L, Side.LOWER) == False
    assert geo.reach(m, L, Side.LOWER) == True
    assert geo.pierce_and_reject(m, L, Side.LOWER) == False


def test_high_exactly_at_the_level_is_not_a_pierce():
    assert geo.pierce(_bar(L, 9.0, 9.5), L, Side.UPPER) == False
    assert geo.pierce(_mirror(_bar(L, 9.0, 9.5)), L, Side.LOWER) == False


def test_zero_range_bar_at_the_level():
    bar = OhlcBar(L, L, L, L, 0)
    for side in (Side.UPPER, Side.LOWER):
        assert geo.pierce(bar, L, side) == False
        assert geo.beyond(bar, L, side) == False
        assert geo.reach(bar, L, side) == True
        assert geo.pierce_and_reject(bar, L, side) == False


def test_gap_bar_is_evaluated_as_given():
    upper = OhlcBar(12.2, 13.0, 12.0, 12.5, 0)
    assert geo.pierce(upper, L, Side.UPPER) == True
    assert geo.beyond(upper, L, Side.UPPER) == True
    assert geo.pierce_and_reject(upper, L, Side.UPPER) == False
    lower = OhlcBar(7.8, 8.0, 7.0, 7.5, 0)
    assert geo.pierce(lower, L, Side.LOWER) == True
    assert geo.beyond(lower, L, Side.LOWER) == True
    assert geo.pierce_and_reject(lower, L, Side.LOWER) == False


def test_no_hidden_epsilon():
    assert geo.pierce(OhlcBar(L, L + 1e-9, L - 1.0, L, 0), L, Side.UPPER) == True
    assert geo.beyond(OhlcBar(L, L + 1.0, L - 1.0, L + 1e-9, 0), L, Side.UPPER) == True


def test_overlap_edges_are_inclusive_and_mirror():
    bar = _bar(10.0, 8.0, 9.0)
    assert geo.overlap(bar, 10.0, 12.0) == True
    assert geo.overlap(bar, 10.0001, 12.0) == False
    m = _mirror(bar)
    assert geo.overlap(m, 8.0, 10.0) == True


def test_directional_impulse_mirrors_and_inherits_bias():
    bar = _bar(12.0, 9.0, 11.0, open_=10.0)
    m = _mirror(bar)
    assert geo.directional_impulse(bar, 9.5, Bias.LONG) == True
    assert geo.directional_impulse(bar, 9.5, Bias.LONG) == geo.directional_impulse(m, 2 * L - 9.5, Bias.SHORT)


def test_gp07_in_band_does_not_exist():
    assert not hasattr(geo, "in_band")
    funcs = {
        name
        for name, obj in inspect.getmembers(geo, inspect.isfunction)
        if getattr(obj, "__module__", "") == "semantics.geometry"
    }
    assert funcs == {
        "pierce",
        "beyond",
        "reach",
        "pierce_and_reject",
        "overlap",
        "directional_impulse",
    }