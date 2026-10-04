"""Run-Identity Governance (EFAP Stage 0/2) — the join-gate adversarial floor.

Proves the four load-bearing mechanisms:
  1. canonical identity authority (single build point),         [Phase 1-B.2]
  2. VERIFIED/UNVERIFIED identity_status is first-class,        [Phase 1-B.2]
  3. always-on identity status decision,                        [Phase 1-B.3]
  4. can_join() denies cross-run / config-drift / UNVERIFIED    [Phase 1-B.4]
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from governance.run_identity import (
    ALLOW_REASON_CODE,
    DENY_CONFIG_HASH_MISMATCH,
    DENY_RUN_ID_MISMATCH,
    DENY_UNVERIFIED_OPERAND,
    UNVERIFIED,
    VERIFIED,
    build_identity,
    can_join,
    dataset_hash,
    validate_join_artifacts,
    RunIdentity,
)

_TS = "2026-09-16T10:15:06+00:00"


def _id(overrides: dict | None = None) -> RunIdentity:
    d = {
        "run_id": "run_20260916_101506_XAUUSD",
        "config_version": "v2_multi_2026_04",
        "config_hash": "a" * 64,
        "dataset_hash": "b" * 64,
        "artifact_timestamp": _TS,
    }
    d.update(overrides or {})
    return build_identity(**d)


# ── identity authority / status ───────────────────────────────────────────────

def test_build_identity_verified_when_all_fields_present():
    r = _id()
    assert r.identity_status == VERIFIED
    assert r.is_verified


def test_missing_dataset_hash_forces_unverified():
    # RECOMPUTE != RECOVER: no fabricated dataset identity
    r = _id({"dataset_hash": ""})
    assert r.identity_status == UNVERIFIED
    assert not r.is_verified


def test_missing_config_hash_forces_unverified():
    r = _id({"config_hash": None})
    assert r.identity_status == UNVERIFIED


def test_missing_run_id_forces_unverified():
    r = _id({"run_id": ""})
    assert r.identity_status == UNVERIFIED


def test_roundtrip_to_dict_from_dict():
    r = _id()
    assert RunIdentity.from_dict(r.to_dict()) == r


def test_from_json_file(tmp_path: Path):
    p = tmp_path / "run_identity.json"
    p.write_text(json.dumps(_id().to_dict()), encoding="utf-8")
    assert RunIdentity.from_json_file(p) == _id()


# ── can_join gate ─────────────────────────────────────────────────────────────

def test_can_join_same_verified_run_allowed():
    a = _id()
    b = _id()
    ok, reason = can_join(a, b)
    assert ok and "JOIN ALLOWED" in reason
    assert ALLOW_REASON_CODE in reason


def test_can_join_cross_run_denied_with_code():
    a = _id()
    b = _id({"run_id": "run_20260918_204734_XAUUSD"})
    ok, reason = can_join(a, b)
    assert not ok and "cross-run" in reason
    assert DENY_RUN_ID_MISMATCH in reason


def test_can_join_config_drift_denied_with_code():
    a = _id()
    b = _id({"config_hash": "c" * 64})
    ok, reason = can_join(a, b)
    assert not ok and "config_hash mismatch" in reason
    assert DENY_CONFIG_HASH_MISMATCH in reason


def test_can_join_unverified_operand_denied_first(tmp_path: Path):
    # The historical-run loophole: an UNVERIFIED record (e.g. pre-2026-09-16) can
    # never join, regardless of matching run_id/config_hash.
    a = _id()
    b = _id({"dataset_hash": ""})  # missing hash ⇒ build_identity marks UNVERIFIED
    assert b.identity_status == UNVERIFIED
    ok, reason = can_join(a, b)
    assert not ok and "not VERIFIED" in reason
    assert DENY_UNVERIFIED_OPERAND in reason


def test_can_join_unverified_code_wins_over_run_id_mismatch():
    # Load-bearing order: an UNVERIFIED operand must deny with UNVERIFIED_OPERAND
    # even when the other operand carries a different run_id.
    a = _id({"run_id": "run_AAAA"})
    b = _id({"run_id": "run_BBBB", "dataset_hash": ""})  # UNVERIFIED + cross-run
    assert b.identity_status == UNVERIFIED
    ok, reason = can_join(a, b)
    assert not ok
    assert DENY_UNVERIFIED_OPERAND in reason
    assert DENY_RUN_ID_MISMATCH not in reason


def test_can_join_both_unverified_denied():
    a = _id({"dataset_hash": ""})
    b = _id({"dataset_hash": ""})
    ok, _ = can_join(a, b)
    assert not ok


def test_validate_join_artifacts(tmp_path: Path):
    la = tmp_path / "a.json"
    lb = tmp_path / "b.json"
    la.write_text(json.dumps(_id().to_dict()), encoding="utf-8")
    lb.write_text(json.dumps(_id({"run_id": "run_other_XAEURUD"}).to_dict()), encoding="utf-8")
    ok, reason = validate_join_artifacts(la, lb)
    assert not ok and "cross-run" in reason


# ── dataset_hash (registered formula) ─────────────────────────────────────────

def test_dataset_hash_deterministic(tmp_path: Path):
    p = tmp_path / "data.csv"
    p.write_text("ts,open,high,low,close\n", encoding="utf-8")
    assert dataset_hash(p) == dataset_hash(p)


def test_dataset_hash_differs_between_files(tmp_path: Path):
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    a.write_text("a", encoding="utf-8")
    b.write_text("b", encoding="utf-8")
    assert dataset_hash(a) != dataset_hash(b)