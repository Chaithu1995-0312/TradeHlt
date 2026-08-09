"""XAUUSD corpus certification floor (ERP T1) — offline, fast, deterministic.

Asserts that XAUUSD M15 loads resolve ONLY to the governance-canonical frozen candidate
(data/mt5/XAUUSD_M15.csv) via the guard, that the frozen binding verifies, that the schema contract
holds, and that the certify driver records an honest integrity decision under a run_manifest. The
corpus is gitignored → SKIP cleanly when absent (e.g. CI without the file).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from data_ingestion.xauusd_phase1_candidate import (
    PHASE1_SHA256,
    PHASE1_STATUS,
    guard_xauusd_csv_path,
    verify_phase1_frozen_candidate,
)

_ROOT = Path(__file__).resolve().parents[2]
_CORPUS = _ROOT / "data" / "mt5" / "XAUUSD_M15.csv"

pytestmark = pytest.mark.research_integrity
skip_if_absent = pytest.mark.skipif(
    not _CORPUS.exists(), reason="gitignored XAUUSD frozen candidate not present")


def _load_driver():
    spec = importlib.util.spec_from_file_location(
        "certify_xauusd_corpus", _ROOT / "scripts" / "research" / "certify_xauusd_corpus.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@skip_if_absent
def test_guard_resolves_only_to_frozen_candidate():
    # The root data/XAUUSD_M15.csv must be rewritten to the mt5 frozen candidate.
    guarded = guard_xauusd_csv_path("data/XAUUSD_M15.csv", "XAUUSD").replace("\\", "/")
    assert guarded.endswith("data/mt5/XAUUSD_M15.csv"), guarded
    rep = verify_phase1_frozen_candidate()
    assert rep["ok"] is True
    assert rep["content_hash_sha256"] == PHASE1_SHA256
    assert rep["rows"] == 47275


@skip_if_absent
def test_certify_driver_records_honest_decision_and_manifest():
    drv = _load_driver()
    a = drv.certify()
    assert a["schema_ok"] is True
    assert a["timestamps_monotonic_unique"] is True
    assert a["integrity_decision"] in ("APPROVE", "WARN", "REJECT")  # recorded, not required-clean
    assert a["non_promotable"] is True
    assert a["phase1_status"] == PHASE1_STATUS
    assert a["corpus_path"].endswith("data/mt5/XAUUSD_M15.csv")
    # driver emits a provenance manifest and exits 0 (WARN/REJECT is not a failure)
    assert drv.main() == 0
