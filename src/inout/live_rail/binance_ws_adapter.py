"""Binance combined-stream paper-data. Crypto only. No orders."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import AsyncIterator, Optional

from inout.live_rail.config import LiveRailConfig
from inout.live_rail.resilience import CircuitBreaker, ReconnectPolicy
from inout.live_rail.types import ClockBasis, NormalizedTick, VenueName
from utils.logging_config import get_flow_logger

logger = get_flow_logger("LIVE_RAIL")

try:
    import websockets  # type: ignore
    _WS_AVAILABLE = True
except Exception:
    websockets = None  # type: ignore[assignment]
    _WS_AVAILABLE = False


class BinanceWsAdapter:
    """Async bookTicker + trade. Crypto PAPER-DATA only. Not XAUUSD.

    Combined stream: {ws_base}/stream?streams=btcusdt@bookTicker/btcusdt@trade
    Exchange event time only (E or T). Absent → drop. seq is always None.
    """

    name = VenueName.BINANCE

    def __init__(
        self,
        cfg: LiveRailConfig,
        breaker: CircuitBreaker,
        policy: ReconnectPolicy,
    ) -> None:
        self._cfg = cfg
        self._breaker = breaker
        self._policy = policy
        self._max_age_ms = cfg.binance.max_quote_age_ms
        self._heartbeat_s = cfg.binance.heartbeat_s
        self._ws_base = cfg.binance.ws_base
        self._streams: list[str] = list(cfg.binance.streams)
        self._running = False
        self._last_bid: Optional[float] = None
        self._last_ask: Optional[float] = None

    async def start(self) -> None:
        if not _WS_AVAILABLE:
            raise RuntimeError(
                "BinanceWsAdapter: 'websockets' extra is not installed. "
                "Install optional extra live_rail (websockets>=12) or use venue=tickdb."
            )
        if self._cfg.clock_basis is not ClockBasis.UTC:
            raise RuntimeError(
                "BinanceWsAdapter: Binance timestamps are UTC — refuse other clock_basis"
            )
        if self._cfg.symbol.upper() == "XAUUSD":
            raise RuntimeError(
                "BinanceWsAdapter: refuse XAUUSD (wrong venue for ACTIVE_VERSION)"
            )
        self._running = True

    async def stop(self) -> None:
        self._running = False

    def _url(self) -> str:
        return f"{self._ws_base}/stream?streams={'/'.join(self._streams)}"

    async def ticks(self) -> AsyncIterator[NormalizedTick]:
        attempt = 0
        while self._running:
            if self._breaker.is_open():
                raise RuntimeError("BinanceWsAdapter: circuit open — fail-closed")
            try:
                async for tick in self._session():
                    attempt = 0
                    self._breaker.record_success()
                    yield tick
            except Exception as exc:
                logger.warning("BinanceWsAdapter: session ended: %s", exc)
                self._breaker.record_failure()
                if not self._running:
                    return
                await self._policy.sleep(attempt)
                attempt += 1

    async def _session(self) -> AsyncIterator[NormalizedTick]:
        if websockets is None:
            raise RuntimeError("BinanceWsAdapter: websockets missing")
        async with websockets.connect(
            self._url(),
            ping_interval=self._heartbeat_s,
            ping_timeout=self._heartbeat_s,
        ) as ws:
            async for raw in ws:
                if not self._running:
                    return
                msg = json.loads(raw)
                tick = self._coerce(msg)
                if tick is None:
                    continue
                tick.validate()
                age_ms = (datetime.now(timezone.utc) - tick.ts).total_seconds() * 1000.0
                if age_ms > self._max_age_ms:
                    logger.warning(
                        "BinanceWsAdapter: stale quote age_ms=%.0f — drop", age_ms
                    )
                    self._breaker.record_failure()
                    continue
                yield tick

    def _event_ts(self, data: dict) -> Optional[datetime]:
        """Exchange event time only. Do not stamp wall clock."""
        ms = data.get("E") if data.get("E") is not None else data.get("T")
        if ms is None:
            return None
        return datetime.fromtimestamp(int(ms) / 1000.0, tz=timezone.utc)

    def _coerce(self, msg: dict) -> Optional[NormalizedTick]:
        data = msg.get("data", msg)
        stream = str(msg.get("stream", ""))
        ts = self._event_ts(data)
        if ts is None:
            return None
        if "bookTicker" in stream or ("b" in data and "a" in data):
            self._last_bid = float(data["b"])
            self._last_ask = float(data["a"])
            last = (self._last_bid + self._last_ask) / 2.0
            size = 0.0
            kind = "book"
        elif "trade" in stream or "p" in data:
            last = float(data["p"])
            size = float(data.get("q", 0.0))
            kind = "trade"
            if self._last_bid is None or self._last_ask is None:
                return None
        else:
            return None
        if self._last_bid is None or self._last_ask is None:
            return None
        return NormalizedTick(
            ts=ts,
            symbol=self._cfg.symbol,
            bid=self._last_bid,
            ask=self._last_ask,
            last=last,
            size=size,
            seq=None,
            clock_basis=ClockBasis.UTC,
            venue=VenueName.BINANCE,
            raw_kind=kind,
        )
