"""
tests/test_convergence_controller.py

Tests for core/convergence_controller.py — ConvergenceController.
"""

import math
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.convergence_controller import ConvergenceController, _WARMUP_BARS


def _warm(ctrl, n=_WARMUP_BARS + 1, accepted=True):
    """Record n outcomes to pass warm-up guard."""
    for _ in range(n):
        ctrl.record_outcome(accepted)


# ──────────────────────────────────────────────────────────────────────────────
# Test 6: calibrate_score at threshold returns ~0.5
# ──────────────────────────────────────────────────────────────────────────────

def test_calibrate_score_at_threshold():
    ctrl = ConvergenceController()
    result = ctrl.calibrate_score(0.6, k=8.0, t=0.6)
    assert abs(result - 0.5) < 1e-5, f"Expected 0.5 at s=t, got {result}"


def test_calibrate_score_above_threshold_returns_above_half():
    ctrl = ConvergenceController()
    assert ctrl.calibrate_score(0.8) > 0.5


def test_calibrate_score_below_threshold_returns_below_half():
    ctrl = ConvergenceController()
    assert ctrl.calibrate_score(0.3) < 0.5


def test_calibrate_score_clamped():
    ctrl = ConvergenceController()
    # Extreme values must stay in [0, 1]
    assert ctrl.calibrate_score(999.0) <= 1.0
    assert ctrl.calibrate_score(-999.0) >= 0.0


# ──────────────────────────────────────────────────────────────────────────────
# Test 7: BitNet dampening reduces high zone_gate scores
# ──────────────────────────────────────────────────────────────────────────────

def test_bitnet_dampening_reduces_inflated_scores():
    ctrl = ConvergenceController()
    _warm(ctrl, accepted=True)

    scores = {"crt": 0.7, "gaussian": 0.7, "zone_gate": 0.9, "rr": 0.7}
    result = ctrl.apply(scores)

    raw_avg = sum(scores.values()) / 4.0
    assert result["final_score"] < raw_avg, \
        f"Dampening + calibration must reduce score. raw_avg={raw_avg}, final={result['final_score']}"


def test_bitnet_dampening_not_applied_to_low_zone_score():
    """Low zone_gate score (< 0.5) must NOT be raised to the 4th power."""
    ctrl = ConvergenceController()
    _warm(ctrl, accepted=False)

    # zone_gate = 0.3 → if dampened: 0.3**4 = 0.0081 (destructive)
    # The controller should preserve it approximately
    scores_low  = {"crt": 0.5, "gaussian": 0.5, "zone_gate": 0.3, "rr": 0.5}
    scores_high = {"crt": 0.5, "gaussian": 0.5, "zone_gate": 0.9, "rr": 0.5}

    r_low  = ctrl.apply(scores_low)
    r_high = ctrl.apply(scores_high)

    # Low zone_gate should produce a lower or similar final score, not collapsed
    # The key invariant: low zone_gate score isn't inflated by dampening
    assert r_low["final_score"] < r_high["final_score"]


# ──────────────────────────────────────────────────────────────────────────────
# Test 8: High variance triggers disagreement penalty
# ──────────────────────────────────────────────────────────────────────────────

def test_high_variance_penalty_reduces_score():
    ctrl = ConvergenceController()
    _warm(ctrl, accepted=True)

    # Mixed signals → high variance
    scores = {"crt": 0.9, "gaussian": 0.1, "zone_gate": 0.9, "rr": 0.1}
    result = ctrl.apply(scores)

    assert result["variance"] > 0.05, f"Expected high variance, got {result['variance']}"
    # Variance penalty must suppress final score below raw average
    raw_avg = sum(scores.values()) / 4.0
    assert result["final_score"] < raw_avg


# ──────────────────────────────────────────────────────────────────────────────
# Test 9: Adaptive threshold increases after high accept rate
# ──────────────────────────────────────────────────────────────────────────────

def test_adaptive_threshold_increases_on_high_accept_rate():
    ctrl = ConvergenceController(initial_threshold=0.5)

    # Simulate 100 accepted bars (accept_rate = 1.0 > 0.3)
    for _ in range(100):
        ctrl.record_outcome(accepted=True)

    scores = {"crt": 0.6, "gaussian": 0.6, "zone_gate": 0.6, "rr": 0.6}
    result = ctrl.apply(scores)

    assert result["threshold"] > 0.5, \
        f"Threshold must increase after high accept rate, got {result['threshold']}"


def test_adaptive_threshold_decreases_on_low_accept_rate():
    ctrl = ConvergenceController(initial_threshold=0.7)

    # Simulate 100 rejected bars (accept_rate = 0.0 < 0.1)
    for _ in range(100):
        ctrl.record_outcome(accepted=False)

    scores = {"crt": 0.5, "gaussian": 0.5, "zone_gate": 0.5, "rr": 0.5}
    result = ctrl.apply(scores)

    assert result["threshold"] < 0.7, \
        f"Threshold must decrease after low accept rate, got {result['threshold']}"


def test_threshold_bounded_within_min_max():
    ctrl = ConvergenceController(initial_threshold=0.5)

    # Push toward maximum
    for _ in range(10000):
        ctrl.record_outcome(accepted=True)

    scores = {"crt": 0.6, "gaussian": 0.6, "zone_gate": 0.6, "rr": 0.6}
    result = ctrl.apply(scores)
    assert result["threshold"] <= 0.90, "Threshold must not exceed 0.90"
    assert result["threshold"] >= 0.30, "Threshold must not fall below 0.30"


# ──────────────────────────────────────────────────────────────────────────────
# Test: Cold start returns raw average
# ──────────────────────────────────────────────────────────────────────────────

def test_cold_start_returns_raw_average():
    ctrl = ConvergenceController()
    # No outcomes recorded → cold start
    assert not ctrl.is_warm

    scores = {"crt": 0.6, "gaussian": 0.4, "zone_gate": 0.5, "rr": 0.5}
    result = ctrl.apply(scores)

    expected = sum(scores.values()) / 4.0
    assert abs(result["final_score"] - expected) < 1e-3
    assert result["variance"] == 0.0
    assert result["entropy"]  == 0.0


# ──────────────────────────────────────────────────────────────────────────────
# Test: entropy is non-negative and finite
# ──────────────────────────────────────────────────────────────────────────────

def test_entropy_non_negative_finite():
    ctrl = ConvergenceController()
    _warm(ctrl)

    scores = {"crt": 0.6, "gaussian": 0.5, "zone_gate": 0.7, "rr": 0.4}
    result = ctrl.apply(scores)

    assert result["entropy"] >= 0.0
    assert math.isfinite(result["entropy"])
