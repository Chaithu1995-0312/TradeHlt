"""Venue port factory. Paper order venue only."""
from __future__ import annotations

from typing import Optional

from inout.live_rail.binance_ws_adapter import BinanceWsAdapter
from inout.live_rail.config import LiveRailConfig
from inout.live_rail.longport_adapter import LongPortAdapter
from inout.live_rail.resilience import CircuitBreaker, ReconnectPolicy
from inout.live_rail.tickdb_adapter import TickDBAdapter
from inout.live_rail.types import DataVenue, MarketDataPort


def build_port(
    cfg: LiveRailConfig,
    breaker: CircuitBreaker,
    policy: ReconnectPolicy,
) -> Optional[MarketDataPort]:
    if cfg.data_venue is DataVenue.TICKDB:
        return TickDBAdapter(cfg)
    if cfg.data_venue is DataVenue.BINANCE:
        return BinanceWsAdapter(cfg, breaker, policy)
    if cfg.data_venue is DataVenue.MT5_CANDLES:
        return None
    if cfg.data_venue is DataVenue.LONGPORT:
        return LongPortAdapter()
    raise RuntimeError(f"unknown data_venue {cfg.data_venue}")
