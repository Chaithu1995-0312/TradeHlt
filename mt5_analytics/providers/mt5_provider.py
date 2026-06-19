"""
mt5_provider — live candle source: a thin wrapper over `mt5_adapter.copy_rates_range`.

Maps MT5 rate rows (numpy structured array, fields time/open/high/low/close/tick_volume)
into `Bar`s. Read-only. The M15 timeframe constant is resolved lazily so this module
imports even when the MetaTrader5 wheel is absent (the adapter fails fast at use).
"""
from __future__ import annotations

import datetime as _dt

from ..engines.features._bars import Bar


class MT5CandleProvider:
    def __init__(self, adapter, timeframe=None) -> None:
        self._adapter = adapter
        if timeframe is None:
            import MetaTrader5 as mt5  # type: ignore  (resolved lazily, live-only)
            timeframe = mt5.TIMEFRAME_M15
        self._tf = timeframe

    def get_window(self, symbol: str, start_epoch: int, end_epoch: int) -> list[Bar]:
        # start/end are TRUE UTC epochs; the adapter handles the server-tz conversion and
        # returns UTC-normalized rate dicts (`time` already in true UTC epoch).
        start = _dt.datetime.fromtimestamp(start_epoch, tz=_dt.timezone.utc)
        end = _dt.datetime.fromtimestamp(end_epoch, tz=_dt.timezone.utc)
        rates = self._adapter.copy_rates_range(symbol, self._tf, start, end)
        return [
            Bar(
                index=i,
                time=int(r["time"]),
                open=r["open"], high=r["high"], low=r["low"], close=r["close"],
                volume=r["tick_volume"],
            )
            for i, r in enumerate(rates)
        ]
