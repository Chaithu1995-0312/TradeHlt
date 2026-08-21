"""htf_state.py — CH-htf-state-objective (Stage 3): HTFState + Objective.

A SECOND dimension of the parent candle, orthogonal to C1/C2/C3
(`config_layer.parent_crt.ParentCRTTrack`). Do NOT add these members to `CRTState`
(F-077 / study plan Stage 3).

    CANDLE PROFILE (existing)     HTF STATE (this module)
         C1 → C2 → C3          EXPANSION / ACCUMULATION
                               / DISTRIBUTION / REVERSAL
                    └──────────┬──────────┘
                          OBJECTIVE STATUS
                     NONE / EXISTS / ACHIEVED / INVALIDATED

Classifier is local parent-range ratio against the previous closed parent.
It is NOT CandleStateEncoder, NOT RegimeLabeler, NOT FM volatility_regime —
those three already exist; this is a fourth *question* (Sujan HTF posture),
not a fourth ATR-expansion implementation.

DISTRIBUTION here is Sujan's "large-in-range / look for reversal evidence"
posture. It is NOT `CRTState.DISTRIBUTION_C3` (an F-074 impulse). F-077.

Objective is derived from ParentCRTTrack.bias + C1 range vs the last closed
parent close. Distinct from GoalSpec (G001).

Activation (allow_exists_only) is a separate config-gated elif on
process_candle. Default OFF. HTFState is computed even when the gate is off.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Optional

from config_layer.state_identity import Direction

if TYPE_CHECKING:
    from config_layer.crt_engine_v2 import Candle
    from config_layer.parent_crt import ParentRange


class HTFState(Enum):
    """Namespaced HTF posture. Not CRTState. Not weekly_range.ACCUMULATION_WEEKDAYS."""

    UNKNOWN = "UNKNOWN"
    EXPANSION = "EXPANSION"
    ACCUMULATION = "ACCUMULATION"
    DISTRIBUTION = "DISTRIBUTION"
    REVERSAL = "REVERSAL"


class ObjectiveStatus(Enum):
    """Whether the completed parent narrative still has an open objective."""

    NONE = "NONE"
    EXISTS = "EXISTS"
    ACHIEVED = "ACHIEVED"
    INVALIDATED = "INVALIDATED"


@dataclass(frozen=True)
class HTFStateThresholds:
    expansion_min_range_ratio: float
    accumulation_max_range_ratio: float
    distribution_min_range_ratio: float

    def __post_init__(self) -> None:
        if self.expansion_min_range_ratio <= 0:
            raise ValueError("expansion_min_range_ratio must be > 0")
        if self.accumulation_max_range_ratio <= 0:
            raise ValueError("accumulation_max_range_ratio must be > 0")
        if self.distribution_min_range_ratio <= 0:
            raise ValueError("distribution_min_range_ratio must be > 0")
        if self.accumulation_max_range_ratio > self.distribution_min_range_ratio:
            raise ValueError(
                "accumulation_max_range_ratio must be <= distribution_min_range_ratio"
            )


@dataclass(frozen=True)
class Objective:
    status: ObjectiveStatus
    direction: Direction
    target: Optional[float] = None
    invalidate_at: Optional[float] = None


def classify_htf_state(
    prev: "Candle",
    curr: "Candle",
    thresholds: HTFStateThresholds,
) -> HTFState:
    """Classify `curr` against `prev`. Both must be already-closed parents."""
    prev_range = prev.high - prev.low
    curr_range = curr.high - curr.low
    ratio = curr_range / prev_range if prev_range > 0 else 1.0
    broke_high = curr.close > prev.high
    broke_low = curr.close < prev.low
    inside = (not broke_high) and (not broke_low)
    prev_bull = prev.close > prev.open
    opposite_break = (prev_bull and broke_low) or ((not prev_bull) and broke_high)

    if opposite_break:
        return HTFState.REVERSAL
    if (broke_high or broke_low) and ratio >= thresholds.expansion_min_range_ratio:
        return HTFState.EXPANSION
    if broke_high or broke_low:
        return HTFState.EXPANSION
    if inside and ratio >= thresholds.distribution_min_range_ratio:
        return HTFState.DISTRIBUTION
    if inside and ratio <= thresholds.accumulation_max_range_ratio:
        return HTFState.ACCUMULATION
    return HTFState.ACCUMULATION


def resolve_objective(
    bias: Direction,
    rng: Optional["ParentRange"],
    last_close: Optional[float],
) -> Objective:
    """NONE until C3 bias exists. Then EXISTS / ACHIEVED / INVALIDATED vs C1 bounds."""
    if bias is Direction.NONE or rng is None or last_close is None:
        return Objective(status=ObjectiveStatus.NONE, direction=Direction.NONE)
    if bias is Direction.LONG:
        target, invalidate_at = rng.h_ref, rng.l_ref
        if last_close >= target:
            status = ObjectiveStatus.ACHIEVED
        elif last_close < invalidate_at:
            status = ObjectiveStatus.INVALIDATED
        else:
            status = ObjectiveStatus.EXISTS
        return Objective(status, bias, target, invalidate_at)
    if bias is Direction.SHORT:
        target, invalidate_at = rng.l_ref, rng.h_ref
        if last_close <= target:
            status = ObjectiveStatus.ACHIEVED
        elif last_close > invalidate_at:
            status = ObjectiveStatus.INVALIDATED
        else:
            status = ObjectiveStatus.EXISTS
        return Objective(status, bias, target, invalidate_at)
    return Objective(status=ObjectiveStatus.NONE, direction=Direction.NONE)


def activation_allows(status: ObjectiveStatus, mode: str) -> bool:
    if mode != "allow_exists_only":
        raise ValueError(
            f"objective_gate.mode={mode!r} is not implemented "
            "(only 'allow_exists_only' exists)"
        )
    return status is ObjectiveStatus.EXISTS
