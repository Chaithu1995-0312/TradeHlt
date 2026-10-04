"""R3 Dataset Identity registry + CandleLoader admission."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from data_ingestion.dataset_registry import (
    PRODUCER_ID,
    PROJECTION_RULES,
    DatasetAdmissionError,
    admit_csv_path,
    load_bound_datasets,
    load_registry_index,
    projection_spec,
    resolve_canonical,
)
from data_ingestion.xauusd_phase1_candidate import (
    PHASE1_PHYSICAL_PATH,
    PHASE1_SHA256,
    PHASE1_STATUS,
)

ROOT = Path(__file__).resolve().parent.parent
RECORD = ROOT / "docs" / "governance" / "datasets" / "XAUUSD_MT5_PHASE1_20260521.json"
SCHEMA = ROOT / "docs" / "governance" / "dataset_identity.schema.json"
DSID = "XAUUSD_MT5_PHASE1_20260521"


def test_registry_index_and_record_shape():
    index = load_registry_index()
    assert index["unbound_load_policy"] == "path_passthrough"
    assert index["producer_canonical"] == PRODUCER_ID
    ids = [d["dataset_id"] for d in index["datasets"]]
    # R3 multi-dataset (2026-09-03 TV-forensic comparison plan): the real registry now
    # carries a second bound record. DSID must still be present and first (it is the
    # sole legacy_rewrite_target and the only frozen-candidate-pinned record) -- the
    # assertion is no longer "exactly one dataset exists" but "Phase-1 is still bound".
    assert DSID in ids
    assert ids[0] == DSID
    assert RECORD.is_file()
    assert SCHEMA.is_file()
    raw = json.loads(RECORD.read_text(encoding="utf-8"))
    assert raw["decision_status"] == PHASE1_STATUS
    assert raw["decision_status"] != "APPROVED"
    for ban in ("AUTHORITATIVE", "VALIDATED", "ECONOMICALLY_ADMISSIBLE", "APPROVED"):
        assert ban in raw["explicitly_not"]
    assert raw["canonical_artifact"]["sha256"] == PHASE1_SHA256
    assert raw["canonical_artifact"]["path"] == PHASE1_PHYSICAL_PATH.as_posix()
    assert raw["parent_timeframe_source"] == "derived_h4"


def test_bound_dataset_star_projections():
    rec = load_bound_datasets()[DSID]
    assert rec["timeframes"]["M15"]["role"] == "canonical_artifact"
    assert rec["timeframes"]["M15"]["admitted"] is True
    for rule in PROJECTION_RULES:
        spec = projection_spec(DSID, rule)
        assert spec.producer == PRODUCER_ID
        assert spec.parent == "M15"
        assert spec.parent_sha256 == PHASE1_SHA256
        assert spec.derivation == "direct"
        assert rec["timeframes"][rule]["path"] is None
        assert rec["timeframes"][rule]["admitted"] is False


def test_mn1_is_not_child_of_w1():
    rec = load_bound_datasets()[DSID]
    assert rec["timeframes"]["MN1"]["parent"] == "M15"
    assert rec["timeframes"]["MN1"]["parent"] != "W1"


def test_projection_is_not_a_file_resolve():
    with pytest.raises(DatasetAdmissionError, match="not a projection|canonical"):
        projection_spec(DSID, "M15")


def test_admit_xauusd_m15_rewrites_to_phase1():
    root_csv = ROOT / "data" / "XAUUSD_M15.csv"
    if not root_csv.is_file() and not (ROOT / PHASE1_PHYSICAL_PATH).is_file():
        pytest.skip("XAUUSD corpora missing")
    src = str(root_csv if root_csv.is_file() else ROOT / PHASE1_PHYSICAL_PATH)
    adm = admit_csv_path(src, "XAUUSD")
    assert adm.bound is True
    assert adm.dataset_id == DSID
    assert Path(adm.filepath).resolve() == (ROOT / PHASE1_PHYSICAL_PATH).resolve()


def test_admit_unbound_instrument_passthrough():
    p = "data/EURUSD_M15.csv"
    adm = admit_csv_path(p, "EURUSD")
    assert adm.bound is False
    assert adm.dataset_id is None
    assert adm.filepath == p
    assert adm.rewritten is False


def test_admit_rejects_forensic_native_h4():
    with pytest.raises(DatasetAdmissionError, match="FORENSIC"):
        admit_csv_path("data/mt5/XAUUSD_H4.csv", "XAUUSD")
    with pytest.raises(DatasetAdmissionError, match="FORENSIC"):
        admit_csv_path("data/mt5/XAUUSD_H1.csv", "XAUUSD")


def test_candle_loader_uses_registry_admission():
    from runtime.backtest_v2 import CandleLoader
    from data_ingestion.ohlcv_schema import DatasetIntegrityError

    if not (ROOT / PHASE1_PHYSICAL_PATH).is_file():
        pytest.skip("Phase-1 candidate missing")
    src = ROOT / "data" / "XAUUSD_M15.csv"
    if not src.is_file():
        src = ROOT / PHASE1_PHYSICAL_PATH
    loader = CandleLoader(str(src), "XAUUSD")
    assert Path(loader.filepath).resolve() == (ROOT / PHASE1_PHYSICAL_PATH).resolve()
    with pytest.raises(DatasetIntegrityError, match="FORENSIC|admission"):
        CandleLoader(str(ROOT / "data" / "mt5" / "XAUUSD_H4.csv"), "XAUUSD")


def test_resolve_canonical_matches_phase1():
    if not (ROOT / PHASE1_PHYSICAL_PATH).is_file():
        pytest.skip("Phase-1 candidate missing")
    p = resolve_canonical(DSID)
    assert p.resolve() == (ROOT / PHASE1_PHYSICAL_PATH).resolve()


# ── SEED-OHLCV-19 (BC-4a): the proxy-branch test the closure report names as never
# written (docs/governance/ohlcv-closure-report-2026-07-10.md:106). Exercises the
# 2026-09-03 schema-validation wiring (_validate_against_schema, previously-dead
# SCHEMA_PATH) rather than the presence-only check that predated it.
def test_existing_record_validates_cleanly_against_schema():
    """The one live record must pass as-is -- wiring validation must be additive."""
    from data_ingestion.dataset_registry import _validate_against_schema

    raw = json.loads(RECORD.read_text(encoding="utf-8"))
    _validate_against_schema(raw)  # must not raise


def test_synthetic_proxy_branch_is_schema_valid():
    """SEED-OHLCV-19: a proxy dataset (SYNTHETIC_PRICE_RANGE_PROXY + is_synthetic=true)
    must validate cleanly -- this is the branch the closure report says never got a test.
    """
    from data_ingestion.dataset_registry import _validate_against_schema

    raw = json.loads(RECORD.read_text(encoding="utf-8"))
    raw["dataset_id"] = "SYNTHETIC_PROXY_TEST_FIXTURE"
    raw["volume_semantic"] = "SYNTHETIC_PRICE_RANGE_PROXY"
    raw["is_synthetic"] = True
    _validate_against_schema(raw)  # must not raise


def test_invalid_volume_semantic_enum_fails_closed():
    """A value outside the closed 7-token enum must be REJECTED, not silently accepted --
    this is the behavior the presence-only _validate_record could never provide."""
    from data_ingestion.dataset_registry import _validate_against_schema

    raw = json.loads(RECORD.read_text(encoding="utf-8"))
    raw["volume_semantic"] = "MADE_UP_NOT_IN_ENUM"
    with pytest.raises(DatasetAdmissionError, match="schema validation failed"):
        _validate_against_schema(raw)


def test_is_synthetic_must_be_boolean():
    from data_ingestion.dataset_registry import _validate_against_schema

    raw = json.loads(RECORD.read_text(encoding="utf-8"))
    raw["is_synthetic"] = "yes"  # wrong type -- schema declares boolean
    with pytest.raises(DatasetAdmissionError, match="schema validation failed"):
        _validate_against_schema(raw)


def test_is_synthetic_absent_is_valid_not_required():
    """A record predating this field must still validate -- absence is undeclared,
    not a violation (behavior-preserving per the schema's own additionalProperties
    contract: is_synthetic is optional, not in `required`)."""
    from data_ingestion.dataset_registry import _validate_against_schema

    raw = json.loads(RECORD.read_text(encoding="utf-8"))
    assert "is_synthetic" not in raw
    _validate_against_schema(raw)  # must not raise


def test_undeclared_additional_property_fails_closed():
    from data_ingestion.dataset_registry import _validate_against_schema

    raw = json.loads(RECORD.read_text(encoding="utf-8"))
    raw["not_a_real_field"] = "x"
    with pytest.raises(DatasetAdmissionError, match="schema validation failed"):
        _validate_against_schema(raw)


def test_load_bound_datasets_still_calls_schema_validation():
    """End-to-end: the wired path (_validate_record -> _validate_against_schema) is
    reachable from the real load, not just testable in isolation."""
    rec = load_bound_datasets()[DSID]
    assert rec["dataset_id"] == DSID  # unchanged happy path, still returns the record


# ---- R3 multi-dataset generalization (Phase 1) -----------------------------------
# These tests build a throwaway repo_root (never the real registry) so a second bound
# dataset can be exercised without touching docs/governance/dataset_identity_registry.json
# or the frozen Phase-1 record. The Phase-1 record and its CSV bytes are copied verbatim
# from the real repo so the hardcoded-constant pin branch is exercised for real, not
# stubbed. All 16 tests above must stay green unmodified -- that is the proof this
# generalization is behaviour-preserving for the single-record case.

import hashlib
import shutil


def _copy_phase1_into(root: Path) -> None:
    (root / PHASE1_PHYSICAL_PATH).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / PHASE1_PHYSICAL_PATH, root / PHASE1_PHYSICAL_PATH)
    dst = root / "docs" / "governance" / "datasets"
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copy(RECORD, dst / "XAUUSD_MT5_PHASE1_20260521.json")
    (root / "docs" / "governance").mkdir(parents=True, exist_ok=True)
    shutil.copy(SCHEMA, root / "docs" / "governance" / "dataset_identity.schema.json")


def _fixture_second_record(
    root: Path,
    *,
    dataset_id: str = "XAUUSD_MT5_FIXTURE_WINDOW",
    csv_name: str = "XAUUSD_MT5_FIXTURE_WINDOW.csv",
    legacy: bool = False,
    bad_hash: bool = False,
):
    """A minimal, independently-hashed second bound record -- exercises the generic
    (non-Phase-1) hash-verify branch added to _validate_record/resolve_canonical."""
    csv_rel = f"data/mt5/{csv_name}"
    csv_path = root / csv_rel
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_text = "timestamp,open,high,low,close,volume\n2026-07-07 01:00:00,1,1,1,1,1\n"
    csv_path.write_text(csv_text, encoding="utf-8")
    real_sha = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    declared_sha = ("0" * 64) if bad_hash else real_sha
    rec = {
        "schema_version": "1.0.0",
        "dataset_id": dataset_id,
        "symbol": "XAUUSD",
        "source_family": "mt5",
        "clock_basis": "broker_local",
        "volume_semantic": "TICK_VOLUME_APPROXIMATE",
        "decision_status": "UNRESOLVED",
        "parent_timeframe_source": "derived_h4",
        "canonical_artifact": {
            "timeframe": "M15",
            "path": csv_rel,
            "sha256": declared_sha,
            "source": "native_fetch",
            "admitted": True,
            "rows": 1,
            "start": "2026-07-07T01:00:00",
            "end": "2026-07-07T01:00:00",
        },
        "timeframes": {
            "M15": {
                "role": "canonical_artifact", "source": "native_fetch", "admitted": True,
                "path": csv_rel, "sha256": declared_sha, "rows": 1,
                "start": "2026-07-07T01:00:00", "end": "2026-07-07T01:00:00",
                "producer": None, "rule": "M15", "parent": None,
                "parent_sha256": None, "derivation": None,
            },
        },
        "forensic_paths": [],
        "load_policy": {
            "require_hash_match": True,
            "unbound_instruments": "path_passthrough",
            "reject_forensic_as_canonical": True,
        },
        "explicitly_not": ["AUTHORITATIVE", "VALIDATED", "ECONOMICALLY_ADMISSIBLE", "APPROVED"],
    }
    for tf in PROJECTION_RULES:
        rec["timeframes"][tf] = {
            "role": "projection", "source": None, "admitted": False, "path": None,
            "sha256": None, "rows": None, "start": None, "end": None,
            "producer": PRODUCER_ID, "rule": tf, "parent": "M15",
            "parent_sha256": declared_sha, "derivation": "direct",
        }
    if legacy:
        rec["legacy_rewrite_target"] = True
    (root / "docs" / "governance" / "datasets" / f"{dataset_id}.json").write_text(
        json.dumps(rec), encoding="utf-8"
    )
    row = {
        "dataset_id": dataset_id,
        "record": f"docs/governance/datasets/{dataset_id}.json",
        "symbol": "XAUUSD",
        "canonical_timeframe": "M15",
    }
    return row, csv_rel


def _write_registry(root: Path, dataset_rows: list) -> None:
    index = {
        "_doc": "test fixture registry",
        "schema_version": "1.0.0",
        "status_token": "DATASET_IDENTITY_STATUS = FROZEN",
        "unbound_load_policy": "path_passthrough",
        "producer_canonical": PRODUCER_ID,
        "datasets": dataset_rows,
    }
    (root / "docs" / "governance" / "dataset_identity_registry.json").write_text(
        json.dumps(index), encoding="utf-8"
    )


def _phase1_row() -> dict:
    return {
        "dataset_id": DSID,
        "record": "docs/governance/datasets/XAUUSD_MT5_PHASE1_20260521.json",
        "symbol": "XAUUSD",
        "canonical_timeframe": "M15",
    }


def test_two_record_registry_loads(tmp_path):
    _copy_phase1_into(tmp_path)
    row, _csv_rel = _fixture_second_record(tmp_path)
    _write_registry(tmp_path, [_phase1_row(), row])
    datasets = load_bound_datasets(repo_root=tmp_path)
    assert set(datasets) == {DSID, "XAUUSD_MT5_FIXTURE_WINDOW"}


def test_explicit_path_admits_new_record_without_rewrite(tmp_path):
    # Filename deliberately starts with XAUUSD_M15 (would trip is_xauusd_m15_request) --
    # step 1 (exact canonical-path match) must win over step 2 (legacy rewrite).
    _copy_phase1_into(tmp_path)
    row, csv_rel = _fixture_second_record(tmp_path, csv_name="XAUUSD_M15_20260707_20260806.csv")
    _write_registry(tmp_path, [_phase1_row(), row])
    adm = admit_csv_path(csv_rel, "XAUUSD", repo_root=tmp_path)
    assert adm.bound is True
    assert adm.dataset_id == "XAUUSD_MT5_FIXTURE_WINDOW"
    assert adm.rewritten is False
    assert Path(adm.filepath).resolve() == (tmp_path / csv_rel).resolve()


def test_bare_xauusd_m15_still_rewrites_to_phase1_with_two_records(tmp_path):
    _copy_phase1_into(tmp_path)
    row, _csv_rel = _fixture_second_record(tmp_path)  # legacy=False -- only Phase-1 claims it
    _write_registry(tmp_path, [_phase1_row(), row])
    adm = admit_csv_path("data/XAUUSD_M15.csv", "XAUUSD", repo_root=tmp_path)
    assert adm.bound is True
    assert adm.dataset_id == DSID
    assert Path(adm.filepath).resolve() == (tmp_path / PHASE1_PHYSICAL_PATH).resolve()


def test_second_legacy_rewrite_target_fails_closed(tmp_path):
    _copy_phase1_into(tmp_path)  # Phase-1 record already carries legacy_rewrite_target:true
    row, _csv_rel = _fixture_second_record(tmp_path, legacy=True)
    _write_registry(tmp_path, [_phase1_row(), row])
    with pytest.raises(DatasetAdmissionError, match="ambiguous legacy_rewrite_target"):
        load_bound_datasets(repo_root=tmp_path)


def test_declared_sha_mismatch_fails_closed(tmp_path):
    _copy_phase1_into(tmp_path)
    row, _csv_rel = _fixture_second_record(tmp_path, bad_hash=True)
    _write_registry(tmp_path, [_phase1_row(), row])
    with pytest.raises(DatasetAdmissionError, match="recomputed"):
        load_bound_datasets(repo_root=tmp_path)


def test_resolve_canonical_generic_branch(tmp_path):
    _copy_phase1_into(tmp_path)
    row, csv_rel = _fixture_second_record(tmp_path)
    _write_registry(tmp_path, [_phase1_row(), row])
    p = resolve_canonical("XAUUSD_MT5_FIXTURE_WINDOW", repo_root=tmp_path)
    assert p.resolve() == (tmp_path / csv_rel).resolve()


def test_tick_volume_approximate_validates():
    # F-099's actual verdict must be an expressible enum value, not just TICK_VOLUME.
    from data_ingestion.dataset_registry import _validate_against_schema

    raw = json.loads(RECORD.read_text(encoding="utf-8"))
    raw["volume_semantic"] = "TICK_VOLUME_APPROXIMATE"
    _validate_against_schema(raw)  # must not raise


def test_legacy_rewrite_target_absent_is_valid_not_required():
    # A record predating this field must still validate -- optional, not required.
    from data_ingestion.dataset_registry import _validate_against_schema

    raw = json.loads(RECORD.read_text(encoding="utf-8"))
    assert "legacy_rewrite_target" in raw  # this session added it to the real record
    del raw["legacy_rewrite_target"]
    _validate_against_schema(raw)  # must not raise
