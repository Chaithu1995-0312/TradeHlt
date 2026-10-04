"""
test_ema_momentum_kernel_slot.py
================================
The fusion slot is EmaMomentumKernel. Schema width stays 48.
"""

import inspect

import pytest


@pytest.fixture
def feature_dict_32():
    """A minimal 48-dim canonical feature dict (name kept for test stability)."""
    from features.feature_schema import CANONICAL_FEATURES
    d = {k: 0.0 for k in CANONICAL_FEATURES}
    d["ema_fast"] = 1.01
    d["ema_slow"] = 1.00
    d["momentum_score"] = 0.1
    return d


def test_tradenet_schema_is_32():
    from features.feature_schema import TRADENET_SCHEMA, CANONICAL_FEATURES, CANONICAL_FEATURE_DIM
    assert TRADENET_SCHEMA.n_features == len(CANONICAL_FEATURES) == CANONICAL_FEATURE_DIM == 48


def test_gaussian_schema_is_32():
    from features.feature_schema import GAUSSIAN_SCHEMA, CANONICAL_FEATURES, CANONICAL_FEATURE_DIM
    assert GAUSSIAN_SCHEMA.n_features == len(CANONICAL_FEATURES) == CANONICAL_FEATURE_DIM == 48


def test_schema_object_attribute_and_dict_access():
    from features.feature_schema import TRADENET_SCHEMA, GAUSSIAN_SCHEMA, SchemaObject
    assert isinstance(TRADENET_SCHEMA, SchemaObject)
    assert isinstance(GAUSSIAN_SCHEMA, SchemaObject)
    assert TRADENET_SCHEMA.n_features == 48
    assert GAUSSIAN_SCHEMA.n_features == 48
    assert TRADENET_SCHEMA["n_features"] == 48
    assert GAUSSIAN_SCHEMA.get("n_features") == 48
    assert len(TRADENET_SCHEMA.feature_names) == 48
    assert len(GAUSSIAN_SCHEMA.checksum) == 32


def test_validate_vector_with_label():
    from features.feature_schema import validate_vector, GAUSSIAN_SCHEMA
    vec = [0.0] * GAUSSIAN_SCHEMA.n_features
    assert validate_vector(vec, GAUSSIAN_SCHEMA, label="test_label") is True


def test_validate_vector_raises_on_mismatch():
    from features.feature_schema import validate_vector, GAUSSIAN_SCHEMA
    with pytest.raises(ValueError, match="expected 48"):
        validate_vector([0.0] * 10, GAUSSIAN_SCHEMA, label="wrong_dim")


def test_trainer_n_features_is_32():
    from training.trainer import N_FEATURES, GAUSSIAN_N_FEATURES
    from features.feature_schema import CANONICAL_FEATURE_DIM
    assert N_FEATURES == CANONICAL_FEATURE_DIM == 48, f"TradeNet N_FEATURES={N_FEATURES}"
    assert GAUSSIAN_N_FEATURES == CANONICAL_FEATURE_DIM == 48


def test_heuristic_engine_import():
    from engines.ema_momentum_kernel import EmaMomentumKernel
    assert EmaMomentumKernel is not None


def test_ml_engine_import():
    from engines.ml_gaussian_engine import MLGaussianEngine
    assert MLGaussianEngine is not None


def test_retired_module_exports_no_alias():
    import engines.gaussian_engine as ge
    assert not hasattr(ge, "GaussianEngine")
    assert not hasattr(ge, "EmaMomentumKernel")


def test_heuristic_engine_compute_32dim(feature_dict_32):
    from engines.ema_momentum_kernel import EmaMomentumKernel
    engine = EmaMomentumKernel(config={"gaussian_mu": 0.0, "gaussian_sigma": 1.0}, instrument="XAUUSD")
    result = engine.compute(feature_dict_32)
    assert "score" in result
    assert 0.0 <= result["score"] <= 1.0
    assert "reason" in result


def test_ml_engine_fallback_no_model(feature_dict_32):
    from engines.ml_gaussian_engine import MLGaussianEngine
    engine = MLGaussianEngine(config={})
    result = engine.compute(feature_dict_32)
    assert "score" in result
    assert 0.0 <= result["score"] <= 1.0
    if result.get("reason") == "ml_gaussian_fallback":
        assert result["score"] == 0.5


def test_runner_slot_source_is_fixed():
    from core.engine_runner import EngineRunner
    from engines.ema_momentum_kernel import EmaMomentumKernel
    src = inspect.getsource(EngineRunner.__init__)
    assert "EmaMomentumKernel" in src
    assert "MLGaussianEngine" not in src
    assert not hasattr(EngineRunner, "_get_gaussian_engine")
    assert not hasattr(EngineRunner, "_get_shadow_gaussian_engine")


def test_kernel_without_instrument_raises():
    from engines.ema_momentum_kernel import EmaMomentumKernel
    with pytest.raises(ValueError, match="no instrument"):
        EmaMomentumKernel(config={})
