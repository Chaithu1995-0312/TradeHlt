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


# --------------------------------------------------------------------------- #
# run selection — a family that spans two emits must never bind one silently
# --------------------------------------------------------------------------- #
def _construction_records(run_id: str) -> list[dict]:
    return [
        {
            "schema_version": "2.0.0", "run_id": run_id, "instrument": "XAUUSD",
            "timeframe": "M15", "bar_index": i, "phase": phase,
            "engine_state_after": state, "agree": None,
        }
        for i, phase, state in ((0, "WARMUP", None), (80, "LIVE", "RANGE"))
    ]


@pytest.fixture()
def two_emits(tmp_path: Path, monkeypatch) -> Path:
    """Fake ROOT with the SAME family projected from two different runs."""
    import query_trace as qt

    for run in ("dual_construction_a", "dual_construction_b"):
        d = tmp_path / "logs" / run
        d.mkdir(parents=True)
        src = _write_jsonl(d / "XAUUSD_crt_construction.jsonl", _construction_records(run))
        compact_jsonl(src, partition_by="engine_state_after", verify=True)
    monkeypatch.setattr(qt, "ROOT", tmp_path)
    return tmp_path


def test_ambiguous_family_refuses_instead_of_binding_first(two_emits, capsys) -> None:
    """The F-079/F-083 silent-gap guard: two emits + no --run-dir must be an ERROR.

    Binding `sorted(paths)[0]` would pair views from different runs, and a join on
    (run_id, bar_index) would then return 0 rows at exit 0 -- a skipped comparison
    indistinguishable from an empty one.
    """
    import query_trace as qt

    with pytest.raises(SystemExit) as exc:
        qt.main(["--family", "crt_construction"])
    assert exc.value.code != 0
    message = str(exc.value)
    assert "dual_construction_a" in message and "dual_construction_b" in message
    assert "--run-dir" in message


