# tests/test_volatility_regime.py
"""
volatility_regime = causal trailing percentile of ATR(14) against the prior 200 bars.
Spec: current bar excluded, mid-rank ties, NaN until a full valid window, missing -> NaN.
"""

import numpy as np
import pandas as pd
import pytest

from features.feature_pipeline import (
    FeaturePipeline, VOL_REGIME_WINDOW, trailing_atr_percentile,
)

W = VOL_REGIME_WINDOW


def test_constants():
    assert W == 200


def test_warmup_is_nan_until_full_window():
    out = trailing_atr_percentile(np.arange(W + 5, dtype=float), W)
    assert np.isnan(out[:W]).all()
    assert not np.isnan(out[W:]).any()


def test_too_short_series_is_all_nan():
    assert np.isnan(trailing_atr_percentile(np.arange(W, dtype=float), W)).all()


def test_current_bar_does_not_participate():
    ref = np.linspace(1.0, 2.0, W)
    high = np.append(ref, 99.0)         # above every prior value
    low = np.append(ref, -99.0)         # below every prior value
    assert trailing_atr_percentile(high, W)[-1] == 1.0     # would be capped below 1 if included
    assert trailing_atr_percentile(low, W)[-1] == 0.0      # would be >= 1/200 if included


def test_mid_rank_ties():
    ref = np.full(W, 5.0)
    assert trailing_atr_percentile(np.append(ref, 5.0), W)[-1] == 0.5
    half = np.concatenate([np.full(W // 2, 1.0), np.full(W // 2, 5.0)])
    # 100 below, 100 equal -> (100 + 0.5*100)/200 = 0.75
    assert trailing_atr_percentile(np.append(half, 5.0), W)[-1] == pytest.approx(0.75)


def test_missing_values_give_nan_never_a_neutral_class():
    base = np.linspace(1.0, 2.0, W + 3)
    cur_nan = base.copy(); cur_nan[-1] = np.nan
    assert np.isnan(trailing_atr_percentile(cur_nan, W)[-1])
    ref_nan = base.copy(); ref_nan[10] = np.nan
    out = trailing_atr_percentile(ref_nan, W)
    assert np.isnan(out[W: W + 10]).all()      # windows containing index 10 are undefined
    assert not np.isnan(out[W + 11:]).any()    # windows past it are defined again
    inf = base.copy(); inf[-1] = np.inf
    assert np.isnan(trailing_atr_percentile(inf, W)[-1])


def test_causal_future_bars_do_not_change_past_values():
    rng = np.random.default_rng(0)
    x = np.abs(rng.normal(1.0, 0.3, W + 80))
    full = trailing_atr_percentile(x, W)
    for cut in (W + 1, W + 30, W + 79):
        part = trailing_atr_percentile(x[:cut], W)
        np.testing.assert_array_equal(part[W:], full[W:cut])


def _ohlcv(n, seed=3):
    rng = np.random.default_rng(seed)
    ts = pd.date_range("2024-01-01", periods=n, freq="15min")
    close = 100 + np.cumsum(rng.normal(0, 0.2, n))
    wick = np.abs(rng.normal(0, 0.3, n)); body = rng.normal(0, 0.2, n)
    o = close - body
    return pd.DataFrame({"timestamp": ts, "open": o, "high": np.maximum(o, close) + wick,
                         "low": np.minimum(o, close) - wick, "close": close,
                         "volume": rng.uniform(100, 2000, n)})


@pytest.fixture(scope="module")
def full_output():
    df, _ = FeaturePipeline(_ohlcv(700)).run()
    return df


def test_pipeline_values_dtype_and_dropped_warmup(full_output):
    df = full_output
    assert df["volatility_regime"].dtype == np.int8
    assert set(df["volatility_regime"].unique()) <= {0, 1, 2}
    raw = _ohlcv(700)
    # first defined regime needs ATR(14) (index 14) + 200 prior ATRs -> index 214 or later
    assert df["timestamp"].iloc[0] >= raw["timestamp"].iloc[W + 14]


def test_pipeline_regime_is_unaffected_by_truncating_the_future(full_output):
    part, _ = FeaturePipeline(_ohlcv(700).iloc[:560]).run()
    common = part["timestamp"].iloc[:-3]   # last rows of a truncated frame are affected by other (swing) features
    a = part.set_index("timestamp").loc[common, "volatility_regime"]
    b = full_output.set_index("timestamp").loc[common, "volatility_regime"]
    pd.testing.assert_series_equal(a, b)


def test_pipeline_regime_independent_of_input_slice(full_output):
    # same bars, different amount of history after them -> same label (old full-file rank failed this)
    part, _ = FeaturePipeline(_ohlcv(700).iloc[:650]).run()
    ts = part["timestamp"].iloc[100]
    assert part.set_index("timestamp").loc[ts, "volatility_regime"] == full_output.set_index("timestamp").loc[ts, "volatility_regime"]
