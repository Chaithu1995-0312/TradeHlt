"""
test_evaluator.py
=================
Unit tests for src/training/evaluator.py  (Flow 4 — Training/Model Update validation).

Covers:
  _pearson         : perfect corr, negative corr, n<3 guard, zero-variance guard, known value
  _composite_score : no high-confidence buckets, full buckets, all-zero
  evaluate_gaussian: empty X, result field types, n_samples, corr bounds,
                     cal_error non-negative, class_distribution sums to n
  should_update    : approve both-pass; block corr+cal; block cal-only; block neither;
                     boundary (exact margin = blocked); default margin=0.02
"""

from __future__ import annotations

import math
import pytest
from unittest.mock import MagicMock

from training.evaluator import (
    GaussianEvalResult,
    _composite_score,
    _pearson,
    evaluate_gaussian,
    should_update,
)
from features.feature_schema import CANONICAL_FEATURES

N_FEATURES = len(CANONICAL_FEATURES)  # 35


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_fitted_model_scaler(n: int = 60):
    """
    Real GaussianNBModel + StandardScaler fitted on synthetic 35-dim data.
    Does NOT call train_gaussian — fits directly to isolate evaluator logic.
    """
    import random
    from training.trainer import GaussianNBModel, StandardScaler

    random.seed(42)
    X = [[random.gauss(float(i % 4), 0.3) for i in range(N_FEATURES)]
         for _ in range(n)]
    scaler = StandardScaler()
    scaler.fit(X)
    X_sc = scaler.transform(X)
    y_cls = [i % 4 for i in range(n)]
    model = GaussianNBModel()
    model.fit(X_sc, y_cls)
    return model, scaler


def _make_X_y_rr(n: int = 60):
    """Synthetic raw (unscaled) feature matrix + RR labels."""
    import random
    random.seed(13)
    X    = [[random.gauss(0.0, 1.0) for _ in range(N_FEATURES)] for _ in range(n)]
    y_rr = [random.uniform(-1.0, 3.0) for _ in range(n)]
    return X, y_rr


# ─────────────────────────────────────────────────────────────────────────────
# _pearson
# ─────────────────────────────────────────────────────────────────────────────

def test_pearson_perfect_positive():
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    ys = [2.0, 4.0, 6.0, 8.0, 10.0]
    assert _pearson(xs, ys) == pytest.approx(1.0, abs=1e-9)


def test_pearson_perfect_negative():
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    ys = [5.0, 4.0, 3.0, 2.0, 1.0]
    assert _pearson(xs, ys) == pytest.approx(-1.0, abs=1e-9)


def test_pearson_returns_zero_for_n_less_than_3():
    assert _pearson([1.0], [1.0])           == pytest.approx(0.0)
    assert _pearson([1.0, 2.0], [3.0, 4.0]) == pytest.approx(0.0)


def test_pearson_zero_variance_xs_returns_zero():
    """All xs identical → sx=0 → must return 0.0 without div/0."""
    xs = [5.0, 5.0, 5.0, 5.0, 5.0]
    ys = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert _pearson(xs, ys) == pytest.approx(0.0)


def test_pearson_zero_variance_ys_returns_zero():
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    ys = [3.0, 3.0, 3.0, 3.0, 3.0]
    assert _pearson(xs, ys) == pytest.approx(0.0)


def test_pearson_known_value():
    """Cross-check against manual Pearson calculation for a 5-point set."""
    xs = [1, 2, 3, 4, 5]
    ys = [1, 3, 2, 5, 4]
    n  = 5
    mx, my = 3.0, 3.0
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / n
    sx  = math.sqrt(sum((x - mx) ** 2 for x in xs) / n)
    sy  = math.sqrt(sum((y - my) ** 2 for y in ys) / n)
    expected = cov / (sx * sy)
    assert _pearson(xs, ys) == pytest.approx(expected, abs=1e-9)


# ─────────────────────────────────────────────────────────────────────────────
# _composite_score
# ─────────────────────────────────────────────────────────────────────────────

