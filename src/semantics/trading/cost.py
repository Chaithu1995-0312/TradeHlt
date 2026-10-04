"""TRS-07 cost. UNKNOWN is None, never 0. The R figure is the cost model's own cost_r.

A component cost depends on the exit kind, so it is available on the exit bar.
A flat bps cost does not, so it stays on the plan bar.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from research.costs import UNKNOWN, ComponentCostModel, CostModel

from semantics.identity import parameterization_id

COST = "TRS-07"


@dataclass(frozen=True)
class Cost:
    """TRS-07. cost_model and cost_source are the identity. cost_r is the measured value."""

    concept_id: str
    parameterization_id: str
    available_at: int
    cost_r: float
    cost_model: str
    cost_source: str


def _unavailable(risk_distance: Optional[float]) -> bool:
    return risk_distance is None or risk_distance <= 0


def component_cost(
    model: ComponentCostModel,
    *,
    entry: float,
    risk_distance: Optional[float],
    exit_kind: str,
    direction: str,
    exit_bar: int,
    nights_held: int = 0,
) -> Optional[Cost]:
    """None when status is UNKNOWN, before cost_r (that call raises unless MEASURED).

    INSUFFICIENT_DATA is not absence: the authority raises UnmeasuredCostError.
    nights_held defaults to 0, which is "no overnight", not a hidden calibration.
    available_at is the exit bar: the exit kind is not knowable before then.
    """
    if model.status == UNKNOWN:
        return None
    if _unavailable(risk_distance):
        return None
    value = model.cost_r(
        entry, float(risk_distance), exit_kind=exit_kind, direction=direction, nights_held=nights_held,
    )
    source = model.source
    if not source:
        raise ValueError("TRS-07 cost_source is empty")
    pid = parameterization_id(COST, {"cost_model": "component", "cost_source": source},
                              ("cost_model", "cost_source"))
    return Cost(COST, pid, exit_bar, float(value), "component", source)


def flat_cost(
    model: CostModel,
    *,
    entry: float,
    risk_distance: Optional[float],
    cost_source: str,
    plan_bar: int,
) -> Optional[Cost]:
    """CostModel has no status. cost_source is required (identity-bearing, domain str)."""
    if not isinstance(cost_source, str) or not cost_source:
        raise ValueError("TRS-07 flat_bps requires a non-empty cost_source")
    if _unavailable(risk_distance):
        return None
    value = model.cost_r(entry, float(risk_distance))
    pid = parameterization_id(
        COST, {"cost_model": "flat_bps", "cost_source": cost_source}, ("cost_model", "cost_source"),
    )
    return Cost(COST, pid, plan_bar, float(value), "flat_bps", cost_source)
