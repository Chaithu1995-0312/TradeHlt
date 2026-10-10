# tests/test_backtest_fill_prices.py
"""
Spread/slippage fills must be adverse for BOTH directions.
A flat round trip (no price move, no slippage) must cost exactly the full spread
for longs and shorts alike; net R must be below raw R.
"""

import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from config_layer.crt_engine_v2 import Candle, Direction, Trade
from runtime.backtest_v2 import (
    CapitalCurve, SlippageModel, TradeJournal, signed_half_spread,
)

_T = datetime(2025, 5, 22, 15, 0)
_PIP = 0.01


def _candle() -> Candle:
    return Candle(timestamp=_T, open=100.0, high=101.0, low=99.0, close=100.0)


def _journal() -> TradeJournal:
    return TradeJournal(
        "XAUUSD", _PIP,
        SlippageModel(atr_fraction=0.0, seed=1),
        CapitalCurve(100_000.0, 0.01, False),
    )


def _flat_round_trip(direction: Direction, spread_half: float = 0.5):
    entry = 100.0
    sl = entry - 5.0 if direction == Direction.LONG else entry + 5.0
    tp1 = entry + 5.0 if direction == Direction.LONG else entry - 5.0
    trade = Trade(id="T1", direction=direction, entry_price=entry,
                  sl_price=sl, tp1_price=tp1, tp2_price=tp1)
    j = _journal()
    j.on_trade_opened(
        trade, _candle(), 1, 0.5, [], "HTF-1", "NEWYORK", 1.0, spread_half,
        [0.0] * 35,
    )
    rec = j.on_trade_closed(trade, entry, "RESET_CLOSE", _candle(), 2, 1.0, spread_half)
    return rec


def test_signed_half_spread():
    assert signed_half_spread(Direction.LONG, 0.5) == 0.5
    assert signed_half_spread(Direction.SHORT, 0.5) == -0.5


def test_long_fills_adverse():
    rec = _flat_round_trip(Direction.LONG)
    assert rec.entry_price_fill == pytest.approx(100.5)   # pays ask
    assert rec.exit_price_fill == pytest.approx(99.5)     # sells bid


def test_short_fills_adverse():
    rec = _flat_round_trip(Direction.SHORT)
    assert rec.entry_price_fill == pytest.approx(99.5)    # sells bid
    assert rec.exit_price_fill == pytest.approx(100.5)    # buys back ask


@pytest.mark.parametrize("direction", [Direction.LONG, Direction.SHORT])
def test_flat_round_trip_costs_full_spread(direction):
    rec = _flat_round_trip(direction)
    # spread_half = 0.5 -> round-trip cost = 1.0 price = 100 pips (pip 0.01)
    assert rec.pnl_pips_raw == pytest.approx(0.0)
    assert rec.pnl_pips_net == pytest.approx(-100.0)
    assert rec.pnl_rr_net < rec.pnl_rr_raw
    assert rec.spread_pips == pytest.approx(100.0)


@pytest.mark.parametrize("direction", [Direction.LONG, Direction.SHORT])
def test_slippage_pips_excludes_spread(direction):
    rec = _flat_round_trip(direction)
    assert rec.slippage_pips == pytest.approx(0.0)


def test_compute_fill_prices_adverse_for_short():
    s = SlippageModel(atr_fraction=0.0, seed=1)
    entry_fill, exit_fill, _, spread_cost = s.compute_fill_prices(
        100.0, 100.0, Direction.SHORT, 1.0, 0.5,
    )
    assert entry_fill == pytest.approx(99.5)
    assert exit_fill == pytest.approx(100.5)
    assert spread_cost == pytest.approx(1.0)
