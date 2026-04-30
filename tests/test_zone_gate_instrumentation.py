"""
tests/test_zone_gate_instrumentation.py

Tests for zone_gate_engine.py instrumentation:
  - execution_mode force_pass
  - empty zones / no crash
  - counters
  - soft zone score helper
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engines.zone_gate_engine import (
    run_zone_gate_engine,
    get_zone_gate_counters,
    reset_zone_gate_counters,
    _compute_soft_zone_score,
)

# Minimal canonical features — use a real import if available
try:
    from features.feature_schema import CANONICAL_FEATURE_ORDER
    _RAW = {k: 0.0 for k in CANONICAL_FEATURE_ORDER}
except ImportError:
    pytest.skip("feature_schema not available", allow_module_level=True)


def _low_model(vector):
    """Always returns 0.1 — well below threshold."""
    return 0.1


def _high_model(vector):
    """Always returns 0.9 — above threshold."""
    return 0.9


@pytest.fixture(autouse=True)
def reset_counters():
    reset_zone_gate_counters()
    yield
    reset_zone_gate_counters()


# ──────────────────────────────────────────────────────────────────────────────
# Test 1: force_pass overrides block but preserves real decision
# ──────────────────────────────────────────────────────────────────────────────

def test_force_pass_overrides_block_but_logs_real():
    raw = dict(_RAW)
    raw["close"] = 1.2345

    result = run_zone_gate_engine(
        raw_features=raw,
        model_fn=_low_model,
        threshold=0.5,
        execution_mode="force_pass",
    )

    assert result["passed"] is True, "force_pass must override to True"
    assert result["force_pass_override"] is True
    assert result["real_passed"] is False, "real decision must be False when score < threshold"
    assert abs(result["score"] - 0.1) < 0.01


# ──────────────────────────────────────────────────────────────────────────────
# Test 2: force_pass with high score — real_passed should be True
# ──────────────────────────────────────────────────────────────────────────────

def test_force_pass_high_score_real_passed_is_true():
    result = run_zone_gate_engine(
        raw_features=dict(_RAW),
        model_fn=_high_model,
        threshold=0.5,
        execution_mode="force_pass",
    )

    assert result["passed"] is True
    assert result["force_pass_override"] is True
    assert result["real_passed"] is True


# ──────────────────────────────────────────────────────────────────────────────
# Test 3: normal mode — counters update correctly
# ──────────────────────────────────────────────────────────────────────────────

def test_normal_mode_pass_counter_increments():
    run_zone_gate_engine(raw_features=dict(_RAW), model_fn=_high_model, threshold=0.5)
    counters = get_zone_gate_counters()
    assert counters["total_pass"] == 1
    assert counters["total_block"] == 0


def test_normal_mode_block_counter_increments():
    run_zone_gate_engine(raw_features=dict(_RAW), model_fn=_low_model, threshold=0.5)
    counters = get_zone_gate_counters()
    assert counters["total_block"] == 1
    assert counters["total_pass"] == 0


# ──────────────────────────────────────────────────────────────────────────────
# Test 4: zone_debug_config is accepted without crashing
# ──────────────────────────────────────────────────────────────────────────────

def test_debug_config_does_not_crash():
    raw = dict(_RAW)
    raw["close"] = 1.5

    zone_debug = {
        "zones_loaded_count": 3,
        "inside_zone": True,
        "zone_strength": 0.8,
        "zone_freshness": 0.6,
        "distance_to_nearest": 0.002,
    }

    result = run_zone_gate_engine(
        raw_features=raw,
        model_fn=_high_model,
        threshold=0.5,
        zone_debug_config=zone_debug,
    )

    assert "passed" in result
    assert "score" in result


# ──────────────────────────────────────────────────────────────────────────────
# Test 5: soft zone score helper
# ──────────────────────────────────────────────────────────────────────────────

def test_soft_zone_score_range():
    features = {
        "zone_distance":  0.0,   # closest possible → exp(0) = 1.0
        "zone_freshness": 1.0,
        "zone_strength":  1.0,
    }
    score = _compute_soft_zone_score(features)
    assert 0.0 <= score <= 1.0

    features_far = {
        "zone_distance":  10.0,  # very far
        "zone_freshness": 0.0,
        "zone_strength":  0.0,
    }
    score_far = _compute_soft_zone_score(features_far)
    assert score_far < score, "farther zone must score lower"


def test_soft_zone_score_clamped():
    # Weights sum to 1.0, all inputs at max → should be close to 1.0
    features = {"zone_distance": 0.0, "zone_freshness": 1.0, "zone_strength": 1.0}
    score = _compute_soft_zone_score(features)
    assert 0.0 <= score <= 1.0
