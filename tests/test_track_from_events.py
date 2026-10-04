"""Floor for `charts.crt_overlay.track_from_events` (CH-trade-chart-tab, 2026-09-10).

`resolve_states` was refactored to extract the parse/align/fill body into
`track_from_events` so the dashboard (reading an already-produced run's `events.jsonl`)
never triggers a fresh spine run to get a CRT track. This floor is behaviour-preserving
evidence for that split: `track_from_events` in isolation, and `resolve_states` composed
from it via a monkeypatched `run_spine_for_states` (no real spine execution, no
ACTIVE_VERSION dependency).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from charts import crt_overlay as co            # noqa: E402


def _write_events(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def _base_ts(n: int, start: datetime | None = None, step_min: int = 15) -> list[datetime]:
    t0 = start or datetime(2026, 1, 1, 0, 0, 0)
    return [t0 + timedelta(minutes=step_min * i) for i in range(n)]


def test_track_from_events_forward_fills_between_events(tmp_path):
    base = _base_ts(6)
    events_path = tmp_path / "XAUUSD_events.jsonl"
    _write_events(events_path, [
        {"event": "STATE_TRANSITION", "timestamp": base[1].isoformat(),
         "candle_index": 1, "state_from": "RANGE", "state_to": "SWEEP"},
        {"event": "STATE_TRANSITION", "timestamp": base[4].isoformat(),
         "candle_index": 4, "state_from": "SWEEP", "state_to": "DISPLACEMENT"},
        # A non-state-moving line must be ignored, not misparsed.
        {"event": "SWEEP", "timestamp": base[1].isoformat(), "direction": "LONG"},
    ])

    track = co.track_from_events(events_path, base, "test_version")

    assert track.states == ["RANGE", "SWEEP", "SWEEP", "SWEEP", "DISPLACEMENT", "DISPLACEMENT"]
    assert track.source == "RESOLVED:test_version"
    assert track.version == "test_version"
    assert track.transitions == 2
    assert track.resolved is True


def test_track_from_events_reset_after_transition_same_bar_uses_emission_order(tmp_path):
    """A RESET landing on the same bar as a STATE_TRANSITION must resolve to whichever
    the engine emitted LAST, not to a re-sorted order (docstring invariant of
    `_forward_fill`: 'Do NOT re-sort: same-bar RESET vs STATE_TRANSITION ordering is
    carried by emission order')."""
    base = _base_ts(3)
    events_path = tmp_path / "XAUUSD_events.jsonl"
    _write_events(events_path, [
        {"event": "STATE_TRANSITION", "timestamp": base[1].isoformat(),
         "candle_index": 1, "state_from": "RANGE", "state_to": "SWEEP"},
        {"event": "RESET", "timestamp": base[1].isoformat(),
         "candle_index": 1, "state_from": "SWEEP", "state_to": "RANGE"},
    ])

    track = co.track_from_events(events_path, base, "v")
    assert track.states == ["RANGE", "RANGE", "RANGE"]


def test_track_from_events_degrades_honestly_on_corpus_mismatch(tmp_path):
    """Event timestamps absent from `base_ts` is a wrong-corpus error — fail closed with
    an UNAVAILABLE track, never a partially-coloured or exception-raising one."""
    base = _base_ts(3)
    events_path = tmp_path / "XAUUSD_events.jsonl"
    _write_events(events_path, [
        {"event": "STATE_TRANSITION", "timestamp": (base[0] - timedelta(days=999)).isoformat(),
         "candle_index": 0, "state_from": "RANGE", "state_to": "SWEEP"},
    ])

    track = co.track_from_events(events_path, base, "v")
    assert track.resolved is False
    assert track.source.startswith("UNAVAILABLE:alignment failed")
    assert track.states == [co.CRT_UNAVAILABLE] * len(base)


def test_track_from_events_empty_events_file_stays_initial_state(tmp_path):
    base = _base_ts(4)
    events_path = tmp_path / "XAUUSD_events.jsonl"
    events_path.write_text("", encoding="utf-8")

    track = co.track_from_events(events_path, base, "v")
    assert track.resolved is False
    assert "no state events" in track.source or track.source.startswith("UNAVAILABLE")


def test_resolve_states_composes_track_from_events(tmp_path, monkeypatch):
    """`resolve_states` must produce EXACTLY what `track_from_events` would on the same
    events file — the refactor moved code, it must not have changed behaviour. The spine
    itself is never run: `run_spine_for_states` is monkeypatched to hand back a fixed
    events file, and an explicit `version=` skips the ACTIVE_VERSION lookup."""
    base = _base_ts(5)
    events_path = tmp_path / "XAUUSD_events.jsonl"
    _write_events(events_path, [
        {"event": "STATE_TRANSITION", "timestamp": base[2].isoformat(),
         "candle_index": 2, "state_from": "RANGE", "state_to": "SWEEP"},
    ])

    monkeypatch.setattr(co, "run_spine_for_states",
                         lambda instrument, csv_path, ver: events_path)

    direct = co.track_from_events(events_path, base, "pinned_version")
    composed = co.resolve_states("XAUUSD", "unused.csv", base, version="pinned_version")

    assert composed.states == direct.states
    assert composed.source == direct.source
    assert composed.transitions == direct.transitions
