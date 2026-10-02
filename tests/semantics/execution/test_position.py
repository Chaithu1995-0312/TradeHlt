"""DEX-05/06/07. The resting exits are multi_tp_walk; rules close at the firing bar's close."""

from __future__ import annotations

import pytest

from research.oracle.multi_tp_walk import multi_tp_walk
from semantics.execution.position import (
    CLOSED, OPEN, PARTIAL, ExitReason, exit_rule, exit_schedule, replay_position,
)
from semantics.trading.thesis import ACTIVE, FAILED, mark_failed
from tests.semantics.execution._fixtures import ENTRY_BAR, ORIGIN, filled, path

_SCHEDULE = exit_schedule(0.5, 0.5, plan_bar=ENTRY_BAR)

STOP_PATH = ((108, 109, 106, 107), (107, 107.5, 97.0, 98.5))
TRAIL_PATH = ((108, 119, 107, 117), (117, 117.5, 112.0, 112.5))
TARGET_PATH = ((108, 119, 107, 117), (117, 129, 116, 128))


def _replay(rows, rule="hold", **kwargs):
    made, done = filled()
    bars = path(*rows)
    position = replay_position(made, done, _SCHEDULE, exit_rule(rule, plan_bar=ENTRY_BAR, ttl_bars=kwargs.pop("ttl", None)),
                               bars, **kwargs)
    return made, bars, position


@pytest.mark.parametrize("rows,reason", [
    (STOP_PATH, ExitReason.STOP), (TRAIL_PATH, ExitReason.TRAIL_STOP), (TARGET_PATH, ExitReason.TARGET_FINAL),
])
def test_hold_equals_multi_tp_walk(rows, reason):
    _made, bars, position = _replay(rows)
    walk = multi_tp_walk(108.0, "long", 98.0, 118.0, 128.0, bars, partial_fraction=0.5,
                         trail_fraction=0.5, max_forward=len(bars), entry_index=ENTRY_BAR)
    assert position.state == CLOSED and position.exit_reason is reason
    assert position.gross_r == walk.rr_gross
    assert position.exit_bar == bars[walk.duration_candles - 1].index


def test_close_on_invalidation_closes_at_the_breach_close_and_hold_keeps_it_open():
    rows = ((108, 109, 106, 106.5), (106.5, 107, 103.5, 104.0), (104, 106, 103.8, 105.5))
    made, bars, closed = _replay(rows, "close_on_invalidation")
    assert closed.exit_reason is ExitReason.INVALIDATION and closed.exit_bar == bars[1].index
    assert closed.gross_r == pytest.approx((104.0 - 108.0) / 10)
    _made, _bars, held = _replay(rows, "hold")
    assert held.state == OPEN and held.exit_reason is None and held.gross_r is None
    # the invalidation is recorded on the thesis (slice-2 code), whatever the rule
    assert made.thesis.status == ACTIVE
    assert mark_failed(made.thesis, bars[1]).status == FAILED


def test_close_on_origin_needs_a_close_beyond_the_origin_not_a_wick():
    wick = ((108, 109, 101.0, 103.0), (103, 104, 102.5, 103.5))
    _m, _b, open_position = _replay(wick, "close_on_origin", origin_price=ORIGIN)
    assert open_position.state == OPEN
    through = ((108, 109, 101.0, 103.0), (103, 104, 100.5, 101.5))
    _m, bars, closed = _replay(through, "close_on_origin", origin_price=ORIGIN)
    assert closed.exit_reason is ExitReason.ORIGIN and closed.exit_bar == bars[1].index
    with pytest.raises(ValueError, match="close_on_origin"):
        _replay(through, "close_on_origin")


def test_tp1_and_the_rule_on_one_bar_book_the_partial_then_close_the_runner():
    rows = ((110, 119, 100.0, 101.5),)
    _m, _b, position = _replay(rows, "close_on_origin", origin_price=ORIGIN)
    assert position.exit_reason is ExitReason.ORIGIN and position.reached_tp1
    assert position.gross_r == pytest.approx(0.5 * 1.0 + 0.5 * (101.5 - 108.0) / 10)


def test_a_resting_stop_on_the_firing_bar_wins():
    rows = ((108, 109, 97.0, 99.0),)   # stop touched and close below origin on the same bar
    _m, _b, position = _replay(rows, "close_on_origin", origin_price=ORIGIN)
    assert position.exit_reason is ExitReason.STOP and position.gross_r == pytest.approx(-1.0)


def test_the_earliest_rule_wins_and_ttl_closes_at_its_bar():
    rows = ((108, 109, 106, 107), (107, 108, 103.5, 104.0), (104, 105, 103, 104))
    _m, bars, by_ttl = _replay(rows, "close_on_invalidation", ttl=1)
    assert by_ttl.exit_reason is ExitReason.TIMEOUT and by_ttl.exit_bar == bars[0].index
    _m, bars, by_breach = _replay(rows, "close_on_invalidation", ttl=3)
    assert by_breach.exit_reason is ExitReason.INVALIDATION


def test_end_of_bars_leaves_the_position_open_or_partial():
    _m, _b, partial = _replay(((108, 119, 107, 117),))
    assert partial.state == PARTIAL and partial.reached_tp1 and partial.gross_r is None
    _m, _b, nothing = _replay(())
    assert nothing.state == OPEN


def test_every_rule_and_schedule_value_is_its_own_identity():
    ids = {exit_rule(v, plan_bar=0).parameterization_id for v in ("hold", "close_on_invalidation", "close_on_origin")}
    ids.add(exit_rule("hold", plan_bar=0, ttl_bars=5).parameterization_id)
    assert len(ids) == 4
    assert exit_schedule(0.5, 0.5, plan_bar=0).parameterization_id != exit_schedule(0.5, 0.0, plan_bar=0).parameterization_id
    with pytest.raises(ValueError, match="only 'after_resting_fills'"):
        exit_rule("hold", plan_bar=0, precedence="absolute")
    with pytest.raises(ValueError):
        exit_rule("close_on_stop", plan_bar=0)


def test_bars_at_or_before_the_fill_are_refused():
    made, done = filled()
    with pytest.raises(ValueError, match="I-6"):
        replay_position(made, done, _SCHEDULE, exit_rule("hold", plan_bar=ENTRY_BAR),
                        path((108, 109, 107, 108), start=ENTRY_BAR))


def test_availability_never_precedes_its_inputs():
    made, bars, position = _replay(TARGET_PATH)
    assert position.available_at >= position.fill.available_at >= made.available_at
    assert position.available_at == position.exit_bar
