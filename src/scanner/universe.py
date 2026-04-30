# universe.py — configurable symbol list for multi-symbol scanning
#
import copy
import logging
from typing import Optional

log = logging.getLogger(__name__)


class Universe:
    """
    Defines which symbols to scan.

    Default symbol list (can be overridden via constructor or config):
      Crypto: BTCUSDT, ETHUSDT, SOLUSDT
      FX: EURUSD, GBPUSD, USDJPY, AUDUSD
      Stocks: AAPL, TSLA (stub — data feed not wired yet)

    Usage:
        uni = Universe()
        symbols = uni.symbols()          # → full list

        # Filtered by asset class:
        uni.symbols(asset_class="crypto")
        uni.symbols(asset_class="fx")
    """

    _DEFAULT_SYMBOLS = {
        "crypto": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
        "fx":     ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"],
        "stocks": ["AAPL", "TSLA"],
    }

    def __init__(self, symbol_map: Optional[dict] = None):
        """
        Args:
            symbol_map: optional {asset_class: [symbols]} override.
        """
        self._map = symbol_map if symbol_map is not None else copy.deepcopy(self._DEFAULT_SYMBOLS)

    def symbols(self, asset_class: Optional[str] = None) -> list:
        """
        Return list of symbols.

        Args:
            asset_class: optional filter — "crypto" | "fx" | "stocks"
                         If None, returns all symbols.

        Returns:
            List of symbol strings.
        """
        if asset_class is not None:
            result = list(self._map.get(asset_class, []))
            if not result:
                log.warning("Universe: unknown asset_class=%s", asset_class)
            return result

        # All symbols across all classes
        all_syms = []
        for syms in self._map.values():
            all_syms.extend(syms)
        return all_syms

    def asset_classes(self) -> list:
        """Return list of configured asset class names."""
        return list(self._map.keys())

    def add_symbol(self, symbol: str, asset_class: str = "custom") -> None:
        """Add a symbol to the universe at runtime."""
        if asset_class not in self._map:
            self._map[asset_class] = []
        if symbol not in self._map[asset_class]:
            self._map[asset_class].append(symbol)
            log.info("Universe: added symbol=%s to class=%s", symbol, asset_class)

    def remove_symbol(self, symbol: str) -> bool:
        """Remove a symbol from the universe. Returns True if removed."""
        for syms in self._map.values():
            if symbol in syms:
                syms.remove(symbol)
                log.info("Universe: removed symbol=%s", symbol)
                return True
        return False