"""Program 9 — compression_box_straddle: registration, D4 first-bar gating, oco Signal
shape, box geometry, purity/determinism.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.crt_engine_v2 import Candle                            # noqa: E402
import research.hypotheses                                               # noqa: F401,E402 (register)
from research.candle_state.encoder import CandleStateEncoder             # noqa: E402
from research.hypotheses.compression_box_straddle import CompressionBoxStraddle  # noqa: E402
from research.registry import get_hypothesis                             # noqa: E402


def _c(i, o, h, l, c, v=10.0):
    return Candle(timestamp=datetime(2024, 1, 1) + timedelta(minutes=5 * i),
                  open=o, high=h, low=l, close=c, volume=v, index=i)


def _wide_then_compression(n_tight: int) -> list[Candle]:
    """20 wide bars (high trailing ATR), then `n_tight` tight bars (COMPRESSION states)."""
    bars = [_c(i, 100.0, 101.0, 99.0, 100.0) for i in range(20)]
    for j in range(n_tight):
        i = 20 + j
        bars.append(_c(i, 100.0, 100.15, 99.85, 100.0))
    return bars


def test_registered():
    h = get_hypothesis("compression_box_straddle")
    assert h.name == "compression_box_straddle"
    assert h.family == "transition"


def test_fires_on_first_compression_bar_with_oco_signal():
    h = CompressionBoxStraddle(compression_lookback=5)
    window = _wide_then_compression(1)                    # current bar = FIRST compression bar
    enc = CandleStateEncoder()
    assert enc.encode(window).vol == "COMPRESSION"        # sanity: setup really is compression
    assert enc.encode(window[:-1]).vol != "COMPRESSION"   # ...and the prior bar is not
    sigs = h.detect(window, {}, {"instrument": "TEST"})
    assert len(sigs) == 1
    s = sigs[0]
    assert s.direction == "oco"
    assert s.entry_index == window[-1].index
    # box spans the trailing 5 bars (4 wide + the compression bar)
    assert s.meta["box_high"] == max(float(b.high) for b in window[-5:])
    assert s.meta["box_low"] == min(float(b.low) for b in window[-5:])
    assert s.entry == (s.meta["box_high"] + s.meta["box_low"]) / 2.0   # telemetry midpoint


def test_does_not_refire_inside_a_compression_run():
    """D4: consecutive compression bars must not arm overlapping straddles."""
    h = CompressionBoxStraddle(compression_lookback=5)
    window = _wide_then_compression(2)                    # prior bar ALSO compression
    enc = CandleStateEncoder()
    assert enc.encode(window).vol == "COMPRESSION"
    assert enc.encode(window[:-1]).vol == "COMPRESSION"
    assert h.detect(window, {}, {"instrument": "TEST"}) == []


def test_no_signal_without_compression():
    h = CompressionBoxStraddle(compression_lookback=5)
    bars = [_c(i, 100.0, 101.0, 99.0, 100.0) for i in range(26)]   # all wide
    assert h.detect(bars, {}, {"instrument": "TEST"}) == []


def test_no_signal_on_short_window():
    h = CompressionBoxStraddle(compression_lookback=5)
    assert h.detect(_wide_then_compression(1)[:4], {}, {"instrument": "TEST"}) == []


def test_detect_is_deterministic_and_pure():
    h = CompressionBoxStraddle()
    window = _wide_then_compression(1)
    a = h.detect(window, {}, {"instrument": "T"})
    b = h.detect(window, {}, {"instrument": "T"})
    assert a == b
    # purity: detect took no mutable state from the call (same result on a fresh instance)
    assert CompressionBoxStraddle().detect(window, {}, {"instrument": "T"}) == a
