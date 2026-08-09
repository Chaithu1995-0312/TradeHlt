"""M1 measurement-core tests: EdgeAggregator stats from a list of Outcomes."""

from datetime import datetime

from research.contracts import Outcome, Signal
from research.costs import ZERO_COST
from research.measurement.metrics import EdgeAggregator


def _sig() -> Signal:
    return Signal(
        instrument="TEST", timestamp=datetime(2026, 1, 1), entry_index=0,
        direction="long", entry=100.0, sl_atr_mult=1.0, tp_atr_mult=2.0, atr=1.0,
    )


def _out(rr: float, *, mfe: float = 0.0, mae: float = 0.0,
         ttf: int | None = None, reached_1r: bool = False) -> Outcome:
    return Outcome(
        signal=_sig(), outcome="TP_HIT" if rr > 0 else "SL_HIT", rr_achieved=rr,
        mfe=mfe, mae=mae, duration_candles=1, time_to_tp=1 if rr > 0 else None,
        time_to_failure=ttf, reached_1r=reached_1r,
    )


def test_basic_aggregation():
    # 3 wins of +2R, 2 losses of -1R: PF = 6/2 = 3.0, expectancy = (6-2)/5 = 0.8
    outs = [
        _out(2.0, mfe=2.0, reached_1r=True),
        _out(2.0, mfe=2.0, reached_1r=True),
        _out(2.0, mfe=2.0, reached_1r=True),
        _out(-1.0, mae=-1.5, ttf=4),
        _out(-1.0, mae=-1.2, ttf=2),
    ]
    rep = EdgeAggregator().aggregate("test_hyp", ["TEST"], outs, cost_model=ZERO_COST)
    assert rep.n == 5
    assert rep.wins == 3 and rep.losses == 2
    assert rep.win_rate == 0.6
    assert rep.profit_factor == 3.0
    assert rep.expectancy_rr == 0.8
    assert rep.continuation_prob == 0.6           # 3/5 reached 1R
    assert rep.median_time_to_failure == 3.0       # median(4, 2)
    assert rep.verdict == "INSUFFICIENT"           # M1 does not set a verdict


def test_max_drawdown_rr():
    # equity: +2, +1(peak3->... ), sequence chosen for a clear -1 -1 trough
    outs = [_out(2.0), _out(-1.0, ttf=1), _out(-1.0, ttf=1), _out(2.0)]
    rep = EdgeAggregator().aggregate("test_hyp", ["TEST"], outs, cost_model=ZERO_COST)
    # peak equity = 2 (after first), trough = 0 (after two losses) -> dd = 2.0
    assert rep.max_drawdown_rr == 2.0


def test_empty_outcomes():
    rep = EdgeAggregator().aggregate("test_hyp", ["TEST"], [])
    assert rep.n == 0
    assert rep.reject_reasons == ["no_outcomes"]


def test_profit_factor_no_losses_is_inf():
    outs = [_out(2.0), _out(2.0)]
    rep = EdgeAggregator().aggregate("test_hyp", ["TEST"], outs, cost_model=ZERO_COST)
    assert rep.profit_factor == float("inf")
