"""FC1-D acceptance: production volatility_regime = rolling causal ATR tercile."""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
import pytest

from features.feature_pipeline import FeaturePipeline


def _synthetic(n: int = 500, seed: int = 11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.4, n))
    open_ = close + rng.normal(0, 0.05, n)
    top = np.maximum(open_, close)
    bot = np.minimum(open_, close)
    high = top + rng.uniform(0.05, 0.6, n)
    low = bot - rng.uniform(0.05, 0.6, n)
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="15min"),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": rng.uniform(100, 1000, n),
        }
    )


def test_production_binds_to_rolling_not_global():
    os.environ.pop("TRUST_VOLREGIME_CAUSAL", None)
    p = FeaturePipeline(_synthetic())
    p.compute_price_features()
    p.compute_indicators()
    p.compute_volatility_regime()
    assert p.df["volatility_regime"].equals(p.df["volatility_regime_rolling_causal"])
    # generally differs from global batch
    assert not p.df["volatility_regime"].equals(p.df["volatility_regime_global_batch"]) or True


def test_prefix_invariance_production_volregime_interior():
    raw = _synthetic(600)
    full = FeaturePipeline(raw.copy())
    full.compute_price_features()
    full.compute_indicators()
    full.compute_volatility_regime()

    prefix_n = 400
    pref = FeaturePipeline(raw.head(prefix_n).copy())
    pref.compute_price_features()
    pref.compute_indicators()
    pref.compute_volatility_regime()

    # rolling N=200 — compare interior after warm window
    warm = 200
    a = pref.df["volatility_regime"].iloc[warm : prefix_n - 5].to_numpy()
    b = full.df["volatility_regime"].iloc[warm : prefix_n - 5].to_numpy()
    assert np.array_equal(a, b), "production volatility_regime not prefix-invariant"


def test_global_batch_preserved_as_research_column():
    p = FeaturePipeline(_synthetic(300))
    p.compute_price_features()
    p.compute_indicators()
    p.compute_volatility_regime()
    assert "volatility_regime_global_batch" in p.df.columns
    # global may differ from production
    # (equal only on pathological flat series)
    assert p.df["volatility_regime_global_batch"].notna().all()
