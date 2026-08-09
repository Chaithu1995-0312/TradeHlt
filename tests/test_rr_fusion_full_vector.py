"""
F-038 Fix A — rr_fusion full-vector mode.

The defect: engine_runner fed `RRFusionLayer.score_dict()` only 3 of 38 features
(retest_depth/body_ratio/disp_strength), starving the model → confidence≈1e-88 →
100% gaussian bypass. Fix A routes through the existing `RRFusionLayer.score()` (full
canonical vector) behind the config knob `engine_runner.rr_fusion.full_feature_vector`.

These tests prove the two paths differ in how many features reach the model, using a
fake inference engine (no dependence on the real models/rr_model.json).
"""
from __future__ import annotations

from config_layer.rr.rr_fusion import RRFusionLayer
from features.feature_schema import CANONICAL_FEATURES
from core.engine_runner import ENGINE_RUNNER_DEFAULTS


class _FakeEngine:
    """Records how many nonzero features reach predict(); returns a fixed success result."""

    def __init__(self) -> None:
        self.last_nonzero: int | None = None
        self.W = [0.0] * len(CANONICAL_FEATURES)

    def predict(self, features, gaussian_score, gaussian_p_win, threshold=0.5):
        self.last_nonzero = sum(1 for f in features if abs(float(f)) > 1e-12)
        return {"final_score": 0.42, "status": "success", "confidence": 0.9,
                "expected_rr": 0.0, "probability_of_win": 0.5}


def _layer_with_fake() -> tuple[RRFusionLayer, _FakeEngine]:
    layer = RRFusionLayer(enabled=False)   # skip the real model load
    layer._enabled = True
    layer._loaded = True
    fake = _FakeEngine()
    layer._engine = fake
    return layer, fake


def test_score_dict_starves_the_model_to_three_features():
    """The legacy stub path: only depth/body/disp are nonzero."""
    layer, fake = _layer_with_fake()
    layer.score_dict(depth=0.2, body=0.8, disp=0.5, gaussian_score=0.7, gaussian_p_win=0.7,
                     is_asia=0.0, is_london=1.0, is_newyork=0.0, hour=10)
    assert fake.last_nonzero is not None
    assert fake.last_nonzero <= 3   # the F-038 defect: 2-3 of 38


def test_score_full_feeds_many_features():
    """Fix A path: score() feeds the full canonical vector → many nonzero features."""
    layer, fake = _layer_with_fake()
    trade = {k: 0.25 for k in CANONICAL_FEATURES}   # all continuous, in-range, no drift (<1.5)
    trade["gaussian_score"] = 0.7
    trade["gaussian_p_win"] = 0.7
    layer.score(trade)
    assert fake.last_nonzero is not None
    assert fake.last_nonzero > 3            # strictly more than the stub
    assert fake.last_nonzero >= 10          # genuinely the full vector, not a few


def test_config_knob_default_is_false():
    """Default preserves the legacy (byte-identical) path."""
    assert ENGINE_RUNNER_DEFAULTS["rr_fusion"].get("full_feature_vector") is False
