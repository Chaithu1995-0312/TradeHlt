"""
P0 2026-07-22 — RR Fusion FAIL_CLOSED on feature-dimension mismatch.

Closes the FAIL_OPEN path where NanoInferenceEngine.predict silently truncated
longer vectors (schema v4 39-dim → model 38-dim index slice).

Contract:
  - exact width only at predict()
  - RRFusionLayer refuses load when model n_features != CANONICAL_FEATURE_DIM
  - no silent truncate/pad
"""
from __future__ import annotations

import pytest

from config_layer.rr.rr_pattern_miner import (
    FeatureDimensionError,
    NanoInferenceEngine,
    DEFAULT_MODEL_PATH,
)
from config_layer.rr.rr_fusion import RRFusionLayer
from features.feature_schema import CANONICAL_FEATURE_DIM, CANONICAL_FEATURES


@pytest.fixture(scope="module")
def engine() -> NanoInferenceEngine:
    return NanoInferenceEngine.load(DEFAULT_MODEL_PATH)


def test_predict_rejects_overlong_vector_no_truncate(engine: NanoInferenceEngine):
    n = len(engine.W)
    overlong = [0.0] * (n + 1)  # classic v4→v3 FAIL_OPEN input
    with pytest.raises(FeatureDimensionError) as ei:
        engine.predict(
            features=overlong,
            gaussian_score=0.5,
            gaussian_p_win=0.5,
            threshold=0.5,
        )
    msg = str(ei.value)
    assert str(n) in msg
    assert str(n + 1) in msg
    assert "truncate" in msg.lower() or "Refusing" in msg


def test_predict_rejects_short_vector(engine: NanoInferenceEngine):
    n = len(engine.W)
    if n < 2:
        pytest.skip("degenerate model")
    short = [0.0] * (n - 1)
    with pytest.raises(FeatureDimensionError):
        engine.predict(features=short, gaussian_score=0.5, gaussian_p_win=0.5)


def test_predict_exact_width_still_runs(engine: NanoInferenceEngine):
    n = len(engine.W)
    exact = [0.0] * n
    out = engine.predict(
        features=exact,
        gaussian_score=0.42,
        gaussian_p_win=0.6,
        threshold=0.5,
    )
    assert "status" in out
    assert "final_score" in out
    # Under legacy confidence gate the zero vector still bypasses (F-044) —
    # that is orthogonal to the dimension contract.
    assert out["status"] in {
        "bypassed_low_confidence",
        "success",
        "capped_by_threshold",
    }


def test_live_canonical_vector_is_rejected_against_v3_model(engine: NanoInferenceEngine):
    """Spine feeds CANONICAL_FEATURE_DIM; current rr_model is 38 under v4=39."""
    model_n = len(engine.W)
    if model_n == CANONICAL_FEATURE_DIM:
        pytest.skip("model already matches live schema — no dim gap to assert")
    live = [0.0] * CANONICAL_FEATURE_DIM
    with pytest.raises(FeatureDimensionError) as ei:
        engine.predict(features=live, gaussian_score=0.5, gaussian_p_win=0.5)
    assert str(model_n) in str(ei.value)
    assert str(CANONICAL_FEATURE_DIM) in str(ei.value)


def test_rr_fusion_layer_refuses_load_on_canonical_dim_mismatch():
    """When enabled, layer must not report is_loaded if model width ≠ live schema."""
    layer = RRFusionLayer(model_path=DEFAULT_MODEL_PATH, enabled=True)
    model = NanoInferenceEngine.load(DEFAULT_MODEL_PATH)
    model_n = len(model.W)
    if model_n == CANONICAL_FEATURE_DIM:
        # After a future remap/retrain this becomes a positive load test.
        assert layer.is_loaded is True
        return
    assert layer.is_loaded is False
    assert "FeatureDimensionError" in (layer.load_error or "")
    assert str(model_n) in (layer.load_error or "")
    assert str(CANONICAL_FEATURE_DIM) in (layer.load_error or "")


def test_rr_fusion_score_passthrough_when_not_loaded_due_to_dim():
    """Spine-safe: score() does not invent ML scores when load was refused."""
    layer = RRFusionLayer(model_path=DEFAULT_MODEL_PATH, enabled=True)
    model_n = len(NanoInferenceEngine.load(DEFAULT_MODEL_PATH).W)
    if model_n == CANONICAL_FEATURE_DIM:
        pytest.skip("model matches live schema")
    assert layer.is_loaded is False
    out = layer.score(
        {
            **{k: 0.1 for k in CANONICAL_FEATURES},
            "gaussian_score": 0.77,
            "gaussian_p_win": 0.66,
        }
    )
    assert out["status"] == "model_not_loaded"
    assert out["final_score"] == pytest.approx(0.77)


def test_score_path_feature_dimension_mismatch_status_if_engine_forced():
    """If a mismatched engine is forced onto a loaded layer, predict refuses cleanly."""
    layer = RRFusionLayer(enabled=False)
    layer._enabled = True
    layer._loaded = True
    layer._engine = NanoInferenceEngine.load(DEFAULT_MODEL_PATH)
    model_n = len(layer._engine.W)
    if model_n == CANONICAL_FEATURE_DIM:
        pytest.skip("model matches live schema — force path not exercisable")

    trade = {k: 0.1 for k in CANONICAL_FEATURES}
    trade["gaussian_score"] = 0.55
    trade["gaussian_p_win"] = 0.55
    # All continuous values below drift threshold
    trade["retest_depth"] = 0.2
    trade["body_ratio"] = 0.5
    trade["disp_strength"] = 0.4

    out = layer.score(trade)
    assert out["status"] == "feature_dimension_mismatch"
    assert out["final_score"] == pytest.approx(0.55)
