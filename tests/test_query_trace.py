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
