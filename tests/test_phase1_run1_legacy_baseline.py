"""Phase 1 RUN 1 — legacy baseline + universe census artifact integrity."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOV = ROOT / "docs" / "governance"
DATE = "2026-07-10"

BASELINE = GOV / f"phase1_run1_legacy_baseline_verification-{DATE}.json"
UNIVERSE = GOV / f"phase1_run1_feature_universe_census-{DATE}.json"
IDENTITY = GOV / f"phase1_run1_formula_identity_census-{DATE}.json"
COLLISION = GOV / f"phase1_run1_formula_collision_report-{DATE}.json"
PC = GOV / f"phase1_run1_feature_producer_consumer_graph-{DATE}.json"
COVERAGE = GOV / f"phase1_run1_search_coverage-{DATE}.json"
MANIFEST = GOV / f"phase1_run1_manifest-{DATE}.json"
LEGACY_FP = GOV / "legacy_feature_output_fingerprint_xauusd-2026-07-10.json"
LEGACY_SEM = GOV / "legacy_feature_semantics_v1-2026-07-10.json"


def test_run1_artifacts_exist():
    for p in (BASELINE, UNIVERSE, IDENTITY, COLLISION, PC, COVERAGE, MANIFEST):
        assert p.is_file(), f"missing {p} — run scripts/analysis/phase1_run1_feature_truth.py"


def test_prior_fc_artifacts_preserved():
    # Prior freeze must still exist (append-only; not deleted)
    assert LEGACY_FP.is_file()
    assert LEGACY_SEM.is_file()
    assert (GOV / "feature_contract_v1-2026-07-10.json").is_file()
    assert (GOV / "feature_dependency_graph_fc05-2026-07-10.json").is_file()


def test_legacy_baseline_status_shape():
    b = json.loads(BASELINE.read_text(encoding="utf-8"))
    status = b["LEGACY_BASELINE_STATUS"]
    assert status == "VERIFIED_REPRODUCIBLE" or status.startswith("BLOCKED:")
    assert b["fingerprint_reproducible"] is True or status.startswith("BLOCKED")
    if b["fingerprint_reproducible"]:
        assert b["live_output_fingerprint"]["joint_float32_sha256"] == b[
            "stored_joint_float32_sha256"
        ]
        stored = json.loads(LEGACY_FP.read_text(encoding="utf-8"))
        assert (
            b["live_output_fingerprint"]["joint_float32_sha256"]
            == stored["output"]["joint_float32_sha256"]
        )
    assert b["production_feature_code_modified_by_this_script"] is False
    assert b["prior_fc_artifacts_preserved"] is True
    assert b["corpus_binding"]["sha256"].startswith("4d73f5ce")


def test_universe_has_explicit_unknowns_and_classes():
    u = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    assert u["n_quantities"] > 38
    assert u["FORMULA_COLLISION_EXHAUSTIVENESS_STATUS"] == "UNPROVEN"
    counts = u["counts_by_class"]
    assert "UNIQUE_CANONICAL_CANDIDATE" in counts
    assert "FORMULA_COLLISION" in counts
    assert counts.get("UNKNOWN", 0) >= 1  # explicit unknowns required
    # no silent empty unknown list while class says unknown
    if counts.get("UNKNOWN", 0):
        assert len(u["unknowns_explicit"]) == counts["UNKNOWN"]


def test_collision_exhaustiveness_unproven():
    c = json.loads(COLLISION.read_text(encoding="utf-8"))
    assert c["FORMULA_COLLISION_EXHAUSTIVENESS_STATUS"] == "UNPROVEN"


def test_manifest_run1_complete_or_blocked():
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert m["run"] == 1
    assert m["phases"] == ["1A", "1B"]
    assert m["PHASE1_RUN1_STATUS"] in ("COMPLETE",) or m[
        "PHASE1_RUN1_STATUS"
    ].startswith("BLOCKED:")
    assert m["production_feature_code_changed"] is False
    assert m["model_enablement_changed"] is False
    assert m["model_training_lineage_started"] is False
    assert m["run2_authorized"] is False
    assert m["ECONOMIC_CLAIMS_ALLOWED"] is False
    assert m["DISCOVERED_MATHEMATICAL_QUANTITIES"] > 0


def test_coverage_has_numerators_denominators():
    cov = json.loads(COVERAGE.read_text(encoding="utf-8"))
    assert "directories" in cov
    for name, d in cov["directories"].items():
        assert "numerator_scanned" in d
        assert "denominator_found" in d
        assert d["numerator_scanned"] <= d["denominator_found"]


def test_producer_consumer_graph_counts():
    g = json.loads(PC.read_text(encoding="utf-8"))
    assert g["counts"]["FEATURE_PRODUCING_PATHS_DISCOVERED"] >= 5
    assert g["counts"]["FEATURE_CONSUMING_PATHS_DISCOVERED"] >= 3
    assert g["counts"]["UNRESOLVED_DYNAMIC_PATHS"] >= 1
