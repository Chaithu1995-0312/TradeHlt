"""Market EVENTS: things that happen on one bar, always with a reference.

    MKT-E01 sweep              GP-04 on a liquidity level (strict tie, founding is a parameter)
    MKT-E02 structure_break    onset of a structural_position change (consumption = "onset";
                               "once_per_level" is PROPOSED and not implemented)
    MKT-E06 zone_touch         GP-05, first bar strictly after the zone is available
    MKT-E07 zone_break         GP-02 on the zone's far edge (same bar as availability is allowed)
    MKT-E08 level_pierce       GP-01 on a level (today's higher_high / lower_low)
    MKT-E10 retrace_breach     GP-02 against the move, on a MKT-L02 retracement
    MKT-E11 extension_reach    GP-03 with the move, on a MKT-L02 extension
    MKT-E12 clock_rollover     the governing clock changed period

An EVENT never persists (I-1): it is emitted for exactly one bar.
This module takes primitives (prices, available_at). It does not import zones.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from semantics import geometry as gp
from semantics.identity import parameterization_id
from semantics.market.conditions import ConditionSeries, StructuralPosition
from semantics.market.levels import Level
from semantics.types import Bar, Bias, LevelStatus, Side, implied_bias_of_sweep

SWEEP = "MKT-E01"
STRUCTURE_BREAK = "MKT-E02"
ZONE_TOUCH = "MKT-E06"
ZONE_BREAK = "MKT-E07"
LEVEL_PIERCE = "MKT-E08"
RETRACE_BREACH = "MKT-E10"
EXTENSION_REACH = "MKT-E11"
CLOCK_ROLLOVER = "MKT-E12"

_CLOCKS = ("htf_period", "session", "broker_day")
_EMPTY: dict = {}


def _empty_pid(concept_id: str) -> str:
    return parameterization_id(concept_id, _EMPTY, ())


@dataclass(frozen=True)
class MarketEvent:
    concept_id: str
    bar: int
    available_at: int
    parameterization_id: str
    side: Optional[Side] = None
    implied_bias: Optional[Bias] = None
    reference: Optional[str] = None     # founding / anchor / clock id of what was interacted with
    reference_price: Optional[float] = None


def sweep(bar: Bar, level: Level) -> Optional[MarketEvent]:
    """MKT-E01. `swept_side` = the level's side; implied bias is the opposite direction."""
    if level.side is None or level.available_at > bar.index:
        return None   # a level not yet knowable cannot be swept (I-6)
    if level.status is not LevelStatus.ACTIVE:
        return None   # MKT-E01 rule: only an ACTIVE level can be swept
    if not gp.pierce_and_reject(bar, level.price, level.side):
        return None
    pid = parameterization_id(SWEEP, {"founding": level.founding, "tie": "strict"}, ("founding", "tie"))
    return MarketEvent(SWEEP, bar.index, bar.index, pid, level.side, implied_bias_of_sweep(level.side),
                       level.founding, level.price)


def level_pierce(bar: Bar, level: Level) -> Optional[MarketEvent]:
    """MKT-E08. Pierce without any close condition."""
    if level.side is None or level.available_at > bar.index or not gp.pierce(bar, level.price, level.side):
        return None
    pid = parameterization_id(LEVEL_PIERCE, {"founding": level.founding}, ("founding",))
    return MarketEvent(LEVEL_PIERCE, bar.index, bar.index, pid, level.side, None, level.founding, level.price)


def structure_breaks(position: ConditionSeries, *, consumption: str = "onset") -> tuple[Optional[MarketEvent], ...]:
    """MKT-E02 from MKT-C01: an event only on the bar where the position CHANGES to ABOVE/BELOW.

    Identity-bearing parameters are `k` (from the condition) and `consumption`. The only
    accepted consumption is "onset". "once_per_level" is PROPOSED and raises.
    """
    if consumption != "onset":
        raise ValueError(
            f"MKT-E02 consumption {consumption!r} is not accepted (once_per_level is PROPOSED)"
        )
    params = dict(position.parameters)
    if "k" not in params:
        raise KeyError("MKT-E02: identity-bearing parameter(s) missing: ['k']")
    pid = parameterization_id(
        STRUCTURE_BREAK, {"k": int(params["k"]), "consumption": "onset"}, ("k", "consumption"),
    )
    out: list[Optional[MarketEvent]] = []
    prev = None
    for i, v in enumerate(position.values):
        ev = None
        if v is not None and v is not StructuralPosition.INSIDE and v != prev:
            side = Side.UPPER if v is StructuralPosition.ABOVE_LAST_SWING_HIGH else Side.LOWER
            ev = MarketEvent(STRUCTURE_BREAK, i, i, pid, side, None, "swing_pivot")
        out.append(ev)
        prev = v
    return tuple(out)


