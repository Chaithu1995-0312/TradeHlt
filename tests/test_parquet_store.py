"""
test_parquet_store.py — floors for the JSONL -> Parquet projection layer.

The module's whole value rests on three claims, so each gets a test that can actually
fail:

  1. LOSSLESS  — a round-tripped record equals the original dict. The sharp edge here is
     null semantics: a key that is ABSENT must not come back as `None`, and a key whose
     value is an explicit `null` must not vanish. Both directions are covered, including
     the ambiguous column where a key is sometimes absent and sometimes null.
  2. NEVER STALE — a projection whose source moved on is ignored, not served.
  3. OPTIONAL  — with pyarrow unavailable, every read degrades to JSONL.

`test_null_semantics_round_trip` is the regression pin for a real bug: the first
implementation treated "unmasked null" as "absent", silently dropping `tp2: None` from
every `clean_labels` row. The verify gate caught it before any corpus was converted.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils import parquet_store as ps
from utils.parquet_store import (
    ABSENT,
    FRESH,
    STALE,
    compact_jsonl,
    iter_records,
    manifest_path,
    projection_path,
    projection_status,
    verify_projection,
)

pytestmark = pytest.mark.skipif(
    not ps.parquet_available(), reason="pyarrow not installed (optional extra)"
)


def _write(path: Path, records: list[dict]) -> Path:
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8"
    )
    return path


# --------------------------------------------------------------------------- #
# 1. lossless
# --------------------------------------------------------------------------- #
def test_round_trip_exercises_every_column_policy(tmp_path: Path) -> None:
    """scalar / json / list_f64 / flatten all reconstruct exactly."""
    records = [
        {
            "s": "a", "i": 1, "f": 1.5, "b": True,          # scalar, one type each
            "vec": [1.0, 2.0, 3.0],                          # list_f64
            "feat": {"x": 1.0, "y": 2.0},                    # flatten (stable key set)
            "meta": {"kind": "A", "n": 1},                   # json (varying key set)
        },
        {
            "s": "b", "i": 2, "f": 2.5, "b": False,
            "vec": [4.0, 5.0, 6.0],
            "feat": {"x": 3.0, "y": 4.0},
            "meta": {"other": [1, 2]},
        },
    ]
    src = _write(tmp_path / "corpus.jsonl", records)
    manifest = compact_jsonl(src, verify=True)

    assert manifest["verified"]["ok"], manifest["verified"]
    assert manifest["rows"] == 2
    plan = manifest["columns"]
    assert plan["feat"]["policy"] == "flatten"   # stable keys -> prunable columns
    assert plan["meta"]["policy"] == "json"      # varying keys -> lossless JSON text
    assert plan["vec"]["policy"] == "list_f64"
    assert plan["i"]["type"] == "int64"
    assert list(iter_records(src)) == records


def test_null_semantics_round_trip(tmp_path: Path) -> None:
    """Absent key stays absent; explicit null stays null. Regression pin.

    Three distinct regimes must survive, and they cannot all be inferred from a null:
      always_present  — `tp2` is on every row, sometimes null   -> null means NULL
      sometimes_absent— `extra` is missing on some rows, never null -> null means ABSENT
      ambiguous       — `both` is sometimes missing AND sometimes null -> needs a mask
    """
    records = [
        {"id": 1, "tp2": None, "extra": "here", "both": None},
        {"id": 2, "tp2": 9.5, "both": "x"},                  # `extra` absent
        {"id": 3, "tp2": None, "extra": "also"},             # `both` absent
    ]
    src = _write(tmp_path / "nulls.jsonl", records)
    manifest = compact_jsonl(src, verify=True)
    plan = manifest["columns"]

    assert plan["tp2"]["always_present"] is True and plan["tp2"]["mask"] is False
    assert plan["extra"]["always_present"] is False and plan["extra"]["mask"] is False
    assert plan["both"]["mask"] is True, "ambiguous column must carry a presence mask"

    assert manifest["verified"]["ok"], manifest["verified"]
    got = list(iter_records(src))
    assert got == records
    # Stated explicitly, because these are the two ways to get this wrong:
    assert "extra" not in got[1], "absent key must not reappear as None"
    assert "tp2" in got[0] and got[0]["tp2"] is None, "explicit null must not vanish"


def test_flatten_parent_null_is_not_an_all_null_dict(tmp_path: Path) -> None:
    """A FLATTEN parent that is explicitly null must not return as an all-null dict.

    Regression pin for a real MISMATCH: `XAUUSD_crt_construction.jsonl` carries
    `engine.live_context` / `resolver.feature_vector` / `resolver.l2_map` on EVERY row, but
    null on the 78 warmup rows. The parent's null-ness lives only in its children once
    flattened, and a null parent flattens to the same all-null children a real all-null dict
    produces -- so decode rebuilt `{k: None, ...}` where the source had `None`. `__present__`
    could not see it: the key WAS present. That is the third null regime, and it needs its
    own bit (`__null__`).

    All four regimes are asserted together because collapsing any two of them is the bug.
    """
    records = [
        {"i": 0, "ctx": None},                     # present, explicit null  <- the failing case
        {"i": 1, "ctx": {"a": 1.0, "b": 2.0}},     # a real dict
        {"i": 2, "ctx": {"a": None, "b": None}},   # all-null dict -- must NOT become None
        {"i": 3},                                  # absent entirely
    ]
    src = _write(tmp_path / "flat_nulls.jsonl", records)
    manifest = compact_jsonl(src, verify=True)
    plan = manifest["columns"]

    assert plan["ctx"]["policy"] == "flatten"
    assert plan["ctx"]["null_mask"] is True, "explicit-null parent must carry a null mask"
    assert manifest["verified"]["ok"], manifest["verified"]

    got = list(iter_records(src))
    assert got == records
    assert got[0]["ctx"] is None, "null parent must not become an all-null dict"
    assert got[2]["ctx"] == {"a": None, "b": None}, "all-null dict must not collapse to None"
    assert "ctx" not in got[3], "absent parent must not reappear"


def test_verified_block_is_persisted_to_disk(tmp_path: Path) -> None:
    """The verify result must land in the ON-DISK manifest, not just the returned dict.

    A failed projection stays fully readable on disk. If `verified` lives only in memory, a
    MISMATCHed projection is byte-indistinguishable from a passing one and any later reader
    (query_trace) cannot tell that the check failed -- the F-056/F-079/F-083/F-085 class
    where a skipped or failed check looks exactly like an absent one.
    """
    src = _write(tmp_path / "v.jsonl", [{"i": 1}, {"i": 2}])

    compact_jsonl(src, verify=False)
    assert "verified" not in json.loads(manifest_path(src).read_text(encoding="utf-8"))

    compact_jsonl(src, verify=True)
    on_disk = json.loads(manifest_path(src).read_text(encoding="utf-8"))
    assert on_disk["verified"]["ok"] is True
    assert on_disk["verified"]["rows"] == 2


def test_flatten_preserves_source_key_order(tmp_path: Path) -> None:
    """Flattened dict keys come back in SOURCE order, not sorted. Regression pin.

    Not cosmetic: `replay_memory_engine._parse_jsonl` builds its feature vector with
    `features_dict.values()`, so re-emitting the same keys alphabetically silently
    scrambles the vector with no error raised anywhere. The first implementation sorted
    them, and the round-trip gate could not see it because `_canonical` compares dicts
    order-insensitively — it was caught only by real-reader parity on the XAUUSD corpus.
    """
    order = ["zeta", "alpha", "mid", "beta"]  # deliberately NOT alphabetical
    records = [
        {"id": 1, "features": {"zeta": 1.0, "alpha": 2.0, "mid": 3.0, "beta": 4.0}},
        {"id": 2, "features": {"zeta": 5.0, "alpha": 6.0, "mid": 7.0, "beta": 8.0}},
    ]
    src = _write(tmp_path / "ordered.jsonl", records)
    manifest = compact_jsonl(src, verify=True)

    entry = manifest["columns"]["features"]
    assert entry["children"] == order, "plan must record SOURCE order"
    assert entry["key_order_stable"] is True
    assert manifest["verified"]["ok"], manifest["verified"]

    got = list(iter_records(src))
    assert [list(r["features"].keys()) for r in got] == [order, order]
    # The consumer-shaped assertion — this is the value that actually breaks:
    assert [list(r["features"].values()) for r in got] == [
        [1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0]
    ]


def test_verify_catches_a_reordered_flatten_group(tmp_path: Path) -> None:
    """The order check must be able to FAIL, or it is decoration."""
    records = [{"features": {"zeta": 1.0, "alpha": 2.0}}]
    src = _write(tmp_path / "ord2.jsonl", records)
    compact_jsonl(src)
    assert verify_projection(src)["ok"]

    # Corrupt only the ORDER in the manifest; values stay identical.
    mp = manifest_path(src)
    m = json.loads(mp.read_text(encoding="utf-8"))
    m["columns"]["features"]["children"] = ["alpha", "zeta"]
    mp.write_text(json.dumps(m), encoding="utf-8")

    result = verify_projection(src)
    assert result["ok"] is False, "a reordered flatten group must be reported"
    assert "key order" in result["first_mismatch"]["reason"]


def test_mixed_int_float_column_stays_lossless(tmp_path: Path) -> None:
    """A column holding both ints and floats must not silently coerce to float."""
    src = _write(tmp_path / "mixed.jsonl", [{"v": 1}, {"v": 2.5}])
    manifest = compact_jsonl(src, verify=True)
    assert manifest["columns"]["v"]["policy"] == "json"
    assert manifest["verified"]["ok"]
    assert [r["v"] for r in iter_records(src)] == [1, 2.5]
    assert isinstance(list(iter_records(src))[0]["v"], int)


def test_partitioned_round_trip_and_skip_predicate(tmp_path: Path) -> None:
    """Partitioning by a kind column preserves the full multiset; headers are dropped."""
    records = [
        {"type": "run_header", "run_id": "r1"},
        {"kind": "A", "n": 1},
        {"kind": "B", "n": 2},
        {"kind": "A", "n": 3},
    ]
    src = _write(tmp_path / "parted.jsonl", records)
    manifest = compact_jsonl(
        src,
        partition_by="kind",
        skip_predicate=lambda rec: rec.get("type") == "run_header",
        verify=True,
    )
    assert manifest["rows"] == 3, "the run_header row must be excluded"
    assert manifest["verified"]["ok"], manifest["verified"]
    assert projection_path(src).is_dir()
    assert sorted(manifest["partitions"]) == ["A", "B"]
    assert sorted(r["n"] for r in iter_records(src)) == [1, 2, 3]


def test_verify_detects_a_corrupted_projection(tmp_path: Path) -> None:
    """The gate must actually fail on a bad projection, or it is not a gate."""
    src = _write(tmp_path / "c.jsonl", [{"a": 1}, {"a": 2}])
    compact_jsonl(src)
    assert verify_projection(src)["ok"]

    # Rewrite the projection with different data while keeping the manifest FRESH.
    import pyarrow as pa
    import pyarrow.parquet as pq

    pq.write_table(pa.table({"a": [99, 98]}), projection_path(src))
    result = verify_projection(src)
    assert result["ok"] is False
    assert result["mismatches"] == 2
    assert result["first_mismatch"]["diff"]["a"]["source"] == 1


# --------------------------------------------------------------------------- #
# 2. never stale
# --------------------------------------------------------------------------- #
def test_status_transitions_absent_fresh_stale(tmp_path: Path) -> None:
    src = _write(tmp_path / "s.jsonl", [{"a": 1}])
    assert projection_status(src) == ABSENT
    compact_jsonl(src)
    assert projection_status(src) == FRESH

    _write(src, [{"a": 1}, {"a": 2}])  # source moves on
    assert projection_status(src) == STALE


def test_stale_projection_falls_back_to_jsonl(tmp_path: Path) -> None:
    """A stale projection must never serve data the source no longer contains."""
    src = _write(tmp_path / "f.jsonl", [{"a": 1}])
    compact_jsonl(src)
    _write(src, [{"a": 1}, {"a": 2}, {"a": 3}])

    assert projection_status(src) == STALE
    assert [r["a"] for r in iter_records(src)] == [1, 2, 3], "must read the CURRENT source"


def test_strict_mode_catches_a_same_size_edit(tmp_path: Path) -> None:
    """size+mtime can miss an in-place edit; strict=True re-hashes and catches it."""
    src = _write(tmp_path / "h.jsonl", [{"a": 1}])
    compact_jsonl(src)
    st = src.stat()
    _write(src, [{"a": 2}])  # identical byte length
    import os

    os.utime(src, ns=(st.st_atime_ns, st.st_mtime_ns))  # restore mtime -> cheap check fooled

    assert projection_status(src) == FRESH, "precondition: the cheap check cannot see this"
    assert projection_status(src, strict=True) == STALE
    assert [r["a"] for r in iter_records(src, strict=True)] == [2]


def test_unreadable_manifest_falls_back(tmp_path: Path) -> None:
    src = _write(tmp_path / "m.jsonl", [{"a": 1}])
    compact_jsonl(src)
    manifest_path(src).write_text("{not json", encoding="utf-8")
    assert projection_status(src) == STALE
    assert [r["a"] for r in iter_records(src)] == [1]


# --------------------------------------------------------------------------- #
# 3. column pruning + optional dependency
# --------------------------------------------------------------------------- #
def test_columns_prunes_and_matches_the_jsonl_path(tmp_path: Path) -> None:
    """Pruned reads return the same shape whether or not a projection exists."""
    records = [{"a": 1, "b": 2, "c": {"x": 1.0}}, {"a": 3, "b": 4, "c": {"x": 2.0}}]
    src = _write(tmp_path / "p.jsonl", records)

    from_jsonl = list(iter_records(src, columns=["a", "c"]))  # ABSENT -> JSONL path
    compact_jsonl(src)
    from_parquet = list(iter_records(src, columns=["a", "c"]))

    assert from_parquet == from_jsonl == [{"a": 1, "c": {"x": 1.0}}, {"a": 3, "c": {"x": 2.0}}]
    assert all("b" not in r for r in from_parquet)


def test_unknown_requested_column_is_ignored_not_fatal(tmp_path: Path) -> None:
    src = _write(tmp_path / "u.jsonl", [{"a": 1}])
    compact_jsonl(src)
    assert list(iter_records(src, columns=["a", "nope"])) == [{"a": 1}]


def test_reads_degrade_to_jsonl_without_pyarrow(tmp_path: Path, monkeypatch) -> None:
    """The optional-import guard must degrade, not raise (conventions.md 3.2)."""
    records = [{"a": 1, "b": {"x": 1}}, {"a": 2, "b": {"x": 2}}]
    src = _write(tmp_path / "o.jsonl", records)
    compact_jsonl(src)

    monkeypatch.setattr(ps, "_PARQUET_AVAILABLE", False)
    assert projection_status(src) == "UNAVAILABLE"
    assert list(iter_records(src)) == records
    assert list(iter_records(src, columns=["a"])) == [{"a": 1}, {"a": 2}]

    with pytest.raises(RuntimeError, match="pyarrow"):
        compact_jsonl(src)


def test_missing_source_is_not_silently_empty(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        compact_jsonl(tmp_path / "nope.jsonl")


# --------------------------------------------------------------------------- #
# 4. dual-read parity at the real call sites
# --------------------------------------------------------------------------- #
def test_replay_engine_reads_identically_with_and_without_projection(tmp_path: Path) -> None:
    """The migrated reader must return the same records from either path.

    This is the seam that matters: `ReplayMemoryEngine._parse_jsonl` takes a Parquet fast
    path when a projection is FRESH and the raw line-numbered path otherwise. Both must
    yield the same ReplayRecords, or the projection has changed behaviour rather than
    just storage.
    """
    from replay.replay_memory_engine import ReplayMemoryEngine, ReplayRecord

    feats = {"a": 1.0, "b": 2.0, "c": 3.0}
    rows = [{"type": "run_header", "run_id": "r1"}] + [
        {
            "timestamp": "2026-08-20T00:00:00",
            "instrument": "XAUUSD",
            "direction": "long",
            "outcome": "TP_HIT",
            "rr_achieved": 1.5,
            "features": dict(feats),
        }
        for _ in range(20)
    ]
    src = _write(tmp_path / "opportunities.jsonl", rows)

    def _load() -> list:
        # ReplayRecord uses __slots__ with no __eq__, so compare by field.
        engine = ReplayMemoryEngine(opportunities_dir=str(tmp_path), min_cluster_samples=1)
        return [
            {f: getattr(r, f) for f in ReplayRecord.__slots__}
            for r in engine._parse_jsonl(src, now_ts=1_800_000_000.0)
        ]

    from_jsonl = _load()
    assert projection_status(src) == ABSENT and from_jsonl, "precondition: raw path, non-empty"

    compact_jsonl(src, skip_predicate=lambda rec: rec.get("type") == "run_header", verify=True)
    assert projection_status(src) == FRESH
    from_parquet = _load()

    assert from_parquet == from_jsonl
    assert len(from_parquet) == 20


def test_timing_reconstructor_iter_jsonl_parity(tmp_path: Path) -> None:
    """`iter_jsonl` keeps dropping the run_header on both paths."""
    from replay.timing_reconstructor import iter_jsonl

    rows = [
        {"type": "run_header", "run_id": "r1"},
        {"timestamp": "t1", "outcome": "TP_HIT", "rr_achieved": 1.0},
        {"timestamp": "t2", "outcome": "SL_HIT", "rr_achieved": -1.0},
    ]
    src = _write(tmp_path / "opportunities.jsonl", rows)

    from_jsonl = list(iter_jsonl(src))
    compact_jsonl(src)  # header row retained in the projection; iter_jsonl still drops it
    from_parquet = list(iter_jsonl(src))

    assert from_jsonl == from_parquet == rows[1:]
    assert all(r.get("type") != "run_header" for r in from_parquet)


# --------------------------------------------------------------------------- #
# 5. real-corpus parity (skips unless the XAUUSD corpora are on disk)
# --------------------------------------------------------------------------- #
#
# The unit tests above all build their own tiny fixtures. These two run the REAL
# migrated readers against the REAL converted XAUUSD corpora, because that is the one
# thing a synthetic fixture cannot establish: that a projection built from a 121 MB
# production artifact feeds a production reader the same records its JSONL does.
#
# Note on why these exist at all: a backtest run on the XAUUSD corpus was byte-identical
# to its predecessor, but NONE of the migrated modules are on the backtest path, so that
# run was not evidence about this change. This is.
_REPO = Path(__file__).resolve().parents[1]
_OPPS = _REPO / "logs/XAUUSD/xauusd_phase1_20260723/opportunities.jsonl"
_EVENTS = (
    _REPO / "results/research/_spine_entries/XAUUSD__v2_multi_2026_04"
    / "run_20260822_162108_XAUUSD/XAUUSD_events.jsonl"
)

_needs_corpus = pytest.mark.skipif(
    not _OPPS.exists(), reason="real XAUUSD opportunities corpus not on disk"
)
_needs_events = pytest.mark.skipif(
    not _EVENTS.exists(), reason="real XAUUSD events corpus not on disk"
)


@_needs_corpus
@pytest.mark.slow
def test_real_corpus_replay_engine_parity(monkeypatch) -> None:
    """ReplayMemoryEngine returns identical records through Parquet and through JSONL.

    Two traps this test is built to avoid, each of which yields a green-but-empty pass:

      * VACUITY. These records are stamped 2024-05-xx and `_parse_jsonl` drops anything
        older than 2x staleness_threshold_days (default 90 => 180). Left at the default
        this compares [] == [] and "passes". Hence the large threshold and the explicit
        non-vacuity floor below.
      * IDENTITY. ReplayRecord uses __slots__ with no __eq__, so `==` compares addresses.
        Hence the field-wise projection.

    The JSONL arm is forced by monkeypatching `projection_status` rather than by renaming
    the sidecar on disk — this repo runs many concurrent sessions and a test must not
    mutate shared artifacts.
    """
    from replay import replay_memory_engine as rme
    from replay.replay_memory_engine import ReplayMemoryEngine, ReplayRecord

    if projection_status(_OPPS) != FRESH:
        pytest.skip("no fresh projection for the opportunities corpus")

    def _load() -> list[dict]:
        engine = ReplayMemoryEngine(
            opportunities_dir=str(_OPPS.parent),
            min_cluster_samples=1,
            staleness_threshold_days=5000.0,  # keep 2024 records in scope (anti-vacuity)
        )
        return [
            {f: getattr(r, f) for f in ReplayRecord.__slots__}
            for r in engine._parse_jsonl(_OPPS, now_ts=1_800_000_000.0)
        ]

    from_parquet = _load()  # projection is FRESH -> fast path

    monkeypatch.setattr(rme, "projection_status", lambda *a, **k: "ABSENT")
    from_jsonl = _load()  # forced onto the raw line-numbered path

    # Non-vacuity floor FIRST: an empty comparison must fail, not pass.
    assert len(from_jsonl) > 1_000, f"vacuous test — only {len(from_jsonl)} records survived"
    assert len(from_parquet) == len(from_jsonl)
    assert from_parquet == from_jsonl


@_needs_events
def test_real_corpus_events_seam_parity() -> None:
    """The exact column set `structural_event_source` requests survives the projection.

    That module's harvest() runs a backtest internally, so the testable unit is the read
    seam it now goes through, applying its own STATE_TRANSITION filter.
    """
    cols = ["event", "state_to", "timestamp"]
    if projection_status(_EVENTS) != FRESH:
        pytest.skip("no fresh projection for the events corpus")

    from_parquet = [
        r for r in iter_records(_EVENTS, columns=cols) if r.get("event") == "STATE_TRANSITION"
    ]
    from_jsonl = [
        {k: rec[k] for k in cols if k in rec}
        for rec in (json.loads(line) for line in _EVENTS.read_text(encoding="utf-8").splitlines() if line.strip())
        if rec.get("event") == "STATE_TRANSITION"
    ]

    assert len(from_jsonl) > 100, f"vacuous test — only {len(from_jsonl)} transitions"
    assert from_parquet == from_jsonl
