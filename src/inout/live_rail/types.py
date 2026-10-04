"""Live-rail value types. PR-1 contracts — no EngineRunner, no orders."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import AsyncIterator, Optional, Protocol, runtime_checkable

from config_layer.crt_engine_v2 import Candle
from data_ingestion.ohlcv_schema import validate_ohlcv_row


class ClockBasis(str, Enum):
    """Tick *label* only. NOT ``feature_pipeline.session_timestamp_basis``.

    Do not pass ``ClockBasis.value`` into ``require_reviewed_clock(basis=)``.
    ``utc`` is a legal tick label; it is an illegal session basis.
    """

    UTC = "utc"
    BROKER_LOCAL = "broker_local"
    UTC_CORRECTED = "utc_corrected"


class DataVenue(str, Enum):
    TICKDB = "tickdb"
    BINANCE = "binance"
    MT5_CANDLES = "mt5_candles"
    LONGPORT = "longport"


class OrderVenue(str, Enum):
    PAPER = "paper"
    MT5 = "mt5"


VenueName = DataVenue


@dataclass(frozen=True)
class NormalizedTick:
    """Venue-normalized quote/trade. Not an OHLCV row."""

    ts: datetime
    symbol: str
    bid: float
    ask: float
    last: float
    size: float
    seq: Optional[int]
    clock_basis: ClockBasis
    venue: VenueName
    raw_kind: str

    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0

    def spread_abs(self) -> float:
        return max(0.0, self.ask - self.bid)

    def spread_bps(self) -> float:
        m = self.mid()
        if m <= 0.0:
            raise ValueError("NormalizedTick: mid<=0 — refuse (fail-closed)")
        return 10_000.0 * self.spread_abs() / m

    def validate(self) -> None:
        if self.ts.tzinfo is None:
            raise ValueError(
                "NormalizedTick.ts must be timezone-aware — refuse naive; "
                "do NOT replace(tzinfo=timezone.utc) (that is the F-066 lie)"
            )
        if self.bid <= 0 or self.ask <= 0 or self.last <= 0:
            raise ValueError("NormalizedTick: non-positive price")
        if self.ask < self.bid:
            raise ValueError("NormalizedTick: crossed book")
        if self.size < 0:
            raise ValueError("NormalizedTick: negative size")
        if self.symbol.strip() == "":
            raise ValueError("NormalizedTick: empty symbol")


@dataclass(frozen=True)
class ClosedBar:
    candle: Candle
    extras: dict[str, float]
    symbol: str
    clock_basis: ClockBasis
    venue: VenueName
    n_ticks: int
    period_start: datetime
    period_end: datetime

    def validate(self) -> None:
        c = self.candle
        validate_ohlcv_row(
            c.open, c.high, c.low, c.close, c.volume, source="BarBuilder",
        )
        if self.period_end <= self.period_start:
            raise ValueError("ClosedBar: empty period")


@runtime_checkable
class MarketDataPort(Protocol):
    """Venue-pluggable tick source. Adapters fail-closed on clock/schema."""

    name: VenueName

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    def ticks(self) -> AsyncIterator[NormalizedTick]: ...
