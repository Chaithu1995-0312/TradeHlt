"""Tests for the Stage-1 transition machinery: targets, robustness kernels, and the
key_series ≡ build() equivalence (the efficiency optimisation must not change the science).
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.crt_engine_v2 import Candle                  # noqa: E402
from research.candle_state.encoder import CandleStateEncoder   # noqa: E402
from research.candle_state.mtf_conjunction import MultiTFConjunctionBuilder  # noqa: E402
from research.candle_state.transition_target import (          # noqa: E402
    atr_per_bar, persistence_target, regime_transition_target,
    range_expansion_target, vol_expansion_target,
)
from research.candle_state.info_robustness import (            # noqa: E402
    cross_market, info_half_life, information_gain, mi_stability, permutation_p,
)


def _series(n, *, start=datetime(2024, 1, 1), base=100.0):
    out = []
    prev = base
    for i in range(n):
        o = prev
        cl = o + (0.4 if i % 3 else -0.3)
        hi = max(o, cl) + 0.2 + 0.001 * i
        lo = min(o, cl) - 0.2 - 0.001 * i
        out.append(Candle(timestamp=start + timedelta(minutes=15 * i),
                          open=o, high=hi, low=lo, close=cl, volume=1.0 + 0.5 * i, index=i))
        prev = cl
    return out


# ── targets ───────────────────────────────────────────────────────────────────
def test_vol_expansion_target_detects_forward_blowup():
    # flat ATR then a forward burst → bars before the burst should be labeled 1
    atrs = np.array([1.0] * 10 + [5.0] * 5, dtype=float)   # burst begins at index 10
    target, valid = vol_expansion_target(atrs, k=3, theta=1.5)
    assert valid[8] and target[8] == 1          # t=8 → fwd mean over 9,10,11 = (1+5+5)/3 > 1.5
    assert valid[6] and target[6] == 0          # t=6 → fwd 7,8,9 still flat
    assert not valid[-1] and not valid[-2] and not valid[-3]   # tail has no forward window


def test_vol_expansion_target_low_when_flat():
    atrs = np.array([1.0] * 20, dtype=float)
    target, valid = vol_expansion_target(atrs, k=4, theta=1.5)
    assert valid[5] and target[5] == 0          # flat forward → no expansion


def test_range_expansion_target_shape():
    candles = _series(40)
    target, valid = range_expansion_target(candles, k=4, theta=1.2)
    assert target.shape == valid.shape == (40,)
    assert not valid[-1]                          # no forward window at the tail


def test_persistence_target():
    labels = ["A", "A", "A", "A", "B", "B"]
    target, valid = persistence_target(labels, k=2)
    assert valid[0] and target[0] == 1           # A,A,A → persists 2 forward
    assert valid[2] and target[2] == 0           # A then A,B → breaks within 2
    na = ["x=NA", "A", "A"]
    _, v = persistence_target(na, k=1)
    assert not v[0]                               # NA cell invalid


def test_regime_transition_target_compression_to_expansion():
    vols = ["COMPRESSION", "NORMAL", "EXPANSION", "NORMAL", "NORMAL"]
    target, valid = regime_transition_target(vols, k=2, from_state="COMPRESSION", to_state="EXPANSION")
    assert valid[0] and target[0] == 1           # compression at 0 → expansion within 2
    assert not valid[1]                            # bar 1 not compression → invalid


# ── robustness kernels ──────────────────────────────────────────────────────────
def test_information_gain_perfectly_conditional():
    cells = ["A"] * 50 + ["B"] * 50
    target = np.array([1] * 50 + [0] * 50, dtype=np.int64)
    valid = np.ones(100, dtype=bool)
    assert abs(information_gain(cells, target, valid) - 1.0) < 1e-9


def test_mi_stability_pass_and_fail():
    cells = ["A"] * 50 + ["B"] * 50
    perfect = np.array([1] * 50 + [0] * 50, dtype=np.int64)
    valid = np.ones(100, dtype=bool)
    # train perfect, test perfect → retention 1.0 → PASS
    ok = mi_stability(cells, perfect, valid, cells, perfect, valid)
    assert ok["passed"] and ok["retention"] >= 0.5
    # train perfect, test random (IG≈0) → retention ≈0 → FAIL
    rng = np.random.default_rng(0)
    noise = rng.integers(0, 2, size=100).astype(np.int64)
    bad = mi_stability(cells, perfect, valid, cells, noise, valid)
    assert not bad["passed"]


def test_info_half_life():
    fast = {1: 0.20, 2: 0.05, 4: 0.01, 8: 0.0}   # collapses before bar 4 → FAIL
    assert info_half_life(fast)["half_life_bars"] < 4
    assert not info_half_life(fast)["passed"]
    slow = {1: 0.20, 2: 0.18, 4: 0.12, 8: 0.02}  # ≥50% of base at bar 4 → PASS
    assert info_half_life(slow)["passed"]


def test_cross_market_policy():
    assert cross_market(True, True) == "UNIVERSAL"
    assert cross_market(True, False) == "DOMAIN_SPECIFIC"
    assert cross_market(False, True) == "REJECTED"
    assert cross_market(False, False) == "REJECTED"


def test_permutation_p_is_deterministic():
    cells = ["A"] * 60 + ["B"] * 40
    target = np.array([1] * 40 + [0] * 20 + [1] * 10 + [0] * 30, dtype=np.int64)
    valid = np.ones(100, dtype=bool)
    a = permutation_p(cells, target, valid, n_permutations=200, name="det")
    b = permutation_p(cells, target, valid, n_permutations=200, name="det")
    assert a == b


# ── key_series ≡ build() (the efficiency optimisation is faithful) ──────────────
def test_key_series_matches_build_at_sampled_indices():
    enc = CandleStateEncoder()
    b = MultiTFConjunctionBuilder(enc)
    series = _series(500)
    keys = b.key_series(series)
    assert len(keys) == 500
    for t in (60, 137, 240, 399, 499):
        assert keys[t] == b.build(series[:t + 1]).key
