"""ReportWriter run_id stamping (2026-09-16, user-authorized): summary.json / trades.csv /
events.jsonl gain a canonical `run_id` field, previously absent from all core-output content
(confirmed absent by direct grep before this change — see docs/current-findings.md F-101 context).

Fast unit-level floors, mirroring `tests/test_bar_structure_snapshot.py`'s discipline: minimal
fake stand-ins for `BacktestMetrics`/`TradeJournal` (pin the ACCESSOR contract `ReportWriter`
actually uses — `.to_dict()` / `.to_csv_rows()` — not a full backtest run). The real-corpus
decision-neutrality proof (trades.csv/summary.json identical to the pre-stamp run except for the
new `run_id` field, zero cells differing in any other column) was done empirically on
`data/mt5/XAUUSD_M15.csv` for this change; these floors pin the writer contract so it cannot
silently regress.
"""

from __future__ import annotations

import csv
import json
import sys
import tempfile
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from runtime.backtest_v2 import ReportWriter  # noqa: E402


class _FakeMetrics:
    """Deliberately not a real `BacktestMetrics` — pins only the `.to_dict()` accessor
    `_write_summary` actually calls."""

    def to_dict(self) -> dict:
        return {"instrument": "XAUUSD", "total_trades": 1, "win_rate": 1.0}


class _FakeJournal:
    """Deliberately not a real `TradeJournal` — pins only the `.to_csv_rows()` accessor
    `_write_trades` actually calls."""

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def to_csv_rows(self) -> list[dict]:
        return self._rows


def _writer(tmp: Path) -> ReportWriter:
    return ReportWriter(str(tmp), "XAUUSD", run_id="run_test_fixed")


def test_write_summary_stamps_run_id_and_preserves_other_keys(tmp_path):
    w = _writer(tmp_path)
    path = w._write_summary(_FakeMetrics(), run_id="run_20260916_000000")
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    assert d["run_id"] == "run_20260916_000000"
    assert d["instrument"] == "XAUUSD"
    assert d["total_trades"] == 1


def test_write_summary_without_run_id_omits_the_field(tmp_path):
    """`run_id=None` (the default) must be a complete no-op — any OTHER existing caller of
    `write_all`/`_write_summary` is unaffected."""
    w = _writer(tmp_path)
    path = w._write_summary(_FakeMetrics())
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    assert "run_id" not in d


def test_write_trades_appends_run_id_as_last_column(tmp_path):
    w = _writer(tmp_path)
    rows = [
        {"trade_id": "CRT-0001", "direction": "LONG", "pnl_rr_net": 1.5},
        {"trade_id": "CRT-0002", "direction": "SHORT", "pnl_rr_net": -0.5},
    ]
    path = w._write_trades(_FakeJournal(rows), run_id="run_20260916_000000")
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        out_rows = list(reader)
    assert fieldnames[-1] == "run_id"
    assert fieldnames[:-1] == ["trade_id", "direction", "pnl_rr_net"]
    assert [r["run_id"] for r in out_rows] == ["run_20260916_000000", "run_20260916_000000"]
    assert [r["trade_id"] for r in out_rows] == ["CRT-0001", "CRT-0002"]


def test_write_trades_without_run_id_adds_no_column(tmp_path):
    w = _writer(tmp_path)
    rows = [{"trade_id": "CRT-0001", "direction": "LONG"}]
    path = w._write_trades(_FakeJournal(rows))
    with open(path, encoding="utf-8", newline="") as f:
        fieldnames = csv.DictReader(f).fieldnames
    assert "run_id" not in fieldnames


def test_write_events_stamps_every_record(tmp_path):
    w = _writer(tmp_path)
    events = [{"kind": "TRADE_OPENED"}, {"kind": "TRADE_CLOSED", "existing": "value"}]
    path = w._write_events(events, run_id="run_20260916_000000")
    lines = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines()]
    assert all(l["run_id"] == "run_20260916_000000" for l in lines)
    assert lines[1]["existing"] == "value"
    # original list of dicts passed in must be untouched (no in-place mutation)
    assert "run_id" not in events[0]
    assert "run_id" not in events[1]


def test_write_events_without_run_id_omits_the_field(tmp_path):
    w = _writer(tmp_path)
    events = [{"kind": "TRADE_OPENED"}]
    path = w._write_events(events)
    line = json.loads(Path(path).read_text(encoding="utf-8").splitlines()[0])
    assert "run_id" not in line


def test_write_all_threads_run_id_through_all_three_writers(tmp_path, monkeypatch):
    w = _writer(tmp_path)
    rows = [{"trade_id": "CRT-0001"}]
    events = [{"kind": "TRADE_OPENED"}]
    # `_write_report` needs a much fuller BacktestMetrics than this test cares about — it is
    # not part of the run_id contract under test, so it is stubbed rather than faked deeper.
    monkeypatch.setattr(ReportWriter, "_write_report", lambda self, m: "stubbed")
    paths = w.write_all(_FakeMetrics(), _FakeJournal(rows), events, run_id="run_20260916_000000")

    summary = json.loads(Path(paths["summary"]).read_text(encoding="utf-8"))
    assert summary["run_id"] == "run_20260916_000000"

    with open(paths["trades_csv"], encoding="utf-8", newline="") as f:
        trade_row = next(csv.DictReader(f))
    assert trade_row["run_id"] == "run_20260916_000000"

    event_line = json.loads(Path(paths["events"]).read_text(encoding="utf-8").splitlines()[0])
    assert event_line["run_id"] == "run_20260916_000000"
