"""TRS-08 outcome. Identity is walk + basis + cost_model + walk_params (I-15).

On a net basis the identity also names cost_source. gross_r is the walk's own R.
net_r subtracts a TRS-07 cost_r computed after the walk, from the exit the walk took.
An empty future is absence (the contract's missing rule), not a manufactured timeout.
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

from research.contracts import Signal
from research.costs import ComponentCostModel, CostModel
from research.measurement.forward_walk import forward_walk
from research.oracle.multi_tp_walk import is_stop_exit, multi_tp_walk

from semantics.identity import parameterization_id
from semantics.trading.cost import Cost, component_cost, flat_cost
from semantics.trading.target import Target
from semantics.types import Bias

OUTCOME = "TRS-08"

_WALKS = ("forward_walk", "multi_tp_walk")


@dataclass(frozen=True)
class Outcome:
    """TRS-08. walk_params is frozen. net_r is None on a gross basis.

    cost is the TRS-07 charge actually subtracted. It is None on a gross basis.
    """

    concept_id: str
    parameterization_id: str
    available_at: int
    gross_r: float
    net_r: Optional[float]
    walk: str
    basis: str
    cost_model: str
    walk_params: Mapping[str, object]
    exit_bar: int
    cost: Optional[Cost] = None


def _identity_params(walk_params: Mapping[str, object]) -> dict:
    """JSON-safe copy. A dataclass (SEM-016 AdverseFill) keeps its type name and fields."""
    if not isinstance(walk_params, dict):
        raise TypeError("walk_params must be a dict")
    encoded: dict = {}
    for key, value in walk_params.items():
        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            encoded[key] = {"__type__": type(value).__name__, **dataclasses.asdict(value)}
        else:
            encoded[key] = value
    try:
        json.dumps(encoded)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"walk_params must be JSON-safe so the identity is canonical: {exc}") from exc
    return encoded


def _target(targets: Sequence[Target], ordinal: int) -> Optional[Target]:
    for target in targets:
        if target.ordinal == ordinal:
            return target
    return None


def _direction(direction: Bias) -> str:
    if direction is Bias.LONG:
        return "long"
    if direction is Bias.SHORT:
        return "short"
    raise ValueError(f"TRS-08 direction {direction!r} is not LONG or SHORT")


def _exit_bar(result, future: Sequence, entry_index: int) -> int:
    duration = int(result.duration_candles)
    if duration <= 0:
        return entry_index
    consumed = list(future)[:duration]
    if not consumed:
        return entry_index
    return int(consumed[-1].index)


def _stop_exit(walk: str, result) -> bool:
    """The walk's own stop predicate. forward_walk names SL_HIT; multi_tp_walk uses is_stop_exit."""
    if walk == "multi_tp_walk":
        return bool(is_stop_exit(result.outcome))
    return result.outcome == "SL_HIT"


def _exit_kind(walk: str, result) -> str:
    """Cost-model exit kind. A stop exit is SL_HIT; otherwise the walk's own non-stop label."""
    if _stop_exit(walk, result):
        return "SL_HIT"
    if walk == "multi_tp_walk":
        return result.exit_kind
    return result.outcome


def _charge(
    model: object,
    *,
    cost_source: Optional[str],
    entry: float,
    risk: float,
    exit_kind: str,
    direction: str,
    exit_bar: int,
    plan_bar: int,
) -> Cost:
    if isinstance(model, ComponentCostModel):
        source = model.source
        if not isinstance(source, str) or not source:
            raise ValueError("TRS-07 cost_source is empty")
        if cost_source is not None and cost_source != source:
            raise ValueError("TRS-08 cost_source must be the component model's source")
        charged = component_cost(
            model, entry=entry, risk_distance=risk, exit_kind=exit_kind,
            direction=direction, exit_bar=exit_bar,
        )
        if charged is None:
            raise ValueError("TRS-07 cost model status UNKNOWN yields no cost")
        return charged
    if isinstance(model, CostModel):
        if not isinstance(cost_source, str) or not cost_source:
            raise ValueError("TRS-07 flat_bps requires a non-empty cost_source")
        charged = flat_cost(
            model, entry=entry, risk_distance=risk, cost_source=cost_source, plan_bar=plan_bar,
        )
        if charged is None:
            raise ValueError("TRS-07 flat_bps yielded no cost")
        return charged
    raise TypeError(f"TRS-08 cost model {type(model).__name__} is not a TRS-07 model")


