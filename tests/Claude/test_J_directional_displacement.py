"""J. Directional displacement — a legal edge is not a legal journey (F-074).

Semantic invariant: SWEEP -> DISPLACEMENT is an edge in VALID_TRANSITIONS, but
the edge is not the authority. Since CH-directional-displacement-contract
(user-authorized 2026-08-13) the impulse must travel AWAY from the swept side:
LONG = bullish close above sweep.price, SHORT = bearish close below. Unsigned
energy-only displacement is no longer a legal hop.

Ordinary tests pin displacement SHAPES (tests/test_directional_displacement.py
walks six LONG/SHORT bar geometries). They do not ask whether graph legality and
geometry legality can disagree, which of the two direction fields is
authoritative when they conflict, or whether the sign gate is evaluated before
the energy gate.
"""
from __future__ import annotations

import pytest

from config_layer.crt_engine_v2 import StateMachine
from config_layer.state_identity import CRTConfig, CRTState, Direction, VALID_TRANSITIONS

from tests.Claude._fixtures import PERMISSIVE, bar, swept


def test_sweep_to_displacement_edge_is_legal_but_geometry_still_refuses():
    """The graph permits the hop that try_sweep_to_displacement then denies.

    Source: state_identity.VALID_TRANSITIONS vs StateMachine.try_sweep_to_displacement
    Failure mode: an auditor reads the edge out of VALID_TRANSITIONS and concludes
    the journey is reachable, so a wrong-signed bar is treated as a valid setup.
    Why ordinary tests miss it: the graph floors and the shape floors are separate
    files, so nothing asserts that the two authorities disagree by design.
    """
    assert CRTState.DISPLACEMENT in VALID_TRANSITIONS[CRTState.SWEEP]
    sm, st = swept(Direction.LONG, sweep_price=4053.91)
    dump = bar(4058.08, 4059.19, 4046.38, 4047.41)
    assert sm.try_sweep_to_displacement(st, dump) is False
    assert st.current_state is CRTState.SWEEP


@pytest.mark.parametrize("direction", [Direction.LONG, Direction.SHORT])
def test_wrong_sign_is_rejected_before_the_energy_gate(direction: Direction):
    """Sign is checked first: overwhelming energy cannot buy a wrong-signed hop.

    Source: try_sweep_to_displacement guards G_SWEEP_DISP_DIR_LONG / _DIR_SHORT
    run ahead of G_SWEEP_DISP_MOVE (move >= atr_min_displacement * atr).
    Failure mode: 'it was a huge candle' is accepted as displacement, restoring
    the pre-F-074 unsigned energy-only reading.
    Numbers: move = 989.0 against thr_move = 0.5 * atr_abs = 0.5.
    """
    sm, st = swept(direction, sweep_price=50.0 if direction is Direction.LONG else 2000.0)
    wrong = (
        bar(1000.0, 1001.0, 10.0, 11.0)        # enormous DOWN body after a LONG sweep
        if direction is Direction.LONG
        else bar(11.0, 1001.0, 10.0, 1000.0)   # enormous UP body after a SHORT sweep
    )
    assert abs(wrong.close - wrong.open) > 100 * st.atr_abs
    assert sm.try_sweep_to_displacement(st, wrong) is False
    assert st.current_state is CRTState.SWEEP


