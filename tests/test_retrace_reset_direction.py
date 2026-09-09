"""retrace_reset_pct measures pullback against state.direction, not unsigned distance."""
from __future__ import annotations

from datetime import datetime, timezone

from config_layer.crt_engine_v2 import (
    CRTConfig,
    Candle,
    Direction,
    EngineState,
    Range,
    ResetLogic,
)

_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
_HTF = "HTF-1"


def _candle(close: float, *, open_: float = 100.0) -> Candle:
    lo, hi = (min(open_, close), max(open_, close))
    return Candle(timestamp=_T0, open=open_, high=hi + 1.0, low=lo - 1.0, close=close)


def _state(direction: Direction, disp: Candle) -> EngineState:
    rng = Range(
        h_ref=120.0, l_ref=80.0, equilibrium=100.0,
        formed_at=_T0, htf_candle_id=_HTF, session="LONDON",
    )
    st = EngineState()
    st.active_range = rng
    st.direction = direction
    st.displacement_candle = disp
    return st


def _check(direction: Direction, disp: Candle, close: float) -> tuple[bool, str]:
    return ResetLogic(CRTConfig()).should_reset(
        _state(direction, disp), _candle(close), _HTF,
    )


def test_long_pullback_half_body_resets():
    # body = 10; close 4 points below disp.close = 0.60 against LONG
    fired, reason = _check(Direction.LONG, _candle(110.0, open_=100.0), 104.0)
    assert fired is True
    assert "retrace=0.600" in reason


def test_long_continuation_does_not_reset():
    # same 6-point move the other way — unsigned formula would have fired
    fired, reason = _check(Direction.LONG, _candle(110.0, open_=100.0), 116.0)
    assert fired is False
    assert reason == ""


def test_long_shallow_pullback_does_not_reset():
    fired, _ = _check(Direction.LONG, _candle(110.0, open_=100.0), 106.0)
    assert fired is False


def test_short_pullback_half_body_resets():
    fired, reason = _check(Direction.SHORT, _candle(100.0, open_=110.0), 106.0)
    assert fired is True
    assert "retrace=0.600" in reason


def test_short_continuation_does_not_reset():
    fired, reason = _check(Direction.SHORT, _candle(100.0, open_=110.0), 94.0)
    assert fired is False
    assert reason == ""


def test_direction_none_does_not_use_this_rule():
    fired, reason = _check(Direction.NONE, _candle(110.0, open_=100.0), 90.0)
    assert fired is False
    assert "retrace" not in reason
