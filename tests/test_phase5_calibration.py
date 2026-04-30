"""
test_phase5_calibration.py
==========================
Unit tests for src/training/phase5_calibration.py (GAP-2).

Covers (per TESTING.md §4 conventions):
  - Phase5Config loads from config or falls back to hard defaults
  - make_calibration_fn returns a callable
  - Returned callable produces a correctly-shaped result dict
  - APPROVE path: all 4 gates pass → integration_approved=True
  - REJECT path (one test per gate):
      • min_val_samples  — insufficient hold-out rows
      • min_corr         — correlation below threshold
      • max_cal_error    — calibration error above threshold
      • cv_stable        — cross-val std too high (unstable)
  - Multiple gate failures reported together (gate_checks dict complete)
  - Closure re-uses the bound model/scaler, not a fresh one each call
"""

import pytest
from unittest.mock import patch, MagicMock

from features.feature_schema import CANONICAL_FEATURES


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

N_FEATURES = len(CANONICAL_FEATURES)


def _make_fitted_model_and_scaler(n: int = 50):
    """
    Minimal GaussianNBModel + StandardScaler pre-fitted on synthetic data.
    Does NOT call train_gaussian — fits directly to isolate gate logic from
    the trainer under test.
    """
    import random
    from training.trainer import GaussianNBModel, StandardScaler

    random.seed(42)
    X = [[random.gauss(float(i % 4), 0.1) for i in range(N_FEATURES)] for _ in range(n)]
    scaler = StandardScaler()
    scaler.fit(X)
    X_sc = scaler.transform(X)
    y_cls = [i % 4 for i in range(n)]   # balanced 4-class labels
    model = GaussianNBModel()
    model.fit(X_sc, y_cls)
    return model, scaler


def _make_X_y(n: int = 100):
    """Synthetic raw feature matrix + RR labels (time-ordered)."""
    import random
    random.seed(7)
    X   = [[random.gauss(0, 1) for _ in range(N_FEATURES)] for _ in range(n)]
    y_rr = [random.uniform(-1, 3) for _ in range(n)]
    return X, y_rr


def _good_eval_result():
    """GaussianEvalResult mock that passes min_corr and max_cal_error gates."""
    ev = MagicMock()
    ev.corr_expected_rr  = 0.30   # > min_corr=0.10 ✅
    ev.calibration_error = 0.10   # < max_cal_error=0.25 ✅
    ev.n_samples         = 35     # > min_val_samples=30 ✅
    return ev


