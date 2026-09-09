"""A. CRT episode journeys — impossible paths, missing intermediates, trade prerequisites.

Semantic invariant: a journey is legal only if every edge is in VALID_TRANSITIONS,
state_before/after agree with the event, and a Trade requires range+sweep+displacement
+direction. Ordinary unit tests pin YAML↔enum counts, not reconstructed episode paths.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from config_layer.crt_engine_v2 import EngineState, StateMachine
from config_layer.state_identity import CRTConfig, CRTState, Direction, VALID_TRANSITIONS

from tests.Grok._fixtures import candle, engine_ready_long, engine_ready_short, executor


# Golden path declared by the auditor prompt (EXPANSION is optional).
_DECLARED_SPINE = (
    CRTState.RANGE,
    CRTState.SWEEP,
    CRTState.DISPLACEMENT,
    CRTState.EXPANSION,
    CRTState.RETEST,
    CRTState.EXECUTION,
)


def _sm() -> StateMachine:
    return StateMachine(CRTConfig())


def test_declared_spine_edges_are_in_valid_transitions():
    """Every consecutive pair of the declared RANGE→…→EXECUTION spine must be legal.

    Source: state_identity.VALID_TRANSITIONS
    Failure mode: a documented journey uses an undeclared hop.
    Why ordinary tests miss it: they check YAML==code, not a specific journey.
    """
    for a, b in zip(_DECLARED_SPINE, _DECLARED_SPINE[1:]):
        assert b in VALID_TRANSITIONS[a], f"illegal spine hop {a.name} → {b.name}"


def test_impossible_direct_range_to_execution_is_rejected():
    """RANGE → EXECUTION is not a legal hop.

    Source: StateMachine._transition + VALID_TRANSITIONS
    Failure mode: skipped causal events (sweep/disp/retest) still open a trade path.
    """
    sm = _sm()
    st = EngineState()
    assert st.current_state == CRTState.RANGE
    bar = candle(datetime(2026, 7, 22, 16, 0, 0), 1, 2, 0.5, 1.5, idx=1)
    assert sm._transition(st, CRTState.EXECUTION, "skip-to-exec", bar) is False
    assert st.current_state == CRTState.RANGE
    assert st.transition_log == []


def test_impossible_retest_to_sweep_is_rejected():
    """Wrong state_after: RETEST cannot return to SWEEP.

    Source: VALID_TRANSITIONS[RETEST] == {EXECUTION, RANGE}
    """
    sm = _sm()
    st = EngineState()
    st.current_state = CRTState.RETEST
    bar = candle(datetime(2026, 7, 22, 19, 0, 0), 1, 2, 0.5, 1.5, idx=2)
    assert sm._transition(st, CRTState.SWEEP, "rewind-sweep", bar) is False
    assert st.current_state == CRTState.RETEST


@pytest.mark.parametrize(
    "src,dst",
    [
        (CRTState.EXECUTION, CRTState.RETEST),
        (CRTState.RESOLUTION, CRTState.EXECUTION),
        (CRTState.EXPIRED, CRTState.RETEST),
        (CRTState.SHADOW_PENDING, CRTState.EXPANSION),  # must be two-step via SWEEP
        (CRTState.SHADOW_PENDING, CRTState.DISPLACEMENT),
        (CRTState.DISPLACEMENT, CRTState.RETEST),  # missing EXPANSION
        (CRTState.SWEEP, CRTState.RETEST),
        (CRTState.RANGE, CRTState.DISPLACEMENT),
    ],
)
def test_missing_intermediate_hops_are_illegal(src: CRTState, dst: CRTState):
    """Skipped causal events must not be a single legal transition.

    Source: VALID_TRANSITIONS
    Failure mode: a trace that writes SHADOW_PENDING→EXPANSION as one hop looks legal
    even though the engine only allows it as SHADOW_PENDING→SWEEP→EXPANSION.
    """
    assert dst not in VALID_TRANSITIONS[src]


def test_shadow_collapse_is_two_legal_hops_not_one():
    """SHADOW_EXPANSION_CONFIRMED is a collapse, not a missing-intermediate journey.

    Source: StateMachine.try_shadow_pending_to_expansion (crt_engine_v2.py:1066-1090)
    Failure mode: traces that record state_before=SHADOW_PENDING, state_after=EXPANSION
    look like an illegal hop; the engine inserts SWEEP.
    Why ordinary tests miss it: they never reconstruct the action token vs the two
    STATE_TRANSITION events.
    """
    sm = _sm()
    st = EngineState()
    st.current_state = CRTState.SHADOW_PENDING
    bar = candle(datetime(2026, 7, 22, 17, 30, 0), 4146.43, 4153.06, 4146.33, 4151.09, idx=66)
    st.pending_displacement_candle = candle(
        datetime(2026, 7, 22, 16, 30, 0), 4132.02, 4146.75, 4132.02, 4142.79, idx=62
    )
    st.pending_displacement_dir = Direction.SHORT
    assert sm.try_shadow_pending_to_expansion(st, bar) is True
    assert st.current_state == CRTState.EXPANSION
    hops = [(e["from"], e["to"]) for e in st.transition_log]
    assert hops == [("SHADOW_PENDING", "SWEEP"), ("SWEEP", "EXPANSION")]
    assert st.displacement_candle is st.pending_displacement_candle


def test_shadow_collapse_restores_older_displacement_than_confirming_bar():
    """Direction/event disagreement class: live bar is not the SL-anchor candle.

    Source: try_shadow_pending_to_expansion assigns pending_displacement_candle
    Failure mode: SL is computed from a pre-RESET candle while the sweep is later.
    Observed in run 20260813T124158Z (disp idx 62 vs sweep idx 65).
    """
    sm = _sm()
    st = EngineState()
    st.current_state = CRTState.SHADOW_PENDING
    confirm = candle(datetime(2026, 7, 22, 17, 30, 0), 1, 2, 0.5, 1.5, idx=66)
    old = candle(datetime(2026, 7, 22, 16, 30, 0), 4132.02, 4146.75, 4132.02, 4142.79, idx=62)
    st.pending_displacement_candle = old
    st.pending_displacement_dir = Direction.SHORT
    sm.try_shadow_pending_to_expansion(st, confirm)
    assert st.displacement_candle.index == 62
    assert st.displacement_candle.index < confirm.index
    assert st.displacement_candle.timestamp < confirm.timestamp


def test_transition_legality_is_graph_only():
    """Class C: VALID_TRANSITIONS is the contract; _transition does not own clocks.

    Timestamp order is the loader's job (CandleLoader.stream). This pins that
    a legal hop is still legal when the candle timestamp goes backwards —
    not a claim that callers should feed reversed clocks.
    """
    sm = _sm()
    st = EngineState()
    later = candle(datetime(2026, 7, 22, 16, 15, 0), 1, 2, 0.5, 1.5, idx=2)
    earlier = candle(datetime(2026, 7, 22, 16, 0, 0), 1, 2, 0.5, 1.5, idx=1)
    assert sm._transition(st, CRTState.SWEEP, "fwd", later) is True
    # legally hop SWEEP → RANGE with a *previous* timestamp
    assert sm._transition(st, CRTState.RANGE, "back-in-time", earlier) is True
    assert st.transition_log[-1]["to"] == "RANGE"
    assert earlier.timestamp < later.timestamp


def test_duplicated_identical_transition_is_not_idempotent_log():
    """Duplicated events: repeating a legal hop after it already happened is illegal,
    but the first hop is logged once. A second RANGE→SWEEP after already SWEEP fails.

    Source: _transition consults current_state, not event identity.
    """
    sm = _sm()
    st = EngineState()
    bar = candle(datetime(2026, 7, 22, 16, 15, 0), 1, 2, 0.5, 1.5, idx=1)
    assert sm._transition(st, CRTState.SWEEP, "first", bar) is True
    assert sm._transition(st, CRTState.SWEEP, "dup", bar) is False
    assert [e["to"] for e in st.transition_log] == ["SWEEP"]


def test_build_trade_refuses_missing_range_or_sweep():
    """Trade created without prerequisites must be None.

    Source: ExecutionEngine.build_trade (crt_engine_v2.py:2194-2211)
    """
    ex = executor()
    empty = EngineState()
    empty.direction = Direction.SHORT
    empty.atr_abs = 9.0
    assert ex.build_trade(empty) is None


def test_build_trade_refuses_missing_displacement():
    st = engine_ready_short()
    st.displacement_candle = None
    assert executor().build_trade(st) is None


def test_build_trade_refuses_direction_none():
    st = engine_ready_short()
    st.direction = Direction.NONE
    assert executor().build_trade(st) is None


def test_build_trade_refuses_inverted_short_from_traced_episode():
    """Wrong-direction geometry: RETEST close past disp_high inverts SHORT SL.

    Source: build_trade SHORT guard sl > entry (crt_engine_v2.py:2237)
    Numbers: proof_2026-07-22_191500_SHORT_A3.md
    """
    trade = executor().build_trade(engine_ready_short())
    assert trade is None


def test_build_trade_refuses_inverted_long_from_traced_episode():
    """Numbers: proof_2026-07-28_054500_LONG_A3.md"""
    trade = executor().build_trade(engine_ready_long())
    assert trade is None


def test_build_trade_succeeds_when_entry_is_on_the_protective_side():
    """Control: same SHORT structure but entry below sl → Trade exists.

    Proves the inverted-SL tests are not vacuously rejecting every SHORT.
    """
    st = engine_ready_short(entry=4140.00)
    st.retest_candle = candle(
        datetime(2026, 7, 22, 19, 0, 0), 4141.0, 4142.0, 4139.0, 4140.00, idx=72
    )
    trade = executor().build_trade(st)
    assert trade is not None
    assert trade.direction == Direction.SHORT
    assert trade.sl_price > trade.entry_price
