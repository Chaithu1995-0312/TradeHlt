"""M1 measurement-core tests: forward_walk no-lookahead + hand-computed outcomes."""

from dataclasses import dataclass
from datetime import datetime

import pytest

from research.contracts import Signal
from research.measurement.forward_walk import forward_walk


@dataclass
class Bar:
    """Minimal Candle-like bar (forward_walk duck-types .high/.low/.close/.index)."""
    high: float
    low: float
    close: float
    index: int


def _long_signal(entry_index: int = 0) -> Signal:
    # risk_distance = 1.0, reward_distance = 2.0  (atr=1, sl x1, tp x2)
    return Signal(
        instrument="TEST", timestamp=datetime(2026, 1, 1), entry_index=entry_index,
        direction="long", entry=100.0, sl_atr_mult=1.0, tp_atr_mult=2.0, atr=1.0,
    )


def test_clean_tp_hit():
    sig = _long_signal()
    # Bar reaches TP (>=102) with low above the trailed stop (101.5) -> clean TP branch.
    out = forward_walk(sig, [Bar(high=102.0, low=101.6, close=101.9, index=1)])
    assert out.outcome == "TP_HIT"
    assert out.rr_achieved == 2.0
    assert out.time_to_tp == 1
    assert out.time_to_failure is None
    assert out.reached_1r is True
    assert out.duration_candles == 1


def test_trailing_sl_hit():
    sig = _long_signal()
    out = forward_walk(sig, [Bar(high=100.2, low=98.5, close=98.8, index=1)])
    assert out.outcome == "SL_HIT"
    assert out.rr_achieved == -1.0           # stop at original SL (99) = -1R
    assert out.time_to_failure == 1
    assert out.time_to_tp is None
    assert out.reached_1r is False
    assert out.mae == pytest.approx(-1.5)


def test_timeout_marks_to_last_close():
    sig = _long_signal()
    bars = [
        Bar(high=100.3, low=99.8, close=100.1, index=1),
        Bar(high=100.4, low=99.9, close=100.2, index=2),
    ]
    out = forward_walk(sig, bars, max_forward=2)
    assert out.outcome == "TIMEOUT"
    assert out.rr_achieved == pytest.approx(0.2)
    assert out.duration_candles == 2
    assert out.time_to_failure is None
    assert out.reached_1r is False


def test_short_clean_tp():
    sig = Signal(
        instrument="TEST", timestamp=datetime(2026, 1, 1), entry_index=0,
        direction="short", entry=100.0, sl_atr_mult=1.0, tp_atr_mult=2.0, atr=1.0,
    )
    out = forward_walk(sig, [Bar(high=98.4, low=98.0, close=98.1, index=1)])
    assert out.outcome == "TP_HIT"
    assert out.rr_achieved == 2.0
    assert out.reached_1r is True


def test_max_forward_caps_simulation():
    sig = _long_signal()
    # 100 flat bars, but only 3 should be walked.
    bars = [Bar(high=100.1, low=99.9, close=100.0, index=i) for i in range(1, 101)]
    out = forward_walk(sig, bars, max_forward=3)
    assert out.outcome == "TIMEOUT"
    assert out.duration_candles == 3


def test_lookahead_guard_raises():
    sig = _long_signal(entry_index=10)
    # A bar at the entry index (or earlier) is contamination -> must raise.
    with pytest.raises(ValueError, match="lookahead"):
        forward_walk(sig, [Bar(high=101.0, low=99.0, close=100.5, index=10)])


def test_nonpositive_risk_rejected():
    sig = Signal(
        instrument="TEST", timestamp=datetime(2026, 1, 1), entry_index=0,
        direction="long", entry=100.0, sl_atr_mult=1.0, tp_atr_mult=2.0, atr=0.0,
    )
    with pytest.raises(ValueError, match="risk_distance"):
        forward_walk(sig, [Bar(high=101.0, low=99.0, close=100.5, index=1)])
