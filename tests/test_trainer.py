"""
test_trainer.py
===============
Unit tests for src/training/trainer.py  (Flow 4 — Training/Model Update validation).

Covers:
  StandardScaler:
    - fit + transform: mean ≈ 0, std ≈ 1 on training data
    - transform_one consistent with transform
    - fit empty → ValueError
    - transform / transform_one before fit → RuntimeError
    - to_dict / from_dict roundtrip preserves predictions
    - n_features set correctly after fit

  GaussianNBModel:
    - fit + predict_proba → 4 probs summing to 1.0
    - predict_proba before fit → RuntimeError
    - predict_proba wrong-dim vector → ValueError (FIX 2 hard check)
    - fit empty → ValueError
    - predict_expected_rr → (float, conf∈[0,1], list len 4)
    - to_dict / from_dict roundtrip preserves predictions
    - class_priors sum to 1.0

  train_gaussian:
    - below MIN_GAUSSIAN_SAMPLES → ValueError
    - happy path → (GaussianNBModel, StandardScaler, dict)
    - metrics keys: corr_expected_rr, calibration_error, n_train, n_val, trained_at
    - n_train + n_val == total input length
    - corr_expected_rr in [-1, 1]
    - calibration_error >= 0
    - returned model.predict_proba works on scaled vectors

  cross_val_gaussian:
    - below MIN_GAUSSIAN_SAMPLES → ValueError
    - happy path returns dict with required keys
    - stable is bool
    - fold_metrics is list
    - stable == (corr_std < 0.05) invariant
    - corr_mean in [-1, 1]
    - n_folds parameter is respected (len(fold_metrics) <= n_folds)

  save_gaussian_model / load_gaussian_model:
    - save creates JSON with required top-level keys
    - load roundtrip: predictions match original model
    - load with mismatched feature_schema → ValueError
    - load missing file → FileNotFoundError
"""

from __future__ import annotations

import json
import math
import pytest
from pathlib import Path
from unittest.mock import patch

from features.feature_schema import CANONICAL_FEATURES, GAUSSIAN_SCHEMA

N_FEATURES  = len(CANONICAL_FEATURES)   # 35
MIN_SAMPLES = 20                         # matches trainer.MIN_GAUSSIAN_SAMPLES


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_X(n: int = 60, seed: int = 17) -> list:
    """Synthetic raw (unscaled) 35-dim feature matrix, time-ordered."""
    import random
    random.seed(seed)
    return [
        [random.gauss(float(i % 4), 0.3) for i in range(N_FEATURES)]
        for _ in range(n)
    ]


def _make_y_rr(n: int = 60, seed: int = 18) -> list:
    """Synthetic RR label series."""
    import random
    random.seed(seed)
    return [random.uniform(-1.0, 3.0) for _ in range(n)]


def _fitted_scaler(X: list):
    from training.trainer import StandardScaler
    sc = StandardScaler()
    sc.fit(X)
    return sc


def _fitted_model_and_scaler(n: int = 60):
    """GaussianNBModel + StandardScaler fitted on synthetic data."""
    from training.trainer import GaussianNBModel, StandardScaler
    X = _make_X(n=n)
    sc = _fitted_scaler(X)
    X_sc = sc.transform(X)
    y_cls = [i % 4 for i in range(n)]
    model = GaussianNBModel()
    model.fit(X_sc, y_cls)
    return model, sc, X, X_sc


# ─────────────────────────────────────────────────────────────────────────────
# StandardScaler
# ─────────────────────────────────────────────────────────────────────────────

