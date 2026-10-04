"""features.smc.order_block — Order Block (OB) detection.

Definition (standard ICT/SMC): a BULLISH order block is the last BEARISH (down-close) candle
immediately preceding a structural break to the upside (a later close above the most recent
confirmed swing high). A BEARISH order block is the symmetric case: the last BULLISH candle
before a close below the most recent confirmed swing low. The OB zone is the origin candle's
full [low, high] range.

An OB is MITIGATED once price later trades back into its zone (any high/low overlap — see
`_geometry.is_mitigated`). `find_active_order_block` returns the most recent UNMITIGATED OB as
of the window's last bar, scanning backward through break events until an unmitigated one is
found (or none exists).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Sequence

from features.smc._geometry import Zone, detect_causal_swings, is_mitigated, signed_atr_distance

if TYPE_CHECKING:
    from config_layer.crt_engine_v2 import Candle


def _origin_candle(bars: "Sequence[Candle]", break_pos: int, bullish: bool) -> Optional[int]:
    """Scan backward from `break_pos - 1` for the nearest opposite-colored candle (the OB
    origin). Bullish break -> look for a bearish (close<open) origin; bearish break -> bullish
    (close>open) origin. Returns its position in `bars`, or None if none precedes the break."""
    want_bearish_origin = bullish
    for j in range(break_pos - 1, -1, -1):
        c = bars[j]
        is_bearish = c.close < c.open
        if want_bearish_origin and is_bearish:
            return j
        if (not want_bearish_origin) and (c.close > c.open):
            return j
    return None


def _find_break_events(bars: "Sequence[Candle]", k: int) -> list[tuple[int, bool]]:
    """All (position, bullish) structural-break events in `bars`, oldest-first. A break at
    position `i` is `bars[i].close` clearing the most recent swing confirmed strictly before
    `i` (using only `bars[:i]` — no lookahead)."""
    events: list[tuple[int, bool]] = []
    n = len(bars)
    for i in range(2 * k + 1, n):
        sh, sl = detect_causal_swings(bars[:i], k)
        if sh is not None and bars[i].close > sh.price:
            events.append((i, True))
        elif sl is not None and bars[i].close < sl.price:
            events.append((i, False))
    return events


def find_active_order_block(
    window: "Sequence[Candle]", k: int,
    break_events: Optional[list[tuple[int, bool]]] = None,
) -> Optional[Zone]:
    """The most recent UNMITIGATED order block as of `window[-1]`. Pure; only inspects
    `window`. Returns None if no break event has ever occurred, or every OB formed so far has
    since been mitigated.

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
        zone = Zone(high=origin.high, low=origin.low, formed_at_index=origin.index, bullish=bullish)
        # Mitigated by any bar strictly AFTER the CONFIRMING BREAK (not after the origin
        # candle) — the break candle itself almost always geometrically overlaps the origin's
        # range (price starts near the zone and moves away from it), so scanning from
        # origin_pos+1 would misread the very candle that confirms the OB as also mitigating
        # it. An OB only becomes a trackable "live" zone once the break confirms it.
        mitigated = any(is_mitigated(zone, b) for b in bars[break_pos + 1:])
        if not mitigated:
            return zone
    return None


def order_block_distance(
    window: "Sequence[Candle]", k: int, atr: float,
    break_events: Optional[list[tuple[int, bool]]] = None,
) -> float:
    """Signed, ATR-normalized, tanh-bounded distance from `window[-1].close` to the nearest
    active (unmitigated) order block's near edge. `0.0` if none exists. Positive = price is on
    the favorable side of the zone (above a bullish OB's top, below a bearish OB's bottom)."""
    zone = find_active_order_block(window, k, break_events)
    if zone is None:
        return 0.0
    close = window[-1].close
    if zone.bullish:
        return signed_atr_distance(close, zone.high, atr, favorable_sign=1)
    return signed_atr_distance(close, zone.low, atr, favorable_sign=-1)
