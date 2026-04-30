"""
test_train_pipeline.py
======================
Tests for GAP-017: dataset validation gate in run_training_pipeline().

Covers:
  - validate_training_dataset passes on clean data
  - validate_training_dataset raises below MIN_RECORDS_TO_TRAIN
  - validate_training_dataset skips records with missing keys
  - validate_training_dataset skips records with bad feature vectors
  - validate_training_dataset skips records with invalid labels
  - run_training_pipeline aborts on under-threshold dataset
  - run_training_pipeline surfaces validation_report in results
"""

import json
import os
import tempfile
import pytest

from training.train_pipeline import (
    validate_training_dataset,
    run_training_pipeline,
)
from features.dataset_validator import MIN_RECORDS_TO_TRAIN, MIN_RECORDS_RECOMMEND
from features.feature_schema import CANONICAL_FEATURE_ORDER


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_valid_features() -> dict:
    """Minimal feature dict accepted by extract_feature_vector()."""
    return {k: 0.5 for k in CANONICAL_FEATURE_ORDER}


def _make_valid_record(label: int = 1) -> dict:
    return {"features": _make_valid_features(), "label": label}


def _make_records(n: int, label: int = 1) -> list:
    return [_make_valid_record(label) for _ in range(n)]


# ---------------------------------------------------------------------------
# validate_training_dataset — pass path
# ---------------------------------------------------------------------------

def test_validate_passes_on_sufficient_clean_data():
    """GAP-017: clean dataset above threshold must pass without raising."""
    records = _make_records(MIN_RECORDS_TO_TRAIN + 10)
    valid, report = validate_training_dataset(records)
    assert report["valid"] == MIN_RECORDS_TO_TRAIN + 10
    assert report["skipped_bad_record"] == 0
    assert report["skipped_bad_features"] == 0
    assert len(valid) == report["valid"]


# ---------------------------------------------------------------------------
# validate_training_dataset — block path
# ---------------------------------------------------------------------------

def test_validate_raises_below_minimum():
    """GAP-017: dataset below MIN_RECORDS_TO_TRAIN must raise ValueError."""
    records = _make_records(MIN_RECORDS_TO_TRAIN - 1)
    with pytest.raises(ValueError, match="Dataset validation failed"):
        validate_training_dataset(records)


def test_validate_raises_on_empty_dataset():
    """GAP-017: empty dataset must raise ValueError."""
    with pytest.raises(ValueError, match="Dataset validation failed"):
        validate_training_dataset([])


# ---------------------------------------------------------------------------
# validate_training_dataset — per-record rejection
# ---------------------------------------------------------------------------

def test_validate_skips_record_missing_features_key():
    """GAP-017: records without 'features' key must be counted and skipped."""
    records = _make_records(MIN_RECORDS_TO_TRAIN + 5)
    records[0] = {"label": 1}   # no 'features'
    valid, report = validate_training_dataset(records)
    assert report["skipped_bad_record"] == 1
    assert report["valid"] == MIN_RECORDS_TO_TRAIN + 4


def test_validate_skips_record_missing_label_key():
    """GAP-017: records without 'label' key must be skipped."""
    records = _make_records(MIN_RECORDS_TO_TRAIN + 5)
    records[1] = {"features": _make_valid_features()}   # no 'label'
    valid, report = validate_training_dataset(records)
    assert report["skipped_bad_record"] == 1


def test_validate_skips_record_invalid_label():
    """GAP-017: records with label not in {0, 1} must be skipped."""
    records = _make_records(MIN_RECORDS_TO_TRAIN + 5)
    records[2] = {"features": _make_valid_features(), "label": 99}
    valid, report = validate_training_dataset(records)
    assert report["skipped_bad_record"] == 1