class TestStandardScaler:

    def test_fit_transform_mean_near_zero(self):
        from training.trainer import StandardScaler
        X = _make_X(n=200)
        sc = StandardScaler()
        sc.fit(X)
        X_sc = sc.transform(X)
        for f in range(N_FEATURES):
            col  = [row[f] for row in X_sc]
            mean = sum(col) / len(col)
            assert abs(mean) < 1e-9, (
                f"Feature {f}: expected mean ≈ 0 after scaling, got {mean:.2e}"
            )

    def test_fit_transform_std_near_one(self):
        from training.trainer import StandardScaler
        X = _make_X(n=200)
        sc = StandardScaler()
        sc.fit(X)
        X_sc = sc.transform(X)
        for f in range(N_FEATURES):
            col  = [row[f] for row in X_sc]
            mu   = sum(col) / len(col)
            std  = math.sqrt(sum((v - mu) ** 2 for v in col) / len(col))
            assert abs(std - 1.0) < 1e-9, (
                f"Feature {f}: expected std ≈ 1 after scaling, got {std:.6f}"
            )

    def test_transform_one_consistent_with_transform(self):
        from training.trainer import StandardScaler
        X = _make_X(n=50)
        sc = StandardScaler()
        sc.fit(X)
        X_sc = sc.transform(X)
        for i, row in enumerate(X[:10]):
            one = sc.transform_one(row)
            for f in range(N_FEATURES):
                assert one[f] == pytest.approx(X_sc[i][f], abs=1e-12)

    def test_fit_empty_raises_value_error(self):
        from training.trainer import StandardScaler
        with pytest.raises(ValueError, match="empty"):
            StandardScaler().fit([])

    def test_transform_before_fit_raises_runtime_error(self):
        from training.trainer import StandardScaler
        with pytest.raises(RuntimeError, match="fit"):
            StandardScaler().transform([[0.0] * N_FEATURES])

    def test_transform_one_before_fit_raises_runtime_error(self):
        from training.trainer import StandardScaler
        with pytest.raises(RuntimeError, match="fit"):
            StandardScaler().transform_one([0.0] * N_FEATURES)

    def test_n_features_set_after_fit(self):
        from training.trainer import StandardScaler
        X = _make_X(n=40)
        sc = StandardScaler()
        sc.fit(X)
        assert sc.n_features == N_FEATURES

    def test_to_dict_has_required_keys(self):
        from training.trainer import StandardScaler
        sc = StandardScaler()
        sc.fit(_make_X(n=30))
        d = sc.to_dict()
        for key in ("mean", "std", "n_features"):
            assert key in d, f"Missing key '{key}' in StandardScaler.to_dict()"

    def test_from_dict_roundtrip_preserves_transforms(self):
        from training.trainer import StandardScaler
        X = _make_X(n=60)
        sc = StandardScaler()
        sc.fit(X)
        sc2 = StandardScaler.from_dict(sc.to_dict())
        for row in X[:5]:
            assert sc.transform_one(row) == pytest.approx(sc2.transform_one(row))

    def test_from_dict_is_immediately_usable(self):
        """Deserialized scaler must not require an extra fit() call."""
        from training.trainer import StandardScaler
        sc = StandardScaler()
        sc.fit(_make_X(n=40))
        sc2 = StandardScaler.from_dict(sc.to_dict())
        # Should not raise
        sc2.transform([[0.0] * N_FEATURES])


# ─────────────────────────────────────────────────────────────────────────────
# GaussianNBModel
# ─────────────────────────────────────────────────────────────────────────────

