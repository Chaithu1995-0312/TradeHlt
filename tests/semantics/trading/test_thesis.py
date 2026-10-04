"""TRS-01. The expected level comes from the market authorities, not a second formula."""

from __future__ import annotations

from semantics.market.levels import extension, range_levels
from semantics.trading.thesis import ACTIVE, EXPIRED, FAILED, SPENT, form_thesis, mark_expired, mark_failed, mark_spent
from semantics.types import Bias, LevelStatus, OhlcBar


def _bar(index, open_, high, low, close):
    return OhlcBar(open_, high, low, close, index)


def _lower():
    _upper, lower = range_levels(
        120.0, 100.0, founding="m15_structural_range", formed_at=0, available_at=0,
        timeframe="M15", clock="htf_period",
    )
    return lower


def _sweep_bar():
    # GP-04 on a LOWER level at 100: low pierces, close rejects back above.
    return _bar(2, 103.0, 104.0, 99.0, 102.0)


def _displacement():
    # GP-06 LONG: close above open and above the sweep price.
    return _bar(5, 102.0, 112.0, 101.0, 110.0)


def _thesis():
    thesis = form_thesis(
        _sweep_bar(), _lower(), _displacement(),
        retrace_fraction=0.5, extension_fib=1.618, clock="htf_period",
    )
    assert thesis is not None
    return thesis


def test_no_displacement_is_no_thesis():
    bearish = _bar(5, 110.0, 112.0, 104.0, 105.0)
    assert form_thesis(
        _sweep_bar(), _lower(), bearish,
        retrace_fraction=0.5, extension_fib=1.618, clock="htf_period",
    ) is None
    inside = _bar(5, 102.0, 106.0, 100.5, 101.0)
    assert form_thesis(
        _sweep_bar(), _lower(), inside,
        retrace_fraction=0.5, extension_fib=1.618, clock="htf_period",
    ) is None


def test_thesis_is_born_on_the_displacement_bar():
    thesis = _thesis()
    assert thesis.born_at == 5
    assert thesis.sweep_bar == 2
    assert thesis.born_at != thesis.sweep_bar
    assert thesis.available_at == thesis.born_at
    assert thesis.available_at >= thesis.sweep_bar
    assert thesis.direction is Bias.LONG
    assert thesis.status == ACTIVE
    assert thesis.invalidation is not None
    assert thesis.invalidation.available_at == thesis.born_at


def test_failed_on_retrace_breach_and_not_on_the_level():
    thesis = _thesis()
    level = thesis.invalidation.level
    assert level.status is LevelStatus.ACTIVE
    at_level = _bar(6, level.price, level.price + 1.0, level.price - 1.0, level.price)
    assert mark_failed(thesis, at_level) is thesis
    breach = _bar(6, level.price, level.price, level.price - 1.0, level.price - 0.1)
    failed = mark_failed(thesis, breach)
    assert failed.status == FAILED
    assert failed.terminal_at == 6
    assert failed.available_at >= breach.index
    assert failed.invalidation.level.status is LevelStatus.ACTIVE
    assert not hasattr(failed, "position")
    assert mark_spent(failed, _bar(7, 110.0, 130.0, 109.0, 120.0)).status == FAILED
    assert mark_expired(failed, ["p1"] * 6 + ["p2"]).status == FAILED


def test_spent_on_extension_reach_including_equality():
    thesis = _thesis()
    level = extension(
        thesis.move_start, thesis.move_end, thesis.extension_fib,
        anchor="displacement", formed_at=thesis.born_at, available_at=thesis.born_at,
    )
    short = _bar(7, 110.0, level.price, 109.0, level.price - 0.01)
    assert mark_spent(thesis, short) is thesis
    reached = _bar(7, 110.0, level.price + 1.0, 109.0, level.price)
    spent = mark_spent(thesis, reached)
    assert spent.status == SPENT
    assert spent.terminal_at == 7
    assert spent.available_at >= reached.index


def test_expired_on_clock_rollover_at_or_after_birth():
    thesis = _thesis()
    early = mark_expired(thesis, ["p0", "p1", "p1", "p1", "p1", "p1", "p1"])
    assert early is thesis
    expired = mark_expired(thesis, ["p1"] * 6 + ["p2"])
    assert expired.status == EXPIRED
    assert expired.terminal_at == 6
    assert expired.available_at >= 6
