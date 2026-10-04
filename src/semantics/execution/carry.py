"""DEX-08 carry. Overnight swap for the broker days a position is held.

A night is a broker-server rollover: each broker date that has bars, after the fill bar's
date, up to and including the exit bar's date (weekends without bars add none; MT5 bar
stamps are server time, F-066). The calibration's triple-swap weekday counts 3.
Unmeasured swap or weekday with at least one night is None, never 0; zero nights is a real 0.
The price comes from ComponentCostModel.cost_price itself: (with nights) - (without nights).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, Sequence

from research.costs import ComponentCostModel, UnmeasuredCostError

from semantics.execution.position import CLOSED, Position
from semantics.identity import parameterization_id

CARRY = "DEX-08"


@dataclass(frozen=True)
class Carry:
    """DEX-08. carry_r is in R over the position's risk distance."""

    concept_id: str
    parameterization_id: str
    available_at: int
    nights: int
    weighted_nights: int
    carry_price: float
    carry_r: float
    cost_source: str


def _day(stamp: object) -> date:
    if isinstance(stamp, datetime):
        return stamp.date()
    if isinstance(stamp, date):
        return stamp
    raise TypeError(f"DEX-08 bar timestamp {stamp!r} is not a datetime")


def rollover_dates(fill_timestamp: object, held_bars: Sequence, exit_bar: int) -> list:
    """Broker dates crossed: distinct bar dates after the fill date, up to the exit bar."""
    start = _day(fill_timestamp)
    days = sorted({_day(b.timestamp) for b in held_bars if b.index <= exit_bar and _day(b.timestamp) > start})
    return days


def carry(
    model: ComponentCostModel,
    position: Position,
    *,
    fill_timestamp: object,
    held_bars: Sequence,
    triple_swap_weekday: Optional[int],
) -> Optional[Carry]:
    """`held_bars` are the bars after the fill (each with .index and .timestamp).

    None when the position is not CLOSED, or when it crossed a night and the swap or the
    triple-swap weekday (0 = Monday … 6 = Sunday) is unmeasured.
    """
    if position.state != CLOSED or position.exit_bar is None:
        return None
    source = model.source
    if not isinstance(source, str) or not source:
        raise ValueError("DEX-08 cost_source is empty")
    pid = parameterization_id(CARRY, {"cost_source": source}, ("cost_source",))
    days = rollover_dates(fill_timestamp, held_bars, position.exit_bar)
    if not days:
        return Carry(CARRY, pid, position.exit_bar, 0, 0, 0.0, 0.0, source)
    if triple_swap_weekday is None:
        return None
    if type(triple_swap_weekday) is not int or not 0 <= triple_swap_weekday <= 6:
        raise ValueError(f"DEX-08 triple_swap_weekday {triple_swap_weekday!r} must be an int 0..6")
    weighted = sum(3 if d.weekday() == triple_swap_weekday else 1 for d in days)
    direction = "long" if position.direction.value == "LONG" else "short"
    exit_kind = "SL_HIT" if position.stop_exit else "TP_HIT"
    try:
        with_nights = model.cost_price(exit_kind=exit_kind, direction=direction, nights_held=weighted)
        without = model.cost_price(exit_kind=exit_kind, direction=direction, nights_held=0)
    except UnmeasuredCostError:
        return None
    price = float(with_nights - without)
    return Carry(CARRY, pid, position.exit_bar, len(days), weighted, price,
                 price / position.risk_distance, source)
