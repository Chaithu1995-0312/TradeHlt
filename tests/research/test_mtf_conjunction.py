"""Tests for MultiTFConjunctionBuilder — resample-causality / no-lookahead + determinism.

The load-bearing property is that the higher-timeframe state in the conjunction is built ONLY
from fully-closed H1/H4 buckets — never from the in-progress bucket containing the current M15
bar. A leak here would invent a same-bar HTF edge that does not exist live.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.crt_engine_v2 import Candle                 # noqa: E402
from research.candle_state.encoder import CandleStateEncoder  # noqa: E402
from research.candle_state.mtf_conjunction import (           # noqa: E402
    MultiTFConjunctionBuilder, _MISSING,
)
from research.resample import resample                        # noqa: E402


def _m15_series(n, *, start=datetime(2024, 1, 1, 0, 0, 0), base=100.0):
    out = []
    prev = base
    for i in range(n):
        o = prev
        cl = o + (0.4 if i % 3 else -0.3)
        hi = max(o, cl) + 0.2 + 0.001 * i
        lo = min(o, cl) - 0.2 - 0.001 * i
        out.append(Candle(timestamp=start + timedelta(minutes=15 * i),
                          open=o, high=hi, low=lo, close=cl, volume=1.0 + 0.5 * i, index=i))
        prev = cl
    return out


def test_key_format_and_axes():
    b = MultiTFConjunctionBuilder()
    series = _m15_series(400)            # plenty of closed H1/H4 buckets
    conj = b.build(series)
    assert conj.key.startswith("M15=")
    assert "|H1=" in conj.key and "|H4=" in conj.key
    assert conj.h1 is not None and conj.h4 is not None


def test_warmup_missing_htf_is_labeled_not_invented():
    b = MultiTFConjunctionBuilder()
    # Only 3 M15 bars: the single in-progress H1 bucket is dropped → no closed H1/H4.
    conj = b.build(_m15_series(3))
    assert conj.h1 is None and conj.h4 is None
    assert f"H1={_MISSING}" in conj.key and f"H4={_MISSING}" in conj.key


def test_no_lookahead_htf_state_matches_closed_buckets_only():
    """The H1 state in the conjunction must equal encoding the LAST CLOSED H1 bucket —
    i.e. it must NOT depend on the current (in-progress) hour's M15 bars."""
    enc = CandleStateEncoder()
    b = MultiTFConjunctionBuilder(enc)
    series = _m15_series(200)
    conj = b.build(series)

    closed_h1 = resample(series, "H1")          # trailing in-progress bucket already dropped
    expected = enc.encode(closed_h1[-b.htf_window:])
    assert conj.h1 == expected


def test_appending_bars_in_same_hour_does_not_change_htf_state():
    """Adding more M15 bars that stay WITHIN the current in-progress hour must not change the
    last-closed H1 state (the in-progress bucket is dropped either way)."""
    b = MultiTFConjunctionBuilder()
    # 8 bars = hours 00 & 01 fully present; bar 8 starts hour 02 (in-progress).
    base = _m15_series(9)                        # ends mid hour-02 (1 bar into it)
    more = _m15_series(11)                       # 3 bars into hour-02, same closed hours 00/01
    assert b.build(base).h1 == b.build(more).h1


def test_build_is_deterministic():
    b = MultiTFConjunctionBuilder()
    series = _m15_series(300)
    assert b.build(series) == b.build(series)


def test_empty_window_raises():
    b = MultiTFConjunctionBuilder()
    try:
        b.build([])
        assert False, "expected ValueError"
    except ValueError:
        pass
