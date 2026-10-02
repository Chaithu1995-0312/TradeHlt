"""TRS-04 entry, TRS-07 cost, TRS-08 outcome."""

from __future__ import annotations

from datetime import datetime

import pytest

from research.costs import UNKNOWN, MEASURED, ComponentCostModel, CostModel
from research.measurement.forward_walk import AdverseFill, forward_walk
from research.contracts import Signal
from research.oracle.multi_tp_walk import multi_tp_walk
from semantics.market.events import MarketEvent
from semantics.trading.cost import component_cost, flat_cost
from semantics.trading.entry import APPROVAL_BAR_LEGACY, LEGACY_DIVERGENCE, RESTING_ORDER, legacy_entry, resting_entry
from semantics.trading.outcome import measure_outcome
from semantics.trading.target import Target
from semantics.types import Bias, OhlcBar


def _bar(index, open_, high, low, close):
    return OhlcBar(open_, high, low, close, index)


def _target(ordinal, price, *, intent=None, policy=None):
    return Target("TRS-06", f"pid-{ordinal}", 1, price, ordinal, 2.0, policy, intent)


def _component(status):
    return ComponentCostModel(
        half_spread=0.045, commission=0.04, entry_slippage=0.0, stop_slippage=0.09,
        swap_long_per_night=None, swap_short_per_night=None,
        instrument="XAUUSD", source="SYNTHETIC", status=status,
    )


def _measure(**overrides):
    future = [_bar(2, 100.0, 120.0, 95.0, 110.0)]
    args = dict(
        walk="forward_walk", basis="gross", cost_model=None, cost_source=None, walk_params={},
        entry=100.0, stop=90.0, targets=(_target(1, 120.0, intent="reversal"), _target(2, 130.0, policy="fixed_r")),
        direction=Bias.LONG, future=future, instrument="XAUUSD",
        timestamp=datetime(2024, 1, 1), entry_index=1, plan_bar=1,
    )
    args.update(overrides)
    return measure_outcome(**args)


def test_resting_order_and_legacy_entry():
    retest = _bar(5, 109.0, 112.0, 108.0, 110.0)
    resting = resting_entry(retest)
    assert resting.price == retest.close
    assert resting.bar == retest.index
    assert resting.available_at == retest.index
    assert resting.entry_semantics == RESTING_ORDER
    assert resting.divergence is None
    event = MarketEvent("MKT-E09", retest.index, retest.index, "pid")
    assert resting_entry(retest, event).bar == retest.index
    with pytest.raises(ValueError):
        resting_entry(retest, MarketEvent("MKT-E01", retest.index, retest.index, "pid"))
    legacy = legacy_entry(retest, 8)
    assert legacy.price == retest.close
    assert legacy.bar == 8
    assert legacy.available_at == 8
    assert legacy.available_at >= retest.index
    assert legacy.entry_semantics == APPROVAL_BAR_LEGACY
    assert legacy.divergence == LEGACY_DIVERGENCE
    assert legacy.parameterization_id != resting.parameterization_id
    with pytest.raises(ValueError, match="I-6"):
        legacy_entry(retest, 4)


def test_unknown_cost_is_none_and_a_measured_cost_is_the_authority():
    unknown = _component(UNKNOWN)
    assert component_cost(
        unknown, entry=2000.0, risk_distance=10.0, exit_kind="SL_HIT", direction="long", exit_bar=4,
    ) is None
    assert component_cost(
        _component(MEASURED), entry=2000.0, risk_distance=None, exit_kind="SL_HIT", direction="long", exit_bar=4,
    ) is None
    assert component_cost(
        _component(MEASURED), entry=2000.0, risk_distance=0.0, exit_kind="SL_HIT", direction="long", exit_bar=4,
    ) is None
    measured = _component(MEASURED)
    cost = component_cost(
        measured, entry=2000.0, risk_distance=10.0, exit_kind="SL_HIT", direction="long", exit_bar=4,
    )
    assert cost is not None
    assert cost.cost_r == measured.cost_r(2000.0, 10.0, exit_kind="SL_HIT", direction="long")
    assert cost.cost_r != 0.0
    assert cost.cost_model == "component"
    assert cost.available_at == 4
    flat_model = CostModel(12.0)
    flat = flat_cost(flat_model, entry=2000.0, risk_distance=10.0, cost_source="SYNTHETIC-FLAT", plan_bar=4)
    assert flat.cost_r == flat_model.cost_r(2000.0, 10.0)
    assert flat.cost_model == "flat_bps"
    assert flat.parameterization_id != cost.parameterization_id
    with pytest.raises(ValueError):
        flat_cost(flat_model, entry=2000.0, risk_distance=10.0, cost_source="", plan_bar=4)


