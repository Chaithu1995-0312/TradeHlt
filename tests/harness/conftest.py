"""Shared fixtures for the ERP anti-hallucination test harness (T0)."""
from __future__ import annotations

from pathlib import Path

import pytest

from utils.run_manifest import build_manifest
from utils.validation_contract import load_intent_contract

FIXTURES = Path(__file__).parent / "fixtures"
INTENT_WI_002 = FIXTURES / "intent_WI-002.json"


def _matching_manifest_fields() -> dict:
    """Caller-supplied manifest fields that MATCH intent_WI-002.json (the happy path)."""
    return dict(
        command="python scripts/research/story_library_build.py",
        argv=["scripts/research/story_library_build.py"],
        validation_lens="synthetic_story_golden",
        exit_model="intrabar_fixed",
        cost_model_bps=0,
        label_source="forward_walk_intrabar_fixed",
        instruments=["SYNTHUSDT"],
        timeframe="M15",
        data_source="synthetic",
        network="none",
        dry_run=True,
        intended_work_item_id="WI-002",
    )


@pytest.fixture
def manifest_fields() -> dict:
    return _matching_manifest_fields()


@pytest.fixture
def valid_manifest(manifest_fields) -> dict:
    return build_manifest(**manifest_fields)


@pytest.fixture
def valid_assertions() -> dict:
    return {"n_stories": 12, "library_all_pass": True}


@pytest.fixture
def intent() -> dict:
    return load_intent_contract(INTENT_WI_002)
