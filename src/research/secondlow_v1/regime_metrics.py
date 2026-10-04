"""Lightweight volatility regime descriptors at purge time (descriptive only)."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from research.secondlow_v1.detector import compute_true_range_atr


@dataclass(frozen=True)
class RegimeMetricRow:
    purge_time: pd.Timestamp
    atr_14: float
    atr_100: float
    atr_200: float
    atr_ratio_14_over_100: float
    atr_ratio_14_over_200: float
    parkinson_vol_20: float
    parkinson_vol_100: float
    parkinson_ratio_20_over_100: float
    atr_above_p70_threshold_200: bool
    binary_high_atr_ratio_1_2: bool


def _parkinson_variance(high: pd.Series, low: pd.Series) -> pd.Series:
    """Per-bar Parkinson variance contribution."""
    ratio = (high / low).clip(lower=1e-12)
    return (math.log(2) ** -1) * (np.log(ratio) ** 2)


def compute_regime_series(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["atr_14"] = compute_true_range_atr(out, period=14)
    out["atr_100"] = compute_true_range_atr(out, period=100)
    out["atr_200"] = compute_true_range_atr(out, period=200)
    pk = _parkinson_variance(out["high"], out["low"])
    out["parkinson_vol_20"] = np.sqrt(pk.rolling(20, min_periods=10).mean())
    out["parkinson_vol_100"] = np.sqrt(pk.rolling(100, min_periods=50).mean())
    rolling200 = out["atr_14"].rolling(200, min_periods=100)
    out["atr_p70_threshold_200"] = rolling200.quantile(0.70)
    out["atr_percentile_proxy"] = (out["atr_14"] >= out["atr_p70_threshold_200"]).astype(float)
    return out


def regime_metrics_at_purge(df: pd.DataFrame, purge_pos: int) -> RegimeMetricRow | None:
    work = compute_regime_series(df)
    atr14 = float(work["atr_14"].iloc[purge_pos])
    atr100 = float(work["atr_100"].iloc[purge_pos])
    atr200 = float(work["atr_200"].iloc[purge_pos])
    pk20 = float(work["parkinson_vol_20"].iloc[purge_pos])
    pk100 = float(work["parkinson_vol_100"].iloc[purge_pos])
    p70 = work["atr_p70_threshold_200"].iloc[purge_pos]
    above_p70 = bool(work["atr_percentile_proxy"].iloc[purge_pos] == 1.0)

    if not all(np.isfinite(v) and v > 0 for v in [atr14, atr100, atr200, pk20, pk100]):
        return None

    atr_r100 = atr14 / atr100
    atr_r200 = atr14 / atr200
    pk_ratio = pk20 / pk100

    return RegimeMetricRow(
        purge_time=work.index[purge_pos],
        atr_14=atr14,
        atr_100=atr100,
        atr_200=atr200,
        atr_ratio_14_over_100=atr_r100,
        atr_ratio_14_over_200=atr_r200,
        parkinson_vol_20=pk20,
        parkinson_vol_100=pk100,
        parkinson_ratio_20_over_100=pk_ratio,
        atr_above_p70_threshold_200=above_p70,
        binary_high_atr_ratio_1_2=atr_r100 > 1.2,
    )