def test_outcome_identity_includes_walk_basis_cost_model_and_walk_params():
    gross = _measure()
    assert gross is not None
    assert gross.net_r is None
    assert gross.cost_model == "none"
    assert gross.exit_bar == 2
    assert gross.available_at == gross.exit_bar
    assert gross.available_at >= 1
    signal = Signal("XAUUSD", datetime(2024, 1, 1), 1, "long", 100.0, 1.0, 2.0, 10.0)
    assert gross.gross_r == forward_walk(signal, [_bar(2, 100.0, 120.0, 95.0, 110.0)]).rr_achieved
    wider = _measure(walk_params={"max_forward": 5})
    assert wider.parameterization_id != gross.parameterization_id
    same = _measure(walk_params={"max_forward": 5, "exit_model": "intrabar_fixed"})
    reordered = _measure(walk_params={"exit_model": "intrabar_fixed", "max_forward": 5})
    assert same.parameterization_id == reordered.parameterization_id
    other_param = _measure(walk_params={"max_forward": 6})
    assert other_param.parameterization_id != same.parameterization_id

    flat_model = CostModel(12.0)
    net = _measure(basis="net", cost_model=flat_model, cost_source="SYNTHETIC-FLAT")
    assert net.parameterization_id != gross.parameterization_id
    assert net.net_r == net.gross_r - flat_model.cost_r(100.0, 10.0)
    assert net.cost_model == "flat_bps"
    assert net.cost is not None and net.cost.available_at == 1
    other_calibration = _measure(basis="net", cost_model=flat_model, cost_source="OTHER-CAL")
    assert other_calibration.parameterization_id != net.parameterization_id
    assert other_calibration.net_r == net.net_r
    other_model = _measure(basis="net", cost_model=_component(MEASURED), cost_source="SYNTHETIC")
    assert other_model.parameterization_id != net.parameterization_id
    walked = multi_tp_walk(100.0, "long", 90.0, 120.0, 130.0, [_bar(2, 100.0, 120.0, 95.0, 110.0)], entry_index=1)
    multi = _measure(walk="multi_tp_walk")
    assert multi.gross_r == walked.rr_gross
    assert multi.parameterization_id != gross.parameterization_id
    assert _measure(future=[]) is None
    with pytest.raises(ValueError, match="I-15"):
        _measure(basis="gross", cost_model=flat_model, cost_source="SYNTHETIC-FLAT")
    with pytest.raises(ValueError, match="I-15"):
        _measure(basis="net", cost_model=None)
    with pytest.raises(TypeError):
        _measure(walk_params={"not_a_walk_argument": 1})


def test_net_component_cost_is_the_exit_the_walk_took():
    model = _component(MEASURED)
    stop_future = [_bar(2, 95.0, 96.0, 89.0, 94.0)]
    target_future = [_bar(2, 100.0, 120.0, 95.0, 110.0)]
    stopped = _measure(basis="net", cost_model=model, cost_source="SYNTHETIC", future=stop_future)
    targeted = _measure(basis="net", cost_model=model, cost_source="SYNTHETIC", future=target_future)
    assert stopped.cost is not None and targeted.cost is not None
    assert stopped.cost.cost_r != targeted.cost.cost_r
    assert stopped.cost.cost_r == model.cost_r(100.0, 10.0, exit_kind="SL_HIT", direction="long")
    assert targeted.cost.cost_r == model.cost_r(100.0, 10.0, exit_kind="TP_HIT", direction="long")
    assert stopped.net_r == stopped.gross_r - stopped.cost.cost_r
    assert targeted.net_r == targeted.gross_r - targeted.cost.cost_r
    assert stopped.cost.available_at == stopped.exit_bar
    assert targeted.cost.available_at == targeted.exit_bar


def test_adverse_fill_is_in_the_identity_and_reaches_the_walk():
    stop_future = [_bar(2, 95.0, 96.0, 89.0, 94.0)]
    exact = AdverseFill(stop_slippage=0.0)
    slipped = AdverseFill(stop_slippage=0.09)
    at_level = _measure(walk_params={"adverse_fill": exact}, future=stop_future)
    drifted = _measure(walk_params={"adverse_fill": slipped}, future=stop_future)
    assert at_level.parameterization_id != drifted.parameterization_id
    signal = Signal("XAUUSD", datetime(2024, 1, 1), 1, "long", 100.0, 1.0, 2.0, 10.0)
    assert at_level.gross_r == forward_walk(signal, stop_future, adverse_fill=exact).rr_achieved
    assert drifted.gross_r == forward_walk(signal, stop_future, adverse_fill=slipped).rr_achieved
    assert at_level.gross_r != drifted.gross_r


def test_forward_walk_oco_is_not_a_trs_08_walk():
    with pytest.raises(ValueError):
        measure_outcome(
            walk="forward_walk_oco", basis="gross", walk_params={},
            entry=100.0, stop=90.0, targets=(_target(1, 120.0, intent="reversal"),),
            direction=Bias.LONG, future=[_bar(2, 105.0, 108.0, 102.0, 106.0)],
            instrument="XAUUSD", timestamp=datetime(2024, 1, 1), entry_index=1,
        )
