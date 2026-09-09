"""Minimal fixtures for the Claude semantic-auditor suite. No production math."""
from __future__ import annotations

from datetime import datetime

from config_layer.crt_engine_v2 import Candle, EngineState, StateMachine, SweepEvent
from config_layer.state_identity import CRTConfig, CRTState, Direction

# Permissive thresholds so a rejection is always attributable to the geometry
# contract under test, never to body_ratio / ATR sizing. Mirrors the shape of
# tests/test_directional_displacement.py::_sm_in_sweep.
PERMISSIVE = dict(body_ratio_min=0.50, atr_min_displacement=0.5, atr_multiplier_min=0.5)


def bar(o: float, h: float, l: float, c: float, *, idx: int = 2) -> Candle:
    return Candle(
        timestamp=datetime(2026, 7, 28, 1, 15, 0),
        open=o, high=h, low=l, close=c, volume=1.0, index=idx,
    )


def swept(
    sweep_direction: Direction,
    sweep_price: float,
    *,
    state_direction: Direction | None = None,
    with_sweep_event: bool = True,
) -> tuple[StateMachine, EngineState]:
    """A StateMachine parked in SWEEP, ready for a displacement candidate.

    `state_direction` defaults to `sweep_direction`; pass a different value to
    make EngineState.direction and SweepEvent.direction disagree (the
    provenance probe).
    """
    sm = StateMachine(CRTConfig(**PERMISSIVE))
    st = EngineState()
    st.current_state = CRTState.SWEEP
    st.direction = sweep_direction if state_direction is None else state_direction
    st.atr_abs = 1.0
    st.sweep_event = (
        SweepEvent(
            direction=sweep_direction,
            price=sweep_price,
            candle=bar(100.0, 110.0, 90.0, 108.0, idx=1),
            double_confirmed=False,
            candle_index=1,
        )
        if with_sweep_event
        else None
    )
    return sm, st