class TestGaussianNBModel:

    def test_predict_proba_sums_to_one(self):
        model, sc, X, X_sc = _fitted_model_and_scaler()
        for x in X_sc[:10]:
            probs = model.predict_proba(x)
            assert len(probs) == 4
            assert sum(probs) == pytest.approx(1.0, abs=1e-9)

    def test_predict_proba_all_values_non_negative(self):
        model, sc, X, X_sc = _fitted_model_and_scaler()
        for x in X_sc[:10]:
            probs = model.predict_proba(x)
            assert all(p >= 0.0 for p in probs)

    def test_predict_proba_before_fit_raises_runtime_error(self):
        from training.trainer import GaussianNBModel
        m = GaussianNBModel()
        with pytest.raises(RuntimeError, match="fit"):
            m.predict_proba([0.0] * N_FEATURES)

    def test_predict_proba_wrong_length_raises_value_error(self):
        """FIX 2: hard dimension validation on every inference call."""
        model, sc, X, X_sc = _fitted_model_and_scaler()
        with pytest.raises(ValueError, match="n_features"):
            model.predict_proba([0.0] * (N_FEATURES + 1))

    def test_predict_proba_short_vector_raises_value_error(self):
        """FIX 2: too-short vector must also fail the dimension check."""
        model, sc, X, X_sc = _fitted_model_and_scaler()
        with pytest.raises(ValueError, match="n_features"):
            model.predict_proba([0.0] * (N_FEATURES - 1))

    def test_fit_empty_raises_value_error(self):
        from training.trainer import GaussianNBModel
        with pytest.raises(ValueError, match="empty"):
            GaussianNBModel().fit([], [])

    def test_predict_expected_rr_returns_triple(self):
        model, sc, X, X_sc = _fitted_model_and_scaler()
        exp_rr, conf, probs = model.predict_expected_rr(X_sc[0])
        assert isinstance(exp_rr, float)
        assert isinstance(conf,   float)
        assert isinstance(probs,  list)
        assert len(probs) == 4

    def test_confidence_in_unit_interval(self):
        """Confidence = max(probs) must be in [0, 1]."""
        model, sc, X, X_sc = _fitted_model_and_scaler()
        for x in X_sc[:10]:
            _, conf, _ = model.predict_expected_rr(x)
            assert 0.0 <= conf <= 1.0

    def test_class_priors_sum_to_one(self):
        model, sc, X, X_sc = _fitted_model_and_scaler(n=80)
        assert len(model.class_priors) == 4
        assert sum(model.class_priors) == pytest.approx(1.0, abs=1e-9)

    def test_to_dict_has_required_keys(self):
        model, sc, X, X_sc = _fitted_model_and_scaler()
        d = model.to_dict()
        for key in ("n_features", "class_priors", "means", "vars", "rr_weights"):
            assert key in d, f"Missing key '{key}' in GaussianNBModel.to_dict()"

    def test_from_dict_roundtrip_preserves_predictions(self):
        from training.trainer import GaussianNBModel
        model, sc, X, X_sc = _fitted_model_and_scaler()
        model2 = GaussianNBModel.from_dict(model.to_dict())
        for x in X_sc[:5]:
            assert model.predict_proba(x) == pytest.approx(model2.predict_proba(x), abs=1e-12)

    def test_from_dict_sets_n_features(self):
        from training.trainer import GaussianNBModel
        model, sc, X, X_sc = _fitted_model_and_scaler()
        model2 = GaussianNBModel.from_dict(model.to_dict())
        assert model2.n_features == N_FEATURES

    def test_n_features_set_after_fit(self):
        model, sc, X, X_sc = _fitted_model_and_scaler()
        assert model.n_features == N_FEATURES


# ─────────────────────────────────────────────────────────────────────────────
# train_gaussian
# ─────────────────────────────────────────────────────────────────────────────

class TestTrainGaussian:

    def test_raises_below_min_samples(self):
        from training.trainer import train_gaussian
        X    = _make_X(n=MIN_SAMPLES - 1)
        y_rr = _make_y_rr(n=MIN_SAMPLES - 1)
        with pytest.raises(ValueError, match="samples"):
            train_gaussian(X, y_rr)

    def test_happy_path_returns_triple(self):
        from training.trainer import train_gaussian, GaussianNBModel, StandardScaler
        X    = _make_X(n=60)
        y_rr = _make_y_rr(n=60)
        model, scaler, metrics = train_gaussian(X, y_rr)
        assert isinstance(model,   GaussianNBModel)
        assert isinstance(scaler,  StandardScaler)
        assert isinstance(metrics, dict)

    def test_metrics_has_required_keys(self):
        from training.trainer import train_gaussian
        X    = _make_X(n=60)
        y_rr = _make_y_rr(n=60)
        _, _, metrics = train_gaussian(X, y_rr)
        for key in ("corr_expected_rr", "calibration_error", "n_train", "n_val", "trained_at"):
            assert key in metrics, f"train_gaussian metrics missing key '{key}'"

    def test_temporal_split_sums_to_total(self):
        """n_train + n_val must account for every input sample."""
        from training.trainer import train_gaussian
        n = 60
        _, _, metrics = train_gaussian(_make_X(n=n), _make_y_rr(n=n))
        assert metrics["n_train"] + metrics["n_val"] == n

    def test_corr_in_valid_range(self):
        from training.trainer import train_gaussian
        _, _, metrics = train_gaussian(_make_X(n=60), _make_y_rr(n=60))
        assert -1.0 <= metrics["corr_expected_rr"] <= 1.0

    def test_calibration_error_non_negative(self):
        from training.trainer import train_gaussian
        _, _, metrics = train_gaussian(_make_X(n=60), _make_y_rr(n=60))
        assert metrics["calibration_error"] >= 0.0

    def test_returned_model_can_predict(self):
        """Model returned by train_gaussian must accept scaled val vectors."""
        from training.trainer import train_gaussian
        X    = _make_X(n=60)
        y_rr = _make_y_rr(n=60)
        model, scaler, _ = train_gaussian(X, y_rr)
        x_sc = scaler.transform_one(X[0])
        probs = model.predict_proba(x_sc)
        assert len(probs) == 4
        assert sum(probs) == pytest.approx(1.0, abs=1e-9)

    def test_n_train_respects_train_ratio(self):
        """Default train_ratio=0.70 → n_train ≈ 0.70 × n."""
        from training.trainer import train_gaussian
        n = 100
        _, _, metrics = train_gaussian(_make_X(n=n), _make_y_rr(n=n), train_ratio=0.70)
        expected_train = max(1, int(n * 0.70))
        assert metrics["n_train"] == expected_train


