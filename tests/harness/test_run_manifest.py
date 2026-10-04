"""Floor for the run_manifest provenance helper (ERP testing-plan §3.3)."""
from __future__ import annotations

import json

import pytest

from utils.run_manifest import (
    REQUIRED_FIELDS,
    ManifestFieldError,
    build_manifest,
    read_run,
    run_sha256,
    write_run,
)


@pytest.mark.unit
def test_build_manifest_populates_all_required_fields(valid_manifest):
    for field in REQUIRED_FIELDS:
        assert field in valid_manifest and valid_manifest[field] is not None, field
    # auto-filled provenance
    assert valid_manifest["run_id"]
    assert valid_manifest["timestamp_utc"].endswith("+00:00")
    assert valid_manifest["validation_flow_review"] == "UNTRUSTED_RAW"


@pytest.mark.unit
def test_build_manifest_fail_closed_on_missing_field():
    # omit a caller-required field -> anti-H1 raise, never a silent default
    with pytest.raises(ManifestFieldError):
        build_manifest(command="x", argv=["x"], validation_lens="l", exit_model="e",
                       cost_model_bps=0, label_source="s", instruments=["I"],
                       timeframe="M15", data_source="d")  # missing intended_work_item_id


@pytest.mark.contract
def test_write_read_roundtrip_and_hash_ok(tmp_path, valid_manifest, valid_assertions):
    written = write_run(tmp_path, valid_manifest, valid_assertions)
    assert written["sha256"] == run_sha256(valid_manifest, valid_assertions)
    back = read_run(tmp_path)
    assert back["manifest"] == valid_manifest
    assert back["assertions"] == valid_assertions
    assert back["hash_ok"] is True


@pytest.mark.contract
def test_tampered_assertions_break_hash(tmp_path, valid_manifest, valid_assertions):
    write_run(tmp_path, valid_manifest, valid_assertions)
    # tamper the assertions file after the fact -> hash must no longer verify
    apath = tmp_path / "assertions.json"
    doctored = json.loads(apath.read_text(encoding="utf-8"))
    doctored["library_all_pass"] = True
    doctored["n_stories"] = 999
    apath.write_text(json.dumps(doctored), encoding="utf-8")
    assert read_run(tmp_path)["hash_ok"] is False


@pytest.mark.unit
def test_read_run_missing_manifest_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_run(tmp_path)
