"""
phase5_calibration.py
═══════════════════════════════════════════════════════════════════════════════
Phase-5 Calibration Gate — post-training quality check before model registration.

Parameterised through configs/production/v1_multi_2026_03.json §phase5_calibration.
Hard defaults are used when the section is absent (fail-open on missing config,
fail-fast on gate failures).

Public API
----------
make_calibration_fn(model, scaler, *, label="gaussian") -> Callable
    Factory that binds a trained GaussianNBModel + StandardScaler into a
    calibration_fn(X_raw, y_rr) -> dict compatible with
    train_pipeline.run_training_pipeline(calibration_fn=...).

Gate checks (ALL must pass for integration_approved=True):
  1. min_val_samples  : hold-out rows >= min_val_samples
  2. min_corr         : corr(expected_rr, pnl_rr) on hold-out >= min_corr
  3. max_cal_error    : calibration_error on hold-out  <= max_cal_error
  4. cv_stable        : cross_val corr_std < cv_corr_std_max

Caller pattern:
    model, scaler, metrics = train_gaussian(X, y_rr)
    cal_fn = make_calibration_fn(model, scaler)
    result = run_training_pipeline(data_path, model_fn, calibration_fn=cal_fn)
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Optional

log = logging.getLogger("Phase5Calibration")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG LOAD  (fail-open on missing section; fail-fast on gate violation)
# ─────────────────────────────────────────────────────────────────────────────

try:
    from config_layer.production_config import get_prod_section as _get_section
    _P5_CFG: dict = _get_section("phase5_calibration")
except Exception:
    _P5_CFG = {}


def _require(key: str, default):
    """Return config value or hard default; logs when falling back."""
    val = _P5_CFG.get(key)
    if val is None:
        log.debug("phase5_calibration: '%s' not in config, default=%s", key, default)
        return default
    return val


# ─────────────────────────────────────────────────────────────────────────────
# GATE CONFIG DATACLASS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Phase5Config:
    """Thresholds for the Phase-5 calibration gate."""

    val_ratio:        float  # fraction of data reserved for hold-out evaluation
    min_val_samples:  int    # minimum hold-out rows for the eval to be meaningful
    min_corr:         float  # corr(expected_rr, pnl_rr) must be >= this
    max_cal_error:    float  # |predicted_win_rate – actual_win_rate| must be <= this
    cv_corr_std_max:  float  # corr_std across CV folds must be < this (stability)
    cv_n_folds:       int    # number of expanding-window CV folds

    @classmethod
    def from_prod_config(cls) -> "Phase5Config":
        return cls(
            val_ratio       = float(_require("val_ratio",       0.30)),
            min_val_samples = int(  _require("min_val_samples", 30)),
            min_corr        = float(_require("min_corr",        0.10)),
            max_cal_error   = float(_require("max_cal_error",   0.25)),
            cv_corr_std_max = float(_require("cv_corr_std_max", 0.05)),
            cv_n_folds      = int(  _require("cv_n_folds",      3)),
        )


# Module-level singleton — loaded once at import time
_CFG = Phase5Config.from_prod_config()


# ─────────────────────────────────────────────────────────────────────────────
# GATE RUNNER
# ─────────────────────────────────────────────────────────────────────────────

def _run_gates(metrics: dict, cv_stable: bool) -> tuple[bool, dict, str]:
    """
    Apply all Phase-5 gate checks.

    Parameters
    ----------
    metrics   : dict with keys corr_expected_rr, calibration_error, n_val
    cv_stable : bool — True when cross-val corr_std < cv_corr_std_max

    Returns
    -------
    (approved, gate_checks, verdict)
      approved    : True only when ALL gates pass
      gate_checks : dict mapping gate name → bool
      verdict     : human-readable summary string
    """
    gate_checks: dict[str, bool] = {
        "min_val_samples": metrics.get("n_val", 0)              >= _CFG.min_val_samples,
        "min_corr":        metrics.get("corr_expected_rr", 0.0) >= _CFG.min_corr,
        "max_cal_error":   metrics.get("calibration_error", 1.0) <= _CFG.max_cal_error,
        "cv_stable":       cv_stable,
    }
    approved = all(gate_checks.values())
    failed   = [k for k, ok in gate_checks.items() if not ok]
    verdict  = (
        "APPROVED"
        if approved
        else f"REJECTED — failed gates: {', '.join(failed)}"
    )
    return approved, gate_checks, verdict


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC FACTORY
# ─────────────────────────────────────────────────────────────────────────────

def make_calibration_fn(
    model,
    scaler,
    *,
    label: str = "gaussian",
) -> Callable[[list, list], dict]:
    """
    Bind a trained GaussianNBModel + StandardScaler into a calibration closure.

    The returned function matches the calibration_fn(X_raw, y_rr) -> dict
    contract expected by train_pipeline.run_training_pipeline().

    Parameters
    ----------
    model  : GaussianNBModel — already trained
    scaler : StandardScaler  — fitted on the same training split as model
    label  : tag shown in log lines (default "gaussian")

    Returns
    -------
    calibration_fn : callable(X_raw, y_rr) -> dict
        X_raw : list[list[float]] — raw (unscaled) feature vectors, time-ordered
        y_rr  : list[float]       — actual pnl_rr_net values

        Return dict keys:
          integration_approved : bool
          verdict              : str  ("APPROVED" or "REJECTED — …")
          metrics              : dict (corr_expected_rr, calibration_error,
                                       n_train, n_val, cv_corr_mean, cv_corr_std)
          gate_checks          : dict (gate_name → bool)
    """
    def calibration_fn(X_raw: list, y_rr: list) -> dict:
        from training.evaluator import evaluate_gaussian
        from training.trainer import cross_val_gaussian

        n     = len(X_raw)
        split = max(1, int(n * (1.0 - _CFG.val_ratio)))
        X_val = X_raw[split:]
        y_val = y_rr[split:]

        # ── Temporal hold-out evaluation ─────────────────────────────────────
        if len(X_val) < _CFG.min_val_samples:
            log.warning(
                "Phase5[%s]: hold-out only %d rows (need >= %d) — "
                "gate 'min_val_samples' will FAIL",
                label, len(X_val), _CFG.min_val_samples,
            )

        if X_val:
            eval_result = evaluate_gaussian(model, scaler, X_val, y_val)
            metrics: dict = {
                "corr_expected_rr":  eval_result.corr_expected_rr,
                "calibration_error": eval_result.calibration_error,
                "n_val":             eval_result.n_samples,
                "n_train":           split,
            }
        else:
            metrics = {
                "corr_expected_rr":  0.0,
                "calibration_error": 1.0,
                "n_val":             0,
                "n_train":           split,
            }

        # ── Cross-val stability gate ──────────────────────────────────────────
        try:
            cv      = cross_val_gaussian(X_raw, y_rr, n_folds=_CFG.cv_n_folds)
            cv_stable               = cv.get("stable", False)
            metrics["cv_corr_mean"] = cv.get("corr_mean", 0.0)
            metrics["cv_corr_std"]  = cv.get("corr_std",  1.0)
        except Exception as exc:
            log.warning(
                "Phase5[%s]: cross_val_gaussian failed (%s) — cv_stable=False",
                label, exc,
            )
            cv_stable               = False
            metrics["cv_corr_mean"] = 0.0
            metrics["cv_corr_std"]  = 1.0

        approved, gate_checks, verdict = _run_gates(metrics, cv_stable)

        log.info(
            "Phase5[%s] %s | corr=%+.4f cal=%.4f n_val=%d cv_stable=%s",
            label, verdict,
            metrics["corr_expected_rr"],
            metrics["calibration_error"],
            metrics["n_val"],
            cv_stable,
        )

        return {
            "integration_approved": approved,
            "verdict":              verdict,
            "metrics":              metrics,
            "gate_checks":          gate_checks,
        }

    return calibration_fn
