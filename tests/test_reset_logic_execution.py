# tests/test_reset_logic_execution.py
"""
ResetLogic.should_reset — an HTF rollover must not close an open trade.

EXPANSION, RETEST and EXECUTION are protected from "HTF changed" resets;
RANGE, SWEEP and DISPLACEMENT are not. Retrace / extension resets still
fire in EXECUTION.
"""

import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from config_layer.crt_engine_v2 import (
    Candle, CRTConfig, CRTState, Direction, EngineState, Range,
    ResetLogic, SweepEvent,
)

_T = datetime(2025, 7, 9, 15, 45)


def _candle(close: float) -> Candle:
    return Candle(timestamp=_T, open=close, high=close + 1.0, low=close - 1.0, close=close)


def _state(current: CRTState, with_setup: bool = False) -> EngineState:
    st = EngineState(current_state=current)
    st.active_range = Range(
        h_ref=100.0, l_ref=90.0, equilibrium=95.0, formed_at=_T, htf_candle_id="HTF-1",
    )
    if with_setup:
        # LONG setup: sweep @ 90, displacement 90 -> 100 (move = 10)
        st.direction = Direction.LONG
        st.displacement_candle = Candle(timestamp=_T, open=90.0, high=101.0, low=89.0, close=100.0)
        st.sweep_event = SweepEvent(direction=Direction.LONG, price=90.0, candle=_candle(90.0))
    return st


@pytest.fixture
def logic() -> ResetLogic:
    return ResetLogic(CRTConfig())


@pytest.mark.parametrize("protected", [CRTState.EXPANSION, CRTState.RETEST, CRTState.EXECUTION])
def test_htf_change_does_not_reset_active_setup_or_trade(logic, protected):
    reset, reason = logic.should_reset(_state(protected), _candle(95.0), "HTF-2")
    assert reset is False and reason == ""


@pytest.mark.parametrize("state", [CRTState.RANGE, CRTState.SWEEP, CRTState.DISPLACEMENT])
def test_htf_change_still_resets_unprotected_states(logic, state):
    reset, reason = logic.should_reset(_state(state), _candle(95.0), "HTF-2")
    assert reset is True and reason.startswith("HTF changed")


def test_same_htf_no_reset(logic):
    reset, _ = logic.should_reset(_state(CRTState.EXECUTION), _candle(95.0), "HTF-1")
    assert reset is False


def test_retrace_reset_still_fires_in_execution(logic):
    # price 94 vs disp close 100 -> retrace 0.6 >= 0.50
    reset, reason = logic.should_reset(_state(CRTState.EXECUTION, with_setup=True), _candle(94.0), "HTF-1")
    assert reset is True and "retrace" in reason


def test_extension_reset_still_fires_in_execution():
    # retrace check disabled so the extension branch is reached:
    # extension level = 90 + |100-90|*1.618 = 106.18 ; price above it
    logic = ResetLogic(CRTConfig(retrace_reset_pct=1e9))
    reset, reason = logic.should_reset(_state(CRTState.EXECUTION, with_setup=True), _candle(107.0), "HTF-1")
    assert reset is True and "extension" in reason


def test_no_active_range_no_reset(logic):
    st = EngineState(current_state=CRTState.EXECUTION)
    assert logic.should_reset(st, _candle(95.0), "HTF-2") == (False, "")
