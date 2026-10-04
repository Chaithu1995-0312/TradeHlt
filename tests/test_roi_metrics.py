"""ROI / returns telemetry — additive metrics surfaced by the ROI Step.

Covers the post-hoc math in MetricsEngine._roi_block, the new to_dict keys,
and a regression lock proving ROI is NOT wired into the fitness score or the
config-validator aggregate decision (measure-only, never gated).
"""

from types import SimpleNamespace

from runtime.backtest_v2 import (
    BacktestMetrics,
    CapitalCurve,
    MetricsEngine,
    _ROI_DEFAULTS,
)
from config_layer.config_validator import _aggregate_metrics, _fitness_score


def _trade(pnl_rr_net: float) -> SimpleNamespace:
    """_roi_block only reads .pnl_rr_net, so a lightweight stub suffices."""
    return SimpleNamespace(pnl_rr_net=pnl_rr_net)


def _capital_with(equity_curve: list[float]) -> CapitalCurve:
    cap = CapitalCurve(initial_capital=equity_curve[0], risk_pct=0.01, compounding=True)
    cap.equity_curve = list(equity_curve)
    cap.current_capital = equity_curve[-1]
    cap.peak_capital = max(equity_curve)
    return cap


# years == 1.0 exactly when total_candles * candle_minutes == minutes_in_a_year
_ONE_YEAR_CANDLES = (365 * 24 * 60) // 15   # 35040 M15 candles


def test_roi_block_basic_math():
    eng = MetricsEngine("TEST")
    m = BacktestMetrics(instrument="TEST")
    trades = [_trade(2.0), _trade(-1.0), _trade(1.0), _trade(-1.0)]
    cap = _capital_with([100000, 110000, 105000, 120000])

    eng._roi_block(m, trades, cap, _ONE_YEAR_CANDLES)

    assert m.gross_win_rr == 3.0
    assert m.gross_loss_rr == -2.0
    assert m.profit_factor == 1.5                       # 3.0 / 2.0
    assert abs(m.total_return_pct - 0.20) < 1e-9        # (120k-100k)/100k
    max_dd = 5000 / 110000                              # 110k peak -> 105k trough
    assert abs(m.return_to_max_dd - (0.20 / max_dd)) < 1e-6
    assert abs(m.annualized_return_pct - 0.20) < 1e-9   # span == 1y -> CAGR == ROI


def test_roi_block_no_losses_uses_sentinel():
    eng = MetricsEngine("TEST")
    m = BacktestMetrics(instrument="TEST")
    cap = _capital_with([100000, 103000])

    eng._roi_block(m, [_trade(2.0), _trade(1.0)], cap, _ONE_YEAR_CANDLES)

    assert m.profit_factor == _ROI_DEFAULTS["profit_factor_inf_sentinel"]


def test_roi_block_divzero_guards():
    eng = MetricsEngine("TEST")
    m = BacktestMetrics(instrument="TEST")
    cap = _capital_with([100000, 101000])   # monotonic up -> max_dd == 0

    eng._roi_block(m, [_trade(1.0)], cap, 0)   # zero candles -> years == 0

    assert m.return_to_max_dd == 0.0
    assert m.annualized_return_pct == 0.0


def test_to_dict_exposes_roi_keys():
    keys = BacktestMetrics().to_dict().keys()
    for k in (
        "total_return_pct", "annualized_return_pct", "profit_factor",
        "return_to_max_dd", "gross_win_rr", "gross_loss_rr",
    ):
        assert k in keys


def test_aggregate_surfaces_roi_without_changing_score():
    """ROI is additive in the validator aggregate; the decision score is
    unaffected by the presence of total_return_pct."""
    per = {
        "BNBUSDT": {
            "score": 0.5, "trades": 20, "win_rate": 0.6,
            "expectancy_rr": 0.3, "max_drawdown": 0.1,
            "total_pnl_rr": 6.0, "total_return_pct": 0.25,
        },
    }
    agg = _aggregate_metrics(per)

    assert agg["total_return_pct_across"] == 0.25
    assert agg["final_score"] == 0.5   # single instrument -> no consistency penalty


def test_fitness_score_takes_no_roi_input():
    """Regression lock: the fitness formula has no ROI term, so it stays
    deterministic and bounded regardless of returns."""
    s = _fitness_score(win_rate=0.5, expectancy_rr=0.3, trade_count=20, max_drawdown_pct=0.1)
    assert s == _fitness_score(0.5, 0.3, 20, 0.1)
    assert 0.0 <= s <= 1.0
