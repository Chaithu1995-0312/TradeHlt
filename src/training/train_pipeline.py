"""
train_pipeline.py
═══════════════════════════════════════════════════════════════════════════════
Training pipeline orchestrators — business logic only.

Two public entry points:

  run_training_pipeline(data_path, model_fn, ...)
      Generic TradeNet / binary-label training loop.
      Wires: load → validate_dataset → prepare_vectors → model_fn
             → Phase-5 calibration gate → save.

  run_gaussian_update(log_paths, version, ...)
      Full 8-step Gaussian model update pipeline.
      Wires: validate_logs → build_dataset → train_gaussian
             → cross_val_gaussian → evaluate_gaussian → Phase-5 gate
             → register_gaussian → promote_gaussian.

This module must NOT import from scripts/. Callers in scripts/ are thin CLI
wrappers that delegate here (per CLAUDE.md §3.1).
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger("TrainPipeline")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG (optional — thresholds live in dataset_validator)
# ─────────────────────────────────────────────────────────────────────────────

from features.dataset_validator import MIN_RECORDS_TO_TRAIN, MIN_RECORDS_RECOMMEND


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS: record-level validation  (TradeNet / binary-label path)
# ─────────────────────────────────────────────────────────────────────────────

def validate_training_record(record: dict) -> bool:
    """Validate a single binary-label training record."""
    if "features" not in record:
        raise ValueError("Training record missing 'features' key")
    if "label" not in record:
        raise ValueError("Training record missing 'label' key")
    if record["label"] not in (0, 1):
        raise ValueError(f"Invalid label: {record['label']}. Must be 0 or 1.")
    return True


def load_training_data(path: str) -> list:
    """Load training records from a JSON file."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Training data not found: {path}")
    with open(path, "r") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Training data must be a list of records")
    return data


def prepare_training_vectors(records: list) -> tuple:
    """
    Convert binary-label records to (X, y) using canonical extract_feature_vector.

    Raises ValueError / TypeError / AssertionError on malformed records.
    """
    from features.dataset_builder import extract_feature_vector

    X, y = [], []
    for i, record in enumerate(records):
        validate_training_record(record)
        X.append(extract_feature_vector(record["features"]))
        y.append(record["label"])
    return X, y


def validate_training_dataset(records: list) -> tuple:
    """
    Validate a binary-label training dataset; skip bad records; raise if below threshold.

    Returns (valid_records, report_dict).
    """
    from features.dataset_builder import extract_feature_vector

    report = {
        "total":                len(records),
        "valid":                0,
        "skipped_bad_record":   0,
        "skipped_bad_features": 0,
        "warnings":             [],
        "errors":               [],
    }
    valid_records = []

    for i, record in enumerate(records):
        try:
            validate_training_record(record)
        except ValueError as exc:
            report["skipped_bad_record"] += 1
            report["warnings"].append(f"Record {i}: {exc}")
            continue
        try:
            extract_feature_vector(record["features"])
        except (ValueError, TypeError, KeyError) as exc:
            report["skipped_bad_features"] += 1
            report["warnings"].append(f"Record {i}: bad feature vector — {exc}")
            continue
        valid_records.append(record)

    report["valid"] = len(valid_records)

    if report["valid"] < MIN_RECORDS_RECOMMEND:
        msg = (
            f"Only {report['valid']} valid records — "
            f"recommend {MIN_RECORDS_RECOMMEND}+ for reliable training."
        )
        report["warnings"].append(msg)
        log.warning("DatasetValidation: %s", msg)

    if report["valid"] < MIN_RECORDS_TO_TRAIN:
        raise ValueError(
            f"Dataset validation failed: {report['valid']} valid records, "
            f"minimum required is {MIN_RECORDS_TO_TRAIN}. "
            f"Skipped {report['skipped_bad_record']} bad records, "
            f"{report['skipped_bad_features']} bad feature vectors."
        )

    log.info(
        "DatasetValidation passed: %d/%d valid (%d bad-record, %d bad-features skipped).",
        report["valid"], report["total"],
        report["skipped_bad_record"], report["skipped_bad_features"],
    )
    return valid_records, report


# ─────────────────────────────────────────────────────────────────────────────
# run_training_pipeline  (TradeNet / generic binary path)
# ─────────────────────────────────────────────────────────────────────────────

