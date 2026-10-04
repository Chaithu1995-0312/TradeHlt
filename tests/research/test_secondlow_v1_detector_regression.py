"""SECONDLOW-v1 detector regression floor.

XAUUSD M15 research corpus = Phase-1 frozen candidate (data/mt5/XAUUSD_M15.csv).
Sandbox xlsx fixture pins detector bytecode only — not economic claims.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from research.secondlow_v1.corpus import (
    CANONICAL_CORPUS_SHA256_PREFIX,
    CANONICAL_EXPECTED_DISCOVERY,
    CANONICAL_EXPECTED_INDEPENDENT,
    CANONICAL_EXPECTED_POST,
    CANONICAL_EXPECTED_PRE,
    CANONICAL_EXPECTED_RAW,
    CANONICAL_XAUUSD_M15,
    REGRESSION_EXPECTED_INDEPENDENT,
    REGRESSION_EXPECTED_RAW,
    REGRESSION_FIXTURE_SHA256_PREFIX,
    REGRESSION_FIXTURE_XLSX,
    REGRESSION_INDEPENDENT_TIMESTAMPS,
    resolved_canonical_csv,
)
from research.secondlow_v1.detector import (
    detect_independent_events,
    load_ohlcv,
    partition_event_times,
    sha256_prefix,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _resolve(path: Path) -> Path:
    return _REPO_ROOT / path


@pytest.fixture(scope="module")
def regression_xlsx() -> Path:
    path = _resolve(REGRESSION_FIXTURE_XLSX)
    if not path.is_file():
        pytest.skip(f"regression fixture missing: {path}")
    return path


@pytest.fixture(scope="module")
def canonical_csv() -> Path:
    path = resolved_canonical_csv(_REPO_ROOT)
    if not path.is_file():
        pytest.skip(f"canonical corpus missing: {path}")
    return path


def test_regression_fixture_hash_prefix(regression_xlsx: Path) -> None:
    assert sha256_prefix(regression_xlsx) == REGRESSION_FIXTURE_SHA256_PREFIX


def test_canonical_corpus_hash_prefix(canonical_csv: Path) -> None:
    assert sha256_prefix(canonical_csv) == CANONICAL_CORPUS_SHA256_PREFIX
    assert CANONICAL_XAUUSD_M15.as_posix() == "data/mt5/XAUUSD_M15.csv"


def test_regression_fixture_event_counts(regression_xlsx: Path) -> None:
    df = load_ohlcv(regression_xlsx)
    raw_mask, events = detect_independent_events(df)
    assert int(raw_mask.sum()) == REGRESSION_EXPECTED_RAW
    assert len(events) == REGRESSION_EXPECTED_INDEPENDENT
    got = [str(e.purge_time) for e in events]
    assert got == list(REGRESSION_INDEPENDENT_TIMESTAMPS)


def test_canonical_corpus_partition_invariants(canonical_csv: Path) -> None:
    df = load_ohlcv(canonical_csv)
    raw_mask, events = detect_independent_events(df)
    assert int(raw_mask.sum()) == CANONICAL_EXPECTED_RAW
    assert len(events) == CANONICAL_EXPECTED_INDEPENDENT
    parts = partition_event_times([e.purge_time for e in events])
    assert len(parts["pre_discovery"]) == CANONICAL_EXPECTED_PRE
    assert len(parts["discovery"]) == CANONICAL_EXPECTED_DISCOVERY
    assert len(parts["post_discovery"]) == CANONICAL_EXPECTED_POST
    assert (
        len(parts["pre_discovery"])
        + len(parts["discovery"])
        + len(parts["post_discovery"])
        == CANONICAL_EXPECTED_INDEPENDENT
    )