def measure_outcome(
    *,
    walk: str,
    basis: str,
    walk_params: Mapping[str, object],
    entry: float,
    stop: float,
    targets: Sequence[Target],
    direction: Bias,
    future: Sequence,
    instrument: str,
    timestamp: datetime,
    entry_index: int,
    cost_model: object = None,
    cost_source: Optional[str] = None,
    plan_bar: Optional[int] = None,
) -> Optional[Outcome]:
    """Refuse a gross outcome that carries a cost, and a net outcome that does not (I-15).

    A net charge is computed after the walk, from the exit the walk actually took.
    walk_params are passed through as the walk's keyword arguments, original objects
    included. They are not filled with the walk's own defaults.
    """
    if walk not in _WALKS:
        raise ValueError(f"TRS-08 walk {walk!r} is outside {_WALKS}")
    if basis not in ("gross", "net"):
        raise ValueError(f"TRS-08 basis {basis!r} is outside ['gross', 'net']")
    if basis == "gross" and cost_model is not None:
        raise ValueError("I-15: a gross outcome cannot carry a cost model")
    if basis == "net" and cost_model is None:
        raise ValueError("I-15: a net outcome requires a cost model other than none")
    if not future:
        return None
    identity_params = _identity_params(walk_params)
    side = _direction(direction)
    risk = abs(entry - stop)
    if risk <= 0:
        raise ValueError(f"TRS-08 non-positive risk distance ({risk})")
    tp1 = _target(targets, 1)
    tp2 = _target(targets, 2)
    if walk == "forward_walk" and tp1 is None:
        raise ValueError("TRS-08 forward_walk requires a target of ordinal 1")
    if walk == "multi_tp_walk" and (tp1 is None or tp2 is None):
        raise ValueError("TRS-08 multi_tp_walk requires targets of ordinal 1 and 2")
    call = dict(walk_params)
    if walk == "multi_tp_walk":
        if "entry_index" not in call:
            call["entry_index"] = entry_index
        result = multi_tp_walk(entry, side, stop, tp1.price, tp2.price, future, **call)
        gross = float(result.rr_gross)
    else:
        reward = abs(tp1.price - entry) / risk
        signal = Signal(
            instrument, timestamp, entry_index, side, float(entry),
            1.0, float(reward), float(risk),
        )
        result = forward_walk(signal, future, **call)
        gross = float(result.rr_achieved)
    exit_bar = _exit_bar(result, future, entry_index)
    built_at = entry_index if plan_bar is None else int(plan_bar)
    charged: Optional[Cost] = None
    model_name = "none"
    bearing = ["walk", "basis", "cost_model", "walk_params"]
    params: dict = {
        "walk": walk, "basis": basis, "cost_model": model_name, "walk_params": identity_params,
    }
    net = None
    if basis == "net":
        charged = _charge(
            cost_model, cost_source=cost_source, entry=float(entry), risk=risk,
            exit_kind=_exit_kind(walk, result), direction=side,
            exit_bar=exit_bar, plan_bar=built_at,
        )
        model_name = charged.cost_model
        params["cost_model"] = model_name
        params["cost_source"] = charged.cost_source
        bearing.append("cost_source")
        net = gross - charged.cost_r
    pid = parameterization_id(OUTCOME, params, bearing)
    return Outcome(
        OUTCOME, pid, exit_bar, gross, net, walk, basis, model_name,
        MappingProxyType(dict(walk_params)), exit_bar, charged,
    )