def test_run_dir_scopes_family_to_one_emit(two_emits, capsys) -> None:
    import query_trace as qt

    rc = qt.main(
        ["--run-dir", "logs/dual_construction_b", "--family", "crt_construction",
         "--sql", "select distinct run_id from crt_construction"]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "dual_construction_b" in out
    assert "dual_construction_a" not in out


def test_unverified_projection_is_refused(tmp_path: Path, monkeypatch, capsys) -> None:
    """A projection whose manifest attests no passing round-trip must not back a view."""
    import query_trace as qt

    d = tmp_path / "logs" / "dual_construction_unverified"
    d.mkdir(parents=True)
    src = _write_jsonl(d / "XAUUSD_crt_construction.jsonl", _construction_records("r0"))
    compact_jsonl(src, partition_by="engine_state_after", verify=False)  # no `verified` block
    monkeypatch.setattr(qt, "ROOT", tmp_path)

    rc = qt.main(["--family", "crt_construction"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "REFUSED crt_construction" in out
    assert "verified" in out


def test_bar_matrix_refused_when_parquet_not_written(tmp_path: Path, monkeypatch, capsys) -> None:
    """`build_bar_matrix` keeps CSV canonical and may skip the optional parquet writer.

    A directory carrying `parquet_written: false` must never be reported as a
    DuckDB-ready family -- that would present a skipped write as a completed one.
    """
    import query_trace as qt

    d = tmp_path / "results" / "research" / "bar_matrix" / "XAUUSD_M15"
    d.mkdir(parents=True)
    (d / "bar_matrix.parquet").write_bytes(b"")  # stale/partial artifact on disk
    (d / "manifest.json").write_text(
        json.dumps({"parquet_written": False, "parquet_skipped_reason": "no engine"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(qt, "ROOT", tmp_path)

    ok, why = qt.admissible("bar_matrix", d / "bar_matrix.parquet")
    assert ok is False
    assert "no engine" in why

    rc = qt.main(["--family", "bar_matrix"])
    assert rc == 1
    assert "REFUSED bar_matrix" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# lineage — run identity must be CHECKED from the data, not trusted from a path
# --------------------------------------------------------------------------- #
def _lineage_records(run_id: str, sha: str, n: int = 2) -> list[dict]:
    return [
        {
            "schema_version": "2.0.0", "run_id": run_id, "instrument": "XAUUSD",
            "timeframe": "M15", "bar_index": i, "phase": "LIVE",
            "engine_state_after": "RANGE", "corpus_sha256": sha,
        }
        for i in range(n)
    ]


def _structure_records(run_id: str, sha: str, n: int = 2) -> list[dict]:
    return [
        {
            "schema_version": "1.0.0", "run_id": run_id, "instrument": "XAUUSD",
            "timeframe": "M15", "bar_index": i, "phase": "LIVE",
            "crt_state_after": "RANGE", "corpus_sha256": sha,
        }
        for i in range(n)
    ]


@pytest.fixture()
def one_run(tmp_path: Path, monkeypatch) -> Path:
    """A single, internally-consistent emit -- crt_construction + bar_structure agree."""
    import query_trace as qt

    d = tmp_path / "logs" / "one_run"
    d.mkdir(parents=True)
    compact_jsonl(
        _write_jsonl(
            d / "XAUUSD_crt_construction.jsonl",
            _lineage_records("run_X", "sha_X"),
        ),
        partition_by="engine_state_after", verify=True,
    )
    compact_jsonl(
        _write_jsonl(
            d / "XAUUSD_bar_structure.jsonl",
            _structure_records("run_X", "sha_X"),
        ),
        partition_by="crt_state_after", verify=True,
    )
    monkeypatch.setattr(qt, "ROOT", tmp_path)
    return tmp_path


def test_lineage_ok_prints_banner_and_matches(one_run, capsys) -> None:
    import query_trace as qt

    rc = qt.main(
        ["--run-dir", "logs/one_run", "--family", "crt_construction",
         "--family", "bar_structure", "--sql", "select 1 as ok"]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "lineage: run_id=run_X" in out
    assert "corpus=sha_X" in out
    assert "UNATTRIBUTABLE" in out and "(none)" in out


@pytest.fixture()
def mismatched_run_dir(tmp_path: Path, monkeypatch) -> Path:
    """ONE directory whose two families were built from DIFFERENT runs.

    --run-dir cannot see this: both files match under one scoped path, so
    `select_projections`'s path-level ambiguity check has nothing to flag. Only reading
    run_id out of the opened views themselves can catch it.
    """
    import query_trace as qt

    d = tmp_path / "logs" / "mixed"
    d.mkdir(parents=True)
    compact_jsonl(
        _write_jsonl(
            d / "XAUUSD_crt_construction.jsonl",
            _lineage_records("run_A", "sha_A"),
        ),
        partition_by="engine_state_after", verify=True,
    )
    compact_jsonl(
        _write_jsonl(
            d / "XAUUSD_bar_structure.jsonl",
            _structure_records("run_B", "sha_B"),
        ),
        partition_by="crt_state_after", verify=True,
    )
    monkeypatch.setattr(qt, "ROOT", tmp_path)
    return tmp_path


def test_cross_view_run_id_mismatch_is_refused(mismatched_run_dir, capsys) -> None:
    """The dangerous case: a bar_index-only join across two runs returns confidently
    wrong rows, not zero. --run-dir alone does not catch it; this must."""
    import query_trace as qt

    with pytest.raises(qt.LineageConflictError) as exc:
        qt.main(
            ["--run-dir", "logs/mixed", "--family", "crt_construction",
             "--family", "bar_structure", "--sql", "select 1"]
        )
    message = str(exc.value)
    assert "run_A" in message and "run_B" in message
    assert "disagree on run_id" in message


def test_single_view_spanning_two_runs_is_refused(tmp_path: Path, monkeypatch) -> None:
    """A projection whose SOURCE already mixed two run_ids -- --run-dir cannot detect
    this either, since it operates on paths, not on the run_id column."""
    import query_trace as qt

    d = tmp_path / "logs" / "split"
    d.mkdir(parents=True)
    records = _lineage_records("run_A", "sha_A", n=1) + _lineage_records("run_B", "sha_B", n=1)
    compact_jsonl(
        _write_jsonl(d / "XAUUSD_crt_construction.jsonl", records),
        partition_by="engine_state_after", verify=True,
    )
    monkeypatch.setattr(qt, "ROOT", tmp_path)

    with pytest.raises(qt.LineageConflictError) as exc:
        qt.main(["--run-dir", "logs/split", "--family", "crt_construction", "--sql", "select 1"])
    message = str(exc.value)
    assert "MORE THAN ONE run" in message
    assert "run_A" in message and "run_B" in message


def test_unattributable_view_reported_not_silently_accepted(tmp_path: Path, monkeypatch, capsys) -> None:
    """A family with no run_id/corpus_sha256 column (events, crt_telemetry today) must be
    named as UNATTRIBUTABLE, never silently treated as compatible with lineage-bearing views."""
    import query_trace as qt

    d = tmp_path / "logs" / "run_with_events"
    d.mkdir(parents=True)
    compact_jsonl(
        _write_jsonl(
            d / "XAUUSD_crt_construction.jsonl",
            _lineage_records("run_X", "sha_X"),
        ),
        partition_by="engine_state_after", verify=True,
    )
    no_lineage_events = [
        {
            "event": "STATE_TRANSITION", "timestamp": "t0", "candle_index": 1,
            "state_from": "RANGE", "state_to": "EXPANSION", "direction": "long",
            "price": 1.0, "reason": "r", "metadata": {},
        },
    ]
    compact_jsonl(
        _write_jsonl(d / "XAUUSD_events.jsonl", no_lineage_events),
        verify=True,
    )
    monkeypatch.setattr(qt, "ROOT", tmp_path)

    rc = qt.main(
        ["--run-dir", "logs/run_with_events", "--family", "crt_construction",
         "--family", "events", "--sql", "select 1"]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "UNATTRIBUTABLE (no run identity in-record): events" in out
