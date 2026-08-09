"""Smoke tests for the read-only feature surface query API."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "feature_surface_query",
    ROOT / "scripts" / "governance" / "feature_surface_query.py",
)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["feature_surface_query"] = _mod
_spec.loader.exec_module(_mod)
FeatureSurfaceIndex = _mod.FeatureSurfaceIndex
main = _mod.main


@pytest.fixture(scope="module")
def idx() -> FeatureSurfaceIndex:
    return FeatureSurfaceIndex.load(ROOT)


def test_loads_39_vector_members(idx: FeatureSurfaceIndex):
    # 39 under schema v4.0 (was 38 under v3.0 before the 2026-07-22 MACD histogram split
    # shifted the tail +1 -- see features/feature_schema.py:47-68).
    vec = idx.list_vector()
    assert len(vec) == 39
    assert idx.meta.get("surface_status") == "CLOSED"


def test_get_by_name_and_feature_id(idx: FeatureSurfaceIndex):
    by_name = idx.get("swing_high")
    assert by_name is not None
    # index 23 under schema v4.0 (was 22 under v3.0; shifted +1 by the MACD split).
    assert by_name["INDEX"] == 23
    assert by_name["PIT_STATUS"]["pit_class_effective"] == "CAUSAL_DELAYED_PUBLICATION"
    assert by_name["CLOSURE_STATUS"]["code_status"] == "CLOSED"
    fid = by_name["FEATURE_ID"]
    by_id = idx.get(fid)
    assert by_id is not None
    assert by_id["NAME"] == "swing_high"


def test_wick_size_aliases_candle_range(idx: FeatureSurfaceIndex):
    row = idx.get("wick_size")
    assert row is not None
    assert "candle_range" in (row.get("ALIASES") or []) or row["FORMULA"].get("ontology_id") == "FM-002"
    assert row["FORMULA"].get("formula_id") in ("FM-002", "FM-range / candle_math.candle_range") or "FM-002" in str(
        row["FORMULA"]
    )


def test_joined_fields_present(idx: FeatureSurfaceIndex):
    row = idx.get("body_ratio")
    assert row is not None
    for k in (
        "FEATURE_ID",
        "FORMULA",
        "OHLCV_INPUTS",
        "ALIASES",
        "PRODUCERS",
        "CONSUMERS",
        "CONFIG_KEYS",
        "ACTIVE_VALUES",
        "OVERRIDE_PATHS",
        "PIT_STATUS",
        "REACHABILITY",
        "TEST_REFERENCE_HITS",
        "CLOSURE_STATUS",
    ):
        assert k in row
    assert "TESTS" not in row, "TESTS was renamed TEST_REFERENCE_HITS (textual hits, not coverage)"


def test_filter_pit(idx: FeatureSurfaceIndex):
    rows = idx.filter(pit="CAUSAL_DELAYED_PUBLICATION")
    names = {r["NAME"] for r in rows}
    assert names == {"swing_high", "swing_low"}


def test_cli_summary_exit_0():
    assert main(["--summary", "--json"]) == 0


def test_cli_unknown_feature():
    assert main(["--feature", "not_a_real_feature_xyz"]) == 1


# ── 2026-07-11 hardening (OHLCFeatureMap correctness review) ─────────────────


def test_consumer_dedup_single_key_domain(idx: FeatureSurfaceIndex):
    """A consumer present in both the binding manifest and the curated lineage list
    must appear exactly once (old bug: tuple keys vs string membership)."""
    for row in idx.list_vector():
        names = [c["consumer"] for c in row["CONSUMERS"]]
        assert len(names) == len(set(names)), (
            f"{row['NAME']}: duplicate consumers {sorted(n for n in names if names.count(n) > 1)}"
        )


def test_consumers_carry_evidence_class(idx: FeatureSurfaceIndex):
    for row in idx.list_vector():
        for c in row["CONSUMERS"]:
            assert c.get("evidence_class") in ("PROVEN", "TEXT_REFERENCE"), c


def test_config_keys_are_heuristic_token_matches(idx: FeatureSurfaceIndex):
    """Config joins are name-based ⇒ HEURISTIC; and 'low'/'high' must not match
    superstring keys like allowed_sessions (token-segment rule)."""
    for row in idx.list_vector():
        for ck in row["CONFIG_KEYS"]:
            assert ck.get("evidence_class") == "HEURISTIC", ck
    low = idx.get("low")
    for ck in low["CONFIG_KEYS"]:
        segs = str(ck.get("key") or "").lower().split("_")
        assert "low" in segs, f"substring trap: {ck}"


def test_formula_metadata_from_primary_identity_only(idx: FeatureSurfaceIndex):
    """Identity-sourced formula fields must come from the SAME identity as FEATURE_ID
    (never identities[0]); the source is labeled."""
    for row in idx.list_vector():
        f = row["FORMULA"]
        assert "identity_metadata_source" in f
        if f["identity_metadata_source"].startswith("ambiguous"):
            assert f.get("formula_version") is None
            assert f.get("implementation_authority") is None


def test_identity_only_rows_first_class_resolvable(idx: FeatureSurfaceIndex):
    """Non-vector identity rows (e.g. centered-batch swings) resolve by canonical name."""
    row = idx.get("swing_high_centered_batch")
    assert row is not None
    assert row["REACHABILITY"]["in_canonical_vector"] is False
    assert row.get("_vector_member") is False


def test_ambiguous_alias_fails_closed(idx: FeatureSurfaceIndex):
    """Synthetic ambiguity must raise AmbiguousAliasError, never silently resolve."""
    import copy
    idx2 = copy.copy(idx)
    idx2.by_alias_ambiguous = {**idx.by_alias_ambiguous, "totally_ambiguous_alias": ["open", "close"]}
    with pytest.raises(_mod.AmbiguousAliasError) as ei:
        idx2.resolve_name("totally_ambiguous_alias")
    assert ei.value.candidates == ["close", "open"]
    # and whatever real ambiguity exists is exposed, not hidden
    assert isinstance(idx.meta.get("ambiguous_aliases"), dict)


def test_freshness_by_embedded_timestamp_not_filename(tmp_path):
    """A decoy artifact with a NEWER filename but OLDER embedded generated_at must lose;
    an empty alternate root must raise FileNotFoundError (never IndexError)."""
    gov = tmp_path / "docs" / "governance"
    gov.mkdir(parents=True)
    old = {"generated_at_utc": "2026-01-01T00:00:00Z", "features": []}
    new = {"generated_at_utc": "2026-07-01T00:00:00Z", "features": []}
    (gov / "feature_38_lineage_census-2099-12-31.json").write_text(json.dumps(old), encoding="utf-8")
    (gov / "feature_38_lineage_census-2026-07-01.json").write_text(json.dumps(new), encoding="utf-8")
    picked, _w = _mod._latest_lineage(gov)
    assert picked.name == "feature_38_lineage_census-2026-07-01.json", "filename date must not win"
    empty = tmp_path / "empty" / "docs" / "governance"
    empty.mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        _mod._latest_lineage(empty)


def test_latest_pointer_wins_when_sha_verifies(tmp_path):
    import hashlib
    root = tmp_path
    gov = root / "docs" / "governance"
    gov.mkdir(parents=True)
    target = gov / "feature_38_lineage_census-2026-07-02.json"
    payload = json.dumps({"generated_at_utc": "2026-07-02T00:00:00Z", "features": []})
    target.write_text(payload, encoding="utf-8")
    # decoy with newer embedded ts — pointer must still win when it verifies
    (gov / "feature_38_lineage_census-2026-07-03.json").write_text(
        json.dumps({"generated_at_utc": "2026-07-03T00:00:00Z", "features": []}), encoding="utf-8")
    (gov / "feature_38_lineage_census.LATEST.json").write_text(json.dumps({
        "path": "docs/governance/feature_38_lineage_census-2026-07-02.json",
        "generated_at": "2026-07-02T00:00:00Z",
        "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
    }), encoding="utf-8")
    picked, warnings = _mod._latest_lineage(gov)
    assert picked == target and not warnings
    # corrupt the sha → pointer rejected, falls back to freshest generated_at
    (gov / "feature_38_lineage_census.LATEST.json").write_text(json.dumps({
        "path": "docs/governance/feature_38_lineage_census-2026-07-02.json",
        "generated_at": "2026-07-02T00:00:00Z",
        "sha256": "deadbeef",
    }), encoding="utf-8")
    picked2, warnings2 = _mod._latest_lineage(gov)
    assert picked2.name == "feature_38_lineage_census-2026-07-03.json"
    assert any("sha_mismatch" in w for w in warnings2)


def test_disp_strength_row_single_canonical_identity(idx: FeatureSurfaceIndex):
    """The lineage row carries exactly ONE canonical formula id (FM-020); FM-028/FM-029
    are related identities, never blended into the formula."""
    row = idx.get("disp_strength")
    assert row["FORMULA"]["formula_id"] == "FM-020"
    assert "FM-028" not in str(row["FORMULA"]["formula_id"])


def test_meta_exposes_staleness_and_collisions(idx: FeatureSurfaceIndex):
    for k in ("stale_artifacts", "artifact_warnings", "ambiguous_aliases",
              "alias_name_shadowing", "ontology_alias_collisions"):
        assert k in idx.meta, k
    assert idx.meta["stale_artifacts"] == [], (
        f"loaded artifacts are stale vs live schema: {idx.meta['stale_artifacts']}"
    )
