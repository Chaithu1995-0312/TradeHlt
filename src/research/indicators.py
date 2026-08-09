"""indicators.py — small, dependency-light technical helpers for hypotheses/controls.

Pure stdlib, no lookahead: every helper consumes only the bars it is given (the past
window up to and including the current bar). Hypotheses call these inside detect().
"""

from __future__ import annotations

from typing import Sequence


def atr(window: Sequence, period: int = 14) -> float:
    """Average True Range over the last `period` bars of `window`.

    `window` is an ordered sequence of Candle-like bars (.high/.low/.close). Uses a
    simple mean of true ranges (not Wilder smoothing) for determinism. Falls back to
    whatever history is available if fewer than `period+1` bars exist; returns 0.0 if
    it cannot be computed.
    """
    bars = list(window)
    if len(bars) < 2:
        return 0.0
    trs: list[float] = []
    lookback = bars[-(period + 1):] if len(bars) > period else bars
    for prev, cur in zip(lookback[:-1], lookback[1:]):
        hi, lo, pc = float(cur.high), float(cur.low), float(prev.close)
        trs.append(max(hi - lo, abs(hi - pc), abs(lo - pc)))
    return sum(trs) / len(trs) if trs else 0.0


def sma(window: Sequence, period: int, field: str = "close") -> float:
    """Simple moving average of `field` over the last `period` bars. 0.0 if empty."""
    bars = list(window)[-period:]
    if not bars:
        return 0.0
    return sum(float(getattr(b, field)) for b in bars) / len(bars)
