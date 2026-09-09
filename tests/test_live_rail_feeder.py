"""PR-4b: LiveRailFeeder warmup + 48-dim keys + no zero-fill."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from config_layer.crt_engine_v2 import Candle
from features.feature_pipeline import required_warmup_rows
from features.feature_schema import CANONICAL_FEATURE_DIM, CANONICAL_FEATURES
from inout.live_rail.types import ClockBasis, ClosedBar, VenueName
from runtime.live_rail_feeder import REQUIRED_LIVE_TRADE_DATA_KEYS, LiveRailFeeder

_PORTFOLIO = {
    "account_balance": 10_000.0,
    "total_open_risk_pct": 0.0,
    "trades_today": 0,
    "daily_loss_pct": 0.0,
    "open_positions": 0,
    "positions": {},
}


def _bar(i: int, *, seed: int = 7) -> ClosedBar:
    rng = np.random.default_rng(seed + i)
    close = 2000.0 + float(np.cumsum(rng.normal(0.0, 0.4, i + 1))[-1])
    high = close + abs(float(rng.normal(0.0, 0.3)))
    low = close - abs(float(rng.normal(0.0, 0.3)))
    open_ = close - float(rng.normal(0.0, 0.2))
    ts = datetime(2026, 1, 2, 1, 0, tzinfo=timezone.utc) + timedelta(minutes=15 * i)
    high = max(high, open_, close)
    low = min(low, open_, close)
    candle = Candle(
        timestamp=ts,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=float(100 + i),
        index=i,
    )
    return ClosedBar(
        candle=candle,
        extras={},
        symbol="XAUUSD",
        clock_basis=ClockBasis.BROKER_LOCAL,
        venue=VenueName.TICKDB,
        n_ticks=1,
        period_start=ts,
        period_end=ts + timedelta(minutes=15),
    )


def test_warmup_matches_required_warmup_rows() -> None:
    feeder = LiveRailFeeder(symbol="XAUUSD", timeframe="M15")
    assert feeder.warmup_rows == required_warmup_rows()
    assert feeder.warmup_rows == 78


def test_not_ready_before_or_at_warmup_prefix() -> None:
    """T-16: finalize() drops 78 rows. 78 pushes leave 0 feature rows."""
    feeder = LiveRailFeeder(symbol="XAUUSD", timeframe="M15")
    warmup = feeder.warmup_rows
    for i in range(warmup):
        feeder.push(_bar(i))
        assert feeder.ready() is False
    with pytest.raises(RuntimeError, match="before ready"):
        feeder.as_trade_data(_bar(warmup - 1), _PORTFOLIO)


def test_ready_on_first_bar_after_prefix() -> None:
    feeder = LiveRailFeeder(symbol="XAUUSD", timeframe="M15")
    n = feeder.warmup_rows + 1
    last = None
    for i in range(n):
        last = _bar(i)
        feeder.push(last)
    assert feeder.ready() is True
    assert last is not None
    data = feeder.as_trade_data(last, _PORTFOLIO)
    assert data["symbol"] == "XAUUSD"
    assert data["timeframe"] == "M15"


def test_as_trade_data_has_all_required_keys_and_48_canonical() -> None:
    feeder = LiveRailFeeder(symbol="XAUUSD", timeframe="M15")
    last = None
    for i in range(feeder.warmup_rows + 1):
        last = _bar(i)
        feeder.push(last)
    data = feeder.as_trade_data(last, _PORTFOLIO)
    missing = sorted(REQUIRED_LIVE_TRADE_DATA_KEYS - set(data))
    assert missing == [], missing
    for name in CANONICAL_FEATURES:
        assert name in data, name
        assert data[name] is not None
        val = float(data[name])
        assert val == val and val not in (float("inf"), float("-inf"))
    assert len(CANONICAL_FEATURES) == CANONICAL_FEATURE_DIM == 48
    assert data["macd_hist"] == pytest.approx(float(data["macd_hist_z"]))
    for smc in (
        "order_block_distance",
        "fvg_distance",
        "change_of_character",
        "liquidity_distance",
        "volume_spike",
    ):
        assert smc in data


def test_no_zero_fill_on_missing_portfolio_key() -> None:
    feeder = LiveRailFeeder(symbol="XAUUSD", timeframe="M15")
    last = None
    for i in range(feeder.warmup_rows + 1):
        last = _bar(i)
        feeder.push(last)
    broken = dict(_PORTFOLIO)
    del broken["account_balance"]
    with pytest.raises(KeyError, match="account_balance"):
        feeder.as_trade_data(last, broken)


def test_no_zero_fill_on_missing_positions() -> None:
    feeder = LiveRailFeeder(symbol="XAUUSD", timeframe="M15")
    last = None
    for i in range(feeder.warmup_rows + 1):
        last = _bar(i)
        feeder.push(last)
    broken = dict(_PORTFOLIO)
    del broken["positions"]
    with pytest.raises(KeyError, match="positions"):
        feeder.as_trade_data(last, broken)


def test_wrong_bar_refused() -> None:
    feeder = LiveRailFeeder(symbol="XAUUSD", timeframe="M15")
    last = None
    for i in range(feeder.warmup_rows + 1):
        last = _bar(i)
        feeder.push(last)
    with pytest.raises(ValueError, match="not the last"):
        feeder.as_trade_data(_bar(0), _PORTFOLIO)


def test_symbol_mismatch_on_push() -> None:
    feeder = LiveRailFeeder(symbol="XAUUSD", timeframe="M15")
    bar = _bar(0)
    # ClosedBar is frozen — rebuild with a different symbol.
    other = ClosedBar(
        candle=bar.candle,
        extras=bar.extras,
        symbol="EURUSD",
        clock_basis=bar.clock_basis,
        venue=bar.venue,
        n_ticks=bar.n_ticks,
        period_start=bar.period_start,
        period_end=bar.period_end,
    )
    with pytest.raises(ValueError, match="symbol"):
        feeder.push(other)
