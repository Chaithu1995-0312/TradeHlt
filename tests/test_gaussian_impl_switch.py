"""
test_gaussian_impl_switch.py
============================
Tests for the configurable Gaussian engine (GAUSSIAN_IMPL env var switching)
and the 32-dim TradeNet/Gaussian schema upgrade.
"""

import os
import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Shared fixture: 32-dim feature dict
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def feature_dict_32():
    """A minimal 32-dim canonical feature dict."""
    from features.feature_schema import CANONICAL_FEATURES
    d = {k: 0.0 for k in CANONICAL_FEATURES}
    d["ema_fast"] = 1.01
    d["ema_slow"] = 1.00
    d["momentum_score"] = 0.1
    return d


# ─────────────────────────────────────────────────────────────────────────────
# Schema assertions
# ─────────────────────────────────────────────────────────────────────────────

def test_tradenet_schema_is_32():
    from features.feature_schema import TRADENET_SCHEMA, CANONICAL_FEATURES
    assert TRADENET_SCHEMA.n_features == len(CANONICAL_FEATURES) == 35


def test_gaussian_schema_is_32():
    from features.feature_schema import GAUSSIAN_SCHEMA, CANONICAL_FEATURES
    assert GAUSSIAN_SCHEMA.n_features == len(CANONICAL_FEATURES) == 35


def test_schema_object_attribute_and_dict_access():
    from features.feature_schema import TRADENET_SCHEMA, GAUSSIAN_SCHEMA, SchemaObject
    assert isinstance(TRADENET_SCHEMA, SchemaObject)
    assert isinstance(GAUSSIAN_SCHEMA, SchemaObject)
    # Attribute access
    assert TRADENET_SCHEMA.n_features == 35
    assert GAUSSIAN_SCHEMA.n_features == 35
    # Dict-style access
    assert TRADENET_SCHEMA["n_features"] == 35
    assert GAUSSIAN_SCHEMA.get("n_features") == 35
    # feature_names and checksum
    assert len(TRADENET_SCHEMA.feature_names) == 35
    assert len(GAUSSIAN_SCHEMA.checksum) == 32   # MD5 hex is always 32 chars


def test_validate_vector_with_label():
    from features.feature_schema import validate_vector, GAUSSIAN_SCHEMA
    vec32 = [0.0] * 35
    assert validate_vector(vec32, GAUSSIAN_SCHEMA, label="test_label") is True


def test_validate_vector_raises_on_mismatch():
    from features.feature_schema import validate_vector, GAUSSIAN_SCHEMA
    with pytest.raises(ValueError, match="expected 35"):
        validate_vector([0.0] * 10, GAUSSIAN_SCHEMA, label="wrong_dim")


# ─────────────────────────────────────────────────────────────────────────────
# Trainer N_FEATURES
# ─────────────────────────────────────────────────────────────────────────────

def test_trainer_n_features_is_32():
    from training.trainer import N_FEATURES, GAUSSIAN_N_FEATURES
    assert N_FEATURES == 35, f"TradeNet N_FEATURES={N_FEATURES}, expected 35"
    assert GAUSSIAN_N_FEATURES == 35, f"Gaussian N_FEATURES={GAUSSIAN_N_FEATURES}, expected 35"


# ─────────────────────────────────────────────────────────────────────────────
# Engine imports
# ─────────────────────────────────────────────────────────────────────────────

def test_heuristic_engine_import():
    from engines.heuristic_gaussian_engine import HeuristicGaussianEngine
    assert HeuristicGaussianEngine is not None


def test_ml_engine_import():
    from engines.ml_gaussian_engine import MLGaussianEngine
    assert MLGaussianEngine is not None


def test_gaussian_engine_is_heuristic_alias():
    from engines.gaussian_engine import GaussianEngine
    from engines.heuristic_gaussian_engine import HeuristicGaussianEngine
    assert GaussianEngine is HeuristicGaussianEngine


# ─────────────────────────────────────────────────────────────────────────────
# Heuristic engine compute with 32-dim dict
# ─────────────────────────────────────────────────────────────────────────────

def test_heuristic_engine_compute_32dim(feature_dict_32):
    from engines.heuristic_gaussian_engine import HeuristicGaussianEngine
    engine = HeuristicGaussianEngine(config={"gaussian_mu": 0.0, "gaussian_sigma": 1.0})
    result = engine.compute(feature_dict_32)
    assert "score" in result
    assert 0.0 <= result["score"] <= 1.0
    assert "reason" in result


# ─────────────────────────────────────────────────────────────────────────────
# ML engine graceful fallback (no trained model on disk)
# ─────────────────────────────────────────────────────────────────────────────

def test_ml_engine_fallback_no_model(feature_dict_32):
    from engines.ml_gaussian_engine import MLGaussianEngine
    engine = MLGaussianEngine(config={})
    result = engine.compute(feature_dict_32)
    assert "score" in result
    assert 0.0 <= result["score"] <= 1.0
    if result.get("reason") == "ml_gaussian_fallback":
        assert result["score"] == 0.5


# ─────────────────────────────────────────────────────────────────────────────
# EngineRunner GAUSSIAN_IMPL env-var switching
# ─────────────────────────────────────────────────────────────────────────────

def test_engine_runner_default_is_heuristic():
    os.environ.pop("GAUSSIAN_IMPL", None)
    from engines.heuristic_gaussian_engine import HeuristicGaussianEngine
    from core.engine_runner import EngineRunner
    engine = EngineRunner._get_gaussian_engine({})
    assert isinstance(engine, HeuristicGaussianEngine)


def test_engine_runner_ml_impl():
    os.environ["GAUSSIAN_IMPL"] = "ml"
    try:
        from engines.ml_gaussian_engine import MLGaussianEngine
        from core.engine_runner import EngineRunner
        engine = EngineRunner._get_gaussian_engine({})
        assert isinstance(engine, MLGaussianEngine)
    finally:
        del os.environ["GAUSSIAN_IMPL"]


def test_engine_runner_heuristic_explicit():
    os.environ["GAUSSIAN_IMPL"] = "heuristic"
    try:
        from engines.heuristic_gaussian_engine import HeuristicGaussianEngine
        from core.engine_runner import EngineRunner
        engine = EngineRunner._get_gaussian_engine({})
        assert isinstance(engine, HeuristicGaussianEngine)
    finally:
        del os.environ["GAUSSIAN_IMPL"]


def test_engine_runner_config_override():
    """Config-level gaussian_impl override works when env var is absent."""
    os.environ.pop("GAUSSIAN_IMPL", None)
    from engines.ml_gaussian_engine import MLGaussianEngine
    from core.engine_runner import EngineRunner
    engine = EngineRunner._get_gaussian_engine({"gaussian_impl": "ml"})
    assert isinstance(engine, MLGaussianEngine)


# ─────────────────────────────────────────────────────────────────────────────
# feature_builder shim
# ─────────────────────────────────────────────────────────────────────────────

def test_feature_dict_to_vector_returns_32(feature_dict_32):
    from features.feature_builder import feature_dict_to_vector
    vec = feature_dict_to_vector(feature_dict_32)
    assert len(vec) == 35
    assert all(isinstance(v, float) for v in vec)