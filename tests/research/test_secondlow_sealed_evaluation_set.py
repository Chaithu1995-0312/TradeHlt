"""Sealed PRE_DISCOVERY evaluation set — timestamp manifest floor."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from research.secondlow_v1.corpus import CANONICAL_CORPUS_SHA256_PREFIX, CANONICAL_XAUUSD_M15
from research.secondlow_v1.detector import (
    DISCOVERY_START,
    detect_independent_events,
    load_ohlcv,
    partition_event_times,
    sha256_prefix,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MANIFEST = _REPO_ROOT / "H-SECONDLOW-002_Complete_Package/data/sealed_evaluation_set_v1.json"


@pytest.fixture(scope="module")
def manifest() -> dict:
    if not _MANIFEST.is_file():
        pytest.skip(f"sealed manifest missing: {_MANIFEST}")
    return json.loads(_MANIFEST.read_text(encoding="utf-8"))


def test_manifest_unsealed_after_prereg_approval(manifest: dict) -> None:
    assert manifest["status"] == "UNSEALED_FOR_H_SECONDLOW_003"
    assert manifest["preregistration_status"] == "APPROVED"
    assert manifest["preregistration_id"] == "H-SECONDLOW-003"
    assert manifest["event_count"] == 21
    assert len(manifest["purge_times"]) == 21
    split = manifest["internal_split"]
    assert split["seed"] == 42
    assert len(split["development"]) + len(split["holdout"]) == 21


def test_manifest_matches_live_detector(manifest: dict) -> None:
    from research.secondlow_v1.corpus import resolved_canonical_csv

    corpus = resolved_canonical_csv(_REPO_ROOT)
    if not corpus.is_file():
        pytest.skip("canonical corpus missing")
    assert sha256_prefix(corpus) == CANONICAL_CORPUS_SHA256_PREFIX
    assert manifest["corpus"]["sha256_prefix"] == CANONICAL_CORPUS_SHA256_PREFIX
    assert manifest["corpus"]["path"] == CANONICAL_XAUUSD_M15.as_posix()

    df = load_ohlcv(corpus)
    _, events = detect_independent_events(df)
    parts = partition_event_times([e.purge_time for e in events])
    pre_times = sorted(parts["pre_discovery"])
    manifest_times = sorted(pd.to_datetime(manifest["purge_times"]))
    assert pre_times == manifest_times


def test_manifest_forbids_outcome_fields_until_prereg(manifest: dict) -> None:
    forbidden = set(manifest["forbidden_until_prereg"])
    assert "close_disp_atr" in forbidden
    assert "pre_2h_return_atr" in forbidden
    assert "exposure_threshold_sweeps" in forbidden