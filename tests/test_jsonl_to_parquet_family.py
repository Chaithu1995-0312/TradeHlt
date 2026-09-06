"""
test_jsonl_to_parquet_family.py — FAMILY_DEFAULTS resolve_family floors.

Pins the measured family → (partition_by, skip) map, including the additive
`_crt_construction.jsonl` entry (partition by engine_state_after).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "maintenance"))

from jsonl_to_parquet import FAMILY_DEFAULTS, resolve_family  # noqa: E402


def test_crt_construction_defaults_to_engine_state_after() -> None:
    partition_by, skip = resolve_family(Path("logs/dual_construction/XAUUSD_crt_construction.jsonl"))
    assert partition_by == "engine_state_after"
    assert skip is None


def test_bar_structure_still_partitions_on_crt_state_after() -> None:
    partition_by, skip = resolve_family(Path("logs/bar_structure/XAUUSD_bar_structure.jsonl"))
    assert partition_by == "crt_state_after"
    assert skip is None


def test_unknown_family_has_no_partition() -> None:
    partition_by, skip = resolve_family(Path("logs/misc/something_else.jsonl"))
    assert partition_by is None
    assert skip is None


def test_family_defaults_contains_crt_construction_suffix() -> None:
    assert "_crt_construction.jsonl" in FAMILY_DEFAULTS
    assert FAMILY_DEFAULTS["_crt_construction.jsonl"] == ("engine_state_after", None)


def test_crt_construction_real_reader_parity(tmp_path: Path) -> None:
    """Project synthetic CRTConstructionTrace rows and compare JSONL vs Parquet reads.

    Equality alone is insufficient (order-insensitive dict compare can hide scramble).
    Assert consumer-shaped fields: bar_index sequence, engine_state_after stratum
    multiset, and agree null-vs-bool semantics on warmup vs live.
    """
    import json

    from utils.parquet_store import (
        compact_jsonl,
        iter_records,
        parquet_available,
        projection_path,
    )

    if not parquet_available():
        import pytest

        pytest.skip("pyarrow not installed")

    # Minimal schema v2.0.0-shaped rows (docs/reference/schemas.md §9.17).
    records = [
        {
            "schema_version": "2.0.0",
            "run_id": "parity",
            "instrument": "XAUUSD",
            "timeframe": "M15",
            "bar_index": 0,
            "phase": "WARMUP",
            "engine_state_before": None,
            "engine_state_after": None,
            "engine_action": None,
            "agree": None,
            "engine.transitions": None,
            "emitted_by": "runtime.crt_construction_trace",
        },
        {
            "schema_version": "2.0.0",
            "run_id": "parity",
            "instrument": "XAUUSD",
            "timeframe": "M15",
            "bar_index": 10,
            "phase": "LIVE",
            "engine_state_before": "RANGE",
            "engine_state_after": "RANGE",
            "engine_action": "HOLD",
            "agree": True,
            "engine.transitions": [],
            "emitted_by": "runtime.crt_construction_trace",
        },
        {
            "schema_version": "2.0.0",
            "run_id": "parity",
            "instrument": "XAUUSD",
            "timeframe": "M15",
            "bar_index": 11,
            "phase": "LIVE",
            "engine_state_before": "RANGE",
            "engine_state_after": "EXPANSION",
            "engine_action": "ENTER",
            "agree": False,
            "engine.transitions": [
                {"from": "RANGE", "to": "EXPANSION", "reason": "test"}
            ],
            "emitted_by": "runtime.crt_construction_trace",
        },
    ]
    src = tmp_path / "XAUUSD_crt_construction.jsonl"
    src.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
        encoding="utf-8",
    )

    # Use the family default the CLI would pick.
    partition_by, skip = resolve_family(src)
    assert partition_by == "engine_state_after"
    manifest = compact_jsonl(
        src, partition_by=partition_by, skip_predicate=skip, verify=True
    )
    assert manifest["verified"]["ok"], manifest["verified"]
    assert projection_path(src).is_dir()

    from_jsonl = records
    from_parquet = list(iter_records(src))

    # Non-vacuity. Partitioned iter_records is stratum-ordered, not source-ordered —
    # align on bar_index (the spine join key) before consumer-shaped checks.
    assert len(from_parquet) == 3
    by_bar = {r["bar_index"]: r for r in from_parquet}
    assert set(by_bar) == {0, 10, 11}

    # Stratum multiset (partition key) — equality alone would miss a dropped stratum
    strata = [
        "∅" if r.get("engine_state_after") is None else r["engine_state_after"]
        for r in from_parquet
    ]
    assert sorted(strata) == sorted(["∅", "RANGE", "EXPANSION"])

    # Null semantics: warmup agree stays None (not dropped, not False)
    assert "agree" in by_bar[0] and by_bar[0]["agree"] is None
    assert by_bar[10]["agree"] is True
    assert by_bar[11]["agree"] is False

    # Empty list vs null on engine.transitions are different facts (schemas.md §9.17)
    assert by_bar[0]["engine.transitions"] is None
    assert by_bar[10]["engine.transitions"] == []
    assert by_bar[11]["engine.transitions"] == [
        {"from": "RANGE", "to": "EXPANSION", "reason": "test"}
    ]

    # Full record multiset equality (order-normalized on bar_index)
    assert [by_bar[i] for i in (0, 10, 11)] == from_jsonl