def zone_touch(bar: Bar, *, zone_low: float, zone_high: float, available_at: int,
               reference: str, already_touched: bool) -> Optional[MarketEvent]:
    """MKT-E06 for one bar. The formation bar is not a touch (`available_at < bar`).

    MKT-E06 is the FIRST overlapping bar, so the caller declares whether the zone was
    already touched; once it was, no later overlap is a touch event (`zone_touches`).
    """
    if already_touched or available_at >= bar.index:
        return None
    if not gp.overlap(bar, zone_low, zone_high):
        return None
    return MarketEvent(ZONE_TOUCH, bar.index, bar.index, _empty_pid(ZONE_TOUCH),
                       reference=reference, reference_price=zone_low)


def zone_touches(bars: Sequence[Bar], *, zone_low: float, zone_high: float, available_at: int,
                 reference: str) -> tuple[Optional[MarketEvent], ...]:
    """MKT-E06 once: the first overlapping bar after the zone is available, then silence."""
    out: list[Optional[MarketEvent]] = []
    emitted = False
    for bar in bars:
        ev = zone_touch(bar, zone_low=zone_low, zone_high=zone_high, available_at=available_at,
                        reference=reference, already_touched=emitted)
        emitted = emitted or ev is not None
        out.append(ev)
    return tuple(out)


def zone_break(bar: Bar, *, zone_low: float, zone_high: float, available_at: int,
               bullish: bool, reference: str) -> Optional[MarketEvent]:
    """MKT-E07. Close beyond the far edge. Same bar as `available_at` is allowed (I-6)."""
    if available_at > bar.index:
        return None
    if bullish:
        hit = gp.beyond(bar, zone_low, Side.LOWER)
        side = Side.LOWER
        price = zone_low
    else:
        hit = gp.beyond(bar, zone_high, Side.UPPER)
        side = Side.UPPER
        price = zone_high
    if not hit:
        return None
    return MarketEvent(ZONE_BREAK, bar.index, bar.index, _empty_pid(ZONE_BREAK),
                       side, None, reference, price)


def retrace_breach(bar: Bar, level: Level, move_bias: Bias) -> Optional[MarketEvent]:
    """MKT-E10. Close beyond a retracement level AGAINST the move (LONG move -> close below)."""
    side = Side.LOWER if move_bias is Bias.LONG else Side.UPPER
    if level.available_at > bar.index or not gp.beyond(bar, level.price, side):
        return None
    return MarketEvent(RETRACE_BREACH, bar.index, bar.index, _empty_pid(RETRACE_BREACH), side, None,
                       level.anchor, level.price)


def extension_reach(bar: Bar, level: Level, move_bias: Bias) -> Optional[MarketEvent]:
    """MKT-E11. Close reaches an extension level WITH the move (inclusive)."""
    side = Side.UPPER if move_bias is Bias.LONG else Side.LOWER
    if level.available_at > bar.index or not gp.reach(bar, level.price, side):
        return None
    return MarketEvent(EXTENSION_REACH, bar.index, bar.index, _empty_pid(EXTENSION_REACH), side, None,
                       level.anchor, level.price)


def clock_rollovers(clock_ids: Sequence[str], *, clock: str) -> tuple[Optional[MarketEvent], ...]:
    """MKT-E12. One event on each bar whose clock period differs from the previous bar's."""
    if clock not in _CLOCKS:
        raise ValueError(f"MKT-E12 clock {clock!r} is not in {_CLOCKS}")
    pid = parameterization_id(CLOCK_ROLLOVER, {"clock": clock}, ("clock",))
    out: list[Optional[MarketEvent]] = []
    prev = None
    for i, cid in enumerate(clock_ids):
        ev = None
        if prev is not None and cid != prev:
            ev = MarketEvent(CLOCK_ROLLOVER, i, i, pid, reference=cid)
        out.append(ev)
        prev = cid
    return tuple(out)
