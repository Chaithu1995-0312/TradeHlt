"""Unit tests for the Phase B (B1) conditional-entropy grid.

Covers the load-bearing properties: entropy sanity (coin-flip -> H≈1, perfectly conditional
-> H≈0 / IG≈1), label-permutation-null calibration (informative partition is significant; an
independent partition is NOT), labeler purity, and determinism of the permutation p-value.
Pure — no spine, no data files.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta

import numpy as np

from research.conditional_entropy_grid import (
    bar_features, candidate_cells, horizon_pairs, hour_to_session, momentum_label,
    partition_stat, permutation_pvalue, seed_for, vol_label,
)

_WINDOWS = {"ASIA": [0, 7], "LONDON": [7, 13], "NEWYORK": [13, 21], "OFF": [21, 24]}


# ── entropy sanity ───────────────────────────────────────────────────────────
def test_coinflip_partition_has_max_entropy_zero_ig():
    labels = ["X"] * 200
    ups = np.array([i % 2 for i in range(200)], dtype=np.int64)  # 50/50, no structure
    st = partition_stat(labels, ups)
    assert abs(st.h_conditional - 1.0) < 1e-9
    assert abs(st.h_unconditional - 1.0) < 1e-9
    assert abs(st.information_gain) < 1e-9


def test_perfectly_conditional_partition_has_zero_entropy_unit_ig():
    # cell A is always up, cell B is always down -> H(dir|cell)=0, H(dir)=1 -> IG=1
    labels = ["A"] * 50 + ["B"] * 50
    ups = np.array([1] * 50 + [0] * 50, dtype=np.int64)
    st = partition_stat(labels, ups)
    assert abs(st.h_conditional) < 1e-9
    assert abs(st.h_unconditional - 1.0) < 1e-9
    assert abs(st.information_gain - 1.0) < 1e-9


# ── permutation-null calibration ─────────────────────────────────────────────
def test_informative_partition_is_significant():
    labels = ["A"] * 100 + ["B"] * 100
    ups = np.array([1] * 100 + [0] * 100, dtype=np.int64)
    p = permutation_pvalue(labels, ups, 200, seed_for("test", "informative"))
    assert p < 0.05            # destroying the association collapses IG -> tiny p


def test_independent_partition_is_not_significant():
    # each cell is balanced 50/50 -> IG_obs = 0 (the minimum) -> permutations never beat it
    labels = ["A"] * 50 + ["B"] * 50
    ups = np.array([1] * 25 + [0] * 25 + [1] * 25 + [0] * 25, dtype=np.int64)
    p = permutation_pvalue(labels, ups, 200, seed_for("test", "independent"))
    assert p > 0.05


def test_permutation_pvalue_is_deterministic():
    labels = ["A"] * 60 + ["B"] * 40
    ups = np.array([1] * 40 + [0] * 20 + [1] * 10 + [0] * 30, dtype=np.int64)
    a = permutation_pvalue(labels, ups, 300, seed_for("det"))
    b = permutation_pvalue(labels, ups, 300, seed_for("det"))
    assert a == b


# ── labeler purity ───────────────────────────────────────────────────────────
def test_hour_to_session():
    assert hour_to_session(0, _WINDOWS) == "ASIA"
    assert hour_to_session(8, _WINDOWS) == "LONDON"
    assert hour_to_session(13, _WINDOWS) == "NEWYORK"
    assert hour_to_session(22, _WINDOWS) == "OFF"


def test_vol_and_momentum_labels():
    assert vol_label(1.0, 2.0, 5.0) == "C"
    assert vol_label(3.0, 2.0, 5.0) == "N"
    assert vol_label(9.0, 2.0, 5.0) == "E"
    assert momentum_label(0.5, 0.1) == "up"
    assert momentum_label(-0.5, 0.1) == "down"
    assert momentum_label(0.05, 0.1) == "flat"


# ── end-to-end on synthetic candles (alignment + no-lookahead) ───────────────
class _C:
    __slots__ = ("high", "low", "close", "timestamp", "index")

    def __init__(self, high, low, close, ts, index):
        self.high, self.low, self.close, self.timestamp, self.index = high, low, close, ts, index


def _synth(n=300):
    t0 = datetime(2024, 1, 1)
    out = []
    price = 100.0
    for i in range(n):
        price += math.sin(i / 5.0)  # deterministic wander
        out.append(_C(price + 1.0, price - 1.0, price, t0 + timedelta(minutes=15 * i), i))
    return out


def test_bar_features_and_horizon_pairs_align_without_lookahead():
    candles = _synth(300)
    feats = bar_features(candles, session_windows=_WINDOWS, atr_period=14,
                         mom_lookback=3, mom_eps=0.1)
    assert feats.closes.size == 300
    for h in (1, 5, 20):
        labels, ups, idx = horizon_pairs(feats, h)
        assert len(labels) == ups.size == idx.size
        if idx.size:
            assert int(idx.max()) < 300 - h          # next-h target exists (no lookahead)
            assert all("|" in lab for lab in labels)  # cell = SESSION|VOL|MOM


def test_candidate_cells_filters_on_power_and_direction():
    labels = ["A"] * 300 + ["B"] * 20
    ups = np.array([1] * 270 + [0] * 30 + [1] * 10 + [0] * 10, dtype=np.int64)
    st = partition_stat(labels, ups)
    cands = candidate_cells(st, min_n=200, dir_floor=0.05)
    assert [c.cell for c in cands] == ["A"]   # A: n=300, p_up=0.9 passes; B: n=20 underpowered