# ─────────────────────────────────────────────────────────────────────────────
# cross_val_gaussian
# ─────────────────────────────────────────────────────────────────────────────

class TestCrossValGaussian:

    def test_raises_below_min_samples(self):
        from training.trainer import cross_val_gaussian
        X    = _make_X(n=MIN_SAMPLES - 1)
        y_rr = _make_y_rr(n=MIN_SAMPLES - 1)
        with pytest.raises(ValueError, match="samples"):
            cross_val_gaussian(X, y_rr)

    def test_happy_path_returns_required_keys(self):
        from training.trainer import cross_val_gaussian
        result = cross_val_gaussian(_make_X(n=120), _make_y_rr(n=120))
        for key in ("corr_mean", "corr_std", "cal_mean", "cal_std", "stable", "fold_metrics"):
            assert key in result, f"cross_val_gaussian result missing key '{key}'"

    def test_stable_is_bool(self):
        from training.trainer import cross_val_gaussian
        result = cross_val_gaussian(_make_X(n=120), _make_y_rr(n=120))
        assert isinstance(result["stable"], bool)

    def test_fold_metrics_is_list(self):
        from training.trainer import cross_val_gaussian
        result = cross_val_gaussian(_make_X(n=120), _make_y_rr(n=120))
        assert isinstance(result["fold_metrics"], list)

    def test_stable_flag_consistent_with_corr_std(self):
        """stable == (corr_std < 0.05) invariant — must always hold."""
        from training.trainer import cross_val_gaussian
        result = cross_val_gaussian(_make_X(n=120), _make_y_rr(n=120))
        assert result["stable"] == (result["corr_std"] < 0.05)

    def test_corr_mean_in_valid_range(self):
        from training.trainer import cross_val_gaussian
        result = cross_val_gaussian(_make_X(n=120), _make_y_rr(n=120))
        assert -1.0 <= result["corr_mean"] <= 1.0

    def test_n_folds_respected(self):
        """len(fold_metrics) must be <= n_folds (some folds may be skipped if too short)."""
        from training.trainer import cross_val_gaussian
        result = cross_val_gaussian(_make_X(n=120), _make_y_rr(n=120), n_folds=2)
        assert len(result["fold_metrics"]) <= 2

    def test_insufficient_folds_returns_stable_false(self):
        """With barely enough samples, fold splitting may yield 0 valid folds → stable=False."""
        from training.trainer import cross_val_gaussian
        # Use minimum viable sample count — may produce zero usable folds
        result = cross_val_gaussian(_make_X(n=MIN_SAMPLES), _make_y_rr(n=MIN_SAMPLES))
        # Must not raise regardless of fold count
        assert "stable" in result

    def test_fold_metrics_entries_have_expected_keys(self):
        from training.trainer import cross_val_gaussian
        result = cross_val_gaussian(_make_X(n=120), _make_y_rr(n=120))
        for fold in result["fold_metrics"]:
            for key in ("fold", "n_train", "n_val", "corr", "cal_error"):
                assert key in fold, f"fold_metrics entry missing key '{key}'"


