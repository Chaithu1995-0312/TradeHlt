"""
test_query_trace.py — CLI floors for scripts/analysis/query_trace.py.

READ-ONLY surface. Exercises --list / --sql against a tiny fixture projection;
does not claim economic meaning.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "analysis"))
sys.path.insert(0, str(ROOT / "src"))

from utils.duckdb_query import duckdb_available  # noqa: E402
from utils.parquet_store import compact_jsonl, parquet_available  # noqa: E402

pytestmark = pytest.mark.skipif(
    not (duckdb_available() and parquet_available()),
    reason="duckdb+pyarrow required for query_trace fixture tests",
)


def _write_jsonl(path: Path, records: list[dict]) -> Path:
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture()
def construction_projection(tmp_path: Path, monkeypatch) -> Path:
    """Tiny crt_construction projection under a fake ROOT logs/ tree."""
    import query_trace as qt

    logs = tmp_path / "logs" / "dual_construction"
    logs.mkdir(parents=True)
    records = [
        {
            "schema_version": "2.0.0",
            "run_id": "t1",
            "instrument": "XAUUSD",
            "timeframe": "M15",
            "bar_index": 0,
            "phase": "WARMUP",
            "engine_state_after": None,
            "agree": None,
        },
        {
            "schema_version": "2.0.0",
            "run_id": "t1",
            "instrument": "XAUUSD",
            "timeframe": "M15",
            "bar_index": 80,
            "phase": "LIVE",
            "engine_state_after": "RANGE",
            "agree": True,
        },
        {
            "schema_version": "2.0.0",
            "run_id": "t1",
            "instrument": "XAUUSD",
            "timeframe": "M15",
            "bar_index": 81,
            "phase": "LIVE",
            "engine_state_after": "EXPANSION",
            "agree": False,
        },
    ]
    src = _write_jsonl(logs / "XAUUSD_crt_construction.jsonl", records)
    compact_jsonl(src, partition_by="engine_state_after", verify=True)
    monkeypatch.setattr(qt, "ROOT", tmp_path)
    return src


def test_list_shows_crt_construction(construction_projection, capsys) -> None:
    import query_trace as qt

    rc = qt.main(["--list", "--family", "crt_construction"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "crt_construction:" in out
    assert "XAUUSD_crt_construction.parquet" in out


def test_sql_counts_live_rows(construction_projection, capsys) -> None:
    import query_trace as qt

    rc = qt.main(
        [
            "--family",
            "crt_construction",
            "--sql",
            "select phase, count(*) as n from crt_construction group by 1 order by 1",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "LIVE" in out
    assert "WARMUP" in out


def test_default_report_is_descriptive(construction_projection, capsys) -> None:
    import query_trace as qt

    rc = qt.main(["--family", "crt_construction"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "DESCRIPTIVE ONLY" in out
    assert "crt_construction" in out


@pytest.fixture()
def events_tree(tmp_path: Path, monkeypatch) -> Path:
    """Fake ROOT logs/ with three *_events families plus one runtime-events one.

    GT-3: integrity_events and secondlow_prospective_events share the
    `*_events.parquet` glob but are NOT the runtime-events population. They must
    be excluded from the `events` view by discover_projections.
    """
    import query_trace as qt
    from utils.parquet_store import compact_jsonl

    logs = tmp_path / "logs"
    runtime = logs / "run_20260903_161258_XAUUSD"
    runtime.mkdir(parents=True)
    foreign2 = logs / "dual_construction_v2" / "scratch" / "arm_a" / "data"
    foreign2.mkdir(parents=True)

    runtime_records = [
        {
            "event": "STATE_TRANSITION", "timestamp": "t0", "candle_index": 1,
            "state_from": "RANGE", "state_to": "EXPANSION", "direction": "long",
            "price": 1.0, "reason": "r", "metadata": {},
        },
        {
            "event": "RESET", "timestamp": "t1", "candle_index": 10,
            "state_from": "RANGE", "state_to": "RANGE", "direction": "long",
            "price": 2.0, "reason": "r2", "metadata": {},
        },
    ]
    integrity_rec = [{"event": "INTEGRITY_FAIL", "payload": "x", "severity": "error", "source": "s", "ts": "t"}]
    prospective_rec = [{"collected_at": "c", "corpus_hash_prefix": "h", "detector": "d", "hypothesis_id": "id", "post_window_complete": True, "purge_time": "p"}]

    compact_jsonl(_write_jsonl(runtime / "XAUUSD_events.jsonl", runtime_records))
    compact_jsonl(_write_jsonl(logs / "integrity_events.jsonl", integrity_rec))
    compact_jsonl(_write_jsonl(foreign2 / "secondlow_prospective_events.jsonl", prospective_rec))

    monkeypatch.setattr(qt, "ROOT", tmp_path)
    return logs


def test_events_discover_excludes_foreign_populations(events_tree) -> None:
    import query_trace as qt

    found = qt.discover_projections(["events"])
    events = [p.relative_to(qt.ROOT).as_posix() for p in found.get("events", [])]
    assert len(events) == 1, f"events should contain ONLY the runtime events family, got {events}"
    assert "XAUUSD_events.parquet" in events[0]
    assert not any("integrity_events" in p for p in events), events
    assert not any("secondlow_prospective_events" in p for p in events), events
