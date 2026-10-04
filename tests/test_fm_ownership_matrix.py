"""Floor for permanent FM ownership / consumer matrix + G001 attribution ledger."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_OWN_JSON = _ROOT / "docs" / "governance" / "fm_ownership_consumer_matrix.json"
_G001_JSON = _ROOT / "docs" / "governance" / "g001_consumer_attribution.json"
_OWN_BUILD = _ROOT / "scripts" / "governance" / "build_fm_ownership_matrix.py"
_G001_BUILD = _ROOT / "scripts" / "governance" / "build_g001_consumer_attribution.py"


def test_ownership_matrix_artifact_exists():
    assert _OWN_JSON.is_file(), (
        f"Missing {_OWN_JSON}; run: python scripts/governance/build_fm_ownership_matrix.py"
    )


def test_ownership_matrix_schema_and_invariants():
    doc = json.loads(_OWN_JSON.read_text(encoding="utf-8"))
    assert doc["schema_version"] == 1
    assert "features" in doc and "consumers" in doc
    assert doc["summary"]["feature_count"] == len(doc["features"])
    assert doc["summary"]["feature_count"] >= 40

    from features.registry import load_ontology

    ont = load_ontology()
    expected_ids = set()
    for sec in (
        "primitives",
        "feature_compositions",
        "derived_metrics",
        "rolling_indicators",
        "temporal_context",
        "structural_states",
    ):
        for name, spec in (ont.get(sec) or {}).items():
            expected_ids.add(spec["id"])
    got_ids = {f["fm_id"] for f in doc["features"]}
    assert got_ids == expected_ids, f"matrix missing/extra FMs: {got_ids ^ expected_ids}"

    for f in doc["features"]:
        assert f["economic_authority"] == "NONE", (
            f"{f['fm_id']}: economic_authority must be NONE at feature layer"
        )
        assert f["g001_status"] == "NOT_APPLICABLE_AT_FEATURE_LAYER"
        assert "semantic_status" in f
        assert "computation_authority" in f


def test_ownership_matrix_builder_check_clean():
    r = subprocess.run(
        [sys.executable, str(_OWN_BUILD), "--check"],
        cwd=str(_ROOT),
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_g001_attribution_artifact_exists():
    assert _G001_JSON.is_file(), (
        f"Missing {_G001_JSON}; run: python scripts/governance/build_g001_consumer_attribution.py"
    )


def test_g001_attribution_invariants():
    doc = json.loads(_G001_JSON.read_text(encoding="utf-8"))
    assert doc["schema_version"] == 1
    assert doc["goal_id"] == "G001"
    assert doc["summary"]["consumer_count"] == len(doc["consumers"])
    assert doc["summary"]["economic_positive_delta_count"] == 0
    assert doc["summary"]["ladder_gt0_count"] == 0

    for c in doc["consumers"]:
        assert c["new_authority_from_parity"] is False
        assert c["authority_ladder_level"] == 0
        assert "semantic_status" in c
        assert "economic_status" in c
        assert "consumer_id" in c


def test_g001_builder_check_clean():
    r = subprocess.run(
        [sys.executable, str(_G001_BUILD), "--check"],
        cwd=str(_ROOT),
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_semantic_vs_economic_separation_documented():
    """Parity floors must not be confused with G001 in the ownership matrix purpose."""
    own = json.loads(_OWN_JSON.read_text(encoding="utf-8"))
    assert "G001" in own["purpose"] or "g001" in own["purpose"].lower()
    g001 = json.loads(_G001_JSON.read_text(encoding="utf-8"))
    assert "parity" in " ".join(g001["invariants"]).lower()
