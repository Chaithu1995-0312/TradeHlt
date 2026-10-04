"""
test_goal_metrics.py — span-derived trades_per_month + additive goal_report
telemetry on BacktestMetrics (measure-only).

Run: python -m pytest tests/test_goal_metrics.py -q
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from runtime.backtest_v2 import BacktestMetrics, MetricsEngine

# total_candles for exactly one year of M15 bars → years = 1.0 → months = 12.
_ONE_YEAR_M15 = (365 * 24 * 60) // 15   # 35040


def _cap(total_return_pct: float = 0.0, max_drawdown_pct: float = 0.0):
    return types.SimpleNamespace(
        total_return_pct=total_return_pct, max_drawdown_pct=max_drawdown_pct
    )


def test_trades_per_month_span_derived():
    eng = MetricsEngine("BTCUSDT")
    m = BacktestMetrics(instrument="BTCUSDT")
    m.approved_trades = 24                       # 24 trades over 12 months
    eng._roi_block(m, [], _cap(), _ONE_YEAR_M15)
    assert round(m.trades_per_month, 4) == 2.0


def test_trades_per_month_zero_span_is_zero():
    eng = MetricsEngine("BTCUSDT")
    m = BacktestMetrics(instrument="BTCUSDT")
    m.approved_trades = 5
    eng._roi_block(m, [], _cap(), 0)             # no candles → no division blowup
    assert m.trades_per_month == 0.0


def test_goal_report_attached_as_telemetry():
    # The additive, measure-only goal_report must be present in distribution and
    # must NOT change any decision (no gating in this hot path).
    eng = MetricsEngine("BTCUSDT")
    m = BacktestMetrics(instrument="BTCUSDT")
    m.approved_trades = 1                          # ~0.08 trades/month → below goal
    eng._roi_block(m, [], _cap(), _ONE_YEAR_M15)
    gr = m.distribution.get("goal_report")
    assert gr is not None
    assert gr["goal_id"] == "G001"
    assert gr["enforced"] is False                 # advisory only
    # Low frequency vs the G001 min(20) → the report records a FAIL (advisory).
    assert gr["decision"] == "FAIL"
    assert "trades_per_month_min" in [c["name"] for c in gr["criteria"]]
