"""
test_gaussian_update_pipeline.py
=================================
Integration tests for run_gaussian_update() in src/training/train_pipeline.py (GAP-3).

Strategy: mock the heavy I/O boundaries (validate_logs, build_dataset,
save_gaussian_model, register_gaussian, promote_gaussian) and exercise the
orchestration logic + Phase-5 gate in-process.

Covers (per TESTING.md §4):
  - Abort early when validate_logs returns insufficient data (is_trainable=False)
  - Abort at Phase-5 gate when model quality is too low
  - Happy path: approved=True, promoted=True
  - promote=False skips the promotion step
  - result dict always has the required keys regardless of path taken
  - Version is threaded through to register/promote calls correctly
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call

from features.feature_schema import CANONICAL_FEATURES

N_FEATURES  = len(CANONICAL_FEATURES)
_TEST_VER   = "gaussian_test_v2026_04"


# ─────────────────────────────────────────────────────────────────────────────
# Shared synthetic data helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_X_y(n: int = 60):
    """Synthetic (X, y_rr, y_win) that satisfies MIN_SAMPLES=20."""
    import random
    random.seed(99)
    X     = [[random.gauss(0, 1) for _ in range(N_FEATURES)] for _ in range(n)]
    y_rr  = [random.uniform(-1, 3) for _ in range(n)]
    y_win = [1 if r > 0 else 0 for r in y_rr]
    return X, y_rr, y_win


def _make_paired_records(n: int = 60):
    """Minimal paired records list matching the contract expected by run_gaussian_update.
    train_pipeline.py reads feature_vec + outcome directly from these records."""
    import random
    random.seed(42)
    return [
        {
            "trade_id":   f"t{i}",
            "features":   {},
            "feature_vec": [random.gauss(0, 1) for _ in range(N_FEATURES)],
            "outcome":    {"pnl_rr_net": random.uniform(-1, 3),
                           "win": random.choice([True, False])},
        }
        for i in range(n)
    ]


def _make_val_report(trainable: bool = True):
    """Synthetic ValidationReport with is_trainable property."""
    rpt = MagicMock()
    rpt.is_trainable       = trainable
    rpt.valid_for_training = 60 if trainable else 5
    return rpt


def _good_calibration_result():
    return {
        "integration_approved": True,
        "verdict":              "APPROVED",
        "metrics":              {"corr_expected_rr": 0.25, "calibration_error": 0.12,
                                  "n_val": 18, "n_train": 42},
        "gate_checks":         {"min_val_samples": True, "min_corr": True,
                                 "max_cal_error": True, "cv_stable": True},
    }


def _bad_calibration_result():
    return {
        "integration_approved": False,
        "verdict":              "REJECTED — failed gates: min_corr",
        "metrics":              {"corr_expected_rr": 0.02, "calibration_error": 0.30,
                                  "n_val": 18, "n_train": 42},
        "gate_checks":         {"min_val_samples": True, "min_corr": False,
                                 "max_cal_error": True, "cv_stable": True},
    }


# ─────────────────────────────────────────────────────────────────────────────
# Result dict shape invariant
# ─────────────────────────────────────────────────────────────────────────────

REQUIRED_RESULT_KEYS = {"approved", "version", "promoted", "metrics", "verdict", "gate_checks"}


def _assert_result_shape(result: dict) -> None:
    missing = REQUIRED_RESULT_KEYS - set(result)
    assert not missing, f"run_gaussian_update result missing keys: {missing}"


# ─────────────────────────────────────────────────────────────────────────────
# Shared patch targets (lazy imports inside run_gaussian_update)
# ─────────────────────────────────────────────────────────────────────────────

_PATCH_VALIDATE_LOGS   = "features.dataset_validator.validate_logs"
_PATCH_BUILD_DATASET   = "config_layer.rr.rr_dataset_builder.build_dataset"
_PATCH_SAVE_MODEL      = "training.trainer.save_gaussian_model"
_PATCH_REGISTER        = "core.model_registry.register_gaussian"
_PATCH_PROMOTE         = "core.model_registry._gaussian_registry"
_PATCH_CAL_FN          = "training.phase5_calibration.make_calibration_fn"


# ─────────────────────────────────────────────────────────────────────────────
# 1. Early abort — insufficient data
# ─────────────────────────────────────────────────────────────────────────────

def test_abort_on_insufficient_data():
    """run_gaussian_update raises ValueError when validate_logs returns is_trainable=False."""
    from training.train_pipeline import run_gaussian_update

    bad_report = MagicMock()
    bad_report.is_trainable       = False
    bad_report.valid_for_training = 5

    with patch("features.dataset_validator.validate_logs",
               return_value=([], bad_report)):
        with pytest.raises(ValueError, match="insufficient data"):
            run_gaussian_update(["logs/GBPUSD_fusion.jsonl"], version=_TEST_VER)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Phase-5 gate rejects → no registration, no promotion
# ─────────────────────────────────────────────────────────────────────────────

def test_phase5_rejection_skips_registration():
    """When Phase-5 gate rejects, result has approved=False and neither register
    nor promote should be called."""
    from training.train_pipeline import run_gaussian_update

    good_report = MagicMock()
    good_report.is_trainable = True

    X, y_rr, y_win = _make_X_y()

    mock_cal_fn = MagicMock(return_value=_bad_calibration_result())

    with patch("features.dataset_validator.validate_logs",
               return_value=(_make_paired_records(), good_report)), \
         patch("config_layer.rr.rr_dataset_builder.build_dataset",
               return_value=(X, y_rr, y_win)), \
         patch("training.phase5_calibration.make_calibration_fn",
               return_value=mock_cal_fn), \
         patch("training.trainer.save_gaussian_model") as mock_save, \
         patch("core.model_registry.register_gaussian") as mock_reg, \
         patch("core.model_registry._gaussian_registry") as mock_preg:

        result = run_gaussian_update(["logs/fake.jsonl"], version=_TEST_VER)

    _assert_result_shape(result)
    assert result["approved"]  is False
    assert result["promoted"]  is False
    assert result["version"]   == _TEST_VER
    assert "REJECTED" in result["verdict"]
    mock_save.assert_not_called()
    mock_reg.assert_not_called()
    mock_preg.promote_gaussian.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# 3. Happy path — approve + promote
# ─────────────────────────────────────────────────────────────────────────────

def test_happy_path_approved_and_promoted():
    """Full happy-path: all steps succeed, result has approved=True, promoted=True."""
    from training.train_pipeline import run_gaussian_update

    good_report = MagicMock()
    good_report.is_trainable = True

    X, y_rr, y_win = _make_X_y()

    mock_cal_fn   = MagicMock(return_value=_good_calibration_result())
    mock_save_path = Path("models/gaussian_test_v2026_04.json")

    mock_gaussian_reg = MagicMock()
    mock_gaussian_reg.promote_gaussian.return_value = (True, "promoted successfully")

    with patch("features.dataset_validator.validate_logs",
               return_value=(_make_paired_records(), good_report)), \
         patch("config_layer.rr.rr_dataset_builder.build_dataset",
               return_value=(X, y_rr, y_win)), \
         patch("training.phase5_calibration.make_calibration_fn",
               return_value=mock_cal_fn), \
         patch("training.trainer.save_gaussian_model",
               return_value=mock_save_path), \
         patch("core.model_registry.register_gaussian"), \
         patch("core.model_registry._gaussian_registry", mock_gaussian_reg):

        result = run_gaussian_update(
            ["logs/fake.jsonl"], version=_TEST_VER, promote=True
        )

    _assert_result_shape(result)
    assert result["approved"]  is True
    assert result["promoted"]  is True
    assert result["version"]   == _TEST_VER
    assert "APPROVED" in result["verdict"]
    mock_gaussian_reg.promote_gaussian.assert_called_once_with(
        _TEST_VER, force=False
    )


# ─────────────────────────────────────────────────────────────────────────────
# 4. promote=False skips promotion step
# ─────────────────────────────────────────────────────────────────────────────

def test_promote_false_skips_promotion():
    """promote=False → register succeeds, promote_gaussian never called."""
    from training.train_pipeline import run_gaussian_update

    good_report = MagicMock()
    good_report.is_trainable = True

    X, y_rr, y_win = _make_X_y()

    mock_cal_fn        = MagicMock(return_value=_good_calibration_result())
    mock_gaussian_reg  = MagicMock()

    with patch("features.dataset_validator.validate_logs",
               return_value=(_make_paired_records(), good_report)), \
         patch("config_layer.rr.rr_dataset_builder.build_dataset",
               return_value=(X, y_rr, y_win)), \
         patch("training.phase5_calibration.make_calibration_fn",
               return_value=mock_cal_fn), \
         patch("training.trainer.save_gaussian_model",
               return_value=Path("models/fake.json")), \
         patch("core.model_registry.register_gaussian"), \
         patch("core.model_registry._gaussian_registry", mock_gaussian_reg):

        result = run_gaussian_update(
            ["logs/fake.jsonl"], version=_TEST_VER, promote=False
        )

    _assert_result_shape(result)
    assert result["approved"]  is True
    assert result["promoted"]  is False
    mock_gaussian_reg.promote_gaussian.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# 5. force_promote=True forwarded to promote_gaussian
# ─────────────────────────────────────────────────────────────────────────────

def test_force_promote_forwarded():
    """force_promote=True must be passed through to promote_gaussian(force=True)."""
    from training.train_pipeline import run_gaussian_update

    good_report = MagicMock()
    good_report.is_trainable = True

    X, y_rr, y_win = _make_X_y()

    mock_cal_fn       = MagicMock(return_value=_good_calibration_result())
    mock_gaussian_reg = MagicMock()
    mock_gaussian_reg.promote_gaussian.return_value = (True, "force-promoted")

    with patch("features.dataset_validator.validate_logs",
               return_value=(_make_paired_records(), good_report)), \
         patch("config_layer.rr.rr_dataset_builder.build_dataset",
               return_value=(X, y_rr, y_win)), \
         patch("training.phase5_calibration.make_calibration_fn",
               return_value=mock_cal_fn), \
         patch("training.trainer.save_gaussian_model",
               return_value=Path("models/fake.json")), \
         patch("core.model_registry.register_gaussian"), \
         patch("core.model_registry._gaussian_registry", mock_gaussian_reg):

        run_gaussian_update(
            ["logs/fake.jsonl"], version=_TEST_VER,
            promote=True, force_promote=True,
        )

    mock_gaussian_reg.promote_gaussian.assert_called_once_with(
        _TEST_VER, force=True
    )


# ─────────────────────────────────────────────────────────────────────────────
# 6. Version threaded through correctly
# ─────────────────────────────────────────────────────────────────────────────

def test_version_passed_to_register():
    """register_gaussian must receive the exact version string supplied by caller."""
    from training.train_pipeline import run_gaussian_update

    good_report = MagicMock()
    good_report.is_trainable = True

    X, y_rr, y_win = _make_X_y()
    custom_version = "gaussian_custom_abc123"

    mock_cal_fn  = MagicMock(return_value=_good_calibration_result())
    mock_register = MagicMock()
    mock_gr       = MagicMock()
    mock_gr.promote_gaussian.return_value = (True, "ok")

    with patch("features.dataset_validator.validate_logs",
               return_value=(_make_paired_records(), good_report)), \
         patch("config_layer.rr.rr_dataset_builder.build_dataset",
               return_value=(X, y_rr, y_win)), \
         patch("training.phase5_calibration.make_calibration_fn",
               return_value=mock_cal_fn), \
         patch("training.trainer.save_gaussian_model",
               return_value=Path(f"models/{custom_version}.json")), \
         patch("core.model_registry.register_gaussian", mock_register), \
         patch("core.model_registry._gaussian_registry", mock_gr):

        result = run_gaussian_update(["logs/fake.jsonl"], version=custom_version)

    assert result["version"] == custom_version
    # register_gaussian is called with keyword args only; inspect via .kwargs
    assert mock_register.call_args is not None, "register_gaussian was not called"
    actual_version_arg = mock_register.call_args.kwargs.get(
        "version",
        mock_register.call_args[1].get("version"),   # fallback for Python <3.8
    )
    assert actual_version_arg == custom_version


# ─────────────────────────────────────────────────────────────────────────────
# 7. Result shape invariant — all paths return required keys
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("trainable,cal_approved", [
    (False, True),    # abort path (insufficient data raises — not tested here)
    (True,  False),   # phase-5 reject path
    (True,  True),    # happy path
])
def test_result_shape_across_paths(trainable, cal_approved):
    """Result dict always contains all required keys on non-raising paths."""
    from training.train_pipeline import run_gaussian_update

    if not trainable:
        # This path raises — skip shape assertion
        pytest.skip("insufficient-data path raises ValueError, tested separately")

    good_report = MagicMock()
    good_report.is_trainable = True

    X, y_rr, y_win = _make_X_y()
    cal_result   = _good_calibration_result() if cal_approved else _bad_calibration_result()
    mock_cal_fn  = MagicMock(return_value=cal_result)
    mock_gr      = MagicMock()
    mock_gr.promote_gaussian.return_value = (True, "ok")

    with patch("features.dataset_validator.validate_logs",
               return_value=(_make_paired_records(), good_report)), \
         patch("config_layer.rr.rr_dataset_builder.build_dataset",
               return_value=(X, y_rr, y_win)), \
         patch("training.phase5_calibration.make_calibration_fn",
               return_value=mock_cal_fn), \
         patch("training.trainer.save_gaussian_model",
               return_value=Path("models/fake.json")), \
         patch("core.model_registry.register_gaussian"), \
         patch("core.model_registry._gaussian_registry", mock_gr):

        result = run_gaussian_update(["logs/fake.jsonl"], version=_TEST_VER)

    _assert_result_shape(result)
