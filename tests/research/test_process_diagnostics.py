"""Pure-function tests for process diagnostics (no I/O, deterministic)."""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pytest

from research.process_diagnostics import (
    _conditional_entropy_bits,
    _contingency,
    _mi_nats,
    arch_lm,
    direction_conditional_entropy,
    ljung_box,
    mutual_information,
    run_diagnostics,
)


@dataclass
class Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


def _bars(closes):
    t0 = datetime(2026, 1, 1)
    return [Bar(t0 + timedelta(minutes=15 * i), c, c + 0.5, c - 0.5, c)
            for i, c in enumerate(closes)]


# ── 1. Ljung-Box ─────────────────────────────────────────────────

def test_ljung_box_iid_fails_to_reject():
    rng = np.random.default_rng(1)
    x = rng.standard_normal(6000)
    lb = ljung_box(x, [10, 20])
    assert lb["20"]["df"] == 20
    assert not lb["10"]["reject_at_5pct"]
    assert not lb["20"]["reject_at_5pct"]


def test_ljung_box_ar1_rejects():
    rng = np.random.default_rng(2)
    n = 6000
    x = np.zeros(n)
    eps = rng.standard_normal(n)
    for t in range(1, n):
        x[t] = 0.6 * x[t - 1] + eps[t]
    lb = ljung_box(x, [10, 20])
    assert lb["10"]["reject_at_1pct"]
    assert lb["20"]["reject_at_1pct"]


# ── 2. ARCH-LM ───────────────────────────────────────────────────

def test_arch_lm_garch_rejects():
    # GARCH(1,1)-like: variance clusters -> strong ARCH effect.
    rng = np.random.default_rng(4)
    n = 8000
    r = np.zeros(n)
    sigma2 = np.ones(n)
    for t in range(1, n):
        sigma2[t] = 0.05 + 0.1 * r[t - 1] ** 2 + 0.85 * sigma2[t - 1]
        r[t] = math.sqrt(sigma2[t]) * rng.standard_normal()
    res = arch_lm(r, q=12)
    assert res["reject_at_1pct"]
    assert res["df"] == 12


def test_arch_lm_white_noise_fails_to_reject():
    rng = np.random.default_rng(6)
    r = rng.standard_normal(8000)  # homoskedastic
    res = arch_lm(r, q=12)
    assert not res["reject_at_5pct"]


def test_arch_lm_too_short_is_nan():
    assert math.isnan(arch_lm([0.1, 0.2, 0.3], q=12)["LM"])


# ── 3. Mutual information ────────────────────────────────────────

def test_mi_independent_near_zero():
    rng = np.random.default_rng(8)
    x = rng.integers(0, 2, 5000)
    y = rng.integers(0, 2, 5000)  # independent
    m = mutual_information(x, y, 2, 2, name="t:indep", n_surrogates=100)
    assert m["mi_nats"] < 0.01
    assert not m["significant"]  # observed within surrogate band


def test_mi_coupled_is_significant():
    rng = np.random.default_rng(10)
    x = rng.integers(0, 2, 5000)
    flip = rng.random(5000) < 0.1
    y = np.where(flip, 1 - x, x)  # y strongly determined by x
    m = mutual_information(x, y, 2, 2, name="t:coupled", n_surrogates=100)
    assert m["mi_nats"] > 0.1
    assert m["significant"]
    assert m["p_value"] < 0.05


def test_mi_helpers():
    m = _contingency(np.array([0, 0, 1, 1]), np.array([0, 0, 1, 1]), 2, 2)
    assert m.tolist() == [[2, 0], [0, 2]]
    assert _mi_nats(m) == pytest.approx(math.log(2), abs=1e-9)  # perfect dependence


def test_mi_deterministic():
    rng = np.random.default_rng(12)
    x = rng.integers(0, 2, 3000)
    y = rng.integers(0, 2, 3000)
    a = mutual_information(x, y, 2, 2, name="t:det", n_surrogates=50)
    b = mutual_information(x, y, 2, 2, name="t:det", n_surrogates=50)
    assert a == b  # same seed-name -> identical surrogate draw


# ── 4. Direction conditional entropy ─────────────────────────────

def test_conditional_entropy_coinflip_is_one():
    # within-band pairs with 50/50 next direction regardless of current -> H≈1.
    counts = np.array([[100.0, 100.0], [100.0, 100.0]])
    assert _conditional_entropy_bits(counts) == pytest.approx(1.0, abs=1e-9)


def test_conditional_entropy_deterministic_is_zero():
    counts = np.array([[100.0, 0.0], [0.0, 100.0]])  # next dir fully determined by current
    assert _conditional_entropy_bits(counts) == pytest.approx(0.0, abs=1e-9)


def test_direction_conditional_entropy_only_within_band():
    # CU->CD (within C), CD->NU (cross-band, excluded), NU->ND (within N)
    states = ["CU", "CD", "NU", "ND"]
    per_band, glob, counts = direction_conditional_entropy(states)
    assert counts["C"] == 1 and counts["N"] == 1 and counts["E"] == 0
    assert not math.isnan(glob)


# ── End-to-end ───────────────────────────────────────────────────

def test_run_diagnostics_shape_and_determinism():
    rng = np.random.default_rng(20)
    closes = 600 + np.cumsum(rng.standard_normal(3000))
    bars = _bars(closes)
    d1 = run_diagnostics(bars, instrument="TEST", ljung_box_lags=(10, 20),
                         arch_q=12, mi_bins=10, mi_surrogates=50)
    d2 = run_diagnostics(bars, instrument="TEST", ljung_box_lags=(10, 20),
                         arch_q=12, mi_bins=10, mi_surrogates=50)
    assert d1.to_dict() == d2.to_dict()  # determinism
    assert d1.n_candles == 3000
    assert set(d1.ljung_box) == {"returns", "squared_returns", "atr"}
    assert set(d1.mutual_information) == {
        "sign_t__sign_next", "atr_t__sign_next", "vol_state_t__sign_next"}
    assert set(d1.thesis_flags) == {
        "returns_linearly_uncorrelated", "arch_effects_present",
        "direction_coinflip_given_vol", "nonlinear_direction_info"}
    # random-walk closes: returns should be linearly uncorrelated
    assert d1.thesis_flags["returns_linearly_uncorrelated"]
