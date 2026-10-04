"""TRS-06 target.

fixed_r arithmetic is the contract rule (no callable authority owns it).
structural_tp2 rejection reasons match ExecutionEngine.build_trade.
Intent is ExecutionEngine._derive_trade_intent. CRTEngine does not define that method
(crt_engine_v2.py); the brief names CRTEngine, the callable authority is ExecutionEngine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

from config_layer.crt_engine_v2 import ExecutionEngine
from config_layer.state_identity import Direction

from semantics.identity import parameterization_id
from semantics.market.levels import Level
from semantics.types import Bias

TARGET = "TRS-06"

STRUCTURAL_INVERTED = "structural_tp2_inverted"
STRUCTURAL_TOO_CLOSE = "structural_tp2_too_close"


@dataclass(frozen=True)
class Target:
    """TRS-06. target_policy is identity-bearing only on ordinal 2; intent only on ordinal 1."""

    concept_id: str
    parameterization_id: str
    available_at: int
    price: float
    ordinal: int
    r_multiple: float
    target_policy: Optional[str] = None
    intent: Optional[str] = None


def _pid(ordinal: int, r_multiple: float, intent: Optional[str], target_policy: Optional[str]) -> str:
    params: dict = {"ordinal": int(ordinal)}
    bearing = ["ordinal"]
    # structural_tp2 prices the range edge. r_multiple is unused and not identity (TRS-06).
    if not (ordinal == 2 and target_policy == "structural_tp2"):
        params["r_multiple"] = float(r_multiple)
        bearing.append("r_multiple")
    if ordinal == 1:
        if intent is None:
            raise KeyError("TRS-06: identity-bearing parameter(s) missing: ['intent']")
        params["intent"] = intent
        bearing.append("intent")
    elif ordinal == 2:
        if target_policy is None:
            raise KeyError("TRS-06: identity-bearing parameter(s) missing: ['target_policy']")
        params["target_policy"] = target_policy
        bearing.append("target_policy")
    else:
        raise ValueError(f"TRS-06 ordinal {ordinal!r} is outside [1, 2]")
    return parameterization_id(TARGET, params, bearing)


def _engine_direction(direction: Bias) -> Direction:
    if direction is Bias.LONG:
        return Direction.LONG
    if direction is Bias.SHORT:
        return Direction.SHORT
    raise ValueError(f"TRS-06 direction {direction!r} is not LONG or SHORT")


def derive_intent(inputs: Mapping[str, object], config, direction: Bias) -> str:
    """Call the engine classifier. A missing INTENT_INPUT_KEYS entry raises KeyError there."""
    return ExecutionEngine._derive_trade_intent(
        dict(inputs), float(config.breakout_disp_threshold), _engine_direction(direction),
    )


def intent_r_multiple(config, inputs: Mapping[str, object], direction: Bias) -> tuple[str, float]:
    """Target-1 multiple: the config field build_trade reads for the derived intent."""
    intent = derive_intent(inputs, config, direction)
    return intent, float(getattr(config, f"tp1_atr_multiplier_{intent}"))


def fixed_r_target(
    entry: float,
    stop: float,
    *,
    ordinal: int,
    r_multiple: float,
    direction: Bias,
    plan_bar: int,
    intent: Optional[str] = None,
    target_policy: Optional[str] = None,
    available_floor: int = 0,
) -> Target:
    """entry ± r_multiple · |entry − stop|, on the thesis side."""
    risk = abs(entry - stop)
    price = entry + r_multiple * risk if direction is Bias.LONG else entry - r_multiple * risk
    available = max(plan_bar, available_floor)
    return Target(
        TARGET, _pid(ordinal, r_multiple, intent, target_policy), available,
        float(price), int(ordinal), float(r_multiple), target_policy, intent,
    )


def structural_tp2_target(
    entry: float,
    stop: float,
    upper: Level,
    lower: Level,
    *,
    direction: Bias,
    r_multiple: float,
    plan_bar: int,
) -> tuple[Optional[Target], Optional[str]]:
    """Ordinal-2 TARGET on the founding range's opposite edge. The levels are not modified.

    Behind entry (LONG edge <= entry, SHORT edge >= entry) is structural_tp2_inverted.
    A distance strictly under 1R is structural_tp2_too_close. Exactly 1R is accepted.
    """
    level = upper if direction is Bias.LONG else lower
    edge = float(level.price)
    risk = abs(entry - stop)
    if direction is Bias.LONG:
        inverted = edge <= entry
        too_close = (edge - entry) < risk
    else:
        inverted = edge >= entry
        too_close = (entry - edge) < risk
    if inverted or too_close:
        return None, STRUCTURAL_INVERTED if inverted else STRUCTURAL_TOO_CLOSE
    available = max(plan_bar, level.available_at)
    target = Target(
        TARGET, _pid(2, r_multiple, None, "structural_tp2"), available,
        edge, 2, float(r_multiple), "structural_tp2", None,
    )
    return target, None
