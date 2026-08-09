"""Tier 0B — ExecutionIntentV1 (minimal human-in-loop state machine)."""
import dataclasses

import pytest

from src.execution.execution_intent_v1_0 import (
    SCHEMA_VERSION,
    ExecutionIntentV1,
    IntentState,
    TerminationReason,
    VALID_TRANSITIONS,
    can_transition,
)


def test_minimal_state_set():
    # Exactly three states — NOT a six-state flat enum.
    assert {s.value for s in IntentState} == {"proposed", "executed", "terminated"}
    assert {r.value for r in TerminationReason} == {
        "rejected", "expired", "replaced", "cancelled"
    }


def test_propose_is_start_state():
    intent = ExecutionIntentV1.propose("t1")
    assert intent.state is IntentState.PROPOSED
    assert intent.reason is None
    assert intent.is_terminal is False
    assert intent.created_at.endswith("Z")
    assert intent.schema_version == SCHEMA_VERSION


def test_legal_transitions_return_new_frozen_snapshots():
    proposed = ExecutionIntentV1.propose("t1", created_at="2026-07-05T00:00:00Z")
    executed = proposed.to(IntentState.EXECUTED)
    assert executed.state is IntentState.EXECUTED and executed.is_terminal
    assert executed is not proposed and proposed.state is IntentState.PROPOSED  # immutable

    terminated = proposed.to(IntentState.TERMINATED, reason=TerminationReason.REJECTED)
    assert terminated.state is IntentState.TERMINATED
    assert terminated.reason is TerminationReason.REJECTED and terminated.is_terminal


@pytest.mark.parametrize("terminal", [IntentState.EXECUTED, IntentState.TERMINATED])
def test_terminal_states_have_no_exit(terminal):
    assert VALID_TRANSITIONS[terminal] == ()
    src = (ExecutionIntentV1.propose("t1").to(terminal, reason=TerminationReason.EXPIRED)
           if terminal is IntentState.TERMINATED
           else ExecutionIntentV1.propose("t1").to(terminal))
    with pytest.raises(ValueError):
        src.to(IntentState.PROPOSED)


def test_illegal_transition_raises():
    proposed = ExecutionIntentV1.propose("t1")
    assert can_transition(IntentState.PROPOSED, IntentState.EXECUTED)
    assert not can_transition(IntentState.EXECUTED, IntentState.PROPOSED)
    with pytest.raises(ValueError):
        # EXECUTED requires no reason; TERMINATED without reason is illegal by invariant
        proposed.to(IntentState.TERMINATED)  # missing reason


def test_reason_iff_terminated_invariant():
    with pytest.raises(ValueError):  # TERMINATED needs a reason
        ExecutionIntentV1(trade_id="t1", state=IntentState.TERMINATED)
    with pytest.raises(ValueError):  # non-terminated must NOT carry a reason
        ExecutionIntentV1(trade_id="t1", state=IntentState.PROPOSED,
                          reason=TerminationReason.REJECTED)


def test_requires_trade_id():
    with pytest.raises(ValueError):
        ExecutionIntentV1(trade_id="")


def test_dict_round_trip_serializes_enum_values():
    intent = ExecutionIntentV1.propose("t1", created_at="2026-07-05T00:00:00Z").to(
        IntentState.TERMINATED, reason=TerminationReason.REPLACED, at="2026-07-05T00:01:00Z"
    )
    d = intent.to_dict()
    assert d["state"] == "terminated" and d["reason"] == "replaced"
    assert ExecutionIntentV1.from_dict(d) == intent

    # PROPOSED serializes reason as None and round-trips.
    p = ExecutionIntentV1.propose("t2", created_at="2026-07-05T00:00:00Z")
    assert ExecutionIntentV1.from_dict(p.to_dict()) == p
