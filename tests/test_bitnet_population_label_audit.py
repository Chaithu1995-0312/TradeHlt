"""Unit tests for population/label audit helpers."""
from __future__ import annotations

import numpy as np

from bitnet.population_label_audit import _balance_block, _label_one


def test_balance_block_extreme():
    b = _balance_block(100, n_pos=98, n_neg=2)
    assert b["pos_rate"] == 0.98
    assert b["majority_class"] == "pos"
    assert b["majority_rate"] == 0.98
    assert b["imbalance_ratio_pos_neg"] == 49.0


def test_balance_block_unlabeled():
    b = _balance_block(500)
    assert b["n"] == 500
    assert b["pos_rate"] is None


def test_label_one_win_and_loss():
    # flat then spike high → win
    closes = np.array([100.0, 100.0, 100.0, 100.0, 100.0], dtype=np.float64)
    highs = np.array([100.0, 100.0, 103.0, 100.0, 100.0], dtype=np.float64)
    lows = np.array([100.0, 100.0, 99.0, 100.0, 100.0], dtype=np.float64)
    atr = 1.0
    # tp = 102, sl = 99
    assert _label_one(0, highs, lows, closes, atr, 2.0, 1.0, 4) == 1.0

    highs2 = np.array([100.0, 100.0, 100.5, 100.0, 100.0], dtype=np.float64)
    lows2 = np.array([100.0, 100.0, 98.5, 100.0, 100.0], dtype=np.float64)
    assert _label_one(0, highs2, lows2, closes, atr, 2.0, 1.0, 4) == 0.0