def run_training_pipeline(
    data_path: str,
    model_fn: Callable,
    output_path: Optional[str] = None,
    threshold: float = 0.5,
    calibration_fn: Optional[Callable] = None,
) -> dict:
    """
    Full TradeNet training pipeline.

    Steps
    -----
    1. Load training data from JSON file.
    2. Validate dataset (raises ValueError if below MIN_RECORDS_TO_TRAIN).
    3. Prepare canonical feature vectors via extract_feature_vector.
    4. Run model_fn(X, y) → results dict.
    5. Phase-5 calibration gate (if calibration_fn provided).
    6. Save results to output_path (if provided).

    Parameters
    ----------
    data_path      : path to training data JSON
    model_fn       : callable(X, y) → dict with training results
    output_path    : optional path to persist results JSON
    threshold      : decision threshold (passed through to results)
    calibration_fn : optional calibration_fn(X, y) → dict
                     (from phase5_calibration.make_calibration_fn)

    Returns
    -------
    results dict including dataset_validation and (optionally) calibration keys.
    """
    records = load_training_data(data_path)
    records, validation_report = validate_training_dataset(records)
    X, y = prepare_training_vectors(records)

    log.info(
        "Training on %d samples with %d features each",
        len(X), len(X[0]) if X else 0,
    )

    results = model_fn(X, y)
    results["dataset_validation"] = validation_report

    if calibration_fn is not None:
        log.info("Phase5Calibration: running post-training calibration gate…")
        calibration_result = calibration_fn(X, y)
        results["calibration"] = calibration_result
        if not calibration_result.get("integration_approved", False):
            raise RuntimeError(
                "Phase5Calibration gate FAILED — model not approved for registration. "
                f"Verdict: {calibration_result.get('verdict', 'unknown')}"
            )
        log.info("Phase5Calibration: %s", calibration_result.get("verdict", ""))

    if output_path:
        os.makedirs(
            os.path.dirname(output_path) if os.path.dirname(output_path) else ".",
            exist_ok=True,
        )
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
        log.info("Training results saved → %s", output_path)

    return results


# ─────────────────────────────────────────────────────────────────────────────
# run_gaussian_update  (full 8-step Gaussian pipeline)
# ─────────────────────────────────────────────────────────────────────────────