def _good_cv_result():
    """cross_val_gaussian result that passes cv_stable gate."""
    return {
        "stable":    True,     # corr_std < 0.05 ✅
        "corr_mean": 0.28,
        "corr_std":  0.02,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Phase5Config
# ─────────────────────────────────────────────────────────────────────────────

def test_phase5_config_loads_defaults():
    """Config falls back to hard-coded defaults when section is absent."""
    from training.phase5_calibration import Phase5Config

    with patch("training.phase5_calibration._P5_CFG", {}):
        cfg = Phase5Config.from_prod_config()

    assert cfg.val_ratio        == pytest.approx(0.30)
    assert cfg.min_val_samples  == 30
    assert cfg.min_corr         == pytest.approx(0.10)
    assert cfg.max_cal_error    == pytest.approx(0.25)
    assert cfg.cv_corr_std_max  == pytest.approx(0.05)
    assert cfg.cv_n_folds       == 3


def test_phase5_config_honours_prod_config_values():
    """Config reads overridden values from the production config section."""
    from training.phase5_calibration import Phase5Config

    override = {
        "val_ratio": 0.20, "min_val_samples": 50,
        "min_corr": 0.15,  "max_cal_error": 0.20,
        "cv_corr_std_max": 0.03, "cv_n_folds": 5,
    }
    with patch("training.phase5_calibration._P5_CFG", override):
        cfg = Phase5Config.from_prod_config()

    assert cfg.val_ratio       == pytest.approx(0.20)
    assert cfg.min_val_samples == 50
    assert cfg.cv_n_folds      == 5


# ─────────────────────────────────────────────────────────────────────────────
# make_calibration_fn — factory contract
# ─────────────────────────────────────────────────────────────────────────────

def test_make_calibration_fn_returns_callable():
    """Factory must return a callable regardless of model content."""
    from training.phase5_calibration import make_calibration_fn

    model, scaler = _make_fitted_model_and_scaler()
    fn = make_calibration_fn(model, scaler, label="test")
    assert callable(fn)


def test_calibration_fn_result_has_required_keys():
    """Closure must return all four required keys."""
    from training.phase5_calibration import make_calibration_fn

    model, scaler = _make_fitted_model_and_scaler()
    fn = make_calibration_fn(model, scaler)
    X, y_rr = _make_X_y(n=100)

    with patch("training.evaluator.evaluate_gaussian", return_value=_good_eval_result()), \
         patch("training.trainer.cross_val_gaussian",  return_value=_good_cv_result()):
        result = fn(X, y_rr)

    assert "integration_approved" in result
    assert "verdict"               in result
    assert "metrics"               in result
    assert "gate_checks"           in result
    assert isinstance(result["integration_approved"], bool)
    assert isinstance(result["gate_checks"],          dict)


# ─────────────────────────────────────────────────────────────────────────────
# APPROVE path
# ─────────────────────────────────────────────────────────────────────────────

def test_approve_path_all_gates_pass():
    """All 4 gates passing → integration_approved=True, verdict starts APPROVED."""
    from training.phase5_calibration import make_calibration_fn

    model, scaler = _make_fitted_model_and_scaler()
    fn  = make_calibration_fn(model, scaler, label="approve_test")
    X, y_rr = _make_X_y(n=100)

    with patch("training.evaluator.evaluate_gaussian", return_value=_good_eval_result()), \
         patch("training.trainer.cross_val_gaussian",  return_value=_good_cv_result()):
        result = fn(X, y_rr)

    assert result["integration_approved"] is True, result["verdict"]
    assert result["verdict"].startswith("APPROVED")
    assert all(result["gate_checks"].values()), (
        f"Expected all gate_checks True, got: {result['gate_checks']}"
    )


def test_approve_path_gate_checks_all_true():
    """Each gate_checks entry must individually be True on the approve path."""
    from training.phase5_calibration import make_calibration_fn

    model, scaler = _make_fitted_model_and_scaler()
    fn  = make_calibration_fn(model, scaler)
    X, y_rr = _make_X_y(n=100)

    with patch("training.evaluator.evaluate_gaussian", return_value=_good_eval_result()), \
         patch("training.trainer.cross_val_gaussian",  return_value=_good_cv_result()):
        result = fn(X, y_rr)

    for gate_name, passed in result["gate_checks"].items():
        assert passed is True, f"Gate '{gate_name}' should be True on approve path"


# ─────────────────────────────────────────────────────────────────────────────
# REJECT paths — one test per gate
# ─────────────────────────────────────────────────────────────────────────────

def test_reject_min_val_samples():
    """Gate 1: n_val below min_val_samples → integration_approved=False."""
    from training.phase5_calibration import make_calibration_fn

    model, scaler = _make_fitted_model_and_scaler()
    fn  = make_calibration_fn(model, scaler)

    # Only 10 samples total → hold-out ≈ 3 rows < min_val_samples=30
    X, y_rr = _make_X_y(n=10)

    ev = _good_eval_result()
    ev.n_samples = 3   # force tiny hold-out count
    with patch("training.evaluator.evaluate_gaussian", return_value=ev), \
         patch("training.trainer.cross_val_gaussian",  return_value=_good_cv_result()):
        result = fn(X, y_rr)

    assert result["integration_approved"] is False
    assert result["gate_checks"]["min_val_samples"] is False
    assert "REJECTED" in result["verdict"]
    assert "min_val_samples" in result["verdict"]


def test_reject_min_corr():
    """Gate 2: corr(expected_rr, pnl_rr) below threshold → rejected."""
    from training.phase5_calibration import make_calibration_fn

    model, scaler = _make_fitted_model_and_scaler()
    fn  = make_calibration_fn(model, scaler)
    X, y_rr = _make_X_y(n=100)

    ev = _good_eval_result()
    ev.corr_expected_rr = 0.02   # below min_corr=0.10 ❌
    with patch("training.evaluator.evaluate_gaussian", return_value=ev), \
         patch("training.trainer.cross_val_gaussian",  return_value=_good_cv_result()):
        result = fn(X, y_rr)

    assert result["integration_approved"] is False
    assert result["gate_checks"]["min_corr"] is False
    assert "min_corr" in result["verdict"]


def test_reject_max_cal_error():
    """Gate 3: calibration error above threshold → rejected."""
    from training.phase5_calibration import make_calibration_fn

    model, scaler = _make_fitted_model_and_scaler()
    fn  = make_calibration_fn(model, scaler)
    X, y_rr = _make_X_y(n=100)

    ev = _good_eval_result()
    ev.calibration_error = 0.40   # above max_cal_error=0.25 ❌
    with patch("training.evaluator.evaluate_gaussian", return_value=ev), \
         patch("training.trainer.cross_val_gaussian",  return_value=_good_cv_result()):
        result = fn(X, y_rr)

    assert result["integration_approved"] is False
    assert result["gate_checks"]["max_cal_error"] is False
    assert "max_cal_error" in result["verdict"]


def test_reject_cv_unstable():
    """Gate 4: CV corr_std above threshold → cv_stable=False → rejected."""
    from training.phase5_calibration import make_calibration_fn

    model, scaler = _make_fitted_model_and_scaler()
    fn  = make_calibration_fn(model, scaler)
    X, y_rr = _make_X_y(n=100)

    unstable_cv = {"stable": False, "corr_mean": 0.10, "corr_std": 0.12}
    with patch("training.evaluator.evaluate_gaussian", return_value=_good_eval_result()), \
         patch("training.trainer.cross_val_gaussian",  return_value=unstable_cv):
        result = fn(X, y_rr)

    assert result["integration_approved"] is False
    assert result["gate_checks"]["cv_stable"] is False
    assert "cv_stable" in result["verdict"]


# ─────────────────────────────────────────────────────────────────────────────
# Multiple simultaneous gate failures
# ─────────────────────────────────────────────────────────────────────────────

def test_multiple_gate_failures_all_reported():
    """gate_checks dict must capture ALL failed gates, not just the first."""
    from training.phase5_calibration import make_calibration_fn

    model, scaler = _make_fitted_model_and_scaler()
    fn  = make_calibration_fn(model, scaler)
    X, y_rr = _make_X_y(n=100)

    ev = _good_eval_result()
    ev.corr_expected_rr  = 0.00   # fails min_corr
    ev.calibration_error = 0.50   # fails max_cal_error
    unstable_cv = {"stable": False, "corr_mean": 0.0, "corr_std": 0.20}

    with patch("training.evaluator.evaluate_gaussian", return_value=ev), \
         patch("training.trainer.cross_val_gaussian",  return_value=unstable_cv):
        result = fn(X, y_rr)

    assert result["integration_approved"] is False
    assert result["gate_checks"]["min_corr"]       is False
    assert result["gate_checks"]["max_cal_error"]  is False
    assert result["gate_checks"]["cv_stable"]      is False
    # gate_checks must have exactly 4 entries
    assert len(result["gate_checks"]) == 4


# ─────────────────────────────────────────────────────────────────────────────
# CV failure fallback (cross_val_gaussian raises)
# ─────────────────────────────────────────────────────────────────────────────

def test_cv_exception_treated_as_unstable():
    """If cross_val_gaussian raises, cv_stable must default to False (no crash)."""
    from training.phase5_calibration import make_calibration_fn

    model, scaler = _make_fitted_model_and_scaler()
    fn  = make_calibration_fn(model, scaler)
    X, y_rr = _make_X_y(n=100)

    with patch("training.evaluator.evaluate_gaussian", return_value=_good_eval_result()), \
         patch("training.trainer.cross_val_gaussian", side_effect=RuntimeError("CV failed")):
        result = fn(X, y_rr)   # must NOT raise

    assert result["gate_checks"]["cv_stable"] is False
    assert "metrics" in result
    assert result["metrics"]["cv_corr_std"] == pytest.approx(1.0)


# ─────────────────────────────────────────────────────────────────────────────
# Metrics dict shape
# ─────────────────────────────────────────────────────────────────────────────

def test_metrics_keys_present_on_approve():
    """Metrics dict must carry all expected keys on the approve path."""
    from training.phase5_calibration import make_calibration_fn

    model, scaler = _make_fitted_model_and_scaler()
    fn  = make_calibration_fn(model, scaler)
    X, y_rr = _make_X_y(n=100)

    with patch("training.evaluator.evaluate_gaussian", return_value=_good_eval_result()), \
         patch("training.trainer.cross_val_gaussian",  return_value=_good_cv_result()):
        result = fn(X, y_rr)

    m = result["metrics"]
    for key in ("corr_expected_rr", "calibration_error", "n_val", "n_train",
                "cv_corr_mean", "cv_corr_std"):
        assert key in m, f"Expected metrics key '{key}' missing"
