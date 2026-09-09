"""Live-rail feature feeder (PR-4b).

FeaturePipeline fills trade_data. FeatureStore (inside the hook) validates.
Do not invent a third 48-dim builder. Do not zero-fill.
"""
from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from features.feature_pipeline import FeaturePipeline, build_features, required_warmup_rows
from features.feature_schema import CANONICAL_FEATURES
from inout.live_rail.types import ClosedBar
from utils.logging_config import get_flow_logger

logger = get_flow_logger("LIVE_RAIL")

# Hook _build_ohlcv_and_auxiliary still _req's the v3 name (live_engine_hook).
_HOOK_MACD_ALIAS = "macd_hist"

_IDENTITY_KEYS = ("symbol", "timeframe", "timestamp")
_OHLCV_KEYS = ("open", "high", "low", "close", "volume")
_PORTFOLIO_KEYS = (
    "account_balance",
    "total_open_risk_pct",
    "trades_today",
    "daily_loss_pct",
    "open_positions",
)
_FRAG2_KEY = "positions"

# Hook `_req` names that are NOT hook-derived from OHLCV (those the feeder must supply).
_HOOK_REQ_FROM_PIPELINE = (
    "atr",
    "ema_fast",
    "ema_slow",
    "ema_spread",
    "trend_bias",
    "trend_strength",
    "momentum_score",
    "volatility_ratio",
    "volume_ratio",
    "sweep_detected",
    "liquidity_sweep",
    "break_of_structure",
    "swing_high",
    "swing_low",
    "higher_high",
    "lower_low",
    "volatility_regime",
    "rsi_14",
    "macd_line",
    "macd_signal",
    _HOOK_MACD_ALIAS,
    "hour_of_day",
    "disp_strength",
    "retest_depth",
    "candles_since_retest",
)

# Schema v5 remainder the existing hook auxiliary does NOT emit (landmine, not a new F-id).
_V5_HOOK_GAP = (
    "liquidity_distance",
    "liquidity_pressure_score",
    "volume_spike",
    "order_block_distance",
    "fvg_distance",
    "breaker_distance",
    "mitigation_block_distance",
    "pdh_distance",
    "pdl_distance",
    "eqh_distance",
    "eql_distance",
    "change_of_character",
)

REQUIRED_LIVE_TRADE_DATA_KEYS: frozenset[str] = frozenset(
    _IDENTITY_KEYS
    + _OHLCV_KEYS
    + _PORTFOLIO_KEYS
    + (_FRAG2_KEY,)
    + _HOOK_REQ_FROM_PIPELINE
    + _V5_HOOK_GAP
    + tuple(CANONICAL_FEATURES)
)


class LiveRailFeeder:
    """Rolling 6-col window → FeaturePipeline last row → live trade_data.

    ``ready()`` is True only when finalize() has produced a valid last row.
    That is ``len(bars) > required_warmup_rows()`` (T-16: drop count 78 ⇒ first
    usable bar is index 78, the 79th push). Length == 78 is not enough.
    """

    def __init__(self, *, symbol: str, timeframe: str) -> None:
        if not symbol.strip():
            raise ValueError("LiveRailFeeder: empty symbol")
        if not timeframe.strip():
            raise ValueError("LiveRailFeeder: empty timeframe")
        self._symbol = symbol
        self._timeframe = timeframe
        self._bars: list[ClosedBar] = []
        self._warmup = int(required_warmup_rows())
        self._last_features: dict[str, float] | None = None
        self._features_for_n = -1

    @property
    def warmup_rows(self) -> int:
        return self._warmup

    def push(self, bar: ClosedBar) -> None:
        bar.validate()
        if bar.symbol != self._symbol:
            raise ValueError(
                f"LiveRailFeeder: symbol {bar.symbol!r} != {self._symbol!r}"
            )
        self._bars.append(bar)
        self._features_for_n = -1
        self._last_features = None

    def ready(self) -> bool:
        self._ensure_features()
        return self._last_features is not None

    def as_trade_data(
        self,
        bar: ClosedBar,
        portfolio_state: Mapping[str, Any],
    ) -> dict[str, Any]:
        if not self.ready():
            raise RuntimeError(
                f"LiveRailFeeder.as_trade_data before ready "
                f"(n={len(self._bars)} warmup={self._warmup})"
            )
        to_dict = getattr(portfolio_state, "to_ultron_dict", None)
        if callable(to_dict):
            portfolio_state = to_dict()
        last = self._bars[-1]
        if bar.candle.timestamp != last.candle.timestamp:
            raise ValueError(
                "LiveRailFeeder.as_trade_data: bar is not the last pushed bar "
                "(fail-closed — do not join features from a different close)"
            )
        assert self._last_features is not None
        out: dict[str, Any] = {
            "symbol": self._symbol,
            "timeframe": self._timeframe,
            "timestamp": bar.candle.timestamp,
            "open": float(bar.candle.open),
            "high": float(bar.candle.high),
            "low": float(bar.candle.low),
            "close": float(bar.candle.close),
            "volume": float(bar.candle.volume),
        }
        for key in _PORTFOLIO_KEYS:
            if key not in portfolio_state:
                raise KeyError(
                    f"LiveRailFeeder: portfolio_state missing {key!r} (no silent default)"
                )
            out[key] = portfolio_state[key]
        if _FRAG2_KEY not in portfolio_state:
            raise KeyError(
                "LiveRailFeeder: portfolio_state missing 'positions' (FRAG-2; no silent default)"
            )
        out[_FRAG2_KEY] = portfolio_state[_FRAG2_KEY]
        for name, value in self._last_features.items():
            out[name] = value
        missing = [k for k in REQUIRED_LIVE_TRADE_DATA_KEYS if k not in out]
        if missing:
            raise KeyError(
                f"LiveRailFeeder: missing required live trade_data keys: {missing}. "
                "Zero-fill is forbidden."
            )
        return out

    def _ensure_features(self) -> None:
        if self._features_for_n == len(self._bars):
            return
        self._features_for_n = len(self._bars)
        self._last_features = None
        # finalize() drops the first warmup rows — need strictly more than warmup.
        if len(self._bars) <= self._warmup:
            return
        frame = self._bars_to_frame()
        pipeline = FeaturePipeline(frame)
        enriched, _vectors = pipeline.run()
        if len(enriched) == 0:
            logger.warning(
                "LIVE_RAIL: FeaturePipeline produced 0 rows after n=%d warmup=%d",
                len(self._bars), self._warmup,
            )
            return
        last_row = enriched.iloc[-1]
        features = build_features(last_row)
        features[_HOOK_MACD_ALIAS] = float(features["macd_hist_z"])
        self._last_features = features

    def _bars_to_frame(self) -> pd.DataFrame:
        rows = []
        for bar in self._bars:
            c = bar.candle
            rows.append({
                "timestamp": c.timestamp,
                "open": float(c.open),
                "high": float(c.high),
                "low": float(c.low),
                "close": float(c.close),
                "volume": float(c.volume),
            })
        return pd.DataFrame(rows)