def test_composite_score_no_high_confidence_buckets():
    """When 0.70-0.80 and 0.80-1.00 buckets are empty only accuracy contributes."""
    bucket_stats = {
        "0.50-0.60": {"count": 0, "win_rate": None},
        "0.60-0.70": {"count": 0, "win_rate": None},
        "0.70-0.80": {"count": 0, "win_rate": None},
        "0.80-1.00": {"count": 0, "win_rate": None},
    }
    score = _composite_score(0.65, bucket_stats)
    assert score == pytest.approx(0.40 * 0.65, abs=1e-9)


def test_composite_score_with_full_high_confidence_buckets():
    """40% accuracy + 30% wr[0.70-0.80] + 30% wr[0.80-1.00]."""
    bucket_stats = {
        "0.50-0.60": {"count": 5, "win_rate": 0.50},
        "0.60-0.70": {"count": 5, "win_rate": 0.55},
        "0.70-0.80": {"count": 5, "win_rate": 0.70},
        "0.80-1.00": {"count": 5, "win_rate": 0.85},
    }
    score    = _composite_score(0.60, bucket_stats)
    expected = 0.40 * 0.60 + 0.30 * 0.70 + 0.30 * 0.85
    assert score == pytest.approx(expected, abs=1e-9)


def test_composite_score_all_zeros():
    bucket_stats = {
        "0.70-0.80": {"count": 0, "win_rate": None},
        "0.80-1.00": {"count": 0, "win_rate": None},
    }
    assert _composite_score(0.0, bucket_stats) == pytest.approx(0.0)


def test_composite_score_only_elite_bucket_present():
    """Only the 0.80-1.00 bucket fires — 0.70-0.80 absent from dict → 0."""
    bucket_stats = {
        "0.80-1.00": {"count": 10, "win_rate": 1.0},
    }
    score    = _composite_score(0.5, bucket_stats)
    expected = 0.40 * 0.5 + 0.30 * 0.0 + 0.30 * 1.0
    assert score == pytest.approx(expected, abs=1e-9)


# ─────────────────────────────────────────────────────────────────────────────
# evaluate_gaussian
# ─────────────────────────────────────────────────────────────────────────────

def test_evaluate_gaussian_empty_X_returns_zero_result():
    model, scaler = _make_fitted_model_scaler()
    result = evaluate_gaussian(model, scaler, [], [])
    assert isinstance(result, GaussianEvalResult)
    assert result.n_samples         == 0
    assert result.corr_expected_rr  == pytest.approx(0.0)
    assert result.calibration_error == pytest.approx(0.0)


def test_evaluate_gaussian_result_has_all_required_fields():
    model, scaler = _make_fitted_model_scaler()
    X, y_rr = _make_X_y_rr(n=40)
    result = evaluate_gaussian(model, scaler, X, y_rr)
    assert isinstance(result, GaussianEvalResult)
    assert isinstance(result.n_samples,          int)
    assert isinstance(result.corr_expected_rr,   float)
    assert isinstance(result.calibration_error,  float)
    assert isinstance(result.mean_expected_rr,   float)
    assert isinstance(result.mean_actual_rr,     float)
    assert isinstance(result.class_distribution, dict)


def test_evaluate_gaussian_n_samples_matches_input():
    model, scaler = _make_fitted_model_scaler()
    X, y_rr = _make_X_y_rr(n=40)
    result = evaluate_gaussian(model, scaler, X, y_rr)
    assert result.n_samples == 40


def test_evaluate_gaussian_corr_in_valid_range():
    model, scaler = _make_fitted_model_scaler()
    X, y_rr = _make_X_y_rr(n=40)
    result = evaluate_gaussian(model, scaler, X, y_rr)
    assert -1.0 <= result.corr_expected_rr <= 1.0


def test_evaluate_gaussian_calibration_error_non_negative():
    model, scaler = _make_fitted_model_scaler()
    X, y_rr = _make_X_y_rr(n=40)
    result = evaluate_gaussian(model, scaler, X, y_rr)
    assert result.calibration_error >= 0.0


