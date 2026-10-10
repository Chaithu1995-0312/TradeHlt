# tests/test_entry_price_no_lookahead.py
"""
The trade entry must be the price known when the decision is made (the
confirming bar's close), not the earlier retest-bar close.
"""

import os
import sys
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from config_layer.crt_engine_v2 import (
    Candle, CRTConfig, CRTState, Direction, EngineState, ExecutionEngine,
    Range, SweepEvent,
)

_T = datetime(2025, 5, 22, 14, 0)


def _candle(o, h, l, c, minutes=0) -> Candle:
    return Candle(timestamp=_T + timedelta(minutes=minutes), open=o, high=h, low=l, close=c)


def _short_state() -> EngineState:
    st = EngineState(current_state=CRTState.RETEST)
    st.direction = Direction.SHORT
    st.atr = 10.0
    st.active_range = Range(h_ref=3320.0, l_ref=3285.0, equilibrium=3302.5,
                            formed_at=_T, htf_candle_id="HTF-1")
    st.sweep_event = SweepEvent(direction=Direction.SHORT, price=3324.0,
                                candle=_candle(3314, 3324, 3314, 3318))
    st.displacement_candle = _candle(3327, 3330, 3310, 3311)      # SL anchor: high 3330
    st.retest_candle = _candle(3290, 3314.7, 3283, 3314.5, minutes=60)
    return st


@pytest.fixture
def executor() -> ExecutionEngine:
    return ExecutionEngine(CRTConfig())


def test_explicit_entry_price_is_used(executor):
    trade = executor.build_trade(_short_state(), None, entry_price=3304.0)
    assert trade is not None
    assert trade.entry_price == 3304.0
    # SL = disp high + 0.2*ATR = 3330 + 2 = 3332 ; 1R = 28 ; TP1 = 3276 ; TP2 = 3248
    assert trade.sl_price == pytest.approx(3332.0)
    assert trade.tp1_price == pytest.approx(3304.0 - 28.0)
    assert trade.tp2_price == pytest.approx(3304.0 - 56.0)


def test_default_entry_is_retest_close(executor):
    trade = executor.build_trade(_short_state(), None)
    assert trade.entry_price == 3314.5


def test_inverted_sl_still_rejected_with_explicit_entry(executor):
    # entry above the SL on a SHORT -> inverted -> no trade
    assert executor.build_trade(_short_state(), None, entry_price=3335.0) is None