@pytest.mark.parametrize("sweep_direction", [Direction.LONG, Direction.SHORT])
@pytest.mark.parametrize("bar_is_bullish", [True, False])
def test_sweep_event_direction_outranks_state_direction(
    sweep_direction: Direction, bar_is_bullish: bool
):
    """When the two direction fields disagree, sweep_event.direction governs.

    Source: try_sweep_to_displacement resolves
    `state.sweep_event.direction if state.sweep_event is not None else state.direction`.
    Failure mode: substituting EngineState.direction (the trade-level field) for the
    sweep-level field silently inverts the whole F-074 contract on any bar where the
    two have drifted apart.
    Why ordinary tests miss it: every domain fixture sets both fields to the same
    value, so the fallback branch is never distinguished from the primary one.
    """
    opposite = Direction.SHORT if sweep_direction is Direction.LONG else Direction.LONG
    sm, st = swept(
        sweep_direction,
        sweep_price=99.0 if sweep_direction is Direction.LONG else 111.0,
        state_direction=opposite,
    )
    candidate = bar(100.0, 112.0, 99.5, 111.0) if bar_is_bullish else bar(110.0, 111.5, 98.0, 99.0)
    expected = bar_is_bullish is (sweep_direction is Direction.LONG)
    assert sm.try_sweep_to_displacement(st, candidate) is expected


@pytest.mark.parametrize("direction", [Direction.LONG, Direction.SHORT])
def test_close_exactly_at_sweep_price_is_not_away_from_liquidity(direction: Direction):
    """The away-from-sweep test is strict: closing ON the swept price is a REJECT.

    Source: guards G_SWEEP_DISP_AWAY_LONG (`close > sweep.price`) and
    G_SWEEP_DISP_AWAY_SHORT (`close < sweep.price`) — both strict inequalities.
    Failure mode: a bar that merely returns to the liquidity it swept is booked as
    an impulse away from it, so the setup survives on zero displacement.
    """
    sm, st = swept(direction, sweep_price=105.0)
    correct_sign = (
        bar(100.0, 106.0, 99.0, 105.0) if direction is Direction.LONG
        else bar(110.0, 111.0, 104.0, 105.0)
    )
    assert (correct_sign.close > correct_sign.open) is (direction is Direction.LONG)
    assert correct_sign.close == 105.0
    assert sm.try_sweep_to_displacement(st, correct_sign) is False


@pytest.mark.parametrize(
    "reason",
    ["wrong_sign", "not_away_from_sweep", "insufficient_energy"],
)
def test_rejected_displacement_leaves_no_transition_trace(reason: str):
    """A refused displacement writes nothing — no state move, no transition_log row.

    Source: try_sweep_to_displacement returns False before calling _transition.
    Failure mode: a rejected candidate still appears in the episode trace, so a
    forensic replay counts displacements that the engine never accepted.
    Why ordinary tests miss it: the shape floors assert current_state only, which
    a log-then-revert implementation would also satisfy.
    """
    if reason == "wrong_sign":
        sm, st = swept(Direction.LONG, sweep_price=50.0)
        candidate = bar(1000.0, 1001.0, 10.0, 11.0)
    elif reason == "not_away_from_sweep":
        sm, st = swept(Direction.LONG, sweep_price=105.0)
        candidate = bar(100.0, 106.0, 99.0, 104.0)
    else:
        sm, st = swept(Direction.LONG, sweep_price=99.0)
        candidate = bar(100.0, 100.2, 99.9, 100.1)
    assert sm.try_sweep_to_displacement(st, candidate) is False
    assert st.current_state is CRTState.SWEEP
    assert st.transition_log == []


def test_direction_none_fails_closed_without_a_sweep_event():
    """No sweep event and Direction.NONE resolves to REJECT, never to a default side.

    Source: guard G_SWEEP_DISP_DIR_NONE — `direction in {LONG, SHORT}` is required
    before any bar geometry is inspected.
    Failure mode: an unresolved direction is treated as LONG, so a bullish bar with
    no sweep behind it opens the displacement path.
    """
    sm = StateMachine(CRTConfig(**PERMISSIVE))
    _, st = swept(Direction.NONE, sweep_price=0.0, with_sweep_event=False)
    assert st.sweep_event is None
    assert st.direction is Direction.NONE
    strong_bull = bar(100.0, 112.0, 99.5, 111.0)
    assert sm.try_sweep_to_displacement(st, strong_bull) is False
    assert st.current_state is CRTState.SWEEP
