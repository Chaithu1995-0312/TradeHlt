"""
test_invariant_guards.py — protect the two strongest Plan-3 invariants end-to-end:
  • explain() is telemetry-only (inert): a run is identical with/without calling it.
  • meta is opaque: injecting garbage meta into events does not change the EdgeReport.

Synthetic candles only (fast, deterministic). Run:
    python -m pytest tests/interpreters/test_invariant_guards.py -q
"""
from __future__ import annotations

import math
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Sequence, Tuple

_SRC = Path(__file__).resolve().parent.parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.crt_engine_v2 import Candle, Direction
from research.contracts import EdgeReport
from research.measurement.forward_walk import forward_walk
from research.measurement.metrics import EdgeAggregator

from interpreters.adapter import InterpreterHypothesis
from interpreters.contract import BaseInterpreter, EventKind, InterpreterEvent
from interpreters.reference import MovingAverageCrossInterpreter

_BASE = datetime(2025, 1, 1, 0, 0, 0)


def _candles(prices) -> list[Candle]:
    return [Candle(timestamp=_BASE + timedelta(minutes=15 * i), open=p, high=p + 1.0,
                   low=p - 1.0, close=p, volume=1.0, index=i) for i, p in enumerate(prices)]


def _run_chain(interp, candles, *, call_explain=False) -> EdgeReport:
    """Mini end-to-end: adapter.detect over sliding windows → forward_walk → EdgeReport."""
    adapter = InterpreterHypothesis(interp)
    outcomes = []
    for i in range(21, len(candles)):
        window = candles[: i + 1]
        for s in adapter.detect(window, {}, {"instrument": "X"}):
            future = candles[i + 1: i + 1 + 40]
            if future:
                outcomes.append(forward_walk(s, future, max_forward=40,
                                             exit_model="intrabar_fixed"))
        if call_explain:
            interp.explain()                    # telemetry call interleaved with the run
    return EdgeAggregator().aggregate(adapter.name, ["X"], outcomes)


def test_reference_explain_is_inert():
    prices = [100 + 10 * math.sin(i / 5.0) for i in range(200)]
    candles = _candles(prices)
    with_explain = _run_chain(MovingAverageCrossInterpreter(fast_period=5, slow_period=20),
                              candles, call_explain=True)
    without = _run_chain(MovingAverageCrossInterpreter(fast_period=5, slow_period=20),
                         candles, call_explain=False)
    assert with_explain == without              # explain() changes nothing


class _FixedLong(BaseInterpreter):
    """Emits one fixed LONG breakout per bar with a configurable `meta` payload."""
    name = "fixed_long"

    def __init__(self, meta):
        self._meta = meta

    def _observe(self, window: Sequence[Candle], features: dict,
                 ctx: dict) -> Tuple[list[InterpreterEvent], float]:
        bar = window[-1]
        ev = InterpreterEvent(kind=EventKind.BREAKOUT, confidence=0.5, strength=0.5,
                              direction=Direction.LONG, entry=bar.close,
                              sl_atr_mult=1.0, tp_atr_mult=2.0, atr=1.0, meta=self._meta)
        return [ev], 0.5


def test_meta_is_unused():
    prices = [100 + 5 * math.sin(i / 7.0) for i in range(120)]
    candles = _candles(prices)
    clean = _run_chain(_FixedLong(meta={}), candles)
    garbage = _run_chain(_FixedLong(meta={"garbage": 123.456, "pnf_secret": 999,
                                          "leak_attempt": "P&F"}), candles)
    assert clean == garbage                     # opaque meta cannot change the EdgeReport
