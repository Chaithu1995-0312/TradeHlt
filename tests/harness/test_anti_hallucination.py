"""Anti-hallucination pack AH-01..AH-05 (ERP testing-plan §6) — pure CI, no network.

Directly targets H1 (invented result) and H2 (misread result): a summary cannot silently disagree
with the manifest, an economic claim cannot be made without a manifest, and a failed/empty run can
never be reported as success.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.run_manifest import REQUIRED_FIELDS, read_run
from utils.validation_contract import (
    MissingManifestError,
    SummaryManifestMismatch,
    assert_summary_matches_manifest,
    classify_run_status,
    require_manifest,
)

_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.contract
def test_ah01_wrong_summary_fails(valid_manifest):
    # a fabricated summary with the wrong instrument must be rejected (H2)
    bad = {"instruments": ["BTCUSDT"], "validation_lens": "synthetic_story_golden"}
    with pytest.raises(SummaryManifestMismatch):
        assert_summary_matches_manifest(bad, valid_manifest)
    # the matching summary passes
    good = {"instruments": ["SYNTHUSDT"], "validation_lens": "synthetic_story_golden",
            "cost_model_bps": 0, "label_source": "forward_walk_intrabar_fixed",
            "exit_model": "intrabar_fixed"}
    assert_summary_matches_manifest(good, valid_manifest)  # no raise


@pytest.mark.contract
def test_ah02_missing_manifest_raises(tmp_path):
    with pytest.raises(MissingManifestError):
        require_manifest(tmp_path)  # no run_manifest.json present


@pytest.mark.unit
def test_ah03_empty_or_failed_run_never_success():
    assert classify_run_status("", 0) == "ERROR"            # empty stdout
    assert classify_run_status("   \n", 0) == "ERROR"       # whitespace-only
    assert classify_run_status("ok", 1) == "ERROR"          # non-zero exit
    assert classify_run_status("ok", 0, timed_out=True) == "ERROR"  # timeout
    assert classify_run_status("real output", 0) == "OK"    # only real success is OK


@pytest.mark.contract
def test_ah04_program_json_metrics_carry_artifact_pointers():
    # A metric block in the program tracker must ship with artifact/path provenance (doc-scan H1).
    prog = json.loads((_ROOT / "docs" / "research-readiness"
                       / "edge-research-platform-program.json").read_text(encoding="utf-8"))
    sl = prog.get("story_library")
    assert sl is not None, "story_library block missing"
    # numeric claims present -> provenance pointers must also be present
    assert "n_stories" in sl and "library_all_pass" in sl
    assert sl.get("data_dir") and sl.get("driver") and sl.get("tests"), \
        "story_library metrics lack artifact/path provenance"


@pytest.mark.contract
def test_ah05_real_producer_golden():
    # AH-05: a REAL producer (the story-library driver) emits a manifest with every required field
    # and a verifying content hash — invoked as the actual CLI (H1: real invocation, not a fixture).
    import subprocess
    import sys

    out_dir = _ROOT / "data" / "synthetic" / "stories"
    proc = subprocess.run([sys.executable, "scripts/research/story_library_build.py"],
                          cwd=_ROOT, capture_output=True, text=True, timeout=180)
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert "LIBRARY_ALL_PASS=PASS" in proc.stdout
    run = read_run(out_dir)
    assert set(REQUIRED_FIELDS) <= set(run["manifest"]), \
        set(REQUIRED_FIELDS) - set(run["manifest"])
    assert run["hash_ok"] is True
    assert run["manifest"]["validation_flow_review"] == "UNTRUSTED_RAW"
    assert run["manifest"]["intended_work_item_id"] == "WI-002"
