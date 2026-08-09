"""Regression floor for the CRT engine-timeline reconstruction (state_from guard).

Guards the accounting-drift root cause: reconstruct_engine_timeline replayed RESET events without
honoring the engine's authoritative state_from (reset_to_range emits state_from=current_state,
crt_engine_v2.py:1712). A reset the engine issued from RANGE/SWEEP was truncating a still-active
reconstructed EXPANSION, giving reconstructed EXPANSION 3,060 vs the authoritative
state_distribution's 4,605. The guard (skip a RESET whose state_from != running state) reconciles
the timeline with state_distribution.

These synthetic tests pin the guard behaviour without depending on any backtest run artifact.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.research.crt_state_confusion_matrix import reconstruct_engine_timeline  # noqa: E402


def _ev(ordi, ci, event, sfrom, sto, reason=""):
    return {
        "_ord": ordi, "candle_index": ci, "event": event,
        "state_from": sfrom, "state_to": sto, "reason": reason,
    }


def test_stale_from_reset_does_not_truncate_active_state():
    """A RESET issued from RANGE while we are reconstructing EXPANSION must be ignored."""
    events = [
        _ev(0, 0, "STATE_TRANSITION", "RANGE", "SWEEP"),
        _ev(1, 1, "STATE_TRANSITION", "SWEEP", "DISPLACEMENT"),
        _ev(2, 2, "STATE_TRANSITION", "DISPLACEMENT", "EXPANSION"),
        # interior resets with STALE state_from (engine was really elsewhere at these bars) —
        # the guard must skip them so EXPANSION dwell is preserved.
        _ev(3, 3, "RESET", "RANGE", "RANGE", "HTF changed"),
        _ev(4, 4, "RESET", "SWEEP", "RANGE", "HTF changed"),
        _ev(5, 5, "RESET", "RANGE", "RANGE", "HTF changed"),
        # real forward exit
        _ev(6, 10, "STATE_TRANSITION", "EXPANSION", "RETEST"),
    ]
    tl = reconstruct_engine_timeline(events, n_bars=12)
    counts = Counter(tl.enter_states)
    # EXPANSION occupies enter bars 3..10 inclusive == 8 bars.
    assert counts["EXPANSION"] == 8, tl.enter_states
    # No spurious RANGE re-entry mid-EXPANSION.
    assert tl.enter_states[3:11] == ["EXPANSION"] * 8


def test_matching_from_reset_is_applied():
    """A RESET whose state_from matches the running state IS a real reset and must be applied."""
    events = [
        _ev(0, 0, "STATE_TRANSITION", "RANGE", "SWEEP"),
        _ev(1, 1, "STATE_TRANSITION", "SWEEP", "DISPLACEMENT"),
        _ev(2, 2, "STATE_TRANSITION", "DISPLACEMENT", "EXPANSION"),
        _ev(3, 5, "RESET", "EXPANSION", "RANGE", "Session gap"),  # genuine EXPANSION reset
    ]
    tl = reconstruct_engine_timeline(events, n_bars=8)
    counts = Counter(tl.enter_states)
    # EXPANSION occupies enter bars 3,4,5 == 3 bars, then RANGE from bar 6.
    assert counts["EXPANSION"] == 3, tl.enter_states
    assert tl.enter_states[6] == "RANGE"


def test_without_guard_the_bug_would_undercount():
    """Documents the defect: an unguarded replay truncates EXPANSION at the first stale reset."""
    events = [
        _ev(0, 2, "STATE_TRANSITION", "DISPLACEMENT", "EXPANSION"),
        _ev(1, 3, "RESET", "RANGE", "RANGE", "HTF changed"),
        _ev(2, 10, "STATE_TRANSITION", "EXPANSION", "RETEST"),
    ]
    tl = reconstruct_engine_timeline(events, n_bars=12)
    # With the guard, EXPANSION spans bars 3..10 (8). The pre-fix behaviour would have been 1.
    assert Counter(tl.enter_states)["EXPANSION"] == 8
    assert any("Skipped 1 RESET" in n for n in tl.reconstruction_notes)
