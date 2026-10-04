"""
candle_provider — the swappable bar-source contract.

`feature_engine` must never know where candles come from (CSV / MT5 / fixture / replay).
`shared_pipeline` depends only on this Protocol; the concrete provider is injected. Each
implementation returns the bars covering `[start_epoch, end_epoch]` (inclusive) for a
symbol; `shared_pipeline` then calls `build_window` to locate the entry bar.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..engines.features._bars import Bar


@runtime_checkable
class CandleProvider(Protocol):
    def get_window(self, symbol: str, start_epoch: int, end_epoch: int) -> list[Bar]:
        """Return M15 bars with `start_epoch <= bar.time <= end_epoch`, time-ascending."""
        ...
