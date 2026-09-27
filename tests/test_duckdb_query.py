"""
test_duckdb_query.py — floors for the DuckDB query helper over Parquet projections.

Mirrors the optional-import / fixture style of test_parquet_store.py. Covers:

  1. single-file parquet → view readable
  2. partitioned (hive-style) parquet dir → view readable via glob
  3. missing-duckdb raises with tradelatest[parquet] install hint
  4. glob/path quoting correctness (apostrophe in path)

STORY-43.2 (safe query contract) additions:
  5. read_only=True refuses a write via SQL text (COPY) — the executable proof that
     motivated this story: this exact call used to succeed and write a file.
  6. read_only=True refuses a write via the DuckDB Relation API (.to_parquet()) — the
     SECOND write path, with zero SQL text, that a keyword scan alone could never catch.
  7. the refusal survives a `.filter().limit()` chain — proves re-wrapping is a graph
     property, not a one-hop check.
  8. read_only=False returns the raw, unwrapped connection (escape hatch, opt-in).
  9. ordinary reads (select / fetchdf / describe) are unaffected by read_only=True.
  10. check_lineage=True (default) refuses a cross-view run_id mismatch automatically —
      closing the gap where 4 of 5 real callers never called assert_view_lineage at all.
  11. check_lineage=True passes silently on a single, internally-consistent view.
  12. check_lineage=False (the query_trace.py CLI's own opt-out) skips the automatic check.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils import duckdb_query as dq
from utils.duckdb_query import (
    LineageConflictError,
    WriteRefusedError,
    duckdb_available,
    open_views,
)

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


# --------------------------------------------------------------------------- #
# read-only enforcement — STORY-43.2
# --------------------------------------------------------------------------- #

def _one_view(tmp_path: Path):
    records = [{"a": 1}, {"a": 2}]
    src = _write_jsonl(tmp_path / "x.jsonl", records)
    proj = _project(src)
    return open_views({"t": proj.as_posix()}, read_only=True, check_lineage=False)


def test_readonly_refuses_write_via_sql_text(tmp_path: Path) -> None:
    """The exact call that succeeded and wrote a 192-byte file before this story."""
    con = _one_view(tmp_path)
    out = tmp_path / "escaped.parquet"
    with pytest.raises(WriteRefusedError, match="COPY"):
        con.execute(f"COPY (SELECT 1 AS x) TO '{out.as_posix()}' (FORMAT PARQUET)")
    assert not out.exists()


def test_readonly_refuses_write_via_relation_api_with_no_sql_text(tmp_path: Path) -> None:
    """DuckDB's Relation API (.to_parquet()) carries NO SQL string at all — a keyword
    scan on `execute()` text alone cannot see this. Proves the method-name denylist layer
    (not just the SQL-text layer) is load-bearing, not redundant defense."""
    con = _one_view(tmp_path)
    out = tmp_path / "escaped2.parquet"
    rel = con.sql("select 1 as x")
    with pytest.raises(WriteRefusedError, match="to_parquet"):
        rel.to_parquet(out.as_posix())
    assert not out.exists()


def test_readonly_refusal_survives_a_relation_chain(tmp_path: Path) -> None:
    """Re-wrapping is a graph property: `.sql().filter().limit()` all return Relations,
    and the write-denial must hold at the END of that chain, not just at the first hop."""
    con = _one_view(tmp_path)
    out = tmp_path / "escaped3.parquet"
    chained = con.sql("select * from t").filter("a > 0").limit(1)
    with pytest.raises(WriteRefusedError, match="to_csv"):
        chained.to_csv(out.as_posix())
    assert not out.exists()


def test_readonly_true_still_permits_ordinary_reads(tmp_path: Path) -> None:
    """The enforcement must not collaterally break the read surface it exists to protect."""
    con = _one_view(tmp_path)
    assert con.execute("select count(*) from t").fetchone() == (2,)
    cols = {r[0] for r in con.execute("describe t").fetchall()}
    assert "a" in cols
    df = con.sql("select * from t order by a").df()
    assert list(df["a"]) == [1, 2]


def test_readonly_false_returns_raw_unwrapped_connection(tmp_path: Path) -> None:
    """The explicit escape hatch: opt out by name, not by accident."""
    import duckdb as _duckdb

    con = open_views(
        {"t": _project(_write_jsonl(tmp_path / "y.jsonl", [{"a": 1}])).as_posix()},
        read_only=False, check_lineage=False,
    )
    assert isinstance(con, _duckdb.DuckDBPyConnection)
    out = tmp_path / "allowed.parquet"
    con.execute(f"COPY (SELECT 1 AS x) TO '{out.as_posix()}' (FORMAT PARQUET)")
    assert out.exists()


# --------------------------------------------------------------------------- #
# automatic lineage enforcement — STORY-43.2 (closes the "4 of 5 callers never call
# assert_view_lineage" gap by making open_views() call it by default)
# --------------------------------------------------------------------------- #

def _lineage_records(run_id: str, sha: str, n: int = 2) -> list[dict]:
    return [
        {"run_id": run_id, "corpus_sha256": sha, "bar_index": i, "v": i}
        for i in range(n)
    ]


def test_open_views_check_lineage_default_refuses_cross_view_mismatch(tmp_path: Path) -> None:
    """The exact defect class this story exists to close: two views, each internally
    consistent, opened together without the caller ever calling assert_view_lineage --
    which is precisely what phase1_resolver_replay_evidence.py / phase1_shadow_create_
    economic_census.py do today. Must now refuse by DEFAULT, with no extra call needed."""
    crt = _project(_write_jsonl(tmp_path / "crt.jsonl", _lineage_records("run_A", "sha_A")))
    bar = _project(_write_jsonl(tmp_path / "bar.jsonl", _lineage_records("run_B", "sha_B")))
    with pytest.raises(LineageConflictError, match="disagree on run_id"):
        open_views({"crt": crt.as_posix(), "bar": bar.as_posix()})


def test_open_views_check_lineage_default_passes_consistent_views(tmp_path: Path) -> None:
    crt = _project(_write_jsonl(tmp_path / "crt2.jsonl", _lineage_records("run_X", "sha_X")))
    bar = _project(_write_jsonl(tmp_path / "bar2.jsonl", _lineage_records("run_X", "sha_X")))
    con = open_views({"crt": crt.as_posix(), "bar": bar.as_posix()})
    assert con.execute("select count(*) from crt").fetchone() == (2,)


def test_check_lineage_false_opts_out(tmp_path: Path) -> None:
    """query_trace.py's own opt-out: it runs a richer, family-aware check itself right
    after, so the automatic generic one must be skippable rather than double-running."""
    crt = _project(_write_jsonl(tmp_path / "crt3.jsonl", _lineage_records("run_A", "sha_A")))
    bar = _project(_write_jsonl(tmp_path / "bar3.jsonl", _lineage_records("run_B", "sha_B")))
    con = open_views(
        {"crt": crt.as_posix(), "bar": bar.as_posix()}, check_lineage=False
    )
    # No raise -- the mismatch is real but uninspected, exactly as before this story for a
    # caller that explicitly opts out.
    assert con.execute("select count(*) from crt").fetchone() == (2,)
