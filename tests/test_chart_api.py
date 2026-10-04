"""Floor for `charts.chart_api.chart_payload` (CH-trade-chart-tab, 2026-09-10).

The dashboard's `/api/chart_series` endpoint (`src/control_plane/server.py`) is a thin
route over this function; this floor tests the function directly, matching
`tests/test_dashboard_run_scope.py`'s discipline (skip cleanly when a real
`results/run_*_<INSTR>/` fixture is absent; never fabricate one).

Every scenario that needs a REAL run uses whatever XAUUSD run already exists on disk
(read-only) rather than writing new ones under `results/` — a gitignored data tree other
concurrent sessions also write to (CLAUDE.md §1.1 / memory: concurrent-sessions gotcha).
The corpus-mismatch / degrade-path tests instead monkeypatch a resolved `RunContext`'s
`events_path` at a temp file, so they never depend on real fixtures at all.
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

from charts import chart_api                                    # noqa: E402
from control_plane.dashboard_api import _instruments_from_disk, _iter_run_dirs  # noqa: E402


def _any_xauusd_run():
    """First real XAUUSD run on disk, or None. XAUUSD is the standing probe corpus
    (CLAUDE.md §1.5) so this is the instrument every other chart test also targets."""
    if "XAUUSD" not in _instruments_from_disk():
        return None
    return next(_iter_run_dirs("XAUUSD"), None)


# ── fixture-independent: unknown run always fails closed ───────────────────

def test_chart_payload_unknown_run_is_ok_false():
    d = chart_api.chart_payload("XAUUSD", "run_totally_not_a_real_run_id")
    assert d["ok"] is False
    assert "error" in d and d["error"]


def test_chart_payload_unsupported_timeframe_is_ok_false():
    d = chart_api.chart_payload("XAUUSD", None, timeframe="M5")
    assert d["ok"] is False
    assert "timeframe" in d["error"]


# ── real-fixture scenarios (skip cleanly if absent) ─────────────────────────

def test_chart_payload_limit_clamped_and_window_is_tail():
    run = _any_xauusd_run()
    if run is None:
        pytest.skip("no results/run_*_XAUUSD/ fixture on disk in this clone")

    d = chart_api.chart_payload("XAUUSD", run.run_id, timeframe="M15", limit=25)
    assert d["ok"] is True
    assert len(d["bars"]) == 25

    d_over = chart_api.chart_payload("XAUUSD", run.run_id, timeframe="M15",
                                      limit=999999)
    assert len(d_over["bars"]) <= chart_api.MAX_LIMIT
    # tail window: the smaller request's last bar is the larger request's last bar too.
    assert d["bars"][-1]["time"] == d_over["bars"][-1]["time"]


def test_chart_payload_timeframe_aggregation_keeps_arrays_aligned():
    run = _any_xauusd_run()
    if run is None:
        pytest.skip("no results/run_*_XAUUSD/ fixture on disk in this clone")

    for tf in ("M15", "H4", "D1"):
        d = chart_api.chart_payload("XAUUSD", run.run_id, timeframe=tf, limit=40)
        assert d["ok"] is True, d.get("error")
        n = len(d["bars"])
        assert n > 0
        assert len(d["crt_state"]["engine"]["states"]) == n
        assert len(d["crt_state"]["resolver"]["states"]) == n


def test_chart_payload_integrity_decision_present():
    run = _any_xauusd_run()
    if run is None:
        pytest.skip("no results/run_*_XAUUSD/ fixture on disk in this clone")

    d = chart_api.chart_payload("XAUUSD", run.run_id, timeframe="M15", limit=10)
    assert d["ok"] is True
    assert d["integrity"]["decision"] in ("APPROVE", "WARN", "REJECT")


def test_chart_payload_resolver_reports_a_status_regardless_of_cache_state():
    """The resolver cache is built OFFLINE (scripts/analysis/build_resolver_overlay.py)
    and may or may not exist in a given clone/CI run — either is a valid, honest state,
    never a crash or a fabricated track."""
    run = _any_xauusd_run()
    if run is None:
        pytest.skip("no results/run_*_XAUUSD/ fixture on disk in this clone")

    d = chart_api.chart_payload("XAUUSD", run.run_id, timeframe="M15", limit=10)
    assert d["ok"] is True
    source = d["crt_state"]["resolver"]["source"]
    assert source.startswith("RESOLVED:") or source.startswith("UNAVAILABLE:")


def test_chart_payload_gap_bands_are_time_ordered_windows():
    run = _any_xauusd_run()
    if run is None:
        pytest.skip("no results/run_*_XAUUSD/ fixture on disk in this clone")

    d = chart_api.chart_payload("XAUUSD", run.run_id, timeframe="M15", limit=2000)
    assert d["ok"] is True
    for g in d["gap_bands"]:
        assert g["from"] < g["to"]
        assert g["span_minutes"] > 0


# ── degrade path: corpus/run mismatch, via a monkeypatched events file ──────

def test_chart_payload_engine_track_unavailable_on_corpus_mismatch(monkeypatch, tmp_path):
    """Wiring test for the fail-closed path `track_from_events` already proves in
    isolation (test_track_from_events.py): if a run's events.jsonl doesn't line up with
    the bound corpus, `chart_payload` must still return bars (ok:true) with an
    UNAVAILABLE engine-state source, never raise and never fabricate colour."""
    run = _any_xauusd_run()
    if run is None:
        pytest.skip("no results/run_*_XAUUSD/ fixture on disk in this clone")

    bad_events = tmp_path / "XAUUSD_events.jsonl"
    bad_events.write_text(json.dumps({
        "event": "STATE_TRANSITION", "timestamp": "1999-01-01T00:00:00",
        "candle_index": 0, "state_from": "RANGE", "state_to": "SWEEP",
    }) + "\n", encoding="utf-8")

    from control_plane import dashboard_api as dash

    real_resolve = dash._resolve_run

    def _patched(instrument, run_id=None):
        r = real_resolve(instrument, run_id)
        if r is not None:
            r.events_path = bad_events
        return r

    monkeypatch.setattr(dash, "_resolve_run", _patched)

    d = chart_api.chart_payload("XAUUSD", run.run_id, timeframe="M15", limit=10)
    assert d["ok"] is True
    assert len(d["bars"]) == 10
    assert d["crt_state"]["engine"]["source"].startswith("UNAVAILABLE")
