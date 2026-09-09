"""I. Parent-timeframe / HTF journeys — disjoint graphs, name collisions.

Semantic invariant: RANGE_C1 / MANIPULATION_C2 / DISTRIBUTION_C3 are a parent-
timeframe 3-candle graph. They never share an edge with the M15 execution
machine. HTFState and ObjectiveStatus are a second dimension, not CRTState
members (F-075 / F-077 / F-078).

Ordinary tests pin ParentCRTTrack walks and HTF classifiers in isolation.
They do not ask the M15 StateMachine to take a parent hop, and they do not
treat DISTRIBUTION vs DISTRIBUTION_C3 as a journey collision.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from config_layer.crt_engine_v2 import EngineState, StateMachine
from config_layer.htf_state import HTFState, ObjectiveStatus
from config_layer.state_identity import (
    CRTConfig,
    CRTState,
    Direction,
    EXECUTION_TIMEFRAME_STATES,
    PARENT_TIMEFRAME_STATES,
    VALID_TRANSITIONS,
)

from tests.Grok._fixtures import candle


_PARENT_SPINE = (
    CRTState.RANGE_C1,
    CRTState.MANIPULATION_C2,
    CRTState.DISTRIBUTION_C3,
    CRTState.RANGE_C1,
)


def _sm() -> StateMachine:
    return StateMachine(CRTConfig())


def test_parent_spine_edges_are_in_valid_transitions():
    """C1 → C2 → C3 → C1 must be a declared parent journey.

    Source: state_identity.VALID_TRANSITIONS parent sub-graph
    Failure mode: a documented H4 narrative uses an undeclared hop.
    """
    for a, b in zip(_PARENT_SPINE, _PARENT_SPINE[1:]):
        assert b in VALID_TRANSITIONS[a], f"illegal parent hop {a.name} → {b.name}"


def test_range_c1_self_loop_is_legal_unlike_m15_range():
    """Parent C1 may roll forward in place. M15 RANGE may not.

    Source: VALID_TRANSITIONS[RANGE_C1] includes RANGE_C1; RANGE does not.
    Failure mode: treating both RANGE names as the same self-loop rule.
    """
    assert CRTState.RANGE_C1 in VALID_TRANSITIONS[CRTState.RANGE_C1]
    assert CRTState.RANGE not in VALID_TRANSITIONS[CRTState.RANGE]


@pytest.mark.parametrize(
    "src,dst",
    [
        (src, dst)
        for src in EXECUTION_TIMEFRAME_STATES
        for dst in PARENT_TIMEFRAME_STATES
    ],
)
def test_m15_cannot_hop_into_parent_states(src: CRTState, dst: CRTState):
    """No M15 execution state may become C1/C2/C3 in one hop.

    Source: VALID_TRANSITIONS disjoint-split comment (state_identity.py:95-103)
    Failure mode: process_candle writes RANGE → RANGE_C1 and the parent
    narrative is treated as the M15 episode.
    """
    assert dst not in VALID_TRANSITIONS[src]


@pytest.mark.parametrize(
    "src,dst",
    [
        (src, dst)
        for src in PARENT_TIMEFRAME_STATES
        for dst in EXECUTION_TIMEFRAME_STATES
    ],
)
def test_parent_cannot_hop_into_m15_states(src: CRTState, dst: CRTState):
    """C3 is not EXECUTION. A parent impulse cannot open an M15 trade path.

    Failure mode: DISTRIBUTION_C3 → EXECUTION looks like F-075 'wired'.
    """
    assert dst not in VALID_TRANSITIONS[src]


def test_state_machine_refuses_range_to_range_c1():
    """Live walker agrees with the graph: M15 RANGE cannot become C1.

    Source: StateMachine._transition consults valid_transitions
    """
    sm = _sm()
    st = EngineState()
    assert st.current_state == CRTState.RANGE
    bar = candle(datetime(2026, 7, 15, 20, 0, 0), 1, 2, 0.5, 1.5, idx=1)
    assert sm._transition(st, CRTState.RANGE_C1, "cross-graph", bar) is False
    assert st.current_state == CRTState.RANGE
    assert st.transition_log == []


def test_state_machine_refuses_distribution_c3_to_execution():
    """Even if EngineState is stuffed with C3, EXECUTION is not a legal target."""
    sm = _sm()
    st = EngineState()
    st.current_state = CRTState.DISTRIBUTION_C3
    bar = candle(datetime(2026, 7, 15, 20, 0, 0), 1, 2, 0.5, 1.5, idx=2)
    assert sm._transition(st, CRTState.EXECUTION, "c3-is-not-exec", bar) is False
    assert st.current_state == CRTState.DISTRIBUTION_C3
    assert st.transition_log == []


def test_state_machine_is_graph_only_on_parent_edges():
    """Class C (same as suite A): _transition does not own timeframes.

    If a caller puts RANGE_C1 on the M15 EngineState, the walker will take
    the declared parent hop. Timeframe isolation is the caller's contract
    (ParentCRTTrack + parent_state keyword), not a second graph inside
    StateMachine.
    """
    sm = _sm()
    st = EngineState()
    st.current_state = CRTState.RANGE_C1
    bar = candle(datetime(2026, 7, 15, 20, 0, 0), 1, 2, 0.5, 1.5, idx=3)
    assert sm._transition(st, CRTState.MANIPULATION_C2, "parent-edge", bar) is True
    assert st.current_state == CRTState.MANIPULATION_C2


def test_distribution_c3_is_not_a_trade_opening_state():
    """C3 classifies a parent impulse. TRADE_OPENED requires M15 EXECUTION."""
    assert CRTState.DISTRIBUTION_C3 not in (
        CRTState.EXECUTION,
        CRTState.RETEST,
        CRTState.RESOLUTION,
    )
    assert CRTState.EXECUTION in EXECUTION_TIMEFRAME_STATES
    assert CRTState.DISTRIBUTION_C3 in PARENT_TIMEFRAME_STATES


def test_htf_distribution_is_not_crt_distribution_c3():
    """F-077 name collision: Sujan HTF DISTRIBUTION ≠ parent C3 impulse.

    Source: htf_state.py module doc + HTFState enum
    Failure mode: a report that says 'DISTRIBUTION' is treated as C3.
    """
    assert HTFState.DISTRIBUTION is not CRTState.DISTRIBUTION_C3
    assert HTFState.DISTRIBUTION.name != CRTState.DISTRIBUTION_C3.name
    assert HTFState.EXPANSION is not CRTState.EXPANSION
    assert HTFState.EXPANSION.name == CRTState.EXPANSION.name  # same spelling, different enum
    assert "ACCUMULATION" not in CRTState.__members__
    assert "REVERSAL" not in CRTState.__members__
    assert "UNKNOWN" not in CRTState.__members__


def test_objective_status_is_not_a_crt_state():
    """ObjectiveStatus is a second parent dimension, not a CRTState hop.

    Source: htf_state.ObjectiveStatus; F-078
    Failure mode: EXISTS/ACHIEVED/INVALIDATED appear as state_after.
    """
    for name in ObjectiveStatus.__members__:
        assert name not in CRTState.__members__, name
    assert ObjectiveStatus.NONE.value == "NONE"
    assert Direction.NONE.value == "NONE"
    assert Direction.NONE is not ObjectiveStatus.NONE


def test_parent_and_execution_sets_partition_crtstate():
    """12 = 9 + 3, exhaustive, no overlap.

    Source: PARENT_TIMEFRAME_STATES / EXECUTION_TIMEFRAME_STATES
    """
    assert PARENT_TIMEFRAME_STATES.isdisjoint(EXECUTION_TIMEFRAME_STATES)
    assert PARENT_TIMEFRAME_STATES | EXECUTION_TIMEFRAME_STATES == frozenset(CRTState)
    assert len(PARENT_TIMEFRAME_STATES) == 3
    assert len(EXECUTION_TIMEFRAME_STATES) == 9
    assert set(VALID_TRANSITIONS) == set(CRTState)