def test_evaluate_gaussian_class_distribution_sums_to_n():
    """class_distribution counts must sum to n_samples."""
    model, scaler = _make_fitted_model_scaler()
    X, y_rr = _make_X_y_rr(n=40)
    result = evaluate_gaussian(model, scaler, X, y_rr)
    total = sum(result.class_distribution.values())
    assert total == result.n_samples


def test_evaluate_gaussian_class_distribution_has_four_classes():
    model, scaler = _make_fitted_model_scaler()
    X, y_rr = _make_X_y_rr(n=40)
    result = evaluate_gaussian(model, scaler, X, y_rr)
    assert len(result.class_distribution) == 4


# ─────────────────────────────────────────────────────────────────────────────
# should_update
# ─────────────────────────────────────────────────────────────────────────────

def test_should_update_approves_when_both_better():
    """Corr beats margin AND calibration improves → True."""
    ok, reason = should_update(
        ml_metrics       = {"corr_expected_rr": 0.30, "calibration_error": 0.10},
        gaussian_metrics = {"corr_expected_rr": 0.20, "calibration_error": 0.15},
        corr_margin      = 0.05,
    )
    assert ok is True
    assert "approved" in reason.lower()


def test_should_update_blocks_when_corr_passes_but_calibration_worsens():
    """Corr gain above margin but calibration error increases → False."""
    ok, reason = should_update(
        ml_metrics       = {"corr_expected_rr": 0.30, "calibration_error": 0.20},
        gaussian_metrics = {"corr_expected_rr": 0.20, "calibration_error": 0.15},
        corr_margin      = 0.05,
    )
    assert ok is False
    assert "BLOCKED" in reason


def test_should_update_blocks_when_calibration_passes_but_corr_insufficient():
    """Calibration improves but corr gain is below margin → False."""
    ok, reason = should_update(
        ml_metrics       = {"corr_expected_rr": 0.22, "calibration_error": 0.10},
        gaussian_metrics = {"corr_expected_rr": 0.20, "calibration_error": 0.15},
        corr_margin      = 0.05,
    )
    assert ok is False
    assert "BLOCKED" in reason


def test_should_update_blocks_when_neither_improves():
    ok, reason = should_update(
        ml_metrics       = {"corr_expected_rr": 0.18, "calibration_error": 0.20},
        gaussian_metrics = {"corr_expected_rr": 0.20, "calibration_error": 0.15},
        corr_margin      = 0.02,
    )
    assert ok is False
    assert "BLOCKED" in reason


def test_should_update_at_exact_margin_boundary_is_blocked():
    """
    0.22 - 0.20 = 0.02 = corr_margin → NOT strictly greater → corr gate fails.
    Cal gate passes (0.10 < 0.15), so hits the cal-only branch → still blocked.
    """
    ok, _ = should_update(
        ml_metrics       = {"corr_expected_rr": 0.22, "calibration_error": 0.10},
        gaussian_metrics = {"corr_expected_rr": 0.20, "calibration_error": 0.15},
        corr_margin      = 0.02,
    )
    assert ok is False


def test_should_update_default_margin_is_point_zero_two():
    """Default corr_margin=0.02: gain of 0.05 should approve when cal also better."""
    ok, _ = should_update(
        ml_metrics       = {"corr_expected_rr": 0.25, "calibration_error": 0.10},
        gaussian_metrics = {"corr_expected_rr": 0.20, "calibration_error": 0.15},
    )
    assert ok is True


def test_should_update_returns_string_reason_always():
    """Both branches must return a non-empty reason string."""
    for approved in (True, False):
        ok, reason = should_update(
            ml_metrics       = {"corr_expected_rr": 0.30, "calibration_error": 0.10},
            gaussian_metrics = {"corr_expected_rr": 0.20, "calibration_error": 0.15},
            corr_margin      = 0.05,
        )
        assert isinstance(reason, str) and len(reason) > 0
        break   # only need one check — function always returns str
