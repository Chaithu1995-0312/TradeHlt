"""
WS3.5 golden ledgers — tiny hand-verified fixtures asserted against the independent
oracle. Parity proves "oracle == production"; these prove "oracle == truth". If the
oracle drifts, these break regardless of what the production path does.

See docs/analysis/backtest-trust-audit-2026-06-10.md.
"""
from __future__ import annotations

import math

import pytest

from analytics import metrics_oracle as mo


# Fixture A — mixed: [+1R, −1R, +2R]
def test_fixture_A_mixed():
    rr = [1.0, -1.0, 2.0]
    assert mo.profit_factor(rr) == pytest.approx(3.0)          # (1+2)/|−1|
    assert mo.win_rate(rr) == pytest.approx(2 / 3)             # 66.67%
    assert mo.expectancy_mean(rr) == pytest.approx(2 / 3)      # (1−1+2)/3
    assert mo.expectancy_classical(rr) == pytest.approx(2 / 3)
    assert mo.max_drawdown_rr(rr) == pytest.approx(1.0)        # cum [1,0,2] → dd 1R


# Fixture B — all losers → PF = 0, WR = 0
def test_fixture_B_all_losers():
    rr = [-1.0, -0.5, -1.0]
    assert mo.profit_factor(rr) == pytest.approx(0.0)          # gross_win = 0
    assert mo.win_rate(rr) == pytest.approx(0.0)
    assert mo.expectancy_mean(rr) == pytest.approx(-2.5 / 3)
    assert mo.max_drawdown_rr(rr) == pytest.approx(2.5)        # monotonic down


# Fixture C — no trades → sentinels, no div-by-zero
def test_fixture_C_no_trades():
    rr: list[float] = []
    assert mo.win_rate(rr) == 0.0
    assert mo.profit_factor(rr) == 0.0
    assert mo.expectancy_mean(rr) == 0.0
    assert mo.expectancy_classical(rr) == 0.0
    assert mo.max_drawdown_rr(rr) == 0.0
    assert mo.max_drawdown_pct([]) == 0.0


# Fixture D — single winner → PF inf-sentinel (no losses)
def test_fixture_D_single_winner():
    rr = [2.0]
    assert mo.win_rate(rr) == pytest.approx(1.0)
    assert mo.profit_factor(rr) == mo.PF_INF_SENTINEL          # no losses
    assert mo.expectancy_mean(rr) == pytest.approx(2.0)
    assert mo.max_drawdown_rr(rr) == pytest.approx(0.0)        # never underwater


# Fixture E — alternating equity (drawdown-walk stress): [+1,−1,+1,−1,+1]
def test_fixture_E_alternating():
    rr = [1.0, -1.0, 1.0, -1.0, 1.0]
    assert mo.win_rate(rr) == pytest.approx(3 / 5)             # 60%
    assert mo.profit_factor(rr) == pytest.approx(3 / 2)        # 3 / |−2|
    assert mo.expectancy_mean(rr) == pytest.approx(1 / 5)      # +1R / 5
    assert mo.max_drawdown_rr(rr) == pytest.approx(1.0)        # cum [1,0,1,0,1]


# Capital-curve fixtures (max_drawdown_pct / total_return_pct)
def test_capital_curve_drawdown_pct():
    # peak 110 then trough 88 → max dd = (110−88)/110 = 0.2
    equity = [100.0, 110.0, 99.0, 88.0, 105.0]
    assert mo.max_drawdown_pct(equity) == pytest.approx(22.0 / 110.0)


def test_total_return_and_mar():
    assert mo.total_return_pct(120.0, 100.0) == pytest.approx(0.20)
    assert mo.return_to_max_dd(0.20, 0.10) == pytest.approx(2.0)
    assert mo.return_to_max_dd(0.20, 0.0) == 0.0               # zero-DD guard


def test_cagr_one_year_span():
    # 35,040 M15 candles ≈ 1 year; 20% total return → CAGR ≈ 20%
    candles_one_year = (365 * 24 * 60) // 15
    assert mo.cagr(0.20, candles_one_year) == pytest.approx(0.20, abs=1e-3)
    # half-year span doubles the annualized rate (compounding)
    assert mo.cagr(0.20, candles_one_year // 2) == pytest.approx((1.20 ** 2) - 1, abs=1e-2)
