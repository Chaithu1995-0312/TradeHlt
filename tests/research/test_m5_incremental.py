"""Program 9 — m5_incremental kernels: coarse projection, the within-coarse permutation
null (Gate B), and the frozen Stage-1 verdict combinator (D6).

The statistical pins: (a) a target that depends ONLY on the coarse (M15-level) cell is
declared redundant (large p) even when the fine partition is globally significant — the
F-043 trap; (b) a target with a genuine fine-level (M5) refinement is detected (small p);
(c) the shuffle is seeded-deterministic.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from research.candle_state.m5_incremental import (                       # noqa: E402
    M5_HALF_LIFE_MIN_BARS, M5_HORIZONS, M5_K_DECISION,
    VERDICT_FAIL, VERDICT_M15_REDUNDANT, VERDICT_PASS,
    coarse_key, stage1_verdict, within_coarse_permutation_p,
)


# ── frozen constants (mirror the pre-registration; a change here is a NEW pre-reg) ────
def test_frozen_constants_match_preregistration():
    assert M5_HORIZONS == [3, 6, 12, 24]
    assert M5_K_DECISION == 12
    assert M5_HALF_LIFE_MIN_BARS == 12


# ── coarse projection ────────────────────────────────────────────────────────────────
def test_coarse_key_strips_base_component():
    assert coarse_key("M5=A/B|M15=C/D|H1=E|H4=F") == "M15=C/D|H1=E|H4=F"
    assert coarse_key("M5=X") == ""            # degenerate: no HTF parts


# ── the within-coarse null ───────────────────────────────────────────────────────────
def _panel(n=4000, seed=7):
    """Synthetic panel: 3 coarse cells, each refined into 2 fine cells."""
    rng = np.random.default_rng(seed)
    coarse_id = rng.integers(0, 3, size=n)
    fine_id = rng.integers(0, 2, size=n)
    coarse = [f"M15=C{c}" for c in coarse_id]
    fine = [f"M5=F{f}|M15=C{c}" for f, c in zip(fine_id, coarse_id)]
    return coarse_id, fine_id, coarse, fine, rng


def test_coarse_only_target_is_redundant():
    """Target driven purely by the COARSE cell: globally informative, zero fine
    refinement -> the within-coarse p must NOT be significant (the F-043 trap)."""
    coarse_id, _, coarse, fine, rng = _panel()
    p_up = np.where(coarse_id == 0, 0.7, np.where(coarse_id == 1, 0.5, 0.3))
    target = (rng.random(coarse_id.size) < p_up).astype(np.int64)
    valid = np.ones(coarse_id.size, dtype=bool)
    p = within_coarse_permutation_p(fine, coarse, target, valid,
                                    n_permutations=500, name="test_redundant")
    assert p > 0.05


def test_fine_refinement_is_detected():
    """Target additionally driven by the FINE (M5) cell inside each coarse cell ->
    the within-coarse p must be significant."""
    coarse_id, fine_id, coarse, fine, rng = _panel()
    p_up = 0.5 + 0.1 * (coarse_id - 1) + np.where(fine_id == 0, 0.15, -0.15)
    target = (rng.random(coarse_id.size) < p_up).astype(np.int64)
    valid = np.ones(coarse_id.size, dtype=bool)
    p = within_coarse_permutation_p(fine, coarse, target, valid,
                                    n_permutations=500, name="test_signal")
    assert p <= 0.05


def test_within_coarse_p_is_seed_deterministic():
    coarse_id, _, coarse, fine, rng = _panel()
    target = rng.integers(0, 2, size=coarse_id.size).astype(np.int64)
    valid = np.ones(coarse_id.size, dtype=bool)
    a = within_coarse_permutation_p(fine, coarse, target, valid,
                                    n_permutations=200, name="determinism")
    b = within_coarse_permutation_p(fine, coarse, target, valid,
                                    n_permutations=200, name="determinism")
    assert a == b


def test_valid_mask_is_honoured():
    coarse_id, _, coarse, fine, rng = _panel(n=1000)
    target = rng.integers(0, 2, size=1000).astype(np.int64)
    valid = np.zeros(1000, dtype=bool)
    assert within_coarse_permutation_p(fine, coarse, target, valid,
                                       n_permutations=100, name="empty") == 1.0


# ── verdict combinator (D6) ──────────────────────────────────────────────────────────
def test_stage1_verdict_combinator():
    assert stage1_verdict(True, 0.01) == VERDICT_PASS
    assert stage1_verdict(True, 0.30) == VERDICT_M15_REDUNDANT
    assert stage1_verdict(True, 0.051) == VERDICT_M15_REDUNDANT   # boundary: p > alpha
    assert stage1_verdict(True, 0.05) == VERDICT_PASS             # p == alpha passes (<=)
    assert stage1_verdict(False, 0.01) == VERDICT_FAIL            # Gate A dominates
    assert stage1_verdict(False, 0.99) == VERDICT_FAIL
