"""features.smc.breaker — Breaker Block detection.

Definition (standard ICT/SMC): a breaker forms when an order block is FULLY VIOLATED — a later
candle CLOSES beyond the zone's far edge (not just a wick touch/mitigation, a full close-through
invalidation). The broken zone then FLIPS polarity: a bullish OB (support) that failed becomes
a bearish breaker (expected resistance on retest from below); a bearish OB that failed becomes
a bullish breaker (expected support on retest from above).

Reuses `order_block`'s break-event/origin detection (intra-package reuse — both live in
`features.smc`, unlike the research/features boundary elsewhere in this program) rather than
re-deriving the same swing/origin logic a third time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Sequence

from features.smc._geometry import Zone, is_mitigated, signed_atr_distance
from features.smc.order_block import _find_break_events, _origin_candle

if TYPE_CHECKING:
    from config_layer.crt_engine_v2 import Candle


def find_active_breaker(
    window: "Sequence[Candle]", k: int,
    break_events: Optional[list[tuple[int, bool]]] = None,
) -> Optional[Zone]:
    """The most recent un-retested breaker as of `window[-1]`. A breaker exists once an OB's
    far edge is fully closed-through by a LATER bar (not the origin's own break bar); it stays
    "active" until price retests (mitigates) the flipped zone. Pure; only inspects `window`.

    `break_events` is an optional PRECOMPUTED `_find_break_events(window, k)` result. It exists
    only so a caller that needs several of the three break-event families on the SAME window
    (order block / breaker / mitigation block) can pay for that scan once instead of three
    times — `_find_break_events` is pure, so passing its own output back in is by construction
    identical to recomputing it. Omitting it (the default) reproduces the original behaviour
    bit-for-bit; `tests/test_smc_break_event_memo.py` pins that equivalence.
    """
    bars = list(window)
    if not bars:
        return None
    events = _find_break_events(bars, k) if break_events is None else break_events
    for break_pos, bullish in reversed(events):
        origin_pos = _origin_candle(bars, break_pos, bullish)
        if origin_pos is None:
            continue
        origin = bars[origin_pos]
        ob_zone = Zone(high=origin.high, low=origin.low, formed_at_index=origin.index, bullish=bullish)
        # Full violation: a later bar CLOSES beyond the OB's far edge (opposite of the OB's
        # own favorable side) -- for a bullish OB the far edge is its low; for a bearish OB
        # the far edge is its high.
        violated_at: Optional[int] = None
        for p in range(origin_pos + 1, len(bars)):
            c = bars[p]
            if bullish and c.close < ob_zone.low:
                violated_at = p
                break
            if (not bullish) and c.close > ob_zone.high:
                violated_at = p
                break
        if violated_at is None:
            continue   # never broken -> not a breaker (still a live OB, order_block.py's domain)
        breaker_zone = Zone(
            high=ob_zone.high, low=ob_zone.low, formed_at_index=ob_zone.formed_at_index,
            bullish=not bullish,   # polarity flip
        )
        retested = any(is_mitigated(breaker_zone, b) for b in bars[violated_at + 1:])
        if not retested:
            return breaker_zone
    return None


def breaker_distance(
    window: "Sequence[Candle]", k: int, atr: float,
    break_events: Optional[list[tuple[int, bool]]] = None,
) -> float:
    """Signed, ATR-normalized, tanh-bounded distance from `window[-1].close` to the nearest
    active (un-retested) breaker's near edge. `0.0` if none exists."""
    zone = find_active_breaker(window, k, break_events)
    if zone is None:
        return 0.0
    close = window[-1].close
    if zone.bullish:
        return signed_atr_distance(close, zone.high, atr, favorable_sign=1)
    return signed_atr_distance(close, zone.low, atr, favorable_sign=-1)
