"""
execution_intent_v1_0 — the human-in-loop execution workflow state (Tier 0B).

Answers "did someone decide to act, and what happened to that decision?" — the layer that makes a
MISSING trade distinguishable from a human REJECTION / EXPIRY / CANCELLATION. Keyed by the opaque
execution-intent `trade_id` (see ``docs/reference/trade_identity_contract.md``).

Event-sourced + frozen: each state is an immutable snapshot; a transition returns a NEW snapshot
(never mutates in place), mirroring the frozen-atom house pattern. **Minimal by design** —
``PROPOSED → {TERMINATED(reason), EXECUTED}``. Splitting `TERMINATED` later is additive; un-merging
states after consumers depend on them is not. A "modification" is NOT a state: it is
``TERMINATED(REPLACED)`` of the old intent + a new ``PROPOSED`` with a fresh `trade_id`.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from enum import Enum

SCHEMA_VERSION = "1.0"


class IntentState(Enum):
    PROPOSED   = "proposed"
    EXECUTED   = "executed"
    TERMINATED = "terminated"


class TerminationReason(Enum):
    REJECTED  = "rejected"     # human / risk gate declined the intent
    EXPIRED   = "expired"      # signal TTL lapsed before action (UltronRiskGate expires_at)
    REPLACED  = "replaced"     # superseded by a re-proposed intent (a "modification")
    CANCELLED = "cancelled"    # withdrawn before execution


# Terminal states have no outgoing transitions.
VALID_TRANSITIONS: "dict[IntentState, tuple[IntentState, ...]]" = {
    IntentState.PROPOSED:   (IntentState.EXECUTED, IntentState.TERMINATED),
    IntentState.EXECUTED:   (),
    IntentState.TERMINATED: (),
}


def can_transition(src: IntentState, dst: IntentState) -> bool:
    return dst in VALID_TRANSITIONS.get(src, ())


def _utc_now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class ExecutionIntentV1:
    """One immutable snapshot of an execution intent's workflow state."""

    trade_id: str
    state: IntentState = IntentState.PROPOSED
    reason: "TerminationReason | None" = None   # required iff state==TERMINATED, else None
    created_at: str = ""
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.trade_id:
            raise ValueError("ExecutionIntentV1.trade_id must be non-empty")
        if self.state is IntentState.TERMINATED and self.reason is None:
            raise ValueError("TERMINATED intent requires a TerminationReason")
        if self.state is not IntentState.TERMINATED and self.reason is not None:
            raise ValueError(
                f"reason must be None unless TERMINATED (state={self.state.value})"
            )
        if not self.created_at:
            object.__setattr__(self, "created_at", _utc_now_iso())

    @classmethod
    def propose(cls, trade_id: str, *, created_at: "str | None" = None) -> "ExecutionIntentV1":
        return cls(trade_id=trade_id, state=IntentState.PROPOSED,
                   created_at=created_at or _utc_now_iso())

    def to(
        self,
        dst: IntentState,
        *,
        reason: "TerminationReason | None" = None,
        at: "str | None" = None,
    ) -> "ExecutionIntentV1":
        """Return a NEW snapshot transitioned to `dst`; raises on an illegal transition."""
        if not can_transition(self.state, dst):
            raise ValueError(f"illegal transition {self.state.value} -> {dst.value}")
        return ExecutionIntentV1(trade_id=self.trade_id, state=dst, reason=reason,
                                 created_at=at or _utc_now_iso())

    @property
    def is_terminal(self) -> bool:
        return not VALID_TRANSITIONS.get(self.state, ())

    def to_dict(self) -> dict:
        return {
            "trade_id": self.trade_id,
            "state": self.state.value,
            "reason": self.reason.value if self.reason else None,
            "created_at": self.created_at,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ExecutionIntentV1":
        reason = d.get("reason")
        return cls(
            trade_id=d["trade_id"],
            state=IntentState(d.get("state", IntentState.PROPOSED.value)),
            reason=TerminationReason(reason) if reason else None,
            created_at=d.get("created_at", ""),
            schema_version=d.get("schema_version", SCHEMA_VERSION),
        )
