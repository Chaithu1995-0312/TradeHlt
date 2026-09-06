"""
test_duckdb_query.py — floors for the DuckDB query helper over Parquet projections.

Mirrors the optional-import / fixture style of test_parquet_store.py. Covers:

  1. single-file parquet → view readable
  2. partitioned (hive-style) parquet dir → view readable via glob
  3. missing-duckdb raises with tradelatest[parquet] install hint
  4. glob/path quoting correctness (apostrophe in path)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils import duckdb_query as dq
from utils.duckdb_query import duckdb_available, open_views

pytestmark = pytest.mark.skipif(
    not duckdb_available(), reason="duckdb not installed (optional parquet extra)"
)


def _write_jsonl(path: Path, records: list[dict]) -> Path:
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
        encoding="utf-8",
    )
    return path


def _project(src: Path, *, partition_by: str | None = None) -> Path:
    from utils.parquet_store import compact_jsonl, parquet_available, projection_path

    if not parquet_available():
        pytest.skip("pyarrow not installed (optional parquet extra)")
    compact_jsonl(src, partition_by=partition_by, verify=True)
    return projection_path(src)


def test_open_views_single_file(tmp_path: Path) -> None:
    records = [
        {"engine_state_after": "RANGE", "bar_index": 1, "phase": "LIVE"},
        {"engine_state_after": "EXPANSION", "bar_index": 2, "phase": "LIVE"},
    ]
    src = _write_jsonl(tmp_path / "XAUUSD_crt_construction.jsonl", records)
    proj = _project(src)
    assert proj.is_file()

    con = open_views({"crt_construction": proj.as_posix()}, read_only=True)
    rows = con.execute(
        "select engine_state_after, bar_index from crt_construction order by bar_index"
    ).fetchall()
    assert rows == [("RANGE", 1), ("EXPANSION", 2)]


def test_open_views_partitioned_dir(tmp_path: Path) -> None:
    records = [
        {"engine_state_after": "RANGE", "n": 1},
        {"engine_state_after": "EXPANSION", "n": 2},
        {"engine_state_after": "RANGE", "n": 3},
    ]
    src = _write_jsonl(tmp_path / "parted_crt_construction.jsonl", records)
    proj = _project(src, partition_by="engine_state_after")
    assert proj.is_dir()
    # Hive layout: <proj>/engine_state_after=<val>/part-0.parquet
    parts = list(proj.glob("engine_state_after=*/*.parquet"))
    assert len(parts) >= 2

    glob = (proj / "**" / "*.parquet").as_posix()
    con = open_views({"crt_construction": glob}, read_only=True)
    got = sorted(
        con.execute("select engine_state_after, n from crt_construction").fetchall()
    )
    assert got == sorted([("RANGE", 1), ("EXPANSION", 2), ("RANGE", 3)])
    # Partition pruning shape: stratum counts match source
    counts = dict(
        con.execute(
            "select engine_state_after, count(*) from crt_construction group by 1"
        ).fetchall()
    )
    assert counts == {"RANGE": 2, "EXPANSION": 1}


def test_glob_path_with_apostrophe_is_quoted(tmp_path: Path) -> None:
    """Interior single quotes in the path must not break the CREATE VIEW SQL."""
    weird = tmp_path / "user's_data"
    weird.mkdir()
    records = [{"k": "a", "v": 1}]
    src = _write_jsonl(weird / "tiny.jsonl", records)
    proj = _project(src)
    con = open_views({"tiny": proj.as_posix()})
    assert con.execute("select v from tiny").fetchone() == (1,)


def test_missing_duckdb_message(monkeypatch) -> None:
    """Absent duckdb must raise with the same install hint spirit as parquet_store."""
    monkeypatch.setattr(dq, "_DUCKDB_AVAILABLE", False)
    monkeypatch.setattr(dq, "_DUCKDB_IMPORT_ERROR", ModuleNotFoundError("duckdb"))
    with pytest.raises(RuntimeError, match=r"pip install tradelatest\[parquet\]"):
        open_views({"t": "x.parquet"})


def test_invalid_view_name_rejected(tmp_path: Path) -> None:
    records = [{"a": 1}]
    src = _write_jsonl(tmp_path / "x.jsonl", records)
    proj = _project(src)
    with pytest.raises(ValueError, match="invalid view name"):
        open_views({"bad-name": proj.as_posix()})
