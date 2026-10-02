"""DEX-04 approval. A rail's verdict on one plan, supplied by the caller (no rail is run here).

The rail is identity-bearing: the CRT engine and planner+Ultron approve different populations
(F-103). A FILTERED verdict ends the plan or position only; it never touches the thesis (I-3).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from semantics.identity import parameterization_id
from semantics.registry import match_terminal
from semantics.types import TerminalClass

APPROVAL = "DEX-04"
CRT_ENGINE = "crt_engine"
PLANNER_ULTRON = "planner_ultron"
RAILS = (CRT_ENGINE, PLANNER_ULTRON)
APPROVED = "APPROVED"
FILTERED = "FILTERED"


@dataclass(frozen=True)
class Approval:
    """DEX-04. legacy_reason keeps the rail's own wording verbatim."""

    concept_id: str
    parameterization_id: str
    available_at: int
    rail: str
    verdict: str
    reason_code: Optional[str]
    bar: int
    legacy_reason: Optional[str] = None


def _pid(rail: str) -> str:
    if rail not in RAILS:
        raise ValueError(f"DEX-04 rail {rail!r} is outside {RAILS}")
    return parameterization_id(APPROVAL, {"rail": rail}, ("rail",))


def approved(rail: str, bar: int) -> Approval:
    return Approval(APPROVAL, _pid(rail), bar, rail, APPROVED, None, bar, None)


def from_crt_reset(reason: str, bar: int) -> Approval:
    """A CRT-rail filter. The reason must map to class FILTERED; any other class is not a verdict."""
    entry = match_terminal(reason)
    if entry.get("class") != TerminalClass.FILTERED.value:
        raise ValueError(f"DEX-04 reason {reason!r} maps to {entry.get('class')}, not FILTERED")
    return Approval(APPROVAL, _pid(CRT_ENGINE), bar, CRT_ENGINE, FILTERED, str(entry["code"]), bar, reason)


def from_ultron(result: Mapping[str, Any], bar: int) -> Approval:
    """UltronRiskGate.evaluate returns decision approve | reject; a reject names risk_reason."""
    decision = result.get("decision")
    if decision == "approve":
        return approved(PLANNER_ULTRON, bar)
    if decision == "reject":
        reason = result.get("risk_reason")
        if not isinstance(reason, str) or not reason:
            raise ValueError("DEX-04 an Ultron reject must carry risk_reason")
        return Approval(APPROVAL, _pid(PLANNER_ULTRON), bar, PLANNER_ULTRON, FILTERED, reason, bar, reason)
    raise ValueError(f"DEX-04 Ultron decision {decision!r} is neither approve nor reject")
