"""
Shadow-memory TTL lifecycle floor — the off-by-one fix.

Root cause (see plan file `pure-conversation-when-you-curried-ocean.md` and the finding
this registers): `reset_to_range`'s `[DEADLOCK FIX]` fall-through means a shadow created on
HTF-triggered reset reaches `process_candle`'s RANGE branch on the SAME candle, and that
branch used to decrement `pending_displacement_ttl` unconditionally — so a configured TTL
of N used to yield only N-1 usable bars. The fix adds `pending_displacement_created_idx`
(set once, on creation) and skips the decrement when `candle.index ==
pending_displacement_created_idx`.

`test_shadow_survives_configured_ttl_then_expires` is written to FAIL against the pre-fix
code (which decrements on the creating bar) and PASS after — see the inline note at that
assertion for the exact pre-fix sequence it would have produced.

These tests drive a real `CRTEngine.process_candle()` through the actual
`ResetLogic.should_reset` -> `reset_to_range` -> RANGE-branch fall-through path (not a
reimplementation of the guard logic), using `CRTConfig()` constructed directly — legitimate
for a unit test even though production code requires the market-router path
(`ConfigBuilder.build`).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from config_layer.crt_engine_v2 import (
    Candle, CRTConfig, CRTEngine, CRTState, Direction, Range, SweepEvent,
)

_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _candle(i: int, o: float, h: float, l: float, c: float) -> Candle:
    return Candle(timestamp=_T0 + timedelta(minutes=15 * i), open=o, high=h, low=l, close=c)


def _engine(ttl: int) -> CRTEngine:
    return CRTEngine(CRTConfig(pending_displacement_ttl_candles=ttl))


def _seed_displacement(
    engine: CRTEngine, htf_id: str = "HTF-1",
    h_ref: float = 110.0, l_ref: float = 90.0, direction: Direction = Direction.LONG,
) -> Range:
    """Force EngineState directly into DISPLACEMENT with an active range, so the next
    process_candle() call — given a NEW htf_candle_id — trips ResetLogic.should_reset's
    'HTF changed' branch and reset_to_range's `_create_shadow` path for real."""
    rng = Range(
        h_ref=h_ref, l_ref=l_ref, equilibrium=(h_ref + l_ref) / 2.0,
        formed_at=_T0, htf_candle_id=htf_id, session="LONDON",
    )
    engine.state.active_range = rng
    engine.state.current_state = CRTState.DISPLACEMENT
    engine.state.direction = direction
    engine.state.displacement_candle = _candle(0, 100.0, 106.0, 99.0, 105.0)
    engine.state.atr_abs = 2.0
    return rng


def _flat_candle(i: int) -> Candle:
    """A candle safely inside [90, 110] that triggers neither sweep boundary."""
    return _candle(i, 100.0, 101.0, 99.0, 100.5)


def _long_sweep_candle(i: int, l_ref: float) -> Candle:
    """low dips below l_ref and closes back above it -> RangeDetector.detect_sweep LONG.
    Offsets are relative to l_ref (not absolute prices) so this works against whatever
    active_range detect_htf_range actually re-seeded — see the caller's note on why the
    manually-seeded Range in _seed_displacement is NOT what survives past the creation bar."""
    return _candle(i, l_ref + 0.5, l_ref + 1.0, l_ref - 2.0, l_ref + 0.5)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Creation
# ─────────────────────────────────────────────────────────────────────────────

def test_creating_bar_does_not_decrement_ttl():
    engine = _engine(ttl=4)
    _seed_displacement(engine, htf_id="HTF-1")

    c1 = _flat_candle(1)
    engine.process_candle(c1, "HTF-2")  # HTF changed -> should_reset -> reset_to_range(HTF...)

    assert engine.state.current_state == CRTState.RANGE
    assert engine.state.pending_displacement_candle is not None
    assert engine.state.pending_displacement_dir == Direction.LONG
    assert engine.state.pending_displacement_ttl == 4          # NOT decremented on its own bar
    assert engine.state.pending_displacement_created_idx == c1.index


def test_non_htf_reset_before_creation_leaves_ttl_untouched():
    """A retrace/extension reset (no 'HTF' in reason) with no pre-existing shadow is a no-op
    on the new field — sanity guard, not the main behavior under test."""
    engine = _engine(ttl=4)
    engine.state.active_range = Range(
        h_ref=110.0, l_ref=90.0, equilibrium=100.0, formed_at=_T0,
        htf_candle_id="HTF-1", session="LONDON",
    )
    assert engine.state.pending_displacement_ttl == 0
    assert engine.state.pending_displacement_created_idx == 0


# ─────────────────────────────────────────────────────────────────────────────
# 2. Survives exactly `ttl_candles` subsequent RANGE bars, then expires
# ─────────────────────────────────────────────────────────────────────────────

def test_shadow_survives_configured_ttl_then_expires():
    ttl = 4
    engine = _engine(ttl=ttl)
    _seed_displacement(engine, htf_id="HTF-1")

    c1 = _flat_candle(1)
    engine.process_candle(c1, "HTF-2")  # creating bar
    created_idx = engine.state.pending_displacement_created_idx
    assert engine.state.pending_displacement_ttl == ttl

    observed = []
    for i in range(2, 2 + ttl):
        engine.process_candle(_flat_candle(i), "HTF-2")  # no further HTF change, no sweep
        observed.append(engine.state.pending_displacement_ttl)

    # Post-fix: 4 further RANGE bars each decrement once -> 3, 2, 1, 0 (expires on the 4th).
    # Pre-fix (creating bar ALSO decremented): the sequence would have been 2, 1, 0, 0 —
    # one bar short of the configured TTL, and this assertion fails against that code.
    assert observed == [ttl - 1, ttl - 2, ttl - 3, 0]
    assert engine.state.pending_displacement_candle is None
    assert engine.state.pending_displacement_dir == Direction.NONE
    assert engine.state.pending_displacement_created_idx == 0  # cleared on TTL exhaustion
    assert created_idx == c1.index


