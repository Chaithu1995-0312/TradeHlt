"""Validation-path identity pack VP-01..VP-05 (ERP testing-plan §5) — the H3 harness.

Asserts the manifest's actual path (lens / label / cost / instruments / network / broker) matches the
work-item intent contract, and that prose summaries are generated FROM the run, not free-handed.
`manifest_fields` and `intent` come from conftest.py fixtures (no cross-module import).
"""
from __future__ import annotations

import pytest

from utils.run_manifest import build_manifest
from utils.validation_contract import (
    MissingManifestError,
    assert_summary_matches_manifest,
    require_manifest,
    summary_from_assertions,
    validate_manifest_against_intent,
)


@pytest.mark.research_integrity
def test_vp01_manifest_records_lens_and_env(valid_manifest):
    assert valid_manifest["validation_lens"] == "synthetic_story_golden"
    assert valid_manifest["exit_model"] == "intrabar_fixed"
    assert valid_manifest["label_source"] == "forward_walk_intrabar_fixed"


@pytest.mark.research_integrity
def test_vp02_matching_manifest_has_no_violations(valid_manifest, intent):
    assert validate_manifest_against_intent(valid_manifest, intent) == []


@pytest.mark.research_integrity
def test_vp02_wrong_lens_is_flagged(manifest_fields, intent):
    bad = build_manifest(**{**manifest_fields, "validation_lens": "fusion_gate_on"})
    assert any("validation_lens" in v for v in validate_manifest_against_intent(bad, intent))


@pytest.mark.research_integrity
def test_vp03_wrong_label_source_is_flagged(manifest_fields, intent):
    bad = build_manifest(**{**manifest_fields, "label_source": "opportunity_stream"})
    assert any("label_source" in v for v in validate_manifest_against_intent(bad, intent))


@pytest.mark.research_integrity
def test_vp03_network_or_broker_leak_is_flagged(manifest_fields, intent):
    net = build_manifest(**{**manifest_fields, "network": "binance_public"})
    assert any("network" in v for v in validate_manifest_against_intent(net, intent))
    live = build_manifest(**{**manifest_fields, "dry_run": False})
    assert any("dry_run" in v for v in validate_manifest_against_intent(live, intent))


@pytest.mark.research_integrity
def test_vp04_economic_claim_refused_without_manifest(tmp_path):
    with pytest.raises(MissingManifestError):
        require_manifest(tmp_path)


@pytest.mark.research_integrity
def test_vp05_summary_is_generated_from_the_run(valid_manifest, valid_assertions):
    summary = summary_from_assertions(valid_assertions, valid_manifest)
    assert summary["result"] == valid_assertions
    assert summary["instruments"] == valid_manifest["instruments"]
    assert_summary_matches_manifest(summary, valid_manifest)  # round-trips clean


@pytest.mark.research_integrity
def test_intent_contract_is_wellformed(intent):
    for k in ("work_item_id", "validation_lens", "label_source", "instruments",
              "allow_network", "allow_broker"):
        assert k in intent
    assert intent["allow_network"] is False and intent["allow_broker"] is False
