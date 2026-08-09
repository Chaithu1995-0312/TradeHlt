"""SECONDLOW-v1 purge detector (trading-day second_low_20d ladder).

Canonical ladder uses trading days with at least one M15 bar. Calendar-day resample
returns zero events on the MT5 corpus; see tests/research/test_secondlow_v1_detector_regression.py.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

DISCOVERY_START = pd.Timestamp("2026-04-17")
DISCOVERY_END = pd.Timestamp("2026-05-22")
MIN_EVENT_SPACING_MIN = 120
ATR_PERIOD = 14
LOOKBACK_TRADING_DAYS = 20
POST_WINDOW_BARS = 8

ExposureGroup = Literal["EXPOSED", "PARTIAL", "BASELINE"]


@dataclass(frozen=True)
class SecondLowEvent:
    purge_time: pd.Timestamp
    purge_low: float
    second_low_20d: float
    purge_depth_price: float
    atr_at_purge: float
    pre_2h_return_atr: float
    purge_depth_atr: float
    close_disp_atr: float | None


def sha256_prefix(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def load_ohlcv(path: Path | str) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp").sort_index()
    df = df.rename(columns={c: c.lower() for c in df.columns})
    required = {"open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"OHLCV missing columns: {sorted(missing)}")
    cols = list(required | ({"volume"} & set(df.columns)))
    return df[cols]


def compute_true_range_atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period, min_periods=max(1, period // 2)).mean()


def compute_trading_day_second_low(df: pd.DataFrame, lookback: int = LOOKBACK_TRADING_DAYS) -> pd.Series:
    daily = df.groupby(df.index.normalize()).agg(Low=("low", "min"))
    daily.index = pd.DatetimeIndex(daily.index)
    second_low = daily["Low"].rolling(lookback, min_periods=lookback).apply(
        lambda x: sorted(x.dropna())[1] if len(x.dropna()) >= 2 else np.nan,
        raw=False,
    ).shift(1)
    return second_low.reindex(df.index, method="ffill")


def _detect_raw_purge_mask(df: pd.DataFrame, second_low_col: str = "second_low_20d") -> np.ndarray:
    n = len(df)
    event = np.zeros(n, dtype=bool)
    armed = False
    sl = df[second_low_col].to_numpy()
    lows = df["low"].to_numpy()
    closes = df["close"].to_numpy()
    for i in range(n):
        if np.isnan(sl[i]):
            continue
        if not armed:
            if lows[i] < sl[i]:
                event[i] = True
                armed = True
        else:
            if closes[i] >= sl[i]:
                armed = False
    return event


def _independent_indices(
    index: pd.DatetimeIndex,
    raw_mask: np.ndarray,
    min_spacing_min: int = MIN_EVENT_SPACING_MIN,
) -> list[int]:
    positions = list(np.where(raw_mask)[0])
    if not positions:
        return []
    selected = [positions[0]]
    last_time = index[positions[0]]
    for pos in positions[1:]:
        t = index[pos]
        if (t - last_time).total_seconds() / 60 >= min_spacing_min:
            selected.append(pos)
            last_time = t
    return selected


def _strict_post_window(df: pd.DataFrame, purge_pos: int) -> pd.DataFrame | None:
    post = df.iloc[purge_pos + 1 : purge_pos + 1 + POST_WINDOW_BARS]
    if len(post) != POST_WINDOW_BARS:
        return None
    expected_first = df.index[purge_pos] + timedelta(minutes=15)
    if post.index[0] != expected_first:
        return None
    return post


def detect_independent_events(
    df: pd.DataFrame,
    *,
    require_post_window: bool = False,
) -> tuple[np.ndarray, list[SecondLowEvent]]:
    """Return (raw_purge_mask, independent_events)."""
    work = df.copy()
    work["atr"] = compute_true_range_atr(work)
    work["second_low_20d"] = compute_trading_day_second_low(work)
    raw_mask = _detect_raw_purge_mask(work)
    events: list[SecondLowEvent] = []
    for pos in _independent_indices(work.index, raw_mask):
        post = _strict_post_window(work, pos) if require_post_window else None
        if require_post_window and post is None:
            continue
        t = work.index[pos]
        entry = float(work["close"].iloc[pos])
        low = float(work["low"].iloc[pos])
        sl = float(work["second_low_20d"].iloc[pos])
        atr = float(work["atr"].iloc[pos])
        if not np.isfinite(atr) or atr <= 0:
            continue
        pre_start = max(0, pos - 8)
        pre_close = float(work["close"].iloc[pre_start])
        pre_2h = (entry - pre_close) / atr
        depth_price = sl - low
        depth_atr = depth_price / atr
        close_disp_atr = None
        if post is not None:
            close_disp_atr = float((post["close"].iloc[-1] - entry) / atr)
        events.append(
            SecondLowEvent(
                purge_time=t,
                purge_low=low,
                second_low_20d=sl,
                purge_depth_price=depth_price,
                atr_at_purge=atr,
                pre_2h_return_atr=pre_2h,
                purge_depth_atr=depth_atr,
                close_disp_atr=close_disp_atr,
            )
        )
    return raw_mask, events


def partition_event_times(
    times: pd.Series | list[pd.Timestamp],
    *,
    discovery_start: pd.Timestamp = DISCOVERY_START,
    discovery_end: pd.Timestamp = DISCOVERY_END,
) -> dict[str, list[pd.Timestamp]]:
    series = pd.Series(times).sort_values()
    pre = series[series < discovery_start].tolist()
    disc = series[(series >= discovery_start) & (series <= discovery_end)].tolist()
    post = series[series > discovery_end].tolist()
    return {"pre_discovery": pre, "discovery": disc, "post_discovery": post}


def classify_exposure(
    pre_2h_return_atr: float,
    purge_depth_atr: float,
    *,
    pre_2h_threshold: float = -2.0,
    depth_threshold: float = 1.5,
) -> ExposureGroup:
    a = pre_2h_return_atr <= pre_2h_threshold
    b = purge_depth_atr >= depth_threshold
    if a and b:
        return "EXPOSED"
    if a ^ b:
        return "PARTIAL"
    return "BASELINE"