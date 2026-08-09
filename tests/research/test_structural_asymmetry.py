"""Unit tests for the Phase E1 structural-asymmetry core (research.structural_asymmetry).

Covers: barrier-race correctness (rising → +L first, falling → −L first), multi-horizon MFE/MAE
monotonicity, population aggregation, planted-asymmetry recovery via permutation (harness validity),
control calibration (symmetric ⇒ not significant), determinism, and the Wilson power half-width.
Pure — no spine, no data files.
"""
from __future__ import annotations

from research.structural_asymmetry import (
    HORIZONS_DEFAULT, LEVELS_DEFAULT, PathMeasure, _wilson_halfwidth, aggregate, measure_path,
    permutation_vs_control, seed_for,
)


class _B:
    __slots__ = ("high", "low", "close")

    def __init__(self, high, low, close=0.0):
        self.high, self.low, self.close = high, low, close


def test_barrier_race_rising_and_falling():
    rising = [_B(100.0 + k, 100.0 + k - 0.5) for k in range(1, 17)]   # long always favorable
    m = measure_path(100.0, "long", 1.0, rising)
    assert m.first_hit[0.5] == +1 and m.first_hit[1.0] == +1
    assert m.mae_r[16] == 0.0 and m.mfe_r[16] > 0
    falling = [_B(100.0 - k + 0.5, 100.0 - k) for k in range(1, 17)]  # long always adverse
    mf = measure_path(100.0, "long", 1.0, falling)
    assert mf.first_hit[0.5] == -1 and mf.mfe_r[16] == 0.0 and mf.mae_r[16] < 0


def test_mfe_mae_monotonic_in_horizon():
    bars = [_B(100.0 + 0.3 * k, 100.0 - 0.2 * k) for k in range(1, 17)]
    m = measure_path(100.0, "long", 1.0, bars)
    for a, b in zip(HORIZONS_DEFAULT, HORIZONS_DEFAULT[1:]):
        assert m.mfe_r[b] >= m.mfe_r[a]            # MFE non-decreasing with horizon
        assert m.mae_r[b] <= m.mae_r[a]            # MAE non-increasing (more negative)


def _pm(first, mfe, mae):
    return PathMeasure(mfe_r={h: mfe for h in HORIZONS_DEFAULT},
                       mae_r={h: mae for h in HORIZONS_DEFAULT},
                       first_hit={L: first for L in LEVELS_DEFAULT})


def test_aggregate_recovers_asymmetry():
    pop = [_pm(+1, 2.0, 0.0)] * 7 + [_pm(-1, 0.0, -2.0)] * 3   # 70% +first, MFE-heavy
    agg = aggregate(pop)
    assert abs(agg["first_hit"]["0.5"]["delta"] - 0.4) < 1e-9   # 0.7 − 0.3
    assert agg["excursion"]["16"]["asymmetry"] > 0


def test_permutation_significant_when_planted():
    test = [_pm(+1, 2.0, 0.0)] * 60
    control = ([_pm(+1, 1.0, -1.0)] * 30 + [_pm(-1, 1.0, -1.0)] * 30)   # symmetric, asym≈0
    obs, p = permutation_vs_control(test, control, stat="first_hit", key=0.5,
                                    n_permutations=500, seed=seed_for("planted"))
    assert obs > 0 and p < 0.05
    obs2, p2 = permutation_vs_control(test, control, stat="excursion", key=16,
                                      n_permutations=500, seed=seed_for("planted2"))
    assert obs2 > 0 and p2 < 0.05


def test_permutation_not_significant_when_same():
    pop = ([_pm(+1, 1.0, -1.0)] * 30 + [_pm(-1, 1.0, -1.0)] * 30)
    obs, p = permutation_vs_control(pop[:30] + pop[30:], list(pop), stat="first_hit", key=0.5,
                                    n_permutations=500, seed=seed_for("same"))
    assert p > 0.05


def test_permutation_deterministic():
    test = [_pm(+1, 2.0, 0.0)] * 20
    control = [_pm(-1, 0.0, -2.0)] * 20
    a = permutation_vs_control(test, control, stat="first_hit", key=0.5, n_permutations=300, seed=seed_for("d"))
    b = permutation_vs_control(test, control, stat="first_hit", key=0.5, n_permutations=300, seed=seed_for("d"))
    assert a == b


def test_wilson_halfwidth():
    assert _wilson_halfwidth(0, 0) == 1.0
    wide = _wilson_halfwidth(7, 13)      # n=13 (the retest-OOS power concern) → wide
    tight = _wilson_halfwidth(700, 1300)
    assert wide > tight and tight < 0.05
