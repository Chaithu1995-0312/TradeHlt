"""Floor for behavioral band-threshold validation (src/research/band_validation.py, A2a).

The two load-bearing guarantees:
  * NULL BEHAVES AS NULL — a temporally-structureless (i.i.d.) label series must FAIL persistence,
    and a partition whose bands don't order forward return must be NOT_SUPPORTED. Frequency alone
    can never earn a FROZEN verdict.
  * PLANTED REGIME PASSES — a series with genuine persistent, adjacency-ordered, monotone-payoff
    bands must be FROZEN_ELIGIBLE. If it weren't, the gate would reject real structure.
"""
from __future__ import annotations

import numpy as np
import pytest

from research.band_validation import (
    BandSpec, BandValidationParams, _codes, _persistence_rate, assign_bands, evaluate_partition,
    validate_partitions,
)
from research.candle_state.transition_target import persistence_target
from research.shape_statistics import BootstrapSpec

# 5 bands over integer-centered values; value b maps to band index b.
EDGES = (0.5, 1.5, 2.5, 3.5)
LABELS = ("StrongBear", "WeakBear", "Neutral", "WeakBull", "StrongBull")
SPEC = BandSpec("quintile_like", EDGES, LABELS)


def _params(**over) -> BandValidationParams:
    base = dict(k_persist=4, fwd_horizon=8, n_perm=150, alpha=0.05, rho_min=0.6, stab_min=0.3,
                min_cell=30, ci=BootstrapSpec(n_boot=200, alpha=0.05, seed=1), seed=7)
    base.update(over)
    return BandValidationParams(**base)


