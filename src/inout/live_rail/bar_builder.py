"""Aggregate ticks into 6-col Candle + optional spread extras. No lookahead."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from config_layer.crt_engine_v2 import Candle
from inout.live_rail.config import LiveRailConfig
from inout.live_rail.types import ClosedBar, NormalizedTick
from utils.logging_config import get_flow_logger

logger = get_flow_logger("LIVE_RAIL")


def _floor_period(ts: datetime, seconds: int) -> datetime:
    """Floor the timestamp *label* to the period grid.

    XAUUSD M15 (F-080): engine day opens 01:00 broker; 00:00–00:45 slots are empty.
    TickDB stamps MUST be on the same clock as the XAUUSD corpus (broker_local
    labeled). Flooring a true-UTC file labeled broker_local silently mis-buckets
    vs ParentCandleBuilder. Do not convert to true UTC before flooring.
    """
    epoch = int(ts.timestamp())
    floored = epoch - (epoch % seconds)
    return datetime.fromtimestamp(floored, tz=ts.tzinfo)


class BarBuilder:
    """Aggregate ticks into OHLCV + optional spread extras.

    NO LOOKAHEAD: a bar emits only when a tick arrives with ts >= period_end.
    That tick belongs to the *next* bar (standard close-on-boundary).
    Skipped periods are logged, never synthesized.
    Candle.timestamp = period start (CandleLoader convention).
    """

    def __init__(self, cfg: LiveRailConfig) -> None:
        bb = cfg.bar_builder
        self._tf = cfg.timeframe_seconds
        self._emit_incomplete = bb.emit_incomplete_on_stop
        self._volume_mode = bb.volume_mode
        self._clock = cfg.clock_basis
        self._venue = cfg.data_venue
        self._symbol = cfg.symbol
        self._reset()
        self._index = 0

    def _reset(self, period_start: Optional[datetime] = None) -> None:
        self._start = period_start
        self._open = self._high = self._low = self._close = None
        self._vol = 0.0
        self._n = 0
        self._bid = self._ask = self._mid = None

    def on_tick(self, tick: NormalizedTick) -> Optional[ClosedBar]:
        tick.validate()
        if tick.symbol != self._symbol:
            raise ValueError(f"BarBuilder: symbol {tick.symbol} != {self._symbol}")
        period = _floor_period(tick.ts, self._tf)
        emitted: Optional[ClosedBar] = None

        if self._start is None:
            self._start = period
        elif period > self._start:
            gap = int((period - self._start).total_seconds() // self._tf)
            if gap > 1:
                logger.error(
                    "BarBuilder: BAR_BOUNDARY_MISS start=%s jumped_to=%s gap=%d — no synthetic bars",
                    self._start, period, gap,
                )
            emitted = self._close_bar()
            self._reset(period)
        elif period < self._start:
            raise RuntimeError("BarBuilder: time-reversed tick (fail-closed)")

        px = tick.last
        if self._open is None:
            self._open = self._high = self._low = px
        self._high = max(self._high, px)  # type: ignore[arg-type]
        self._low = min(self._low, px)    # type: ignore[arg-type]
        self._close = px
        if self._volume_mode == "sum_size":
            self._vol += float(tick.size)
        else:
            self._vol += 1.0
        self._n += 1
        self._bid, self._ask, self._mid = tick.bid, tick.ask, tick.mid()
        return emitted

    def drop_in_progress(self) -> None:
        """EOF / stop: drop the accumulator. emit_incomplete_on_stop is required false."""
        if self._emit_incomplete:
            raise RuntimeError("BarBuilder: emit_incomplete_on_stop is forbidden")
        self._reset()

    def _close_bar(self) -> Optional[ClosedBar]:
        if self._open is None or self._start is None:
            return None
        end = self._start + timedelta(seconds=self._tf)
        close_px = float(self._close)
        bid_px = float(self._bid if self._bid is not None else close_px)
        ask_px = float(self._ask if self._ask is not None else close_px)
        mid_px = float(self._mid if self._mid is not None else close_px)
        spread = max(0.0, ask_px - bid_px)
        extras = {
            "mid": mid_px,
            "spread_abs": spread,
            "spread_bps": (10_000.0 * spread / mid_px) if mid_px > 0 else 0.0,
            "bid_at_close": bid_px,
            "ask_at_close": ask_px,
        }
        candle = Candle(
            timestamp=self._start,
            open=float(self._open),
            high=float(self._high),
            low=float(self._low),
            close=close_px,
            volume=float(self._vol),
            index=self._index,
        )
        bar = ClosedBar(
            candle=candle,
            extras=extras,
            symbol=self._symbol,
            clock_basis=self._clock,
            venue=self._venue,
            n_ticks=self._n,
            period_start=self._start,
            period_end=end,
        )
        bar.validate()
        self._index += 1
        return bar
