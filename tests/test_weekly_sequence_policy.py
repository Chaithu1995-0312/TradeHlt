# tests/test_weekly_sequence_policy.py
"""Weekly BUY/SELL sequence analysis: week bucketing, direction rules, cost symmetry."""

import os
import sys
from datetime import datetime, timedelta

import pytest

_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(_ROOT, "scripts", "analysis"))
sys.path.insert(0, os.path.join(_ROOT, "src"))

import weekly_sequence_policy as w  # noqa: E402
from config_layer.crt_engine_v2 import Candle  # noqa: E402
from runtime.backtest_v2 import BacktestConfig  # noqa: E402


def _bars(start="2025-06-02", end="2025-07-31"):
    out, d = [], datetime.fromisoformat(start)
    stop = datetime.fromisoformat(end)
    px = 3300.0
    while d <= stop:
        if d.weekday() < 5:
            for h in range(1, 24):
                o = px
                c = px + (1.0 if (d.day + h) % 3 else -0.8)
                out.append(Candle(timestamp=d.replace(hour=h), open=o, high=max(o, c) + 2, low=min(o, c) - 2, close=c))
                px = c
        d += timedelta(days=1)
    return out


@pytest.fixture(scope="module")
def bars():
    return _bars()


@pytest.fixture(scope="module")
def cfg():
    return BacktestConfig.from_prod_config(instrument="XAUUSD", pip_size=0.01)


def test_month_weeks_bounded_by_month(bars):
    weeks = w.month_weeks(bars, "2025-07")
    assert [wk[0].timestamp.date().isoformat() for wk in weeks] == [
        "2025-07-01", "2025-07-07", "2025-07-14", "2025-07-21", "2025-07-28"]
    assert weeks[0][0].timestamp.weekday() == 1          # first week starts on a Tuesday
    assert weeks[-1][-1].timestamp.date().isoformat() == "2025-07-31"   # truncated at month end
    assert all(b.timestamp.month == 7 for wk in weeks for b in wk)


@pytest.mark.parametrize("policy,prev_dir,prev_net,expected", [
    ("A", "BUY", 0.5, "BUY"), ("A", "BUY", -0.5, "SELL"), ("A", "SELL", -0.5, "BUY"),
    ("B", "BUY", 0.5, "BUY"), ("B", "SELL", -0.5, "SELL"),
    ("C", "BUY", 0.5, "SELL"), ("C", "BUY", -0.5, "BUY"), ("C", "SELL", 0.5, "BUY"),
    ("C", "SELL", -0.0, "SELL"),              # net R == 0 is a loss -> retain
])
def test_direction_rules(policy, prev_dir, prev_net, expected):
    assert w.next_direction(policy, prev_dir, prev_net, 1, "BUY") == expected


def test_seed_controls_and_alternation():
    assert w.next_direction("A", None, None, 0, "SELL") == "SELL"
    assert w.next_direction("D1", "SELL", -1, 3, "SELL") == "BUY"
    assert w.next_direction("D2", "BUY", 1, 3, "BUY") == "SELL"
    assert [w.next_direction("E", None, None, i, "BUY") for i in range(4)] == ["BUY", "SELL", "BUY", "SELL"]


def test_buy_sell_raw_exact_negatives_and_costs_adverse(bars, cfg):
    weeks = w.month_weeks(bars, "2025-07")
    for i, wk in enumerate(weeks):
        b, s = w.trade_week(bars, wk, "BUY", cfg, i), w.trade_week(bars, wk, "SELL", cfg, i)
        assert b["raw_r"] == pytest.approx(-s["raw_r"], abs=1e-4)
        assert b["unit"] == s["unit"] and b["entry_raw"] == pytest.approx(wk[0].open, abs=0.01)
        assert b["exit_raw"] == pytest.approx(wk[-1].close, abs=0.01)
        assert b["cost_r"] > 0 and s["cost_r"] > 0           # costs hurt both directions
        assert b["net_r"] == pytest.approx(b["raw_r"] - b["cost_r"], abs=1e-3)


def test_sequence_is_deterministic(bars, cfg):
    weeks = w.month_weeks(bars, "2025-07")
    a = w.run_sequence(bars, weeks, cfg, "A", "BUY")
    assert a == w.run_sequence(bars, weeks, cfg, "A", "BUY")
