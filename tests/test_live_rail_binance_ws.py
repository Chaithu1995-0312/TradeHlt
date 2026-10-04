"""PR-5: BinanceWsAdapter paper-data — no network, optional websockets."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from inout.live_rail.binance_ws_adapter import BinanceWsAdapter
from inout.live_rail.config import LiveRailConfig
from inout.live_rail.factory import build_port
from inout.live_rail.resilience import CircuitBreaker, ReconnectPolicy
from inout.live_rail.types import ClockBasis, VenueName

_EXPERIMENTAL = (
    Path(__file__).resolve().parents[1]
    / "configs"
    / "experimental"
    / "spec"
    / "live_rail_tickdb_paper.json"
)


def _cfg(**overrides) -> LiveRailConfig:
    raw = json.loads(_EXPERIMENTAL.read_text(encoding="utf-8"))
    section = dict(raw["live_rail"])
    section["data_venue"] = "binance"
    section["symbol"] = "BTCUSDT"
    section["clock_basis"] = "utc"
    section.update(overrides)
    return LiveRailConfig.from_prod_config(section)


def _adapter(cfg: LiveRailConfig | None = None) -> BinanceWsAdapter:
    cfg = cfg or _cfg()
    return BinanceWsAdapter(
        cfg,
        CircuitBreaker(fail_count_disable=2),
        ReconnectPolicy(base_delay_s=0.0, max_delay_s=0.0, max_attempts=3),
    )


def test_factory_returns_binance_adapter() -> None:
    port = build_port(_cfg(), CircuitBreaker(2), ReconnectPolicy(0.0, 0.0, 3))
    assert isinstance(port, BinanceWsAdapter)
    assert port.name is VenueName.BINANCE


def test_start_refuses_xauusd() -> None:
    cfg = _cfg(symbol="XAUUSD")
    with pytest.raises(RuntimeError, match="XAUUSD"):
        cfg.assert_safe_to_start()
    with patch("inout.live_rail.binance_ws_adapter._WS_AVAILABLE", True):
        with pytest.raises(RuntimeError, match="XAUUSD"):
            import asyncio
            asyncio.run(_adapter(cfg).start())


def test_start_refuses_non_utc_clock() -> None:
    cfg = _cfg(clock_basis="broker_local")
    with patch("inout.live_rail.binance_ws_adapter._WS_AVAILABLE", True):
        import asyncio
        with pytest.raises(RuntimeError, match="UTC"):
            asyncio.run(_adapter(cfg).start())


def test_start_refuses_without_websockets() -> None:
    with patch("inout.live_rail.binance_ws_adapter._WS_AVAILABLE", False):
        import asyncio
        with pytest.raises(RuntimeError, match="websockets"):
            asyncio.run(_adapter().start())


def test_coerce_book_uses_exchange_event_time() -> None:
    ad = _adapter()
    ts_ms = 1_704_067_200_000  # 2023-12-31 16:00 UTC-ish
    tick = ad._coerce({
        "stream": "btcusdt@bookTicker",
        "data": {"E": ts_ms, "b": "100.0", "a": "100.2"},
    })
    assert tick is not None
    assert tick.ts == datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
    assert tick.bid == pytest.approx(100.0)
    assert tick.ask == pytest.approx(100.2)
    assert tick.raw_kind == "book"
    assert tick.seq is None
    assert tick.clock_basis is ClockBasis.UTC
    assert tick.venue is VenueName.BINANCE


def test_coerce_drops_missing_exchange_time() -> None:
    ad = _adapter()
    assert ad._coerce({
        "stream": "btcusdt@bookTicker",
        "data": {"b": "100.0", "a": "100.2"},
    }) is None


def test_coerce_trade_without_book_is_dropped() -> None:
    ad = _adapter()
    tick = ad._coerce({
        "stream": "btcusdt@trade",
        "data": {"E": 1_704_067_200_000, "p": "100.1", "q": "0.5"},
    })
    assert tick is None


def test_coerce_trade_after_book() -> None:
    ad = _adapter()
    ad._coerce({
        "stream": "btcusdt@bookTicker",
        "data": {"E": 1_704_067_200_000, "b": "100.0", "a": "100.2"},
    })
    tick = ad._coerce({
        "stream": "btcusdt@trade",
        "data": {"T": 1_704_067_200_500, "p": "100.1", "q": "0.5"},
    })
    assert tick is not None
    assert tick.raw_kind == "trade"
    assert tick.last == pytest.approx(100.1)
    assert tick.size == pytest.approx(0.5)
    assert tick.bid == pytest.approx(100.0)
    assert tick.seq is None


def test_url_combined_stream() -> None:
    ad = _adapter()
    url = ad._url()
    assert "stream?streams=" in url
    assert "bookTicker" in url
