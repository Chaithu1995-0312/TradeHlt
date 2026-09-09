"""Minimal CRT fixtures for semantic-auditor tests. No production math."""
from __future__ import annotations

from datetime import datetime, time

from config_layer.crt_engine_v2 import (
    Candle,
    EngineState,
    ExecutionEngine,
    Range,
    SweepEvent,
)
from config_layer.state_identity import CRTConfig, CRTState, Direction


def candle(
    ts: datetime,
    o: float,
    h: float,
    l: float,
    c: float,
    *,
    idx: int = 0,
    vol: float = 1.0,
) -> Candle:
    return Candle(timestamp=ts, open=o, high=h, low=l, close=c, volume=vol, index=idx)


def range_box(h_ref: float, l_ref: float, *, session: str = "UNKNOWN") -> Range:
    return Range(
        h_ref=h_ref,
        l_ref=l_ref,
        equilibrium=(h_ref + l_ref) / 2.0,
        formed_at=datetime(2026, 7, 22, 16, 0, 0),
        htf_candle_id="TEST-HTF-000",
        session=session,
    )


def engine_ready_short(
    *,
    entry: float = 4154.55,
    disp_high: float = 4146.75,
    disp_low: float = 4132.02,
    atr_abs: float = 9.562143,
    sweep_price: float = 4156.69,
) -> EngineState:
    """Reproduce the 2026-07-22 SHORT inverted-SL geometry from the episode trace."""
    retest = candle(datetime(2026, 7, 22, 19, 0, 0), 4159.47, 4159.55, 4153.3, entry, idx=72)
    disp = candle(datetime(2026, 7, 22, 16, 30, 0), 4132.02, disp_high, disp_low, 4142.79, idx=62)
    sweep_bar = candle(datetime(2026, 7, 22, 17, 15, 0), 4156.66, sweep_price, 4144.48, 4146.43, idx=65)
    st = EngineState()
    st.current_state = CRTState.RETEST
    st.direction = Direction.SHORT
    st.active_range = range_box(4156.03, 4107.15)
    st.displacement_candle = disp
    st.retest_candle = retest
    st.retest_candle_index = 72
    st.current_candle_index = 73
    st.atr_abs = atr_abs
    st.sweep_event = SweepEvent(
        direction=Direction.SHORT, price=sweep_price, candle=sweep_bar, candle_index=65
    )
    return st


def engine_ready_long(
    *,
    entry: float = 4044.31,
    disp_high: float = 4059.19,
    disp_low: float = 4046.38,
    atr_abs: float = 6.571429,
    sweep_price: float = 4042.53,
) -> EngineState:
    """Reproduce the 2026-07-28 LONG inverted-SL geometry from the episode trace."""
    retest = candle(datetime(2026, 7, 28, 5, 30, 0), 4046.24, 4047.99, 4041.54, entry, idx=386)
    disp = candle(datetime(2026, 7, 28, 4, 15, 0), 4058.08, disp_high, disp_low, 4047.41, idx=381)
    sweep_bar = candle(datetime(2026, 7, 28, 5, 0, 0), 4045.19, 4047.6, sweep_price, 4046.5, idx=384)
    st = EngineState()
    st.current_state = CRTState.RETEST
    st.direction = Direction.LONG
    st.active_range = range_box(4075.08, 4042.58)
    st.displacement_candle = disp
    st.retest_candle = retest
    st.retest_candle_index = 386
    st.current_candle_index = 387
    st.atr_abs = atr_abs
    st.sweep_event = SweepEvent(
        direction=Direction.LONG, price=sweep_price, candle=sweep_bar, candle_index=384
    )
    return st


def executor(cfg: CRTConfig | None = None) -> ExecutionEngine:
    return ExecutionEngine(cfg or CRTConfig())


def filter_session_name(cfg: CRTConfig, t: time) -> str:
    """Mirror crt_engine_v2.py:3111-3115 first-match inclusive lookup."""
    for name, (start, end) in cfg.session_windows.items():
        if start <= t <= end:
            return name
    return "OFF_SESSION"
