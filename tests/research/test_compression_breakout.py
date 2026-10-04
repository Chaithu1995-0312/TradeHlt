"""Tests for the compression_breakout Stage-2 hypothesis — registration, Signal emission on a
compression→breakout setup, the compression precondition, and no-lookahead.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.crt_engine_v2 import Candle                       # noqa: E402
import research.hypotheses                                          # noqa: F401,E402 (register)
from research.candle_state.encoder import CandleStateEncoder        # noqa: E402
from research.hypotheses.compression_breakout import CompressionBreakout  # noqa: E402
from research.registry import get_hypothesis                        # noqa: E402


def _c(i, o, h, l, c, v=10.0):
    return Candle(timestamp=datetime(2024, 1, 1) + timedelta(minutes=15 * i),
                  open=o, high=h, low=l, close=c, volume=v, index=i)


def _compression_then_break(direction="long"):
    """Wide-range warmup (sets a high trailing ATR), then a tight compression box, then a break."""
    bars = []
    # 20 wide bars → trailing ATR large (~2.0)
    for i in range(20):
        bars.append(_c(i, 100.0, 101.0, 99.0, 100.0, 10.0))
    # tight compression box around 100 (range ~0.3 << ATR → COMPRESSION), 6 bars
    for j in range(6):
        i = 20 + j
        bars.append(_c(i, 100.0, 100.15, 99.85, 100.0, 10.0))
    # breakout bar
    i = 26
    if direction == "long":
        bars.append(_c(i, 100.0, 100.6, 99.9, 100.5, 10.0))   # closes above comp box high
    else:
        bars.append(_c(i, 100.0, 100.1, 99.4, 99.5, 10.0))    # closes below comp box low
    return bars


def test_registered():
    assert get_hypothesis("compression_breakout").name == "compression_breakout"
    assert get_hypothesis("compression_breakout").family == "transition"


def test_emits_long_signal_on_compression_breakout():
    h = CompressionBreakout(compression_lookback=5)
    window = _compression_then_break("long")
    sigs = h.detect(window, {}, {"instrument": "TEST"})
    assert len(sigs) == 1
    s = sigs[0]
    assert s.direction == "long"
    assert s.entry_index == window[-1].index          # entry at the break bar, no lookahead
    assert s.entry == window[-1].close
    assert s.instrument == "TEST"


def test_emits_short_signal():
    h = CompressionBreakout(compression_lookback=5)
    sigs = h.detect(_compression_then_break("short"), {}, {"instrument": "TEST"})
    assert len(sigs) == 1 and sigs[0].direction == "short"


def test_no_signal_without_compression_precondition():
    """If the pre-break bar is NOT a compression state, no signal — distinguishes this from
    plain expansion_breakout."""
    h = CompressionBreakout(compression_lookback=5)
    enc = CandleStateEncoder()
    # all wide bars then a break → the pre-break bar is NOT compression
    bars = [_c(i, 100.0, 101.0, 99.0, 100.0, 10.0) for i in range(26)]
    bars.append(_c(26, 100.0, 102.0, 99.9, 101.8, 10.0))
    assert enc.encode(bars[:-1]).vol != "COMPRESSION"
    assert h.detect(bars, {}, {"instrument": "TEST"}) == []


def test_no_signal_when_inside_box():
    """Compression present but the current bar stays inside the box → no break, no signal."""
    h = CompressionBreakout(compression_lookback=5)
    window = _compression_then_break("long")
    window[-1] = _c(26, 100.0, 100.12, 99.9, 100.05, 10.0)   # stays inside the box
    assert h.detect(window, {}, {"instrument": "TEST"}) == []


def test_detect_is_deterministic():
    h = CompressionBreakout()
    window = _compression_then_break("long")
    assert h.detect(window, {}, {"instrument": "T"}) == h.detect(window, {}, {"instrument": "T"})
