"""TradePlan. A composition of a thesis, an entry, a stop and targets. Not a new concept id.

I-11: no invalidation or no stop raises. An inverted stop is no plan (None).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from semantics.trading.entry import Entry
from semantics.trading.roles import Objective
from semantics.trading.stop import Stop
from semantics.trading.target import Target
from semantics.trading.thesis import Thesis
from semantics.types import Bias


@dataclass(frozen=True)
class TradePlan:
    """Uses the thesis concept id. R is |entry − stop| and is not stored."""

    concept_id: str
    parameterization_id: str
    available_at: int
    thesis: Thesis
    entry: Entry
    stop: Stop
    targets: tuple
    objective: Optional[Objective] = None

    def __post_init__(self) -> None:
        if self.thesis.invalidation is None or self.stop is None:
            raise ValueError("I-11: a TradePlan requires a thesis invalidation and a stop")

    @property
    def R(self) -> float:
        return abs(self.entry.price - self.stop.price)


def trade_plan(
    thesis: Thesis,
    entry: Entry,
    stop: Optional[Stop],
    targets: Sequence[Target] = (),
    objective: Optional[Objective] = None,
) -> Optional[TradePlan]:
    """None when the stop is on the wrong side of entry, including equality."""
    if thesis.invalidation is None or stop is None:
        raise ValueError("I-11: a TradePlan requires a thesis invalidation and a stop")
    if thesis.direction is Bias.LONG and stop.price >= entry.price:
        return None
    if thesis.direction is Bias.SHORT and stop.price <= entry.price:
        return None
    if thesis.direction not in (Bias.LONG, Bias.SHORT):
        raise ValueError(f"TradePlan direction {thesis.direction!r} is not LONG or SHORT")
    available = max(
        thesis.available_at, entry.available_at, stop.available_at,
        *(target.available_at for target in targets),
    )
    if objective is not None:
        available = max(available, objective.available_at)
    return TradePlan(
        thesis.concept_id, thesis.parameterization_id, available,
        thesis, entry, stop, tuple(targets), objective,
    )
