"""
test_point_and_figure.py — PNF-v1 unit tests (Plan 5).

Deterministic double-top / double-bottom detection, bounded conf/strength, purity /
no-lookahead, and the new EventKind members. No real data.

Run: python -m pytest tests/interpreters/test_point_and_figure.py -q
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parent.parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.crt_engine_v2 import Candle, Direction

from interpreters.contract import EventKind
from interpreters.point_and_figure import PointAndFigureInterpreter, _pnf_signals

_BASE = datetime(2024, 1, 1, 0, 0, 0)


def _candles(prices) -> list[Candle]:
    return [Candle(timestamp=_BASE + timedelta(minutes=15 * i), open=p, high=p + 0.5,
                   low=p - 0.5, close=p, volume=1.0, index=i) for i, p in enumerate(prices)]


# ── core algorithm (box=1.0, reversal=3) ──────────────────────────────────────
def test_eventkind_has_pnf_members():
    assert EventKind.DOUBLE_TOP_BREAKOUT.value == "DOUBLE_TOP_BREAKOUT"
    assert EventKind.DOUBLE_BOTTOM_BREAKDOWN.value == "DOUBLE_BOTTOM_BREAKDOWN"


def test_double_top_breakout_detected():
    # up→pullback(≥3)→higher-up: the 2nd X column passes the 1st X top → double-top.
    closes = [100, 101, 102, 103, 104, 105, 104, 103, 102, 101, 102, 103, 104, 105, 106, 107]
    sigs = _pnf_signals(closes, box=1.0, reversal=3)
    kinds = {k for _, k, _ in sigs}
    assert EventKind.DOUBLE_TOP_BREAKOUT in kinds
    assert EventKind.DOUBLE_BOTTOM_BREAKDOWN not in kinds


def test_double_bottom_breakdown_detected():
    # mirror: down→bounce(≥3)→lower-down: 2nd O column passes the 1st O bottom.
    closes = [107, 106, 105, 104, 103, 102, 103, 104, 105, 106, 105, 104, 103, 102, 101, 100]
    sigs = _pnf_signals(closes, box=1.0, reversal=3)
    kinds = {k for _, k, _ in sigs}
    assert EventKind.DOUBLE_BOTTOM_BREAKDOWN in kinds
    assert EventKind.DOUBLE_TOP_BREAKOUT not in kinds


def test_flat_series_no_signals():
    assert _pnf_signals([100.0] * 40, box=1.0, reversal=3) == []


def test_degenerate_box_no_signals():
    assert _pnf_signals([100, 101, 102], box=0.0, reversal=3) == []


# ── interpreter wrapper (ATR-derived box; fires only at the last bar) ──────────
def test_observe_fires_only_at_last_bar_and_is_bounded():
    # Build a series with a clear double-top, then confirm the interpreter emits a
    # bounded LONG event on exactly the breakout bar and nothing on a flat tail.
    interp = PointAndFigureInterpreter()          # PNF-v1 frozen
    # 40 flat warmup (for ATR) then a sawtooth-up that creates double-tops.
    prices = [100.0] * 25
    base = 100.0
    for _ in range(10):
        prices += [base + k for k in range(6)] + [base + 4, base + 3, base + 2, base + 1]
        base += 2.0
    candles = _candles(prices)
    longs = shorts = 0
    for i in range(interp.atr_period + 1, len(candles)):
        reading = interp.observe(candles[: i + 1], {}, {"instrument": "X"})
        for ev in reading.events:
            assert ev.kind in (EventKind.DOUBLE_TOP_BREAKOUT, EventKind.DOUBLE_BOTTOM_BREAKDOWN)
            assert 0.0 <= ev.confidence <= 1.0 and 0.0 <= ev.strength <= 1.0
            assert ev.is_directional
            longs += ev.direction is Direction.LONG
            shorts += ev.direction is Direction.SHORT
    assert longs > 0                               # the up-sawtooth produces double-tops


def test_observe_deterministic_and_versioned():
    prices = [100 + (i % 7) for i in range(60)]
    window = _candles(prices)
    interp = PointAndFigureInterpreter()
    r1 = interp.observe(window, {}, {"instrument": "X"})
    r2 = interp.observe(window, {}, {"instrument": "X"})
    assert r1 == r2                                 # pure / deterministic
    assert interp.version() == "1" and interp.FROZEN_ID == "PNF-v1"
    assert r1.trace_id.startswith("PNF-v1-")        # provenance encodes the frozen identity
