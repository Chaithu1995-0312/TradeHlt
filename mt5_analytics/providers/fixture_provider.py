"""
fixture_provider — in-memory candle source for deterministic tests (no terminal).

Holds `{symbol: [Bar, ...]}` and slices by time. Makes the whole pipeline exercisable
with synthetic candles, so `shared_pipeline` parity/idempotency can be proven in CI.
"""
from __future__ import annotations

from ..engines.features._bars import Bar


class FixtureProvider:
    def __init__(self, bars_by_symbol: "dict[str, list[Bar]]") -> None:
        self._by_symbol = {
            sym: sorted(bars, key=lambda b: b.time)
            for sym, bars in bars_by_symbol.items()
        }

    def get_window(self, symbol: str, start_epoch: int, end_epoch: int) -> list[Bar]:
        return [
            b for b in self._by_symbol.get(symbol, [])
            if start_epoch <= b.time <= end_epoch
        ]
