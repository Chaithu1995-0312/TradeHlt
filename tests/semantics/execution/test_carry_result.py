"""DEX-08 carry (broker rollovers, triple swap, None when unmeasured) and DEX-09 result."""

from __future__ import annotations

from datetime import datetime

import pytest

from research.costs import UNKNOWN, ComponentCostModel
from semantics.execution.carry import carry
from semantics.execution.position import exit_rule, exit_schedule, replay_position
from semantics.execution.result import position_result
from tests.semantics.execution._fixtures import ENTRY_BAR, T0, bar, cost_model, filled, path, size

_SCHEDULE = exit_schedule(0.5, 0.5, plan_bar=ENTRY_BAR)
_HOLD = exit_rule("hold", plan_bar=ENTRY_BAR)


def _position(bars):
    made, done = filled()
    return made, replay_position(made, done, _SCHEDULE, _HOLD, bars)


def _weekend_stop():
    # Friday 21:00 bar, then Monday bars; the stop fills on Monday.
    return [
        bar(9, 108, 109, 106, 107, datetime(2026, 9, 25, 21, 0)),
        bar(10, 107, 107.5, 97.0, 98.5, datetime(2026, 9, 28, 1, 0)),
    ]


def test_a_weekend_is_one_rollover_when_only_monday_has_bars():
    _m, position = _position(_weekend_stop())
    got = carry(cost_model(), position, fill_timestamp=T0, held_bars=_weekend_stop(), triple_swap_weekday=2)
    assert (got.nights, got.weighted_nights) == (1, 1)
    assert got.carry_price == pytest.approx(0.5)
    assert got.carry_r == pytest.approx(0.05) and got.available_at == position.exit_bar


def test_the_triple_swap_weekday_counts_three():
    _m, position = _position(_weekend_stop())
    got = carry(cost_model(), position, fill_timestamp=T0, held_bars=_weekend_stop(), triple_swap_weekday=0)
    assert got.weighted_nights == 3 and got.carry_price == pytest.approx(1.5)


def test_unmeasured_swap_or_weekday_is_none_never_zero():
    _m, position = _position(_weekend_stop())
    assert carry(cost_model(), position, fill_timestamp=T0, held_bars=_weekend_stop(), triple_swap_weekday=None) is None
    assert carry(cost_model(swap_long=None), position, fill_timestamp=T0, held_bars=_weekend_stop(),
                 triple_swap_weekday=2) is None


def test_a_same_day_exit_is_a_real_zero_and_a_credit_adds_nothing():
    rows = ((108, 109, 106, 107), (107, 107.5, 97.0, 98.5))
    bars = path(*rows)
    _m, position = _position(bars)
    zero = carry(cost_model(), position, fill_timestamp=T0, held_bars=bars, triple_swap_weekday=None)
    assert (zero.nights, zero.carry_price) == (0, 0.0)
    _m, weekend = _position(_weekend_stop())
    credit = carry(cost_model(swap_long=0.3), weekend, fill_timestamp=T0, held_bars=_weekend_stop(), triple_swap_weekday=2)
    assert credit.carry_price == 0.0


def test_net_subtracts_the_actual_exit_cost_and_carry():
    made, position = _position(_weekend_stop())
    model = cost_model()
    got_carry = carry(model, position, fill_timestamp=T0, held_bars=_weekend_stop(), triple_swap_weekday=2)
    result = position_result(position, size(made), basis="net", cost_model=model, carry=got_carry)
    stop_cost = model.cost_r(108.0, 10.0, exit_kind="SL_HIT", direction="long")
    assert result.gross_r == position.gross_r == pytest.approx(-1.0)
    assert result.net_r == pytest.approx(-1.0 - stop_cost - got_carry.carry_r)
    assert result.cost.cost_r == pytest.approx(stop_cost)


def test_a_target_exit_charges_no_stop_slippage():
    bars = path((108, 119, 107, 117), (117, 129, 116, 128))
    made, position = _position(bars)
    model = cost_model()
    zero = carry(model, position, fill_timestamp=T0, held_bars=bars, triple_swap_weekday=None)
    result = position_result(position, size(made), basis="net", cost_model=model, carry=zero)
    assert result.cost.cost_r == pytest.approx(model.cost_r(108.0, 10.0, exit_kind="TP_HIT", direction="long"))
    assert result.cost.cost_r < model.cost_r(108.0, 10.0, exit_kind="SL_HIT", direction="long")


def test_net_without_carry_is_none_and_gross_refuses_a_cost():
    made, position = _position(_weekend_stop())
    assert position_result(position, size(made), basis="net", cost_model=cost_model(), carry=None).net_r is None
    with pytest.raises(ValueError, match="I-15"):
        position_result(position, size(made), basis="gross", cost_model=cost_model())
    with pytest.raises(ValueError, match="I-15"):
        position_result(position, size(made), basis="net")


def test_an_open_position_has_no_result_and_unknown_cost_raises():
    made, open_position = _position(path((108, 109, 107, 108)))
    assert position_result(open_position, size(made), basis="gross") is None
    _m, closed = _position(_weekend_stop())
    unknown = ComponentCostModel(0.05, 0.04, 0.0, 0.09, -0.5, -0.4, "XAUUSD", "SYNTHETIC", UNKNOWN)
    with pytest.raises(ValueError, match="UNKNOWN"):
        position_result(closed, size(made), basis="net", cost_model=unknown, carry=None)


def test_identity_names_basis_source_size_schedule_and_rule():
    made, position = _position(_weekend_stop())
    gross = position_result(position, size(made), basis="gross")
    other_size = position_result(position, size(made, risk_fraction=0.02), basis="gross")
    a = position_result(position, size(made), basis="net", cost_model=cost_model(source="A"))
    b = position_result(position, size(made), basis="net", cost_model=cost_model(source="B"))
    assert len({gross.parameterization_id, other_size.parameterization_id,
                a.parameterization_id, b.parameterization_id}) == 4
    with pytest.raises(ValueError, match="one calibration"):
        position_result(position, size(made), basis="net", cost_model=cost_model(source="A"),
                        carry=carry(cost_model(source="B"), position, fill_timestamp=T0,
                                    held_bars=_weekend_stop(), triple_swap_weekday=2))
