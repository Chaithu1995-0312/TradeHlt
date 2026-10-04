"""HTFBuilder window size is only a complete-id clock. n=16 flips every 16 pushes."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from config_layer.crt_engine_v2 import Candle
from runtime.backtest_v2 import HTFBuilder

_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _c(i: int) -> Candle:
    return Candle(
        timestamp=_T0 + timedelta(minutes=15 * i),
        open=1.0, high=1.0, low=1.0, close=1.0, index=i,
    )


def test_window_16_flips_only_on_every_16th_bar():
    htf = HTFBuilder(16, "XAUUSD")
    flips = []
    for i in range(48):
        done = htf.push(_c(i))
        if done:
            flips.append((i, htf.current_htf_id))
    assert [i for i, _ in flips] == [15, 31, 47]
    assert flips[0][1].endswith("HTF-000001")
    assert flips[1][1].endswith("HTF-000002")
    assert flips[2][1].endswith("HTF-000003")


def test_window_4_flips_every_4th_bar():
    htf = HTFBuilder(4, "XAUUSD")
    flip_bars = [i for i in range(16) if htf.push(_c(i))]
    assert flip_bars == [3, 7, 11, 15]
