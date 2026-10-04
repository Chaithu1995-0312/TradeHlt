"""Unit tests for the Phase S1 selection-effect core (research.selection_effect).

Covers: reason folding, ΔE, effect pooling (weight = min(n_sel,n_rej)), stratified-permutation
calibration (planted selected>rejected ⇒ significant; exchangeable ⇒ not), and determinism.
Pure — no spine, no data files.
"""
from __future__ import annotations

import math

from research.selection_effect import (
    delta_e, fold_reason, pooled_delta, seed_for, sign_consistency, stratified_permutation_p,
)

_RC = {"SESSION": ["OFF_SESSION"], "ZONE": ["ZONE"], "SCORE": ["LOW_SCORE"]}


def test_fold_reason():
    assert fold_reason(None, _RC) == "ACCEPTED"
    assert fold_reason("OFF_SESSION", _RC) == "SESSION"
    assert fold_reason("ZONE", _RC) == "ZONE"
    assert fold_reason("LOW_SCORE", _RC) == "SCORE"
    assert fold_reason("SHADOW_ADVISORY", _RC) == "OTHER"


def test_delta_e_basic_and_empty():
    assert delta_e([1.0, 1.0], [0.0, 0.0]) == 1.0
    assert math.isnan(delta_e([], [0.0]))
    assert math.isnan(delta_e([1.0], []))


def test_pooled_delta_weighting_and_skip():
    pooled, W = pooled_delta([([2.0, 2.0], [0.0, 0.0]), ([1.0], [0.0]), ([5.0], [])])
    assert W == 3.0                                   # third group skipped (empty rejected)
    assert abs(pooled - (2 * 2.0 + 1 * 1.0) / 3.0) < 1e-9   # weight = min(n_sel, n_rej)


def test_stratified_permutation_significant_when_planted():
    groups = [([1.0] * 6, [0.0] * 6), ([1.0] * 5, [0.0] * 5), ([1.0] * 7, [0.0] * 7)]
    obs, p, n = stratified_permutation_p(groups, 500, seed_for("planted"))
    assert n == 3 and obs == 1.0 and p < 0.05


def test_stratified_permutation_not_significant_when_exchangeable():
    groups = [([1.0, 0.0, 1.0, 0.0], [1.0, 0.0, 1.0, 0.0]),
              ([1.0, 0.0], [1.0, 0.0])]
    _obs, p, _n = stratified_permutation_p(groups, 500, seed_for("exch"))
    assert p > 0.05


def test_stratified_permutation_deterministic():
    groups = [([2.0, 1.0, 0.5], [0.0, -1.0]), ([1.0], [0.0, 0.0])]
    a = stratified_permutation_p(groups, 300, seed_for("det"))
    b = stratified_permutation_p(groups, 300, seed_for("det"))
    assert a == b


def test_sign_consistency():
    assert sign_consistency([0.5, -0.2, 0.1, float("nan")]) == (2, 3)
