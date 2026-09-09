"""Directional displacement contract (CH-directional-displacement-contract).

After a LONG (range-low) sweep, DISPLACEMENT must be an UP impulse.
After a SHORT (range-high) sweep, DISPLACEMENT must be a DOWN impulse.

Pins the Jul 28 XAUUSD forensic case: the 01:15 UTC dump after a LONG sweep
is no longer a legal DISPLACEMENT.
"""
from __future__ import annotations

from datetime import datetime

from config_layer.crt_engine_v2 import (
    CRTConfig,
    CRTState,
    Candle,
    Direction,
    EngineState,
    StateMachine,
    SweepEvent,
)


def _candle(o: float, h: float, l: float, c: float, idx: int = 2) -> Candle:
    return Candle(
        timestamp=datetime(2026, 7, 28, 1, 15, 0),
        open=o, high=h, low=l, close=c, volume=1.0, index=idx,
    )


def _sm_in_sweep(direction: Direction, sweep_price: float) -> tuple[StateMachine, EngineState]:
    cfg = CRTConfig(body_ratio_min=0.50, atr_min_displacement=0.5, atr_multiplier_min=0.5)
    sm = StateMachine(cfg)
    st = EngineState()
    st.current_state = CRTState.SWEEP
    st.direction = direction
    st.atr_abs = 1.0
    bar = _candle(100, 110, 90, 108, idx=1)
    st.sweep_event = SweepEvent(
        direction=direction, price=sweep_price, candle=bar,
        double_confirmed=False, candle_index=1,
    )
    return sm, st


def test_long_rejects_bearish_dump_jul28_shape():
    """Jul 28 01:15 UTC shape: LONG sweep then a large red body — REJECT."""
    sm, st = _sm_in_sweep(Direction.LONG, sweep_price=4053.91)
    dump = _candle(4058.08, 4059.19, 4046.38, 4047.41, idx=2)
    assert dump.close < dump.open
    assert dump.close < 4053.91
    assert sm.try_sweep_to_displacement(st, dump) is False
    assert st.current_state is CRTState.SWEEP


def test_long_accepts_bullish_impulse_away_from_sweep():
    sm, st = _sm_in_sweep(Direction.LONG, sweep_price=99.0)
    up = _candle(100.0, 112.0, 99.5, 111.0, idx=2)
    assert sm.try_sweep_to_displacement(st, up) is True
    assert st.current_state is CRTState.DISPLACEMENT


def test_long_rejects_bullish_bar_that_fails_to_leave_sweep():
    """Bullish body that still closes at/below the sweep low is not away-from-liquidity."""
    sm, st = _sm_in_sweep(Direction.LONG, sweep_price=105.0)
    trapped = _candle(100.0, 106.0, 99.0, 104.0, idx=2)
    assert trapped.close > trapped.open
    assert trapped.close <= 105.0
    assert sm.try_sweep_to_displacement(st, trapped) is False
    assert st.current_state is CRTState.SWEEP


def test_short_rejects_bullish_impulse():
    sm, st = _sm_in_sweep(Direction.SHORT, sweep_price=110.0)
    up = _candle(100.0, 112.0, 99.5, 111.0, idx=2)
    assert sm.try_sweep_to_displacement(st, up) is False
    assert st.current_state is CRTState.SWEEP


def test_short_accepts_bearish_impulse_away_from_sweep():
    sm, st = _sm_in_sweep(Direction.SHORT, sweep_price=111.0)
    down = _candle(110.0, 111.5, 98.0, 99.0, idx=2)
    assert sm.try_sweep_to_displacement(st, down) is True
    assert st.current_state is CRTState.DISPLACEMENT


def test_missing_direction_fail_closed():
    cfg = CRTConfig(body_ratio_min=0.50, atr_min_displacement=0.5, atr_multiplier_min=0.5)
    sm = StateMachine(cfg)
    st = EngineState()
    st.current_state = CRTState.SWEEP
    st.direction = Direction.NONE
    st.atr_abs = 1.0
    st.sweep_event = None
    bar = _candle(100.0, 112.0, 99.5, 111.0, idx=2)
    assert sm.try_sweep_to_displacement(st, bar) is False
    assert st.current_state is CRTState.SWEEP