# ─────────────────────────────────────────────────────────────────────────────
# 3. A matching-direction sweep one tick before natural expiry still resumes
# ─────────────────────────────────────────────────────────────────────────────

def test_matching_sweep_before_expiry_still_resumes_and_then_consumes():
    ttl = 3
    engine = _engine(ttl=ttl)
    _seed_displacement(engine, htf_id="HTF-1", h_ref=110.0, l_ref=90.0,
                        direction=Direction.LONG)

    engine.process_candle(_flat_candle(1), "HTF-2")   # creation; ttl stays 3
    assert engine.state.pending_displacement_ttl == 3
    # ResetLogic.should_reset's HTF-change branch re-seeds active_range from the recent
    # candle_buffer (detect_htf_range) — it does NOT keep the manually-seeded Range above.
    # Read the REAL post-reset range for the sweep geometry below, rather than assume it.
    real_l_ref = engine.state.active_range.l_ref

    engine.process_candle(_flat_candle(2), "HTF-2")   # ttl 3 -> 2, survives
    assert engine.state.pending_displacement_ttl == 2
    assert engine.state.current_state == CRTState.RANGE

    # This bar: ttl decrements 2 -> 1 (still > 0, does NOT hit the exhaustion-clear branch)
    # BEFORE sweep detection runs later in the same RANGE branch — proving resume still
    # works right up against the edge of expiry, not just immediately after creation.
    engine.process_candle(_long_sweep_candle(3, l_ref=real_l_ref), "HTF-2")

    assert engine.state.current_state == CRTState.SHADOW_PENDING
    assert engine.state.pending_displacement_ttl == 1          # untouched by the RANGE->SHADOW_PENDING hop
    assert engine.state.pending_displacement_candle is not None
    assert engine.state.pending_displacement_created_idx != 0  # not yet consumed

    # Next bar: SHADOW_PENDING branch collapses SHADOW_PENDING -> SWEEP -> EXPANSION and
    # clears ALL pending_* fields, including the new one (the "consumed" teardown path).
    engine.process_candle(_flat_candle(4), "HTF-2")

    assert engine.state.current_state == CRTState.EXPANSION
    assert engine.state.pending_displacement_ttl == 0
    assert engine.state.pending_displacement_candle is None
    assert engine.state.pending_displacement_dir == Direction.NONE
    assert engine.state.pending_displacement_created_idx == 0


# ─────────────────────────────────────────────────────────────────────────────
# 4. Teardown coverage: SHADOW_LEAK and non-HTF reset both clear the new field
# ─────────────────────────────────────────────────────────────────────────────

def test_shadow_leak_clears_created_idx():
    engine = _engine(ttl=4)
    rng = Range(h_ref=110.0, l_ref=90.0, equilibrium=100.0, formed_at=_T0,
                htf_candle_id="HTF-1", session="LONDON")
    engine.state.active_range = rng
    engine.state.current_state = CRTState.SHADOW_PENDING
    engine.state.pending_displacement_dir = Direction.LONG
    engine.state.pending_displacement_ttl = 2
    engine.state.pending_displacement_created_idx = 99
    engine.state.pending_displacement_candle = _candle(0, 100.0, 106.0, 99.0, 105.0)
    # Mismatched sweep direction -> SHADOW_LEAK integrity check fires.
    mismatched_candle = _flat_candle(1)
    engine.state.sweep_event = SweepEvent(
        direction=Direction.SHORT, price=109.0, candle=mismatched_candle,
    )

    engine.process_candle(mismatched_candle, "HTF-1")  # same htf id -> no should_reset trigger

    assert engine.state.pending_displacement_ttl == 0
    assert engine.state.pending_displacement_candle is None
    assert engine.state.pending_displacement_dir == Direction.NONE
    assert engine.state.pending_displacement_created_idx == 0


def test_non_htf_reset_expires_existing_shadow_and_clears_created_idx():
    engine = _engine(ttl=4)
    engine.state.active_range = Range(
        h_ref=110.0, l_ref=90.0, equilibrium=100.0, formed_at=_T0,
        htf_candle_id="HTF-1", session="LONDON",
    )
    engine.state.pending_displacement_ttl = 2
    engine.state.pending_displacement_created_idx = 7
    engine.state.pending_displacement_candle = _candle(0, 100.0, 106.0, 99.0, 105.0)
    engine.state.pending_displacement_dir = Direction.LONG

    c = _flat_candle(1)
    # Direct call, mirroring the non-HTF reset paths in process_candle (retrace/extension) —
    # reason deliberately has no "HTF" substring.
    engine.sm.reset_to_range(engine.state, "50% retrace hit (retrace=1.000)", c, engine.ev_log)

    assert engine.state.pending_displacement_ttl == 0
    assert engine.state.pending_displacement_candle is None
    assert engine.state.pending_displacement_dir == Direction.NONE
    assert engine.state.pending_displacement_created_idx == 0
