"""Derived-metric parity floor — binds the vectorized feature_pipeline columns to the scalar
derived_math primitives (the same discipline test_candle_math.py applies to candle geometry).

This is what makes the ontology's `derived_metrics` declarations AUTHORITATIVE: the pipeline that
actually produces the feature vector MUST equal the registered scalar definition, so the two can
never silently diverge (F-046 extended to normalized metrics, 2026-07-06).

The five ATR-normalized metrics (disp_strength, retest_depth, ema_spread, momentum_score,
volatility_ratio) are parity_verified against the pipeline column. liquidity_distance /
liquidity_pressure_score are lifecycle=registered (pipeline-column parity deferred — structural
level resolution); they carry scalar self-consistency tests only.
"""
from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from features import derived_math as dm
from features.feature_pipeline import FeaturePipeline


def _battery() -> pd.DataFrame:
    rng = np.random.default_rng(11)
    rows = []
    base = datetime(2026, 1, 1)
    for i in range(200):
        o, c = rng.uniform(10, 100), rng.uniform(10, 100)
        lo = min(o, c) - rng.uniform(0, 5)
        hi = max(o, c) + rng.uniform(0, 5)
        rows.append(dict(timestamp=base.replace(minute=i % 60, hour=(i // 60) % 24),
                         open=o, high=hi, low=lo, close=c, volume=rng.uniform(1, 1000)))
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def piped() -> pd.DataFrame:
    """Run the canonical pipeline stages that produce the derived metrics, with a positive
    atr_14_raw (so ATR>0 everywhere → no NaN-warmup rows) and retest_flag=1 (activates retest_depth)."""
    df = _battery()
    fp = FeaturePipeline(df)
    fp.compute_canonical_price_features()          # body_size, wick_size, body_ratio
    fp.df["atr_14_raw"] = (fp.df["high"] - fp.df["low"]).clip(lower=0.5)  # positive absolute ATR proxy
    fp.compute_canonical_volatility_features()     # atr, volatility_ratio
    fp.compute_canonical_ema_features()            # ema_fast, ema_slow, ema_spread, momentum_score
    fp.df["retest_flag"] = 1
    fp.compute_canonical_temporal_features()       # disp_strength, retest_depth
    return fp.df


def test_disp_strength_matches_pipeline(piped):
    for _, r in piped.iterrows():
        assert r["disp_strength"] == pytest.approx(
            dm.disp_strength(r["body_size"], r["atr"], r["close"]), rel=1e-5, abs=1e-6)


def test_retest_depth_matches_pipeline(piped):
    for _, r in piped.iterrows():
        assert r["retest_depth"] == pytest.approx(
            dm.retest_depth(r["close"], r["ema_fast"], r["atr"]), rel=1e-5, abs=1e-6)


def test_ema_spread_matches_pipeline(piped):
    for _, r in piped.iterrows():
        assert r["ema_spread"] == pytest.approx(
            dm.ema_spread(r["ema_fast"], r["ema_slow"], r["atr"]), rel=1e-5, abs=1e-6)


def test_momentum_score_matches_pipeline(piped):
    close_delta = piped["close"].diff()
    for i, (_, r) in enumerate(piped.iterrows()):
        if i == 0:
            continue  # first diff is NaN (pipeline drops it via NaN → warmup)
        assert r["momentum_score"] == pytest.approx(
            dm.momentum_score(close_delta.iloc[i], r["atr"]), rel=1e-5, abs=1e-6)


def test_volatility_ratio_matches_pipeline(piped):
    for _, r in piped.iterrows():
        assert r["volatility_ratio"] == pytest.approx(
            dm.volatility_ratio(r["high"], r["low"], r["atr"], r["close"]), rel=1e-5, abs=1e-6)


# ── Fallback discipline (mirrors the pipeline sentinels exactly) ──────────────────────────
def test_atr_unavailable_fallbacks():
    assert dm.disp_strength(1.0, 0.0, 100.0) != dm.disp_strength(1.0, 0.0, 100.0)   # NaN
    assert dm.ema_spread(1.0, 2.0, 0.0) != dm.ema_spread(1.0, 2.0, 0.0)             # NaN
    assert dm.momentum_score(1.0, 0.0) != dm.momentum_score(1.0, 0.0)               # NaN
    assert dm.retest_depth(100.0, 99.0, 0.0) == 0.0                                 # 0.0 sentinel
    assert dm.volatility_ratio(110.0, 95.0, 0.0, 100.0) == 1.0                      # 1.0 neutral


def test_clip_bounds():
    assert 0.0 <= dm.disp_strength(1e9, 0.01, 100.0) <= 3.0
    assert 0.0 <= dm.retest_depth(1e9, 0.0, 0.01) <= 1.0 or dm.retest_depth(1e9, 0.0, 0.01) == 0.0


# ── liquidity_* : scalar self-consistency (lifecycle=registered, pipeline parity deferred) ──
def test_liquidity_distance_nearest_level():
    # nearest of {|100-101|, |100-98|} / (0.01*100=1.0) = min(1,2)/1 = 1.0
    assert dm.liquidity_distance(100.0, 0.01, 101.0, 98.0) == pytest.approx(1.0)
    # NaN levels are dropped; no finite level → NaN
    nan = float("nan")
    assert dm.liquidity_distance(100.0, 0.01, nan) != dm.liquidity_distance(100.0, 0.01, nan)
    # atr*close <= 0 → NaN
    assert dm.liquidity_distance(100.0, 0.0, 101.0) != dm.liquidity_distance(100.0, 0.0, 101.0)


def test_liquidity_pressure_score_bounds():
    assert dm.liquidity_pressure_score(0.0) == pytest.approx(1.0)      # exp(0)
    assert 0.0 <= dm.liquidity_pressure_score(float("nan")) <= 1.0     # NaN → 10.0 sentinel → exp(-5)
    assert dm.liquidity_pressure_score(float("nan")) == pytest.approx(np.exp(-5.0))
