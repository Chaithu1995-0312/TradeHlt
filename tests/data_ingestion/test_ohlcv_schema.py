"""
test_ohlcv_schema.py
====================
Strict historical-data schema enforcement (no defaults).

Phase 1 — column presence: each of the six mandatory columns
(timestamp, open, high, low, close, volume) must exist or load fails.
Phase 2 — value integrity: no NaN/non-numeric, volume >= 0, candle high/low
consistent with open/close.

Covers self-review items 1-8: a missing timestamp/open/high/low/close/volume
each raises, no defaults remain, and no fillna recreates a missing column.
"""

import numpy as np
import pandas as pd
import pytest

from data_ingestion.ohlcv_schema import (
    REQUIRED_OHLCV_COLUMNS,
    require_ohlcv_columns,
    resolve_ohlcv_headers,
    validate_ohlcv_frame,
    validate_ohlcv_row,
)

_SIX = ["timestamp", "open", "high", "low", "close", "volume"]


def _valid_frame(n: int = 8) -> pd.DataFrame:
    close = np.linspace(1.10, 1.11, n)
    open_ = close - 0.0001
    high = np.maximum(open_, close) + 0.0002
    low = np.minimum(open_, close) - 0.0002
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="15min"),
        "open": open_, "high": high, "low": low, "close": close,
        "volume": np.linspace(100, 200, n),
    })


# ── Phase 1: presence ──────────────────────────────────────────────────────
@pytest.mark.parametrize("missing_col", _SIX)
def test_require_columns_raises_on_each_missing(missing_col):
    df = _valid_frame().drop(columns=[missing_col])
    with pytest.raises(ValueError) as exc:
        require_ohlcv_columns(df.columns)
    assert str(exc.value) == f"Historical dataset missing required columns: {missing_col}"


def test_require_columns_multi_missing_sorted():
    df = _valid_frame().drop(columns=["close", "volume"])
    with pytest.raises(ValueError) as exc:
        require_ohlcv_columns(df.columns)
    assert str(exc.value) == "Historical dataset missing required columns: close, volume"


def test_require_columns_custom_source_in_message():
    df = _valid_frame().drop(columns=["volume"])
    with pytest.raises(ValueError) as exc:
        require_ohlcv_columns(df.columns, source="FeaturePipeline")
    assert str(exc.value) == "FeaturePipeline missing required columns: volume"


def test_require_columns_happy_path_no_raise():
    require_ohlcv_columns(_valid_frame().columns)  # must not raise


def test_required_set_is_exactly_the_six():
    assert REQUIRED_OHLCV_COLUMNS == frozenset(_SIX)


# ── Phase 2: value integrity (frame) ───────────────────────────────────────
@pytest.mark.parametrize("col", _SIX)
def test_frame_raises_on_nan_in_each_column(col):
    df = _valid_frame()
    df.loc[3, col] = np.nan
    with pytest.raises(ValueError, match="NaN/empty values"):
        validate_ohlcv_frame(df)


def test_frame_raises_on_negative_volume():
    df = _valid_frame()
    df.loc[2, "volume"] = -1.0
    with pytest.raises(ValueError, match="negative volume"):
        validate_ohlcv_frame(df)


def test_frame_allows_all_zero_numeric_volume():
    df = _valid_frame()
    df["volume"] = 0.0
    validate_ohlcv_frame(df)  # zero is valid data (forex) — must not raise


def test_frame_raises_when_high_below_low():
    df = _valid_frame()
    df["high"] = df["low"] - 0.01
    with pytest.raises(ValueError, match="inconsistent candles"):
        validate_ohlcv_frame(df)


def test_frame_raises_when_high_below_close():
    df = _valid_frame()
    df.loc[1, "high"] = df.loc[1, "close"] - 0.01
    with pytest.raises(ValueError, match="inconsistent candles"):
        validate_ohlcv_frame(df)


def test_frame_raises_when_low_above_open():
    df = _valid_frame()
    df.loc[1, "low"] = df.loc[1, "open"] + 0.01
    with pytest.raises(ValueError, match="inconsistent candles"):
        validate_ohlcv_frame(df)


def test_frame_happy_path_no_raise():
    validate_ohlcv_frame(_valid_frame())


# ── Phase 2: value integrity (row) ─────────────────────────────────────────
def test_row_happy_path():
    validate_ohlcv_row(1.0, 1.2, 0.9, 1.1, 100.0)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), None])
def test_row_raises_on_nan_inf_none(bad):
    with pytest.raises(ValueError):
        validate_ohlcv_row(1.0, 1.2, 0.9, bad, 100.0)


def test_row_raises_on_negative_volume():
    with pytest.raises(ValueError, match="negative volume"):
        validate_ohlcv_row(1.0, 1.2, 0.9, 1.1, -5.0)


def test_row_raises_on_inconsistent_candle():
    with pytest.raises(ValueError, match="inconsistent candle"):
        validate_ohlcv_row(1.0, 0.8, 0.9, 1.1, 100.0)  # high < low


def test_row_allows_zero_volume_and_flat_candle():
    validate_ohlcv_row(1.0, 1.0, 1.0, 1.0, 0.0)  # high==low==open==close, vol 0


# ── Header resolver ────────────────────────────────────────────────────────
def test_resolve_headers_aliases():
    resolved = resolve_ohlcv_headers(
        ["DateTime", "Open", "High", "Low", "Close", "tick_volume"]
    )
    assert set(resolved.keys()) == set(_SIX)
    assert resolved["volume"] == "tick_volume"
    assert resolved["timestamp"] == "DateTime"


def test_resolve_headers_missing_volume_not_resolved():
    resolved = resolve_ohlcv_headers(["timestamp", "open", "high", "low", "close"])
    assert "volume" not in resolved
    with pytest.raises(ValueError, match="missing required columns: volume"):
        require_ohlcv_columns(resolved.keys())
