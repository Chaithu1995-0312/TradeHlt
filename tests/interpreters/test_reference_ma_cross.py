"""
test_reference_ma_cross.py — unit tests for the MovingAverageCrossInterpreter (Plan 4).

Deterministic cross detection, valid bounded confidence/strength, purity. No real data.

Run: python -m pytest tests/interpreters/test_reference_ma_cross.py -q
"""
from __future__ import annotations

import math
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parent.parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.crt_engine_v2 import Candle, Direction

from interpreters.contract import EventKind
from interpreters.reference import MovingAverageCrossInterpreter

_BASE = datetime(2025, 1, 1, 0, 0, 0)


def _candles(prices) -> list[Candle]:
    return [Candle(timestamp=_BASE + timedelta(minutes=15 * i), open=p, high=p + 1.0,
                   low=p - 1.0, close=p, volume=1.0, index=i) for i, p in enumerate(prices)]


def test_fast_slow_validation():
    with pytest.raises(ValueError):
        MovingAverageCrossInterpreter(fast_period=30, slow_period=10)


def test_no_cross_emits_no_events():
    # Monotone flat → fast == slow, never crosses.
    interp = MovingAverageCrossInterpreter(fast_period=5, slow_period=20)
    reading = interp.observe(_candles([100.0] * 40), {}, {"instrument": "X"})
    assert reading.events == []
    assert reading.confidence == 0.0


def test_detects_both_directions_over_oscillation():
    prices = [100 + 10 * math.sin(i / 5.0) for i in range(200)]
    candles = _candles(prices)
    interp = MovingAverageCrossInterpreter(fast_period=5, slow_period=20)
    longs = shorts = 0
    for i in range(21, len(candles)):
        for ev in interp.observe(candles[: i + 1], {}, {"instrument": "X"}).events:
            assert ev.kind is EventKind.BREAKOUT
            assert ev.direction in (Direction.LONG, Direction.SHORT)
            assert 0.0 <= ev.confidence <= 1.0 and 0.0 <= ev.strength <= 1.0
            assert ev.is_directional        # carries full geometry for the adapter
            longs += ev.direction is Direction.LONG
            shorts += ev.direction is Direction.SHORT
    assert longs > 0 and shorts > 0


def test_observe_is_deterministic():
    prices = [100 + 10 * math.sin(i / 5.0) for i in range(60)]
    window = _candles(prices)
    interp = MovingAverageCrossInterpreter(fast_period=5, slow_period=20)
    assert interp.observe(window, {}, {"instrument": "X"}) == \
           interp.observe(window, {}, {"instrument": "X"})


def test_explain_reflects_last_observation_but_does_not_affect_reading():
    prices = [100 + 10 * math.sin(i / 5.0) for i in range(60)]
    window = _candles(prices)
    interp = MovingAverageCrossInterpreter(fast_period=5, slow_period=20)
    r_before = interp.observe(window, {}, {"instrument": "X"})
    _ = interp.explain()                       # telemetry read
    r_after = interp.observe(window, {}, {"instrument": "X"})
    assert r_before == r_after                  # explain() never perturbs the reading
    assert set(interp.explain()) >= {"observation", "reasoning", "unknowns"}
