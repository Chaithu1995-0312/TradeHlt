"""Pure-function tests for the process characterizer (no I/O, deterministic)."""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pytest

from research.process_characterization import (
    STATE_LABELS,
    autocorrelation,
    characterize,
    digitize_states,
    hurst_rs,
    log_returns,
    transition_matrix,
    variance_ratio,
)


@dataclass
class Bar:
    """Minimal Candle-like bar (characterize duck-types .high/.low/.close)."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


def _walk(closes):
    """Build bars from a close series with small symmetric wicks."""
    t0 = datetime(2026, 1, 1)
    bars = []
    for i, c in enumerate(closes):
        bars.append(Bar(t0 + timedelta(minutes=15 * i), c, c + 0.5, c - 0.5, c))
    return bars


# ── A. Autocorrelation ───────────────────────────────────────────

def test_acf_iid_noise_near_zero():
    rng = np.random.default_rng(7)
    x = rng.standard_normal(5000)
    acf = autocorrelation(x, 20)
    assert len(acf) == 20
    # i.i.d. noise: all lag>0 autocorrelations hug zero.
    assert max(abs(v) for v in acf) < 0.1


def test_acf_ar1_decays_geometrically():
    # AR(1) with phi=0.7 -> rho_k ~= 0.7**k (slow, monotone decay).
    rng = np.random.default_rng(11)
    phi, n = 0.7, 8000
    x = np.zeros(n)
    eps = rng.standard_normal(n)
    for t in range(1, n):
        x[t] = phi * x[t - 1] + eps[t]
    acf = autocorrelation(x, 5)
    assert acf[0] == pytest.approx(0.7, abs=0.06)
    assert acf[0] > acf[1] > acf[2] > 0.0  # monotone positive decay


def test_acf_short_series_clamps():
    assert autocorrelation([1.0, 2.0, 3.0], 50) != []  # clamps max_lag to n-1
    assert autocorrelation([1.0], 5) == []


# ── B. Hurst / variance ratio ────────────────────────────────────

def test_hurst_random_walk_near_half():
    rng = np.random.default_rng(3)
    returns = rng.standard_normal(20000)  # increments of a random walk
    h = hurst_rs(returns)
    assert h == pytest.approx(0.5, abs=0.08)


def test_hurst_trending_above_half():
    # Cumulative random walk (the levels) is strongly persistent.
    rng = np.random.default_rng(5)
    levels = np.cumsum(rng.standard_normal(20000))
    assert hurst_rs(levels) > 0.7


def test_hurst_too_short_is_nan():
    assert math.isnan(hurst_rs([1.0, 2.0, 3.0]))


def test_variance_ratio_random_walk_near_one():
    rng = np.random.default_rng(9)
    returns = rng.standard_normal(20000)
    assert variance_ratio(returns, 4) == pytest.approx(1.0, abs=0.1)


def test_variance_ratio_guards():
    assert math.isnan(variance_ratio([0.1, 0.2], 4))  # too short
    assert math.isnan(variance_ratio([0.1] * 50, 1))  # q<2


# ── C. State digitisation + transition matrix ────────────────────

def test_digitize_terciles_deterministic():
    # ATR ascending 1..9 -> terciles at 33.3/66.7 pct; sign of return -> U/D.
    returns = [1, -1, 1, -1, 1, -1, 1, -1, 1]
    atr_vals = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    states, lo, hi = digitize_states(returns, atr_vals)
    states2, lo2, hi2 = digitize_states(returns, atr_vals)
    assert (states, lo, hi) == (states2, lo2, hi2)  # determinism
    assert lo == pytest.approx(np.percentile(atr_vals, 100 / 3))
    assert hi == pytest.approx(np.percentile(atr_vals, 200 / 3))
    # lowest ATRs -> Compression, highest -> Expansion; alternating direction.
    assert states[0] == "CU" and states[1] == "CD"
    assert states[-1] == "EU"


def test_digitize_mismatched_lengths_empty():
    states, lo, hi = digitize_states([1, 2, 3], [1, 2])
    assert states == [] and math.isnan(lo) and math.isnan(hi)


def test_transition_matrix_rows_sum_to_one():
    states = ["CU", "CD", "CU", "CD", "EU", "CU"]
    matrix, counts, labels = transition_matrix(states)
    assert labels == STATE_LABELS
    # exactly len-1 transitions counted
    assert sum(sum(r) for r in counts) == len(states) - 1
    for row in matrix:
        s = sum(row)
        assert s == pytest.approx(1.0) or s == 0.0  # occupied rows sum to 1


def test_transition_matrix_single_state_empty_rows_zero():
    matrix, counts, labels = transition_matrix(["CU"])
    assert sum(sum(r) for r in counts) == 0
    assert all(sum(r) == 0.0 for r in matrix)


# ── End-to-end manifest ──────────────────────────────────────────

def test_characterize_manifest_shape_and_determinism():
    rng = np.random.default_rng(21)
    closes = 600 + np.cumsum(rng.standard_normal(2000))
    bars = _walk(closes)
    m1 = characterize(bars, instrument="TEST", max_lag=10, vr_qs=(2, 4))
    m2 = characterize(bars, instrument="TEST", max_lag=10, vr_qs=(2, 4))
    assert m1.to_dict() == m2.to_dict()  # byte-identical inputs -> identical output
    assert m1.n_candles == 2000
    assert m1.n_returns == 1999
    assert m1.state_labels == STATE_LABELS
    assert len(m1.acf_returns) == 10
    assert set(m1.thesis_flags) == {
        "returns_near_random_walk",
        "volatility_persistent",
        "volatility_memory_exceeds_direction",
        "direction_near_coinflip",
    }
    # synthetic random-walk closes: returns should look ~random-walk
    assert abs(m1.hurst_returns - 0.5) < 0.15


def test_log_returns_basic():
    r = log_returns([100.0, 110.0, 99.0])
    assert r.size == 2
    assert r[0] == pytest.approx(math.log(110 / 100))