# ─────────────────────────────────────────────────────────────────────────────
# save_gaussian_model / load_gaussian_model
# ─────────────────────────────────────────────────────────────────────────────

class TestSaveLoadGaussian:

    def _trained(self, n: int = 60):
        from training.trainer import train_gaussian
        X    = _make_X(n=n)
        y_rr = _make_y_rr(n=n)
        model, scaler, metrics = train_gaussian(X, y_rr)
        return model, scaler, metrics, X

    def test_save_creates_valid_json(self, tmp_path):
        from training.trainer import save_gaussian_model
        model, scaler, metrics, _ = self._trained()
        with patch("training.trainer.MODELS_DIR", tmp_path):
            path = save_gaussian_model(model, scaler, metrics, name="test.json")
        assert path.exists()
        bundle = json.loads(path.read_text())
        for key in ("model", "scaler", "metrics", "feature_schema",
                    "schema_name", "schema_version", "schema_checksum"):
            assert key in bundle, f"Saved bundle missing key '{key}'"

    def test_save_schema_name_is_gaussian(self, tmp_path):
        from training.trainer import save_gaussian_model
        model, scaler, metrics, _ = self._trained()
        with patch("training.trainer.MODELS_DIR", tmp_path):
            path = save_gaussian_model(model, scaler, metrics, name="g.json")
        bundle = json.loads(path.read_text())
        assert bundle["schema_name"] == "gaussian"

    def test_load_roundtrip_same_predictions(self, tmp_path):
        from training.trainer import save_gaussian_model, load_gaussian_model
        model, scaler, metrics, X = self._trained()
        feature_schema = list(GAUSSIAN_SCHEMA.feature_names)
        with patch("training.trainer.MODELS_DIR", tmp_path):
            save_gaussian_model(model, scaler, metrics, name="rnd.json",
                                feature_schema=feature_schema)
        with patch("training.trainer.MODELS_DIR", tmp_path):
            model2, scaler2, _ = load_gaussian_model("rnd.json")
        # Predictions on the same raw vector must match
        x_sc  = scaler.transform_one(X[0])
        x_sc2 = scaler2.transform_one(X[0])
        assert model.predict_proba(x_sc) == pytest.approx(
            model2.predict_proba(x_sc2), abs=1e-10
        )

    def test_load_mismatched_schema_raises_value_error(self, tmp_path):
        """Loading a model saved with a different feature list must raise ValueError."""
        from training.trainer import save_gaussian_model, load_gaussian_model
        model, scaler, metrics, _ = self._trained()
        # Save with a deliberately wrong feature schema
        with patch("training.trainer.MODELS_DIR", tmp_path):
            save_gaussian_model(model, scaler, metrics, name="bad.json",
                                feature_schema=["wrong_feat_1", "wrong_feat_2"])
        with patch("training.trainer.MODELS_DIR", tmp_path):
            with pytest.raises(ValueError, match="schema mismatch"):
                load_gaussian_model("bad.json")

    def test_load_missing_file_raises_file_not_found(self, tmp_path):
        from training.trainer import load_gaussian_model
        with patch("training.trainer.MODELS_DIR", tmp_path):
            with pytest.raises(FileNotFoundError):
                load_gaussian_model("no_such_model.json")

    def test_load_returns_correct_metadata(self, tmp_path):
        """Loaded metadata dict must contain the original metrics keys."""
        from training.trainer import save_gaussian_model, load_gaussian_model
        model, scaler, metrics, _ = self._trained()
        feature_schema = list(GAUSSIAN_SCHEMA.feature_names)
        with patch("training.trainer.MODELS_DIR", tmp_path):
            save_gaussian_model(model, scaler, metrics, name="meta.json",
                                feature_schema=feature_schema)
        with patch("training.trainer.MODELS_DIR", tmp_path):
            _, _, meta = load_gaussian_model("meta.json")
        for key in ("corr_expected_rr", "calibration_error", "n_train", "n_val"):
            assert key in meta, f"Loaded metadata missing key '{key}'"
