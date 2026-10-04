"""Market ZONES MKT-Z01..Z05.

Lifecycle (FILLED is PROPOSED and is not emitted):

    MKT-Z01 range        ACTIVE -> REFOUNDED on MKT-E12
    MKT-Z02 fvg          ACTIVE -> TOUCHED; available_at = close of bar i+1
    MKT-Z03 order_block  ACTIVE -> TOUCHED -> BROKEN; one zone per break onset
    MKT-Z04 breaker      FLIPPED -> TOUCHED; available_at = first bar the finder returns it
    MKT-Z05 ob_body_zone ACTIVE -> TOUCHED; available_at = first bar the finder returns it

Absence is `present=False` with low/high None. A zone that has been touched or broken
stays present. The per-bar view is the most recently available zone of that type.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional, Sequence

from features.smc.breaker import find_active_breaker
from features.smc.fvg import _find_fvg_events
from features.smc.mitigation import find_active_mitigation_block
from features.smc.order_block import _find_break_events, _origin_candle

from semantics import geometry as gp
from semantics.identity import parameterization_id
from semantics.market.events import CLOCK_ROLLOVER, MarketEvent
from semantics.market.levels import LIQUIDITY_LEVEL, Level
from semantics.types import Bar, Side, ZoneStatus

RANGE = "MKT-Z01"
FVG = "MKT-Z02"
ORDER_BLOCK = "MKT-Z03"
BREAKER = "MKT-Z04"
OB_BODY = "MKT-Z05"


@dataclass(frozen=True)
class MarketZone:
    concept_id: str
    parameterization_id: str
    present: bool
    status: Optional[ZoneStatus]
    low: Optional[float]
    high: Optional[float]
    formed_at: Optional[int]
    available_at: Optional[int]
    bullish: Optional[bool] = None
    founding: Optional[str] = None
    clock: Optional[str] = None


def absent(concept_id: str, param_id: str) -> MarketZone:
    return MarketZone(concept_id, param_id, False, None, None, None, None, None)


def close_relation(zone: MarketZone, bar: Bar) -> Optional[float]:
    """None when no zone is present. 0.0 when close is inside or exactly on an edge."""
    if not zone.present or zone.low is None or zone.high is None:
        return None
    if zone.low <= bar.close <= zone.high:
        return 0.0
    if bar.close > zone.high:
        return bar.close - zone.high
    return bar.close - zone.low


def range_zone(upper: Level, lower: Level) -> MarketZone:
    """MKT-Z01 from two MKT-L01 edges of one founding and one formation."""
    if upper.concept_id != LIQUIDITY_LEVEL or lower.concept_id != LIQUIDITY_LEVEL:
        raise ValueError("a range is two liquidity levels")
    if upper.founding != lower.founding:
        raise ValueError(f"range edges founding {upper.founding!r} != {lower.founding!r}")
    if upper.formed_at != lower.formed_at:
        raise ValueError("range edges must share a formation bar")
    if upper.side is not Side.UPPER or lower.side is not Side.LOWER:
        raise ValueError("range edges must be UPPER and LOWER")
    if upper.price < lower.price:
        raise ValueError(f"upper {upper.price} < lower {lower.price}")
    if upper.clock != lower.clock or upper.timeframe != lower.timeframe:
        raise ValueError("range edges must share timeframe and clock")
    pid = parameterization_id(RANGE, {"founding": upper.founding}, ("founding",))
    return MarketZone(
        RANGE, pid, True, ZoneStatus.ACTIVE, lower.price, upper.price,
        upper.formed_at, max(upper.available_at, lower.available_at),
        founding=upper.founding, clock=upper.clock,
    )


def apply_clock_rollover(zone: MarketZone, event: MarketEvent) -> MarketZone:
    """MKT-Z01 becomes REFOUNDED when an MKT-E12 event is applied. Other zones are unchanged."""
    if zone.concept_id != RANGE or event.concept_id != CLOCK_ROLLOVER or not zone.present:
        return zone
    return replace(zone, status=ZoneStatus.REFOUNDED)


def _pid(concept_id: str, params: dict, bearing: tuple[str, ...]) -> str:
    return parameterization_id(concept_id, params, bearing)


def _broken(bar: Bar, low: float, high: float, bullish: bool) -> bool:
    if bullish:
        return gp.beyond(bar, low, Side.LOWER)
    return gp.beyond(bar, high, Side.UPPER)


def fvg_views(bars: Sequence[Bar]) -> tuple[MarketZone, ...]:
    """MKT-Z02 per bar. `available_at` is the bar after the middle candle (close of i+1)."""
    pid = _pid(FVG, {}, ())
    seq = list(bars)
    if not seq:
        return ()
    by_index = {b.index: pos for pos, b in enumerate(seq)}
    found = []
    for zone in _find_fvg_events(seq):
        pos = by_index.get(zone.formed_at_index)
        if pos is None or pos + 1 >= len(seq):
            continue
        found.append((zone, seq[pos + 1].index))
    out: list[MarketZone] = []
    for i, bar in enumerate(seq):
        eligible = [(z, av) for z, av in found if av <= bar.index]
        if not eligible:
            out.append(absent(FVG, pid))
            continue
        zone, available_at = eligible[-1]
        status = ZoneStatus.ACTIVE
        for b in seq[: i + 1]:
            if b.index <= available_at:
                continue
            if gp.overlap(b, zone.low, zone.high):
                status = ZoneStatus.TOUCHED
                break
        out.append(MarketZone(
            FVG, pid, True, status, zone.low, zone.high, zone.formed_at_index, available_at,
            bullish=zone.bullish,
        ))
    return tuple(out)


def _onsets(bars: Sequence[Bar], k: int) -> list[dict]:
    """One order-block zone per onset. Later bars that re-fire the same origin are not new zones.

    `_find_break_events` emits a break on every bar beyond the swing (recorded on MKT-Z03).
    Collapsing a consecutive same-origin run to its first bar is the MKT-E02 onset reading.
    The finder itself is not modified.
    """
    seq = list(bars)
    events = _find_break_events(seq, k)
    onsets: list[dict] = []
    prev_key = None
    for break_pos, bullish in events:
        origin_pos = _origin_candle(seq, break_pos, bullish)
        if origin_pos is None:
            prev_key = None
            continue
        origin = seq[origin_pos]
        key = (origin.index, bullish, float(origin.low), float(origin.high))
        if key == prev_key:
            continue
        prev_key = key
        onsets.append({
            "low": float(origin.low),
            "high": float(origin.high),
            "bullish": bullish,
            "formed_at": origin.index,
            "available_at": seq[break_pos].index,
        })
    return onsets


def _ob_status(bars: Sequence[Bar], spec: dict, upto: int) -> ZoneStatus:
    status = ZoneStatus.ACTIVE
    for bar in bars:
        if bar.index < spec["available_at"] or bar.index > upto:
            continue
        if _broken(bar, spec["low"], spec["high"], spec["bullish"]):
            return ZoneStatus.BROKEN
        if bar.index > spec["available_at"] and gp.overlap(bar, spec["low"], spec["high"]):
            status = ZoneStatus.TOUCHED
    return status


def order_block_views(bars: Sequence[Bar], *, k: int) -> tuple[MarketZone, ...]:
    """MKT-Z03 per bar. A BROKEN zone stays present."""
    pid = _pid(ORDER_BLOCK, {"k": int(k)}, ("k",))
    seq = list(bars)
    specs = _onsets(seq, k)
    out: list[MarketZone] = []
    for bar in seq:
        eligible = [s for s in specs if s["available_at"] <= bar.index]
        if not eligible:
            out.append(absent(ORDER_BLOCK, pid))
            continue
        spec = eligible[-1]
        out.append(MarketZone(
            ORDER_BLOCK, pid, True, _ob_status(seq, spec, bar.index),
            spec["low"], spec["high"], spec["formed_at"], spec["available_at"],
            bullish=spec["bullish"],
        ))
    return tuple(out)


def _finder_views(bars: Sequence[Bar], *, k: int, concept_id: str, finder, initial: ZoneStatus,
                  touched: ZoneStatus) -> tuple[MarketZone, ...]:
    """Call `finder` on each prefix. Remember the zone after the finder stops returning it.

    `available_at` is the first bar the finder returns that zone, which for a breaker is the
    close-through bar (the finder's own `formed_at_index` is the origin candle).
    """
    pid = _pid(concept_id, {"k": int(k)}, ("k",))
    seq = list(bars)
    remembered: Optional[tuple] = None
    out: list[MarketZone] = []
    for i, bar in enumerate(seq):
        found = finder(seq[: i + 1], k)
        if found is not None:
            ident = (float(found.low), float(found.high), int(found.formed_at_index), bool(found.bullish))
            if remembered is None or remembered[0] != ident:
                remembered = (ident, bar.index, initial)
            else:
                remembered = (ident, remembered[1], initial)
        elif remembered is not None:
            ident, available_at, status = remembered
            low, high, _formed, _bull = ident
            if bar.index > available_at and gp.overlap(bar, low, high):
                status = touched
            remembered = (ident, available_at, status)
        if remembered is None or remembered[1] > bar.index:
            out.append(absent(concept_id, pid))
            continue
        ident, available_at, status = remembered
        low, high, formed, bull = ident
        out.append(MarketZone(
            concept_id, pid, True, status, low, high, formed, available_at, bullish=bull,
        ))
    return tuple(out)


def breaker_views(bars: Sequence[Bar], *, k: int) -> tuple[MarketZone, ...]:
    """MKT-Z04. Calls `find_active_breaker` on each prefix."""
    return _finder_views(
        bars, k=k, concept_id=BREAKER, finder=find_active_breaker,
        initial=ZoneStatus.FLIPPED, touched=ZoneStatus.TOUCHED,
    )


def mitigation_views(bars: Sequence[Bar], *, k: int) -> tuple[MarketZone, ...]:
    """MKT-Z05. Calls `find_active_mitigation_block` on each prefix.

    A bar that touches the outer zone and the inner body on the same bar is not returned by
    the finder, so this view stays absent for that case.
    """
    return _finder_views(
        bars, k=k, concept_id=OB_BODY, finder=find_active_mitigation_block,
        initial=ZoneStatus.ACTIVE, touched=ZoneStatus.TOUCHED,
    )
