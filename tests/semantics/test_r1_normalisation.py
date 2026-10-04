"""Integration run 1 normalisations (SEMANTIC_OS_V2_MEANING_PLANE.md §16).

R1-A: MKT-E01 carries sweep_extreme (the wick); the thesis move starts there.
R1-B: a clock rollover expires a thesis only before its episode is EXTENDED.
"""

from __future__ import annotations

from semantics.market.events import sweep
from semantics.market.levels import range_levels
from semantics.trading.thesis import ACTIVE, EXPIRED, form_thesis, mark_expired
from semantics.types import OhlcBar


def _edges():
    return range_levels(120.0, 100.0, founding="m15_structural_range", formed_at=0, available_at=0,
                        timeframe="M15", clock="htf_period")


def test_r1a_sweep_carries_its_extreme_on_each_side():
    upper, lower = _edges()
    low_sweep = sweep(OhlcBar(103.0, 104.0, 99.0, 102.0, 2), lower)
    high_sweep = sweep(OhlcBar(118.0, 121.5, 117.0, 119.0, 2), upper)
    assert (low_sweep.reference_price, low_sweep.extreme) == (100.0, 99.0)
    assert (high_sweep.reference_price, high_sweep.extreme) == (120.0, 121.5)


def test_r1a_thesis_move_and_invalidation_start_at_the_wick():
    _upper, lower = _edges()
    thesis = form_thesis(OhlcBar(103.0, 104.0, 99.0, 102.0, 2), lower, OhlcBar(102.0, 112.0, 101.0, 110.0, 5),
                         retrace_fraction=0.5, extension_fib=1.618, clock="htf_period")
    assert thesis.move_start == 99.0
    assert thesis.invalidation.level.price == 104.5


def _thesis():
    _upper, lower = _edges()
    return form_thesis(OhlcBar(103.0, 104.0, 99.0, 102.0, 2), lower, OhlcBar(102.0, 112.0, 101.0, 110.0, 5),
                       retrace_fraction=0.5, extension_fib=1.618, clock="htf_period")


def test_r1b_rollover_expires_only_before_extension():
    clocks = ["H1"] * 8 + ["H2"] * 4            # rollover at bar 8; thesis born at bar 5
    expired = mark_expired(_thesis(), clocks)
    assert (expired.status, expired.terminal_at) == (EXPIRED, 8)
    assert mark_expired(_thesis(), clocks, extended_at=9).status == EXPIRED      # extended after the flip
    survived = mark_expired(_thesis(), clocks, extended_at=7)                     # extended before the flip
    assert survived.status == ACTIVE
