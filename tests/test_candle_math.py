"""Candle-geometry single-source-of-truth floor.

Enforces that the three historical computation sites for candle geometry agree with the
canonical primitives in src/features/candle_math.py:
  - the scalar primitives themselves (mathematical identities),
  - the CRT engine `Candle` property (crt_engine_v2.py),
  - the vectorized batch pipeline (feature_pipeline.py compute_canonical_price_features).

Background: `wick_size`/`body_ratio` previously diverged — the single-row builder used
body/total_wick (unbounded), while CRT + pipeline use the canonical body/candle_range
(bounded [0,1], the definition the `body_ratio < 0.70` displacement gate is coherent against).
See docs/topics/model-intent-and-feature-ownership.md (Feature Lineage Matrix).
"""
from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from features import candle_math as cm
from config_layer.crt_engine_v2 import Candle
from features.feature_pipeline import FeaturePipeline


# The worked example from the design discussion: O=100 H=110 L=95 C=108.
_WORKED = dict(open_=100.0, high=110.0, low=95.0, close=108.0)


def test_worked_example_primitives():
    assert cm.body_size(100.0, 108.0) == 8.0
    assert cm.candle_range(110.0, 95.0) == 15.0
    assert cm.upper_wick(100.0, 110.0, 108.0) == 2.0     # high - max(open, close)
    assert cm.lower_wick(100.0, 95.0, 108.0) == 5.0      # min(open, close) - low
    assert cm.total_wick(100.0, 110.0, 95.0, 108.0) == 7.0
    assert cm.body_ratio(**_WORKED) == pytest.approx(8.0 / 15.0)   # 0.5333, NOT 8/7


def test_body_ratio_is_bounded_zero_one():
    rng = np.random.default_rng(0)
    for _ in range(2000):
        o, c = rng.uniform(1, 100), rng.uniform(1, 100)
        lo = min(o, c) - rng.uniform(0, 10)
        hi = max(o, c) + rng.uniform(0, 10)
        r = cm.body_ratio(o, hi, lo, c)
        assert 0.0 <= r <= 1.0


def test_total_wick_identity():
    """total_wick == candle_range - body_size, for any OHLC."""
    rng = np.random.default_rng(1)
    for _ in range(2000):
        o, c = rng.uniform(1, 100), rng.uniform(1, 100)
        lo = min(o, c) - rng.uniform(0, 10)
        hi = max(o, c) + rng.uniform(0, 10)
        assert cm.total_wick(o, hi, lo, c) == pytest.approx(
            cm.candle_range(hi, lo) - cm.body_size(o, c)
        )


def test_degenerate_flat_bar_returns_zero():
    # high == low → range 0 → body_ratio guarded to 0.0 (no ZeroDivisionError).
    assert cm.body_ratio(50.0, 50.0, 50.0, 50.0) == 0.0
    assert cm.candle_range(50.0, 50.0) == 0.0


def test_crt_candle_property_matches_primitive():
    c = Candle(timestamp=datetime(2026, 1, 1), open=100.0, high=110.0, low=95.0, close=108.0)
    assert c.body_size == cm.body_size(100.0, 108.0)
    assert c.wick_size == cm.candle_range(110.0, 95.0)
    assert c.body_ratio == cm.body_ratio(**_WORKED)


def _battery() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    rows = []
    base = datetime(2026, 1, 1)
    for i in range(200):
        o, c = rng.uniform(10, 100), rng.uniform(10, 100)
        lo = min(o, c) - rng.uniform(0, 5)
        hi = max(o, c) + rng.uniform(0, 5)
        rows.append(
            dict(timestamp=base.replace(minute=i % 60, hour=(i // 60) % 24),
                 open=o, high=hi, low=lo, close=c, volume=rng.uniform(1, 1000))
        )
    return pd.DataFrame(rows)


def test_pipeline_vectorized_equals_scalar_primitive():
    df = _battery()
    fp = FeaturePipeline(df)
    fp.compute_canonical_price_features()
    out = fp.df
    for _, row in out.iterrows():
        o, h, l, c = row["open"], row["high"], row["low"], row["close"]
        # float32 columns → tolerance
        assert row["body_size"] == pytest.approx(cm.body_size(o, c), rel=1e-6)
        assert row["wick_size"] == pytest.approx(cm.candle_range(h, l), rel=1e-6)
        assert row["body_ratio"] == pytest.approx(cm.body_ratio(o, h, l, c), rel=1e-5, abs=1e-6)
