"""FC-0 FeatureContract v1 + legacy fingerprint integrity."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "docs" / "governance" / "feature_contract.schema.json"
CONTRACT = ROOT / "docs" / "governance" / "feature_contract_v1-2026-07-10.json"
LEGACY = ROOT / "docs" / "governance" / "legacy_feature_semantics_v1-2026-07-10.json"
FINGERPRINT = ROOT / "docs" / "governance" / "legacy_feature_output_fingerprint_xauusd-2026-07-10.json"
MANIFEST = ROOT / "docs" / "governance" / "feature_pipeline_closure_manifest-2026-07-10.json"

LEGAL_STATUS = {
    "UNADJUDICATED",
    "PROVEN_CORRECT",
    "PROVEN_PIT_SAFE",
    "PROVEN_DELAYED_SAFE",
    "SEMANTICALLY_DIVERGENT",
    "FORMULA_AUTHORITY_AMBIGUOUS",
    "LEAKING",
    "BLOCKED",
    "DEPRECATED_NAME_ONLY",
}
PROVEN = {"PROVEN_CORRECT", "PROVEN_PIT_SAFE", "PROVEN_DELAYED_SAFE"}


def test_fc0_artifacts_exist():
    for p in (SCHEMA, CONTRACT, LEGACY, FINGERPRINT, MANIFEST):
        assert p.is_file(), f"missing {p}"


def test_manifest_fc0_frozen():
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert m["phase"] == "FC-0"
    assert m["status"] == "EVIDENCE_AND_CONTRACT_FROZEN"
    assert m["production_remediation_started"] is False
    assert m["economic_claims_allowed"] is False
    assert m.get("FEATURE_PIPELINE_FC0_STATUS") == "EVIDENCE_AND_CONTRACT_FROZEN"


def test_legacy_freeze_not_authoritative():
    leg = json.loads(LEGACY.read_text(encoding="utf-8"))
    assert leg["freeze_id"] == "LEGACY_FEATURE_SEMANTICS_V1"
    for ban in ("VALIDATED", "APPROVED", "AUTHORITATIVE", "ECONOMICALLY_ADMISSIBLE"):
        assert ban in leg["explicitly_not"]
    assert "ordered_features" in leg
    assert len(leg["ordered_features"]) == 38


def test_fingerprint_shape():
    fp = json.loads(FINGERPRINT.read_text(encoding="utf-8"))
    out = fp["output"]
    assert out["n_features"] == 38
    assert out["rows_after_finalize"] > 0
    assert len(out["joint_float32_sha256"]) == 64
    assert len(out["per_column_float32_sha256"]) == 38
    assert out["feature_order"] == leg_order()


def leg_order():
    return json.loads(LEGACY.read_text(encoding="utf-8"))["ordered_features"]


def test_contract_schema_and_unique_ids():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert schema["properties"]["contract_id"]["const"] == "FEATURE-CONTRACT-V1"
    c = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert c["contract_id"] == "FEATURE-CONTRACT-V1"
    assert c["schema_version"] == "1.0.0"
    assert c["production_remediation_started"] is False
    assert c["economic_claims_allowed"] is False
    assert c["corpus_binding"]["sha256"].startswith("4d73f5ce")

    feats = c["features"]
    assert len(feats) >= 38
    fids = [f["feature_id"] for f in feats]
    assert len(fids) == len(set(fids)), "duplicate feature_id"
    names = [f["feature_name"] for f in feats]
    assert len(names) == len(set(names)), "duplicate feature_name"

    for f in feats:
        assert f["status"] in LEGAL_STATUS
        if f["status"] in PROVEN:
            assert f.get("evidence"), f"{f['feature_id']} PROVEN without evidence"

    # vector order contiguous 0..n-1 for vector members
    vec = [f for f in feats if f.get("is_vector_member")]
    orders = sorted(f["output_order"] for f in vec)
    assert orders == list(range(len(orders)))
    assert len(c["vector_members"]) == len(vec)

    # dependency referential integrity (feature_ids or empty)
    idset = set(fids)
    for f in feats:
        for dep in f.get("direct_feature_dependencies") or []:
            if dep.startswith("FEAT-"):
                assert dep in idset, f"dangling dep {dep} from {f['feature_id']}"


def test_separations_present():
    c = json.loads(CONTRACT.read_text(encoding="utf-8"))
    seps = {s["id"] for s in c["explicit_separations"]}
    assert "SEP-A-SWING-CAUSAL" in seps
    assert "SEP-B-VOLUME" in seps
    assert "SEP-C-FM" in seps
    assert "SEP-D-VOLREGIME" in seps
    # separation feature rows exist
    fids = {f["feature_id"] for f in c["features"]}
    assert "FEAT-VOLUME_RANGE_PROXY" in fids
    assert "FEAT-DISPLACEMENT_RETRACE" in fids
    assert "FEAT-DISPLACEMENT_ATR_RATIO" in fids


def test_change_contracts_drafted():
    d = ROOT / "docs" / "governance" / "feature_pipeline_change_contracts"
    for name in (
        "FC1-A-SWING-CAUSAL.json",
        "FC1-B-VOLUME-SEMANTIC-SPLIT.json",
        "FC1-C-FM-IDENTITY-SEPARATION.json",
        "FC1-D-VOLREGIME-CAUSAL.json",
    ):
        p = d / name
        assert p.is_file()
        obj = json.loads(p.read_text(encoding="utf-8"))
        assert obj["status"] == "DRAFTED_FC0_NOT_IMPLEMENTED"
        assert obj["phase"] == "FC-1"
