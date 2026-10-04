"""info_robustness.py — Stage-1 information-robustness kernels (FROZEN thresholds in pre-reg).

A conjunction may show a significant in-sample information gain by luck. Before it earns a
Stage-2 economic test it must survive three pre-registered robustness gates (Program 4b/c/d
pre-registration):

  1. mi_stability   — MI/IG retention from train (2024) to test (2025) ≥ 50%.
  2. info_half_life — IG must still be ≥ 50% of its horizon-1 value at horizon ≥ 4 bars.
  3. cross_market   — crypto PASS + FX PASS ⇒ UNIVERSAL; crypto PASS + FX FAIL ⇒ DOMAIN_SPECIFIC;
                      else ⇒ REJECTED.

All three reuse the audited information-gain primitive (`conditional_entropy_grid.partition_stat`,
which itself reuses the audited entropy primitive). Pure & deterministic: numpy + stdlib.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from research.conditional_entropy_grid import partition_stat, permutation_pvalue, seed_for

# Frozen thresholds (mirrored in docs/research/preregistration-program-4bcd.md).
MI_RETENTION_MIN = 0.50
HALF_LIFE_MIN_BARS = 4
SIGNIFICANCE_ALPHA = 0.05


def information_gain(cells: Sequence[str], target: np.ndarray, valid: np.ndarray) -> float:
    """IG (bits) of `target` given the partition `cells`, over valid bars only. 0.0 if empty."""
    labels = [c for c, v in zip(cells, valid.tolist()) if v]
    ups = np.asarray([int(t) for t, v in zip(target.tolist(), valid.tolist()) if v], dtype=np.int64)
    if ups.size == 0:
        return 0.0
    ig = partition_stat(labels, ups).information_gain
    return float(ig) if ig == ig else 0.0   # NaN-guard


def permutation_p(cells: Sequence[str], target: np.ndarray, valid: np.ndarray,
                  *, n_permutations: int, name: str) -> float:
    """Add-one permutation p-value of the partition's IG (reuses the audited test)."""
    labels = [c for c, v in zip(cells, valid.tolist()) if v]
    ups = np.asarray([int(t) for t, v in zip(target.tolist(), valid.tolist()) if v], dtype=np.int64)
    if ups.size == 0:
        return 1.0
    return permutation_pvalue(labels, ups, n_permutations, seed_for(name))


def mi_stability(
    cells_train: Sequence[str], target_train: np.ndarray, valid_train: np.ndarray,
    cells_test: Sequence[str], target_test: np.ndarray, valid_test: np.ndarray,
) -> dict:
    """IG on train vs test; retention = IG_test / IG_train. PASS iff retention ≥ MI_RETENTION_MIN."""
    ig_train = information_gain(cells_train, target_train, valid_train)
    ig_test = information_gain(cells_test, target_test, valid_test)
    retention = (ig_test / ig_train) if ig_train > 0.0 else 0.0
    return {
        "ig_train": round(ig_train, 6),
        "ig_test": round(ig_test, 6),
        "retention": round(retention, 6),
        "passed": bool(ig_train > 0.0 and retention >= MI_RETENTION_MIN),
    }


def info_half_life(ig_by_horizon: dict[int, float], *, min_bars: int = HALF_LIFE_MIN_BARS) -> dict:
    """Decay curve of IG across horizons. half_life = largest horizon h with IG(h) ≥ 0.5·IG(h0)
    where h0 is the smallest horizon. PASS iff half_life ≥ `min_bars` (default = the frozen
    Program-4 M15 threshold; Program 9 passes its wall-clock-matched M5 rescale, 12 bars)."""
    if not ig_by_horizon:
        return {"curve": {}, "half_life_bars": 0, "passed": False}
    horizons = sorted(ig_by_horizon)
    h0 = horizons[0]
    base = ig_by_horizon[h0]
    half = 0
    if base > 0.0:
        for h in horizons:
            if ig_by_horizon[h] >= 0.5 * base:
                half = h
            else:
                break
    return {
        "curve": {str(h): round(ig_by_horizon[h], 6) for h in horizons},
        "half_life_bars": half,
        "passed": bool(base > 0.0 and half >= min_bars),
    }


def cross_market(crypto_pass: bool, fx_pass: bool) -> str:
    """Pre-registered cross-market policy → UNIVERSAL | DOMAIN_SPECIFIC | REJECTED."""
    if crypto_pass and fx_pass:
        return "UNIVERSAL"
    if crypto_pass and not fx_pass:
        return "DOMAIN_SPECIFIC"
    return "REJECTED"
