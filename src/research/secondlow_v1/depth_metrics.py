"""Alternative purge-depth metrics (descriptive / pre-reg only — not production defaults)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from research.secondlow_v1.detector import (
    LOOKBACK_TRADING_DAYS,
    compute_true_range_atr,
    compute_trading_day_second_low,
)


@dataclass(frozen=True)
class DepthMetricRow:
    purge_time: pd.Timestamp
    purge_low: float
    atr_14: float
    atr_100: float
    second_low_20d: float
    lowest_low_20d: float
    baseline_depth_atr: float
    lowest_low_depth_atr: float
    regime_normalized_depth_atr: float
    rolling_min_zscore: float | None


def compute_lowest_low_20d(df: pd.DataFrame) -> pd.Series:
    daily = df.groupby(df.index.normalize()).agg(Low=("low", "min"))
    daily.index = pd.DatetimeIndex(daily.index)
    lowest = daily["Low"].rolling(LOOKBACK_TRADING_DAYS, min_periods=LOOKBACK_TRADING_DAYS).min().shift(1)
    return lowest.reindex(df.index, method="ffill")


def compute_rolling_min_zscore(df: pd.DataFrame, window: int = 50) -> pd.Series:
    daily = df.groupby(df.index.normalize()).agg(Low=("low", "min"))
    daily.index = pd.DatetimeIndex(daily.index)
    rolling_min = daily["Low"].rolling(window, min_periods=window).min()
    rolling_std = daily["Low"].rolling(window, min_periods=window).std()
    z = (daily["Low"] - rolling_min) / rolling_std
    return z.reindex(df.index, method="ffill")


def depth_metrics_at_purge(df: pd.DataFrame, purge_pos: int) -> DepthMetricRow | None:
    work = df.copy()
    work["atr_14"] = compute_true_range_atr(work, period=14)
    work["atr_100"] = compute_true_range_atr(work, period=100)
    work["second_low_20d"] = compute_trading_day_second_low(work)
    work["lowest_low_20d"] = compute_lowest_low_20d(work)
    work["rolling_min_z"] = compute_rolling_min_zscore(work)

    t = work.index[purge_pos]
    atr = float(work["atr_14"].iloc[purge_pos])
    atr100 = float(work["atr_100"].iloc[purge_pos])
    low = float(work["low"].iloc[purge_pos])
    sl = work["second_low_20d"].iloc[purge_pos]
    ll = work["lowest_low_20d"].iloc[purge_pos]
    z = work["rolling_min_z"].iloc[purge_pos]

    if not np.isfinite(atr) or atr <= 0 or pd.isna(sl) or pd.isna(ll):
        return None

    baseline = float((sl - low) / atr)
    lowest_low = float((ll - low) / atr)
    regime_factor = atr / atr100 if np.isfinite(atr100) and atr100 > 0 else np.nan
    regime_norm = baseline / regime_factor if np.isfinite(regime_factor) and regime_factor > 0 else np.nan
    zscore = float(z) if np.isfinite(z) else None

    return DepthMetricRow(
        purge_time=t,
        purge_low=low,
        atr_14=atr,
        atr_100=atr100,
        second_low_20d=float(sl),
        lowest_low_20d=float(ll),
        baseline_depth_atr=baseline,
        lowest_low_depth_atr=lowest_low,
        regime_normalized_depth_atr=regime_norm,
        rolling_min_zscore=zscore,
    )