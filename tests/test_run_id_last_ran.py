"""Tests for utils.run_id_last_ran — last-ran time persistence per run_id."""
from __future__ import annotations

import pytest

from utils import run_id_last_ran as mod


@pytest.fixture()
def isolated_index(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_INDEX_DIR", tmp_path)
    monkeypatch.setattr(mod, "_MAP_PATH", tmp_path / "run_id_last_ran.json")
    monkeypatch.setattr(mod, "_HIST_PATH", tmp_path / "run_id_last_ran.jsonl")
    return tmp_path


def test_record_and_get_last_ran(isolated_index):
    rec = mod.record_run_last_ran(
        "run_20240522_143000",
        when="2024-05-22T14:30:00Z",
        source="test",
        instrument="XAUUSD",
        started_at="2024-05-22T14:29:00Z",
    )
    assert rec is not None
    assert rec["last_ran_at"] == "2024-05-22T14:30:00Z"
    assert rec["first_ran_at"] == "2024-05-22T14:29:00Z"
    assert rec["ran_count"] == 1

    got = mod.get_run_last_ran("run_20240522_143000")
    assert got["last_ran_at"] == "2024-05-22T14:30:00Z"
    assert got["instrument"] == "XAUUSD"

    mod.record_run_last_ran(
        "run_20240522_143000",
        when="2024-05-22T15:00:00Z",
        source="test",
        instrument="XAUUSD",
    )
    got2 = mod.get_run_last_ran("run_20240522_143000")
    assert got2["last_ran_at"] == "2024-05-22T15:00:00Z"
    assert got2["first_ran_at"] == "2024-05-22T14:29:00Z"
    assert got2["ran_count"] == 2

    hist = (isolated_index / "run_id_last_ran.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(hist) == 2


def test_blank_run_id_noop(isolated_index):
    assert mod.record_run_last_ran("") is None
    assert mod.get_run_last_ran("") is None


def test_get_missing_returns_none(isolated_index):
    assert mod.get_run_last_ran("no_such_run") is None
