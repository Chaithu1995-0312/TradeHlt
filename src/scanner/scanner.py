# scanner.py — MultiSymbolScanner: generates signals across the universe
#
# Calls EngineRunner (or an injected data/engine provider) per symbol.
# No LLM in runtime. Pure deterministic scan.
#
import logging
from typing import Optional, Callable

log = logging.getLogger(__name__)


class MultiSymbolScanner:
    """
    Scans all symbols in a Universe and generates signals using the engine.

    The engine_runner callable must accept (symbol, data) and return a dict:
        {
            "action": "BUY" | "SELL" | "NO_SIGNAL",
            "confidence": float,
            "rr": float,
            "zone": float,
            ... other engine fields
        }

    The data_fetcher callable must accept (symbol) and return data
    suitable for engine_runner.

    Usage:
        scanner = MultiSymbolScanner(
            universe=universe,
            engine_runner=my_engine_fn,
            data_fetcher=my_data_fn,
        )
        signals = scanner.scan()

    For testing, inject mock engine_runner and data_fetcher.
    """

    def __init__(
        self,
        universe,                          # Universe instance
        engine_runner: Callable,           # (symbol, data) → signal dict
        data_fetcher: Optional[Callable] = None,  # (symbol) → data
        filter_action: str = "BUY",        # only return signals matching this action
    ):
        self.universe = universe
        self.engine_runner = engine_runner
        self.data_fetcher = data_fetcher
        self.filter_action = filter_action

    def scan(self, asset_class: Optional[str] = None) -> list:
        """
        Scan all symbols (or filtered by asset_class) and return signals.

        Args:
            asset_class: optional filter — "crypto" | "fx" | "stocks" | None (all)

        Returns:
            List of signal dicts where action == filter_action.
        """
        symbols = self.universe.symbols(asset_class=asset_class)
        signals = []

        log.info("MultiSymbolScanner: scanning %d symbols", len(symbols))

        for symbol in symbols:
            try:
                data = self._fetch_data(symbol)
                result = self.engine_runner(symbol, data)

                if result is None:
                    continue

                action = result.get("action", "NO_SIGNAL")
                if action != self.filter_action:
                    log.debug("Scanner: symbol=%s action=%s — skipped", symbol, action)
                    continue

                signal = dict(result)
                signal["symbol"] = symbol
                signals.append(signal)
                log.info(
                    "Scanner: signal symbol=%s action=%s confidence=%.2f rr=%.2f",
                    symbol, action,
                    float(result.get("confidence", 0)),
                    float(result.get("rr", 0)),
                )

            except Exception as exc:
                log.warning("Scanner: error scanning symbol=%s: %s", symbol, exc)
                continue

        log.info(
            "MultiSymbolScanner: scan complete — %d signals from %d symbols",
            len(signals), len(symbols),
        )
        return signals

    def _fetch_data(self, symbol: str):
        """Fetch data for symbol using data_fetcher, or return symbol string if no fetcher."""
        if self.data_fetcher is not None:
            return self.data_fetcher(symbol)
        return symbol  # fallback: pass symbol directly to engine_runner