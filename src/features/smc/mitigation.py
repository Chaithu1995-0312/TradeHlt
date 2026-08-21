"""features.smc.mitigation — Mitigation Block.

Definition (standard ICT/SMC refinement of the order block): once an order block's OUTER zone
(full high/low range) has been touched, the standard teaching is that the CANDLE BODY
(open/close range — narrower than the full wick range) is the deeper, stronger reaction level
on a subsequent return. The "mitigation block" is this inner body-only zone of the SAME origin
candle `order_block.find_active_order_block` already identifies — this module does not
re-detect origins, it derives the tighter zone from the active OB's origin candle and reports
distance to it once the outer zone has already been touched at least once (before that, the
outer OB zone at `order_block.py` is the operative level; the two are deliberately DIFFERENT
distances, not aliases of each other).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Sequence

from features.smc._geometry import Zone, is_mitigated, signed_atr_distance
from features.smc.order_block import _find_break_events, _origin_candle

if TYPE_CHECKING:
    from config_layer.crt_engine_v2 import Candle


def find_active_mitigation_block(window: "Sequence[Candle]", k: int) -> Optional[Zone]:
    """The body-only inner zone of the most recent OB origin whose OUTER zone has already been
    touched at least once (mitigation "in progress") and whose INNER (body) zone has not yet
    itself been fully entered. Pure; only inspects `window`."""
    bars = list(window)
    if not bars:
        return None
    events = _find_break_events(bars, k)
    for break_pos, bullish in reversed(events):
        origin_pos = _origin_candle(bars, break_pos, bullish)
        if origin_pos is None:
            continue
        origin = bars[origin_pos]
        outer = Zone(high=origin.high, low=origin.low, formed_at_index=origin.index, bullish=bullish)
        # Scan from the CONFIRMING BREAK, not the origin — see order_block.py's identical
        # fix: the break candle itself almost always overlaps the origin's range.
        later = bars[break_pos + 1:]
        outer_touched = any(is_mitigated(outer, b) for b in later)
        if not outer_touched:
            continue   # outer zone not yet touched -> mitigation block not yet "live"
        body_high = max(origin.open, origin.close)
        body_low = min(origin.open, origin.close)
        if body_high <= body_low:
            continue   # degenerate (doji with open==close) -- no usable inner zone
        inner = Zone(high=body_high, low=body_low, formed_at_index=origin.index, bullish=bullish)
        inner_touched = any(is_mitigated(inner, b) for b in later)
        if not inner_touched:
            return inner
    return None


def mitigation_block_distance(window: "Sequence[Candle]", k: int, atr: float) -> float:
    """Signed, ATR-normalized, tanh-bounded distance from `window[-1].close` to the nearest
    live mitigation block's near edge. `0.0` if none exists."""
    zone = find_active_mitigation_block(window, k)
    if zone is None:
        return 0.0
    close = window[-1].close
    if zone.bullish:
        return signed_atr_distance(close, zone.high, atr, favorable_sign=1)
    return signed_atr_distance(close, zone.low, atr, favorable_sign=-1)
