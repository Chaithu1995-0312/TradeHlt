"""features.smc.rejection — the card's rejection block.

The most recent live wick of a confirmed causal swing. A bearish block is the upper wick
of a swing high: [body top, high], with body top = high - upper_wick. A bullish block is
the lower wick of a swing low: [low, body bottom], with body bottom = low + lower_wick.
A zero wick is not a block.

The swing is the same causal window as features.smc._geometry.detect_causal_swings: bar j
is an extreme of [j-k, j+k], scanned recent to old, ties by == max / == min. The block
goes live at the confirmation bar j+k. Bars through j+k are the confirming window and do
not kill it. A later bar kills a bearish block when its close is above the wick high or
its high reaches the body top. The bullish mirror is a close below the wick low or a low
that reaches the body bottom.

Pure. `k` is an argument. No config read. No scratchpad import.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Sequence

from features import candle_math as _cm
from features.smc._geometry import Zone, signed_atr_distance

if TYPE_CHECKING:
    from config_layer.crt_engine_v2 import Candle


def find_live_rejection_blocks(
    window: "Sequence[Candle]", k: int,
) -> tuple[Optional[Zone], Optional[Zone]]:
    """(bullish block, bearish block) still live as of window[-1]. Either may be None."""
    bars = list(window)
    n = len(bars)
    bull: Optional[Zone] = None
    bear: Optional[Zone] = None
    if k < 0 or n < 2 * k + 1:
        return None, None
    for j in range(n - 1 - k, k - 1, -1):
        seg = bars[j - k: j + k + 1]
        c = bars[j]
        later = bars[j + k + 1:]
        if bear is None and c.high == max(b.high for b in seg):
            wick = _cm.upper_wick(c.open, c.high, c.close)
            if wick > 0:
                body_top = c.high - wick
                dead = any(b.close > c.high or b.high >= body_top for b in later)
                if not dead:
                    bear = Zone(high=c.high, low=body_top, formed_at_index=c.index, bullish=False)
        if bull is None and c.low == min(b.low for b in seg):
            wick = _cm.lower_wick(c.open, c.low, c.close)
            if wick > 0:
                body_bottom = c.low + wick
                dead = any(b.close < c.low or b.low <= body_bottom for b in later)
                if not dead:
                    bull = Zone(low=c.low, high=body_bottom, formed_at_index=c.index, bullish=True)
        if bull is not None and bear is not None:
            break
    return bull, bear


def rejection_bull_present(window: "Sequence[Candle]", k: int) -> float:
    """FM-124: 1.0 when a live bullish rejection block exists, else 0.0."""
    bull, _bear = find_live_rejection_blocks(window, k)
    return 1.0 if bull is not None else 0.0


def rejection_bear_present(window: "Sequence[Candle]", k: int) -> float:
    """FM-125: 1.0 when a live bearish rejection block exists, else 0.0."""
    _bull, bear = find_live_rejection_blocks(window, k)
    return 1.0 if bear is not None else 0.0


def rejection_bull_distance(window: "Sequence[Candle]", k: int, atr: float) -> float:
    """FM-126: signed ATR distance from the close to the bullish block's near edge (body bottom).

    0.0 when no block exists, so present == 0 implies distance == 0. Favorable side is above
    that edge, matching order_block_distance on a bullish zone.
    """
    bull, _bear = find_live_rejection_blocks(window, k)
    if bull is None or not window:
        return 0.0
    return signed_atr_distance(window[-1].close, bull.high, atr, favorable_sign=1)


def rejection_bear_distance(window: "Sequence[Candle]", k: int, atr: float) -> float:
    """FM-127: signed ATR distance from the close to the bearish block's near edge (body top).

    0.0 when no block exists. Favorable side is below that edge, matching order_block_distance
    on a bearish zone.
    """
    _bull, bear = find_live_rejection_blocks(window, k)
    if bear is None or not window:
        return 0.0
    return signed_atr_distance(window[-1].close, bear.low, atr, favorable_sign=-1)
