"""
tests/test_acceptance_controller.py

Tests for core/acceptance_controller.py — AcceptanceController.
"""

from __future__ import annotations

import sys
import os
import pytest
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config_layer.strict_config import ConfigKeyMissingError
from core.acceptance_controller import AcceptanceController

# EPIC-84 STORY-84.2: the module constants _MIN_HISTORY/_THETA_MIN/_THETA_MAX and the in-code
# .get() defaults are gone. Tests pass a complete config (active-config values + the declared
# cold-path thresholds) and override per test.
_THETA_MIN = 0.50
_THETA_MAX = 0.95
_BASE = {
    "theta_min": _THETA_MIN, "theta_max": _THETA_MAX, "min_history": 10,
    "fusion_percentile": 85, "acceptance_alpha": 0.01, "acceptance_target_low": 0.05,
    "acceptance_target_high": 0.15, "acceptance_k_sigma": 1.0, "acceptance_window": 200,
    "engine_threshold": 0.60, "fusion_threshold": 0.65, "score_threshold": 0.45,
}


def _ctrl(overrides: dict | None = None) -> AcceptanceController:
    return AcceptanceController({**_BASE, **(overrides or {})})


def _fill(ctrl, n, accepted, fusion_score=0.6, engine_score=0.6):
    for _ in range(n):
        ctrl.update_metrics({"crt": engine_score}, fusion_score, accepted=accepted)
        ctrl.adjust_thresholds()


# ──────────────────────────────────────────────────────────────────────────────
# Test 10: theta bounds respected under aggressive alpha
# ──────────────────────────────────────────────────────────────────────────────

def test_theta_upper_bound_respected():
    ctrl = _ctrl({"acceptance_alpha": 0.5})
    _fill(ctrl, 1000, accepted=True, fusion_score=0.9)
    assert ctrl.get_thresholds()["score_threshold"] <= _THETA_MAX


def test_theta_lower_bound_respected():
    ctrl = _ctrl({"acceptance_alpha": 0.5})
    _fill(ctrl, 1000, accepted=False, fusion_score=0.1)
    assert ctrl.get_thresholds()["score_threshold"] >= _THETA_MIN


# ──────────────────────────────────────────────────────────────────────────────
# Test 11: fusion_threshold is approximately the 85th percentile
# ──────────────────────────────────────────────────────────────────────────────

def test_fusion_threshold_is_85th_percentile():
    ctrl = _ctrl()
    scores = [i / 100.0 for i in range(1, 101)]  # 0.01 … 1.00
    for s in scores:
        ctrl.update_metrics({"crt": 0.5}, s, accepted=False)

    thresholds = ctrl.compute_thresholds()
    expected_85th = np.percentile(scores, 85)
    assert abs(thresholds["fusion_threshold"] - expected_85th) < 0.02, \
        f"Expected ~{expected_85th:.3f}, got {thresholds['fusion_threshold']}"


# ──────────────────────────────────────────────────────────────────────────────
# Test: returns the configured cold-path thresholds when history < min_history
# ──────────────────────────────────────────────────────────────────────────────

def test_returns_defaults_when_cold():
    ctrl = _ctrl({"score_threshold": 0.45})
    # No updates — cold
    thresholds = ctrl.get_thresholds()
    assert thresholds["score_threshold"] == pytest.approx(0.45, abs=0.001)


def test_adjust_thresholds_noop_when_cold():
    ctrl = _ctrl()
    initial_state = ctrl.state()
    ctrl.adjust_thresholds()  # cold — should not change theta
    assert ctrl.state()["theta"] == initial_state["theta"]


# ──────────────────────────────────────────────────────────────────────────────
# Test: engine_threshold = mean + k*std
# ──────────────────────────────────────────────────────────────────────────────

def test_engine_threshold_formula():
    ctrl = _ctrl({"acceptance_k_sigma": 1.0})
    scores = [0.5, 0.6, 0.7, 0.4, 0.55]
    # Repeat twice to satisfy _MIN_HISTORY=10; mean/std unchanged by repetition
    for s in scores * 2:
        ctrl.update_metrics({"crt": s}, 0.5, accepted=False)

    thresholds = ctrl.compute_thresholds()
    expected = np.mean(scores) + 1.0 * np.std(scores)
    expected_clamped = max(_THETA_MIN, min(_THETA_MAX, expected))
    assert abs(thresholds["engine_threshold"] - expected_clamped) < 0.01


# ──────────────────────────────────────────────────────────────────────────────
# Test: acceptance_rate() returns None when no data
# ──────────────────────────────────────────────────────────────────────────────

def test_acceptance_rate_none_when_empty():
    ctrl = _ctrl()
    assert ctrl.acceptance_rate() is None


def test_acceptance_rate_correct():
    ctrl = _ctrl()
    for _ in range(8):
        ctrl.update_metrics({"crt": 0.5}, 0.5, accepted=True)
    for _ in range(2):
        ctrl.update_metrics({"crt": 0.5}, 0.5, accepted=False)

    rate = ctrl.acceptance_rate()
    assert rate is not None
    assert abs(rate - 0.8) < 0.01


# ──────────────────────────────────────────────────────────────────────────────
# Test: integral control moves theta in correct direction
# ──────────────────────────────────────────────────────────────────────────────

def test_theta_increases_when_above_target():
    ctrl = _ctrl({"acceptance_alpha": 0.05})
    initial_theta = ctrl._theta
    # Force high acceptance rate (above target_high=0.15)
    _fill(ctrl, 50, accepted=True, fusion_score=0.9)
    assert ctrl._theta > initial_theta, "Theta must increase when acceptance rate > target"


def test_theta_decreases_when_below_target():
    ctrl = _ctrl({"acceptance_alpha": 0.05})
    # Start with a high theta so we have room to decrease
    ctrl._theta = 0.80
    # Force zero acceptance rate (below target_low=0.05)
    _fill(ctrl, 50, accepted=False, fusion_score=0.2)
    assert ctrl._theta < 0.80, "Theta must decrease when acceptance rate < target"


# ──────────────────────────────────────────────────────────────────────────────
# EPIC-84: rewritten "defaults" behaviour — missing keys now raise
# ──────────────────────────────────────────────────────────────────────────────

def test_empty_config_raises_listing_all_keys():
    with pytest.raises(ConfigKeyMissingError) as ei:
        AcceptanceController({})
    assert set(ei.value.missing) == set(_BASE)


@pytest.mark.parametrize("key", sorted(_BASE))
def test_missing_key_raises(key):
    with pytest.raises(ConfigKeyMissingError) as ei:
        AcceptanceController({k: v for k, v in _BASE.items() if k != key})
    assert ei.value.missing == (key,)