def _persistent(n=4000, K=5, block=30, band_effect=0.5, fwd_noise=0.2, seed=0):
    """Adjacency-walk latent regime (persistent + ordered transitions) with monotone per-band
    forward return. Returns (values, fwd_ret, years, bands)."""
    rng = np.random.default_rng(seed)
    bands = []
    b = K // 2
    while len(bands) < n:
        bands += [b] * block
        b = int(min(K - 1, max(0, b + rng.choice([-1, 0, 1]))))
    bands = np.array(bands[:n])
    values = bands + rng.normal(0, 0.12, n)                      # stays inside ±0.5 band a.s.
    fwd = (bands - (K - 1) / 2) * band_effect + rng.normal(0, fwd_noise, n)
    years = np.where(np.arange(n) < n // 2, 2024, 2025)
    return values, fwd, years, bands


# ── input contract ─────────────────────────────────────────────────────────────

def test_bandspec_validates_edges_and_labels():
    with pytest.raises(ValueError):
        BandSpec("x", (1.0, 0.5), ("a", "b", "c"))          # non-increasing edges
    with pytest.raises(ValueError):
        BandSpec("x", (0.5, 1.5), ("a", "b"))               # wrong label count


def test_assign_bands_maps_values_and_nonfinite():
    labs = assign_bands([0.0, 1.0, 4.0, float("nan"), float("inf")], SPEC)
    assert labs == ["StrongBear", "WeakBear", "StrongBull", None, None]


def test_vectorized_persistence_matches_canonical_primitive():
    """The fast _persistence_rate must reproduce research.candle_state.transition_target
    .persistence_target exactly — the vectorization is a speed change, not a semantics change."""
    v, _fr, _yr, _ = _persistent(n=800, seed=2)
    labels = assign_bands(v, SPEC)
    for k in (2, 4, 8):
        tgt, valid = persistence_target(labels, k=k)
        canon = float(tgt[valid].mean())
        fast, m = _persistence_rate(_codes(labels, SPEC.labels), k)
        assert m == int(valid.sum())
        assert fast == pytest.approx(canon, abs=1e-12)


def test_length_mismatch_raises():
    with pytest.raises(ValueError):
        validate_partitions([0.0, 1.0], [0.1], [2024, 2024], [SPEC], _params())


# ── planted regime PASSES ───────────────────────────────────────────────────────

def test_planted_monotone_regime_is_frozen_eligible():
    v, fr, yr, _ = _persistent()
    verd = evaluate_partition(v, fr, yr, SPEC, _params())
    assert verd.persistence["p"] < 0.05 and verd.persistence["real_rate"] > verd.persistence["null_mean"]
    assert verd.transition["p"] < 0.05
    assert verd.transition["real_mean_distance"] < verd.transition["null_mean_distance"]
    assert verd.forward_return["monotonic_pass"] and verd.forward_return["stability_pass"]
    assert verd.verdict == "FROZEN_ELIGIBLE", verd.reason
    assert list(verd.supported_edges) == [0, 1, 2, 3]


# ── nulls FAIL ──────────────────────────────────────────────────────────────────

def test_iid_series_fails_persistence():
    """No temporal structure ⇒ persistence must not clear the shuffle null ⇒ NOT_SUPPORTED."""
    rng = np.random.default_rng(3)
    n = 4000
    bands = rng.integers(0, 5, n)                            # i.i.d., no dwell
    v = bands + rng.normal(0, 0.12, n)
    fr = rng.normal(0, 0.2, n)
    yr = np.where(np.arange(n) < n // 2, 2024, 2025)
    verd = evaluate_partition(v, fr, yr, SPEC, _params())
    assert verd.persistence["p"] >= 0.05                    # cannot reject the null
    assert verd.verdict == "NOT_SUPPORTED"
    assert "persistence" in verd.reason


def test_persistent_bands_but_random_payoff_is_not_supported():
    """Bands persist & are ordered, but forward return is band-independent ⇒ boundaries are
    behaviorally empty ⇒ NOT_SUPPORTED (forward-return battery is the gate that catches this)."""
    v, _fr, yr, _ = _persistent()
    rng = np.random.default_rng(9)
    fr_random = rng.normal(0, 0.2, len(v))                  # no relationship to band
    verd = evaluate_partition(v, fr_random, yr, SPEC, _params())
    # persistence/transition still pass (structure is real), but payoff doesn't order
    assert verd.persistence["p"] < 0.05 and verd.transition["p"] < 0.05
    assert verd.verdict == "NOT_SUPPORTED"


def test_merge_recommended_when_two_bands_share_payoff():
    """Collapse WeakBull into Neutral (same forward return) ⇒ that interior boundary is empty ⇒
    MERGE_RECOMMENDED, not FROZEN."""
    rng = np.random.default_rng(1)
    n, K, block = 4000, 5, 30
    bands = []
    b = K // 2
    while len(bands) < n:
        bands += [b] * block
        b = int(min(K - 1, max(0, b + rng.choice([-1, 0, 1]))))
    bands = np.array(bands[:n])
    v = bands + rng.normal(0, 0.12, n)
    # payoff for band 3 (WeakBull) == band 2 (Neutral): boundary 2 becomes empty
    eff = np.array([-1.0, -0.5, 0.0, 0.0, 0.5])
    fr = eff[bands] + rng.normal(0, 0.15, n)
    yr = np.where(np.arange(n) < n // 2, 2024, 2025)
    verd = evaluate_partition(v, fr, yr, SPEC, _params())
    assert verd.verdict == "MERGE_RECOMMENDED", (verd.verdict, verd.reason)
    assert 2 not in verd.supported_edges                    # the Neutral|WeakBull boundary is empty


# ── determinism + recommendation ────────────────────────────────────────────────

def test_report_is_deterministic_and_recommends_best():
    v, fr, yr, _ = _persistent()
    a = validate_partitions(v, fr, yr, [SPEC], _params()).to_dict()
    b = validate_partitions(v, fr, yr, [SPEC], _params()).to_dict()
    assert a == b
    assert a["authority"].startswith("DESCRIPTIVE_ONLY")
    assert a["recommended"] == "quintile_like"
