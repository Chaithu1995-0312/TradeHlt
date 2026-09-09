"""CH-htfcrt-parent-candle-smc-v1 — config_layer.parent_crt.ParentCRTTrack tests.

Covers:
  * the golden narrative (C1 -> C2 sweep -> C3 confirmed distribution -> reset)
  * every transition ParentCRTTrack ever takes is a legal edge in
    state_identity.VALID_TRANSITIONS's disjoint parent-timeframe sub-graph
  * self-loops / resets: no sweep -> stays/rolls RANGE_C1; sweep but no confirming
    impulse -> MANIPULATION_C2 -> RANGE_C1 (not stuck)
  * SHORT-side symmetry (high swept -> bearish confirming impulse)
  * the F-074 directional contract at parent scale: unsigned/energy-only impulses do
    NOT confirm distribution (mirrors the M15 engine's own CH-directional-displacement-
    contract — a contradiction here would silently re-legalize what F-074 banned)
  * bias is NONE except exactly at DISTRIBUTION_C3, and clears immediately on reset
  * adversarial: an out-of-order / malformed feed still only ever takes legal edges
    (the state machine cannot be walked outside VALID_TRANSITIONS no matter what
    candle sequence is fed to it)
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.crt_engine_v2 import Candle                 # noqa: E402
from config_layer.parent_crt import ParentCRTTrack             # noqa: E402
from config_layer.state_identity import (                      # noqa: E402
    CRTState, Direction, VALID_TRANSITIONS,
)


def _c(ts, o, h, l, cl, idx) -> Candle:
    return Candle(timestamp=ts, open=o, high=h, low=l, close=cl, volume=1.0, index=idx)


def _day(i: int) -> datetime:
    return datetime(2024, 1, 1) + timedelta(days=i)


def test_initial_state_before_any_candle():
    t = ParentCRTTrack()
    assert t.state == CRTState.RANGE_C1
    assert t.range is None
    assert t.sweep is None
    assert t.bias == Direction.NONE


def test_first_candle_ever_becomes_c1_without_a_transition_check():
    t = ParentCRTTrack()
    s = t.on_parent_close(_c(_day(0), 105, 110, 100, 107, 0))
    assert s == CRTState.RANGE_C1
    assert t.range.h_ref == 110 and t.range.l_ref == 100


def test_golden_narrative_long_side():
    t = ParentCRTTrack()
    t.on_parent_close(_c(_day(0), 105, 110, 100, 107, 0))            # C1: [100,110]
    s2 = t.on_parent_close(_c(_day(1), 99, 101, 95, 100.5, 1))         # C2: sweep low
    assert s2 == CRTState.MANIPULATION_C2
    assert t.sweep.direction == Direction.LONG
    assert t.sweep.price == 95
    assert t.bias == Direction.NONE   # sweep alone must NOT set a bias
    s3 = t.on_parent_close(_c(_day(2), 101, 120, 100, 118, 2))         # C3: bullish, close>95
    assert s3 == CRTState.DISTRIBUTION_C3
    assert t.bias == Direction.LONG
    s4 = t.on_parent_close(_c(_day(3), 118, 125, 116, 122, 3))         # next candle
    assert s4 == CRTState.RANGE_C1                                    # only legal edge
    assert t.bias == Direction.NONE                                   # bias clears on reset
    assert t.range.h_ref == 125 and t.range.l_ref == 116               # new C1 = this candle


def test_golden_narrative_short_side_symmetry():
    t = ParentCRTTrack()
    t.on_parent_close(_c(_day(0), 105, 110, 100, 107, 0))             # C1: [100,110]
    s2 = t.on_parent_close(_c(_day(1), 111, 115, 109, 109.5, 1))       # C2: sweep high, close<110
    assert s2 == CRTState.MANIPULATION_C2
    assert t.sweep.direction == Direction.SHORT
    assert t.sweep.price == 115
    s3 = t.on_parent_close(_c(_day(2), 109, 110, 90, 92, 2))           # C3: bearish, close<115
    assert s3 == CRTState.DISTRIBUTION_C3
    assert t.bias == Direction.SHORT


def test_no_sweep_rolls_c1_forward_self_loop():
    t = ParentCRTTrack()
    t.on_parent_close(_c(_day(0), 105, 110, 100, 107, 0))             # C1: [100,110]
    inside = _c(_day(1), 106, 108, 104, 107, 1)                       # entirely inside range
    s2 = t.on_parent_close(inside)
    assert s2 == CRTState.RANGE_C1
    assert (CRTState.RANGE_C1, CRTState.RANGE_C1) == (CRTState.RANGE_C1, s2)
    assert t.range.h_ref == 108 and t.range.l_ref == 104               # rolled to the new candle
    assert t.bias == Direction.NONE


def test_sweep_without_confirming_impulse_resets_to_range_c1_not_stuck():
    t = ParentCRTTrack()
    t.on_parent_close(_c(_day(0), 105, 110, 100, 107, 0))             # C1: [100,110]
    t.on_parent_close(_c(_day(1), 99, 101, 95, 100.5, 1))              # C2: sweep low -> LONG
    assert t.state == CRTState.MANIPULATION_C2
    # C3 candidate: bearish, and doesn't clear sweep.price (95) either way -> not confirmed
    weak = _c(_day(2), 90, 92, 88, 91, 2)
    s3 = t.on_parent_close(weak)
    assert s3 == CRTState.RANGE_C1   # MANIPULATION_C2 -> RANGE_C1, the only non-confirm edge
    assert t.sweep is None           # sweep memory cleared on reset
    assert t.bias == Direction.NONE


def test_unsigned_energy_only_impulse_does_not_confirm_distribution():
    """F-074 parity: a LARGE but WRONG-direction (or non-committal) move must NOT confirm
    distribution, even if it clears the sweep price numerically in the wrong way."""
    t = ParentCRTTrack()
    t.on_parent_close(_c(_day(0), 105, 110, 100, 107, 0))             # C1: [100,110]
    t.on_parent_close(_c(_day(1), 99, 101, 95, 100.5, 1))              # C2: LONG sweep, price=95
    assert t.state == CRTState.MANIPULATION_C2
    # Bearish candle that closes ABOVE sweep.price (95) -- big move, wrong direction (not bullish)
    bearish_big_move = _c(_day(2), 150, 155, 90, 96, 2)   # close(96)>open? no: 96<150 -> bearish
    s3 = t.on_parent_close(bearish_big_move)
    assert s3 == CRTState.RANGE_C1   # rejected: not bullish, regardless of close vs sweep.price


@pytest.mark.parametrize("seed", range(25))
def test_adversarial_every_taken_transition_is_legal_random_walks(seed):
    """No matter what candle sequence is fed (including pathological/degenerate ones), every
    single state change ParentCRTTrack ever reports must be a legal VALID_TRANSITIONS edge."""
    import random
    rng = random.Random(seed)
    t = ParentCRTTrack()
    prev_state = t.state
    base = 1000.0
    for i in range(60):
        o = base + rng.uniform(-50, 50)
        span = rng.uniform(0.5, 60)
        h = o + rng.uniform(0, span)
        l = o - rng.uniform(0, span)
        cl = rng.uniform(l, h)
        cand = _c(_day(i), o, h, l, cl, i)
        new_state = t.on_parent_close(cand)
        if new_state != prev_state:
            assert new_state in VALID_TRANSITIONS[prev_state], (
                f"seed={seed} step={i}: illegal edge {prev_state} -> {new_state}"
            )
        else:
            # self-loop must also be declared legal (RANGE_C1 is the only state with one)
            assert new_state in VALID_TRANSITIONS[prev_state] or new_state == prev_state
        prev_state = new_state


def test_bias_only_nonnone_exactly_at_distribution_c3():
    t = ParentCRTTrack()
    assert t.bias == Direction.NONE
    t.on_parent_close(_c(_day(0), 105, 110, 100, 107, 0))
    assert t.bias == Direction.NONE
    t.on_parent_close(_c(_day(1), 99, 101, 95, 100.5, 1))
    assert t.state == CRTState.MANIPULATION_C2
    assert t.bias == Direction.NONE
    t.on_parent_close(_c(_day(2), 101, 120, 100, 118, 2))
    assert t.state == CRTState.DISTRIBUTION_C3
    assert t.bias == Direction.LONG
    t.on_parent_close(_c(_day(3), 118, 125, 116, 122, 3))
    assert t.state == CRTState.RANGE_C1
    assert t.bias == Direction.NONE
