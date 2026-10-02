"""DEX-09 position result. gross R from the bar replay; net subtracts TRS-07 cost and DEX-08 carry.

walk is bar_replay here (OHLC bars). broker_fills (live / paper fills) is a different walk
and is never pooled with it (F-010). The identity also names the position's DEX-01 size,
DEX-06 schedule and DEX-07 rule parameterizations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from research.costs import ComponentCostModel, CostModel

from semantics.execution.carry import Carry
from semantics.execution.position import CLOSED, ExitReason, Position
from semantics.execution.size import PositionSize
from semantics.identity import parameterization_id
from semantics.trading.cost import Cost, component_cost, flat_cost

POSITION_RESULT = "DEX-09"
BAR_REPLAY = "bar_replay"


@dataclass(frozen=True)
class PositionResult:
    """DEX-09. net_r is None on a gross basis, and None on a net basis when carry is None."""

    concept_id: str
    parameterization_id: str
    available_at: int
    gross_r: float
    net_r: Optional[float]
    walk: str
    basis: str
    cost_model: str
    cost_source: Optional[str]
    exit_bar: int
    cost: Optional[Cost] = None
    carry: Optional[Carry] = None


def _exit_kind(position: Position) -> str:
    """Cost-model exit kind: stops are stop orders; rule closes are market closes."""
    if position.stop_exit:
        return "SL_HIT"
    if position.exit_reason is ExitReason.TARGET_FINAL:
        return "TP_HIT"
    return "TIMEOUT"


def position_result(
    position: Position,
    size: PositionSize,
    *,
    basis: str,
    cost_model: object = None,
    cost_source: Optional[str] = None,
    carry: Optional[Carry] = None,
) -> Optional[PositionResult]:
    """None while the position is open. A gross result carries no cost model (I-15)."""
    if basis not in ("gross", "net"):
        raise ValueError(f"DEX-09 basis {basis!r} is outside ['gross', 'net']")
    if basis == "gross" and (cost_model is not None or carry is not None):
        raise ValueError("I-15: a gross result carries no cost model and no carry")
    if basis == "net" and cost_model is None:
        raise ValueError("I-15: a net result requires a cost model other than none")
    if position.state != CLOSED or position.gross_r is None or position.exit_bar is None:
        return None
    params: dict = {
        "walk": BAR_REPLAY, "basis": basis, "cost_model": "none",
        "position_size": size.parameterization_id,
        "exit_schedule": position.schedule.parameterization_id,
        "exit_rule": position.rule.parameterization_id,
    }
    gross = float(position.gross_r)
    if basis == "gross":
        pid = parameterization_id(POSITION_RESULT, params, tuple(params))
        return PositionResult(POSITION_RESULT, pid, position.exit_bar, gross, None, BAR_REPLAY,
                              basis, "none", None, position.exit_bar)
    side = "long" if position.direction.value == "LONG" else "short"
    entry = position.fill.price
    if isinstance(cost_model, ComponentCostModel):
        if cost_source is not None and cost_source != cost_model.source:
            raise ValueError("DEX-09 cost_source must be the component model's source")
        charged = component_cost(cost_model, entry=entry, risk_distance=position.risk_distance,
                                 exit_kind=_exit_kind(position), direction=side,
                                 exit_bar=position.exit_bar)
    elif isinstance(cost_model, CostModel):
        charged = flat_cost(cost_model, entry=entry, risk_distance=position.risk_distance,
                            cost_source=cost_source, plan_bar=position.fill.bar)
    else:
        raise TypeError(f"DEX-09 cost model {type(cost_model).__name__} is not a TRS-07 model")
    if charged is None:
        raise ValueError("TRS-07 cost model status UNKNOWN yields no cost")
    if carry is not None and carry.cost_source != charged.cost_source:
        raise ValueError("DEX-09 carry and cost must name one calibration (cost_source)")
    params["cost_model"] = charged.cost_model
    params["cost_source"] = charged.cost_source
    pid = parameterization_id(POSITION_RESULT, params, tuple(params))
    net = None if carry is None else gross - charged.cost_r - carry.carry_r
    return PositionResult(POSITION_RESULT, pid, position.exit_bar, gross, net, BAR_REPLAY, basis,
                          charged.cost_model, charged.cost_source, position.exit_bar, charged, carry)
