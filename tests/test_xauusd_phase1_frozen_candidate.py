"""Fail-closed enforcement for XAUUSD Phase-1 frozen candidate binding."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from data_ingestion.xauusd_phase1_candidate import (
    BINDING_PATH,
    PHASE1_END,
    PHASE1_PHYSICAL_PATH,
    PHASE1_ROWS,
    PHASE1_SHA256,
    PHASE1_START,
    PHASE1_STATUS,
    Phase1CandidateError,
    load_binding,
    require_phase1_frozen_candidate,
    verify_phase1_frozen_candidate,
)

ROOT = Path(__file__).resolve().parent.parent


def test_binding_file_shape_and_forbidden_labels():
    assert BINDING_PATH.is_file()
    raw = json.loads(BINDING_PATH.read_text(encoding="utf-8"))
    assert raw["status"] == PHASE1_STATUS
    assert raw["physical_path"] == PHASE1_PHYSICAL_PATH.as_posix()
    assert raw["content_hash_sha256"] == PHASE1_SHA256
    assert raw["rows"] == PHASE1_ROWS
    assert raw["allowed_time_range"]["start"] == PHASE1_START.isoformat()
    assert raw["allowed_time_range"]["end"] == PHASE1_END.isoformat()
    for ban in ("AUTHORITATIVE", "VALIDATED", "ECONOMICALLY_ADMISSIBLE", "APPROVED"):
        assert ban in raw["explicitly_not"]
    # must not claim authority in status
    assert "AUTHORITATIVE" not in raw["status"]
    assert "VALIDATED" not in raw["status"]


def test_module_constants_match_on_disk_and_binding():
    b = load_binding()
    assert b.content_hash_sha256 == PHASE1_SHA256
    assert b.physical_path == PHASE1_PHYSICAL_PATH
    assert b.rows == PHASE1_ROWS
    assert b.start == PHASE1_START
    assert b.end == PHASE1_END
    report = verify_phase1_frozen_candidate(repo_root=ROOT, binding=b)
    assert report["ok"] is True
    assert report["content_hash_sha256"] == PHASE1_SHA256
    assert report["rows"] == PHASE1_ROWS


def test_require_phase1_frozen_candidate_green():
    b = require_phase1_frozen_candidate(repo_root=ROOT)
    assert b.status == PHASE1_STATUS


def test_reject_wrong_path_claim(tmp_path: Path):
    """A different physical file must not satisfy the candidate check."""
    # Point binding at a copy with different content → hash drift
    other = tmp_path / "fake.csv"
    other.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2024-05-22 01:00:00,1,1,1,1,1\n",
        encoding="utf-8",
    )
    # Simulate wrong path by verifying against wrong file via monkeypatch of root layout
    # Create mini repo with wrong hash at expected relative path
    mini = tmp_path / "repo"
    target = mini / PHASE1_PHYSICAL_PATH
    target.parent.mkdir(parents=True)
    target.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2024-05-22 01:00:00,1,1,1,1,1\n",
        encoding="utf-8",
    )
    with pytest.raises(Phase1CandidateError, match="hash drift|row count"):
        verify_phase1_frozen_candidate(repo_root=mini)


def test_extended_root_is_not_phase1_candidate():
    """data/XAUUSD_M15.csv (extended) must not be confused with the frozen candidate."""
    root_csv = ROOT / "data" / "XAUUSD_M15.csv"
    if not root_csv.is_file():
        pytest.skip("root corpus missing")
    h = __import__("hashlib").sha256(root_csv.read_bytes()).hexdigest()
    assert h != PHASE1_SHA256
    assert (ROOT / PHASE1_PHYSICAL_PATH).resolve() != root_csv.resolve()


def test_guard_rewrites_root_xauusd_m15_to_frozen_candidate():
    from data_ingestion.xauusd_phase1_candidate import guard_xauusd_csv_path

    root_csv = ROOT / "data" / "XAUUSD_M15.csv"
    if not root_csv.is_file():
        pytest.skip("root corpus missing")
    guarded = Path(guard_xauusd_csv_path(str(root_csv), "XAUUSD"))
    assert guarded.resolve() == (ROOT / PHASE1_PHYSICAL_PATH).resolve()
    assert guarded.name == "XAUUSD_M15.csv"
    assert "mt5" in guarded.as_posix()


def test_candle_loader_xauusd_uses_frozen_candidate():
    from runtime.backtest_v2 import CandleLoader

    root_csv = ROOT / "data" / "XAUUSD_M15.csv"
    if not root_csv.is_file() and not (ROOT / PHASE1_PHYSICAL_PATH).is_file():
        pytest.skip("XAUUSD corpora missing")
    # Pass extended root path — loader must rewrite to mt5 frozen candidate
    loader = CandleLoader(str(root_csv if root_csv.is_file() else ROOT / PHASE1_PHYSICAL_PATH), "XAUUSD")
    assert Path(loader.filepath).resolve() == (ROOT / PHASE1_PHYSICAL_PATH).resolve()
    # stream a few candles without error
    n = 0
    for _ in loader.stream():
        n += 1
        if n >= 3:
            break
    assert n == 3


def test_guard_non_xauusd_passthrough():
    from data_ingestion.xauusd_phase1_candidate import guard_xauusd_csv_path

    p = "data/EURUSD_M15.csv"
    assert guard_xauusd_csv_path(p, "EURUSD") == p