def test_validate_skips_record_bad_feature_vector():
    """GAP-017: records with missing canonical features must be counted."""
    records = _make_records(MIN_RECORDS_TO_TRAIN + 5)
    records[3] = {"features": {"open": 1.0}, "label": 0}   # incomplete features
    valid, report = validate_training_dataset(records)
    assert report["skipped_bad_features"] == 1
    assert report["valid"] == MIN_RECORDS_TO_TRAIN + 4


def test_validate_warns_below_recommend_threshold():
    """GAP-017: dataset between MIN_TO_TRAIN and MIN_RECOMMEND must warn."""
    records = _make_records(MIN_RECORDS_TO_TRAIN)
    valid, report = validate_training_dataset(records)
    if MIN_RECORDS_TO_TRAIN < MIN_RECORDS_RECOMMEND:
        assert any("recommend" in w.lower() for w in report["warnings"]), (
            "Expected a 'recommend' warning for dataset below recommended size"
        )


# ---------------------------------------------------------------------------
# run_training_pipeline integration
# ---------------------------------------------------------------------------

def _dummy_model_fn(X, y):
    return {"accuracy": 1.0, "n_samples": len(X)}


def test_run_training_pipeline_includes_validation_report():
    """GAP-017: run_training_pipeline must include dataset_validation in results."""
    records = _make_records(MIN_RECORDS_TO_TRAIN + 5)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as f:
        json.dump(records, f)
        data_path = f.name

    try:
        results = run_training_pipeline(data_path, _dummy_model_fn)
        assert "dataset_validation" in results, (
            "run_training_pipeline must include 'dataset_validation' in results"
        )
        assert results["dataset_validation"]["valid"] > 0
    finally:
        os.unlink(data_path)


def test_run_training_pipeline_aborts_on_insufficient_data():
    """GAP-017: run_training_pipeline must raise ValueError on tiny dataset."""
    records = _make_records(MIN_RECORDS_TO_TRAIN - 1)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as f:
        json.dump(records, f)
        data_path = f.name

    try:
        with pytest.raises(ValueError, match="Dataset validation failed"):
            run_training_pipeline(data_path, _dummy_model_fn)
    finally:
        os.unlink(data_path)


# ---------------------------------------------------------------------------
# GAP-022: Phase5Calibration Gate Tests
# ---------------------------------------------------------------------------

def test_pipeline_with_approved_calibration():
    """GAP-022: Pipeline passes when calibration_fn returns integration_approved=True."""
    records = _make_records(MIN_RECORDS_TO_TRAIN + 5)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(records, f)
        data_path = f.name

    def approved_calibration_fn(X, y):
        return {
            "integration_approved": True,
            "verdict": "PASSED: corr=+0.123 stable=True",
            "corr": 0.123
        }

    try:
        results = run_training_pipeline(data_path, _dummy_model_fn, calibration_fn=approved_calibration_fn)
        assert "calibration" in results
        assert results["calibration"]["integration_approved"] is True
        assert "verdict" in results["calibration"]
    finally:
        os.unlink(data_path)


def test_pipeline_raises_on_rejected_calibration():
    """GAP-022: Pipeline aborts with RuntimeError when calibration is rejected."""
    records = _make_records(MIN_RECORDS_TO_TRAIN + 5)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(records, f)
        data_path = f.name

    def rejected_calibration_fn(X, y):
        return {
            "integration_approved": False,
            "verdict": "REJECTED: corr=-0.041 unstable",
            "corr": -0.041
        }

    try:
        with pytest.raises(RuntimeError, match="Phase5Calibration gate FAILED"):
            run_training_pipeline(data_path, _dummy_model_fn, calibration_fn=rejected_calibration_fn)
    finally:
        os.unlink(data_path)


def test_pipeline_calibration_fn_none_unchanged():
    """GAP-022: No calibration key when calibration_fn=None (backward compatible)."""
    records = _make_records(MIN_RECORDS_TO_TRAIN + 5)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(records, f)
        data_path = f.name

    try:
        results = run_training_pipeline(data_path, _dummy_model_fn, calibration_fn=None)
        assert "calibration" not in results
    finally:
        os.unlink(data_path)
