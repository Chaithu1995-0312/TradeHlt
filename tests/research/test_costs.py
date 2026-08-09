"""M2 tests: CostModel nets gross RR correctly and EdgeAggregator qualifies on NET."""

from datetime import datetime

import pytest

from research.contracts import Outcome, Signal
from research.costs import DEFAULT_COST_MODEL, ZERO_COST, CostModel
from research.measurement.metrics import EdgeAggregator


def test_cost_r_exact():
    cm = CostModel(round_trip_bps=12.0)
    # 12 bps of entry 100 = 0.12 price; / risk_distance 1.0 = 0.12 R
    assert cm.cost_r(entry=100.0, risk_distance=1.0) == pytest.approx(0.12)
    assert cm.net_rr(2.0, entry=100.0, risk_distance=1.0) == pytest.approx(1.88)


def test_tight_stop_pays_more_cost():
    cm = CostModel(round_trip_bps=12.0)
    wide = cm.cost_r(entry=100.0, risk_distance=2.0)
    tight = cm.cost_r(entry=100.0, risk_distance=0.5)
    assert tight > wide                      # tighter stop => more cost in R terms


def _out(rr: float) -> Outcome:
    sig = Signal(instrument="T", timestamp=datetime(2026, 1, 1), entry_index=0,
                 direction="long", entry=100.0, sl_atr_mult=1.0, tp_atr_mult=2.0, atr=1.0)
    return Outcome(signal=sig, outcome="TP_HIT" if rr > 0 else "SL_HIT", rr_achieved=rr,
                   mfe=0.0, mae=0.0, duration_candles=1, time_to_tp=None,
                   time_to_failure=None, reached_1r=False)


def test_aggregator_nets_by_haircut():
    outs = [_out(2.0), _out(-1.0)]            # gross expectancy 0.5
    gross = EdgeAggregator().aggregate("h", ["T"], outs, cost_model=ZERO_COST)
    net = EdgeAggregator().aggregate("h", ["T"], outs, cost_model=DEFAULT_COST_MODEL)
    assert gross.expectancy_rr == pytest.approx(0.5)
    # each trade pays 0.12 R -> expectancy drops by exactly 0.12
    assert net.expectancy_rr == pytest.approx(0.38)
    assert net.round_trip_bps == 12.0
    assert net.expectancy_rr < gross.expectancy_rr
