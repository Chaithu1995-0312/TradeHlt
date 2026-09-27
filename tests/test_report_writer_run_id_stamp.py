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
    monkeypatch.setattr(ReportWriter, "_write_report",
                        lambda *a, **k: "stubbed")
    paths = w.write_all(_FakeMetrics(), _FakeJournal(rows), events, run_id="run_20260916_000000")

    summary = json.loads(Path(paths["summary"]).read_text(encoding="utf-8"))
    assert summary["run_id"] == "run_20260916_000000"

    with open(paths["trades_csv"], encoding="utf-8", newline="") as f:
        trade_row = next(csv.DictReader(f))
    assert trade_row["run_id"] == "run_20260916_000000"

    event_line = json.loads(Path(paths["events"]).read_text(encoding="utf-8").splitlines()[0])
    assert event_line["run_id"] == "run_20260916_000000"


# ── [CH-run-identity-range-folder-manifest] folder naming, corpus range, manifest ──


def test_folder_name_carries_range_and_config_suffix(tmp_path):
    """Same-time-range-different-config runs must land in DISTINCT, name-readable dirs."""
    w = ReportWriter(
        str(tmp_path), "XAUUSD", run_id="run_20260916_172925",
        walked_range=("2024-05-22 01:00:00", "2026-05-21 23:45:00"),
        config_descriptor="v2_htfcrt_2026_08_3ca7549e",
    )
    assert w.output_dir.name == (
        "run_20260916_172925_XAUUSD__20240522..20260521_v2_htfcrt_2026_08_3ca7549e")
    assert w.output_dir.exists()


def test_folder_name_without_range_keeps_legacy_shape(tmp_path):
    """No corpus range / no config descriptor ⇒ exactly the pre-change folder name."""
    w = ReportWriter(str(tmp_path), "XAUUSD", run_id="run_20260916_172925")
    assert w.output_dir.name == "run_20260916_172925_XAUUSD"


def test_write_run_manifest_persists_verbatim(tmp_path):
    w = _writer(tmp_path)
    payload = {
        "schema": "run_manifest_v2",
        "run_id": "run_test_fixed",
        "corpus": {"start": "2024-05-22 01:00:00", "end": "2026-05-21 23:45:00", "rows": 47197},
        "identity": {"identity_status": "VERIFIED"},
    }
    p = w._write_run_manifest(payload)
    d = json.loads(Path(p).read_text(encoding="utf-8"))
    assert d == payload  # pure sink — verbatim, never recomputed


def test_corpus_range_from_csv_first_and_last_rows(tmp_path):
    from runtime.backtest_v2 import _corpus_range_from_csv
    csv = tmp_path / "mini.csv"
    csv.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2024-05-22 01:00:00,1,2,0.5,1.5,10\n"
        "2024-05-22 01:15:00,1,2,0.5,1.5,11\n"
        "2026-05-21 23:45:00,1,2,0.5,1.5,12\n",
        encoding="utf-8",
    )
    assert _corpus_range_from_csv(str(csv)) == ("2024-05-22 01:00:00", "2026-05-21 23:45:00")
    assert _corpus_range_from_csv(None) is None
    assert _corpus_range_from_csv(str(tmp_path / "missing.csv")) is None


def test_backtest_metrics_summary_carries_corpus_range(tmp_path):
    """The summary.json carrier gains corpus_start/end from the walked run."""
    from runtime.backtest_v2 import BacktestMetrics
    assert BacktestMetrics().to_dict()["corpus_start"] == ""
    assert BacktestMetrics().to_dict()["corpus_end"] == ""
    m = BacktestMetrics(corpus_start="2024-05-22 01:00:00", corpus_end="2026-05-21 23:45:00")
    d = m.to_dict()
    assert d["corpus_start"] == "2024-05-22 01:00:00"
    assert d["corpus_end"] == "2026-05-21 23:45:00"

    # and it lands on the actual summary.json written by the writer
    w = _writer(tmp_path)
    path = w._write_summary(m)
    written = json.loads(Path(path).read_text(encoding="utf-8"))
    assert written["corpus_start"] == "2024-05-22 01:00:00"
    assert written["corpus_end"] == "2026-05-21 23:45:00"


def test_run_wires_canonical_folder_manifest_and_summary_range():
    """End-to-end wiring: the run folder name embeds the canonical id + corpus range +
    config descriptor; summary.json carries the walked range; run_manifest.json consolidates
    the recorded ids and points at the artifacts. Mirrors test_replay_determinism's driver."""
    import itertools
    import tempfile
    from runtime.backtest_v2 import BacktestConfig, BacktestRunner, CandleLoader
    from config_layer.production_config import get_active_version, load_prod_config_from_registry

    repo = Path(__file__).resolve().parents[1]
    csv = repo / "data" / "XAUUSD_M15.csv"
    if not csv.exists():
        pytest.skip("data CSV missing: data/XAUUSD_M15.csv")

    crt_cfg = load_prod_config_from_registry(get_active_version(), "XAUUSD")
    cfg = BacktestConfig.from_prod_config(instrument="XAUUSD", crt_config=crt_cfg)
    n = 3000
    rows = list(itertools.islice(CandleLoader(str(csv), "XAUUSD").stream(), n))
    out_dir = tempfile.mkdtemp(prefix="rid_fold_manifest_")
    runner = BacktestRunner(cfg, csv_path=str(csv))
    m = runner.run(iter(rows), n, output_dir=out_dir)

    run_dir = next(Path(out_dir).iterdir())
    assert "XAUUSD__" in run_dir.name and ".." in run_dir.name

    def _ts(v):
        # CandleLoader yields datetime timestamps in this env; the summary/manifest carry
        # them as "YYYY-MM-DD HH:MM:SS" strings — compare normalized.
        return v.strftime("%Y-%m-%d %H:%M:%S") if hasattr(v, "strftime") else str(v)

    summary = json.loads((run_dir / "XAUUSD_summary.json").read_text(encoding="utf-8"))
    assert summary["corpus_start"] == _ts(rows[0].timestamp), "walked range = actual first candle"
    assert summary["corpus_end"] == _ts(rows[-1].timestamp), "walked range = actual last candle"
    assert summary["corpus_start"] != summary["corpus_end"]
    assert summary["run_id"].startswith("run_")

    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "run_manifest_v2"
    assert manifest["run_id"] == summary["run_id"], "manifest canonical == summary run_id"
    assert manifest["corpus"]["start"] == summary["corpus_start"]
    assert manifest["corpus"]["end"] == summary["corpus_end"]
    assert manifest["corpus"]["rows"] == n
    assert manifest["fingerprint"]["config_version"]
    assert manifest["run_ids"]["runtime.BacktestRunner.canonical_run_id"] == summary["run_id"]
    assert run_dir.name.startswith(summary["run_id"]), "folder stems from the SAME canonical id"
    assert manifest["artifacts"]["summary"].endswith("XAUUSD_summary.json")
    # the layer trace's own minted id is RECORDED (not collapsed) when the trace is enabled
    assert bool(manifest.get("layer_trace_id")), "layer-trace id must be recorded on the manifest"

    # walked-recorded metrics agree with the manifest
    assert m.corpus_start == _ts(rows[0].timestamp)
    assert m.corpus_end == _ts(rows[-1].timestamp)
