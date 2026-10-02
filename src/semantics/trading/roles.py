"""TRS-02 objective and TRS-03 invalidation.

A role names a market level. It never calls Level.with_status and never writes a
level's status (I-10). Whether an invalidation closes an open position is slice 3.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from config_layer.htf_state import resolve_objective
from config_layer.parent_crt import ParentRange
from config_layer.state_identity import Direction

from semantics.identity import parameterization_id
from semantics.market.events import retrace_breach
from semantics.market.levels import Level, retracement
from semantics.types import Bar, Bias

OBJECTIVE = "TRS-02"
INVALIDATION = "TRS-03"

_SCOPE = "parent_range"


@dataclass(frozen=True)
class Invalidation:
    """TRS-03. The retracement rule that falsifies a thesis. Not a position close."""

    concept_id: str
    parameterization_id: str
    available_at: int
    retrace_fraction: float
    level: Level


@dataclass(frozen=True)
class Objective:
    """TRS-02. Status is the role's reading of resolve_objective. The level is untouched."""

    concept_id: str
    parameterization_id: str
    available_at: int
    scope: str
    status: str
    target: Optional[float]
    level: Level


def make_invalidation(move_start: float, move_end: float, fraction: float, *, formed_at: int) -> Invalidation:
    """MKT-L02 retracement of the displacement move. Knowable on the MKT-E04 bar."""
    level = retracement(
        move_start, move_end, float(fraction),
        anchor="displacement", formed_at=formed_at, available_at=formed_at,
    )
    pid = parameterization_id(INVALIDATION, {"retrace_fraction": float(fraction)}, ("retrace_fraction",))
    return Invalidation(INVALIDATION, pid, formed_at, float(fraction), level)


def breach(invalidation: Invalidation, bar: Bar, move_bias: Bias):
    """MKT-E10 against the thesis direction. None when the close is not strictly beyond."""
    return retrace_breach(bar, invalidation.level, move_bias)


def _engine_direction(bias: Bias) -> Direction:
    if bias is Bias.LONG:
        return Direction.LONG
    if bias is Bias.SHORT:
        return Direction.SHORT
    raise ValueError(f"TRS-02 bias {bias!r} is not LONG or SHORT")


def objective_role(
    upper: Level,
    lower: Level,
    bias: Bias,
    last_close: Optional[float],
    bar: int,
    *,
    scope: str = _SCOPE,
) -> Objective:
    """TRS-02 from resolve_objective. Scope other than parent_range is PROPOSED and raises.

    When the range is not yet knowable, status is NONE and the close is not given to
    the authority (I-6).
    """
    if scope != _SCOPE:
        raise ValueError(f"TRS-02 scope {scope!r} is not accepted (an M15 objective is PROPOSED)")
    pid = parameterization_id(OBJECTIVE, {"scope": scope}, ("scope",))
    level = upper if bias is Bias.LONG else lower
    available = max(bar, upper.available_at, lower.available_at)
    if bar < upper.available_at or bar < lower.available_at:
        return Objective(OBJECTIVE, pid, available, scope, "NONE", None, level)
    rng = ParentRange(
        h_ref=upper.price,
        l_ref=lower.price,
        formed_at_index=max(upper.formed_at, lower.formed_at),
    )
    resolved = resolve_objective(_engine_direction(bias), rng, last_close)
    return Objective(
        OBJECTIVE, pid, available, scope, resolved.status.name, resolved.target, level,
    )