def run_gaussian_update(
    log_paths: list,
    version: str,
    *,
    promote: bool = True,
    force_promote: bool = False,
    model_name: Optional[str] = None,
    save_dataset_path: Optional[str] = None,
) -> dict:
    """
    Full Gaussian model update pipeline (8 steps).

    Steps
    -----
    1. validate_logs(*log_paths)
         Load + pair ENTRY/EXIT fusion log records; check feature integrity.
    2. rr_dataset_builder.build_dataset(trades)
         Align trades with FeaturePipeline; extract (X, y_rr, y_win).
    3. trainer.train_gaussian(X, y_rr)
         Fit GaussianNBModel + StandardScaler on 70% temporal split.
    4. trainer.cross_val_gaussian(X, y_rr)
         Stability gate: corr_std < 0.05 across expanding-window folds.
    5. evaluator.evaluate_gaussian(model, scaler, X_val, y_val)
         Corr + calibration on held-out 30%.
    6. phase5_calibration gate
         All 4 hard gates must pass (min_val_samples, min_corr,
         max_cal_error, cv_stable).
    7. model_registry.register_gaussian(version, model_file, schema, metrics)
         Persist to models/gaussian_registry.json.
    8. model_registry.promote_gaussian(version)  (if promote=True)
         Promote only if new model does not regress by > max_regression vs active.

    Parameters
    ----------
    log_paths         : one or more paths to *_fusion.jsonl log files
    version           : registry version key, e.g. "gaussian_v2_2026_04"
    promote           : if False, register but skip promotion step
    force_promote     : bypass regression guard in promote_gaussian()
    model_name        : filename for saved model JSON (default: "{version}.json")
    save_dataset_path : optional path to persist the built dataset JSON

    Returns
    -------
    dict with keys:
      approved   : bool   — Phase-5 gate result
      version    : str
      promoted   : bool
      metrics    : dict   (corr, cal_error, n_train, n_val, cv_*)
      verdict    : str
      gate_checks: dict
    """
    from features.dataset_validator import validate_logs
    from config_layer.rr.rr_dataset_builder import build_dataset
    from training.trainer import train_gaussian, cross_val_gaussian, save_gaussian_model
    from training.evaluator import evaluate_gaussian
    from training.phase5_calibration import make_calibration_fn
    from core.model_registry import register_gaussian, promote_gaussian
    from features.feature_schema import GAUSSIAN_SCHEMA

    # ── Step 1: load + validate logs ─────────────────────────────────────────
    log.info("run_gaussian_update[%s]: step 1/8 — validate_logs", version)
    paired_records, val_report = validate_logs(*log_paths)
    if not val_report.is_trainable:
        raise ValueError(
            f"run_gaussian_update: insufficient data — "
            f"{val_report.valid_for_training} valid records "
            f"(minimum {val_report.valid_for_training} needed). "
            f"Check fusion logs: {log_paths}"
        )

    # ── Step 2: build feature matrix ─────────────────────────────────────────
    log.info("run_gaussian_update[%s]: step 2/8 — build_dataset", version)
    trades = [r for r in paired_records]   # already validated by validate_logs
    X, y_rr, y_win = build_dataset(trades)

    if save_dataset_path:
        from config_layer.rr.rr_dataset_builder import save_dataset
        save_dataset(X, y_rr, y_win, path=save_dataset_path)
        log.info("run_gaussian_update: dataset saved → %s", save_dataset_path)

    # ── Step 3: train ─────────────────────────────────────────────────────────
    log.info("run_gaussian_update[%s]: step 3/8 — train_gaussian", version)
    model, scaler, train_metrics = train_gaussian(X, y_rr)

    # ── Step 4: cross-val stability ───────────────────────────────────────────
    log.info("run_gaussian_update[%s]: step 4/8 — cross_val_gaussian", version)
    cv_result = cross_val_gaussian(X, y_rr)
    if not cv_result.get("stable", False):
        log.warning(
            "run_gaussian_update[%s]: CV not stable (corr_std=%.4f). "
            "Continuing — Phase-5 gate will reject if this persists.",
            version, cv_result.get("corr_std", 1.0),
        )

    # ── Step 5+6: Phase-5 calibration gate ────────────────────────────────────
    log.info("run_gaussian_update[%s]: steps 5-6/8 — Phase-5 calibration gate", version)
    cal_fn     = make_calibration_fn(model, scaler, label=version)
    cal_result = cal_fn(X, y_rr)

    approved    = cal_result["integration_approved"]
    verdict     = cal_result["verdict"]
    merged_metrics = {**train_metrics, **cal_result["metrics"]}

    if not approved:
        log.error(
            "run_gaussian_update[%s]: Phase-5 REJECTED — %s", version, verdict
        )
        return {
            "approved":  False,
            "version":   version,
            "promoted":  False,
            "metrics":   merged_metrics,
            "verdict":   verdict,
            "gate_checks": cal_result["gate_checks"],
        }

    # ── Step 7: register ──────────────────────────────────────────────────────
    log.info("run_gaussian_update[%s]: step 7/8 — register_gaussian", version)
    _model_name = model_name or f"{version}.json"
    model_path  = save_gaussian_model(
        model, scaler, merged_metrics,
        name=_model_name,
        feature_schema=list(GAUSSIAN_SCHEMA.feature_names),
    )
    register_gaussian(
        version       = version,
        model_file    = str(model_path),
        feature_schema= list(GAUSSIAN_SCHEMA.feature_names),
        metrics       = merged_metrics,
    )

    # ── Step 8: promote ───────────────────────────────────────────────────────
    promoted      = False
    promote_reason = "promotion skipped (promote=False)"
    if promote:
        log.info("run_gaussian_update[%s]: step 8/8 — promote_gaussian", version)
        from core.model_registry import _gaussian_registry
        promoted, promote_reason = _gaussian_registry.promote_gaussian(
            version, force=force_promote
        )
    else:
        log.info("run_gaussian_update[%s]: step 8/8 skipped (promote=False)", version)

    log.info(
        "run_gaussian_update[%s] COMPLETE | approved=%s promoted=%s | %s",
        version, approved, promoted, promote_reason,
    )

    return {
        "approved":    approved,
        "version":     version,
        "promoted":    promoted,
        "metrics":     merged_metrics,
        "verdict":     verdict,
        "gate_checks": cal_result["gate_checks"],
    }
