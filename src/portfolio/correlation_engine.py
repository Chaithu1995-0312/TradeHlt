# correlation_engine.py — symbol pair correlation estimation
#
# Phase 1: simple heuristic-based correlation (deterministic, no data needed).
# Phase 2 (future): plug in real rolling correlation from price data.
#
import logging

log = logging.getLogger(__name__)

# Static correlation groups (same group = high correlation)
_CRYPTO_SYMBOLS = {"BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT"}
_FX_MAJORS = {"EURUSD", "GBPUSD", "AUDUSD", "NZDUSD"}
_USD_SHORTS = {"USDJPY", "USDCHF", "USDCAD"}

_HIGH_CORR = 0.8    # same asset class group
_MED_CORR = 0.4     # related but not same group
_LOW_CORR = 0.2     # cross asset class


class CorrelationEngine:
    """
    Estimates correlation between two symbols.

    Phase 1 implementation: heuristic group-based.
      - Same currency pair prefix (e.g. EUR* with EUR*) → 0.8
      - Same asset class (both crypto, both FX) → 0.8
      - Related (FX↔USD cross) → 0.4
      - Otherwise → 0.2

    Can be extended: subclass and override `correlation()`.

    Usage:
        engine = CorrelationEngine()
        c = engine.correlation("BTCUSDT", "ETHUSDT")  # → 0.8
        c = engine.correlation("BTCUSDT", "EURUSD")   # → 0.2
    """

    def correlation(self, sym1: str, sym2: str) -> float:
        """
        Return estimated correlation between sym1 and sym2 in [0, 1].

        Returns 0.0 if either symbol is None/empty.
        Returns 1.0 if sym1 == sym2.
        """
        if not sym1 or not sym2:
            return 0.0
        if sym1 == sym2:
            return 1.0

        c = self._heuristic_correlation(sym1.upper(), sym2.upper())
        log.debug("CorrelationEngine: %s vs %s → %.2f", sym1, sym2, c)
        return c

    def max_correlation_with_existing(
        self, symbol: str, existing_symbols: list
    ) -> float:
        """
        Return maximum correlation between `symbol` and any existing position.

        Args:
            symbol: the new trade symbol
            existing_symbols: list of symbols in open positions

        Returns:
            float in [0, 1] — highest correlation found
        """
        if not existing_symbols:
            return 0.0
        return max(self.correlation(symbol, s) for s in existing_symbols)

    # ── Private ────────────────────────────────────────────────────────────────

    def _heuristic_correlation(self, s1: str, s2: str) -> float:
        """Group-based heuristic correlation."""
        # Same 3-letter prefix (e.g. EURUSD vs EURGBP → both EUR)
        if len(s1) >= 3 and len(s2) >= 3 and s1[:3] == s2[:3]:
            return _HIGH_CORR

        # Both in same crypto group
        if s1 in _CRYPTO_SYMBOLS and s2 in _CRYPTO_SYMBOLS:
            return _HIGH_CORR

        # Both in same FX majors group
        if s1 in _FX_MAJORS and s2 in _FX_MAJORS:
            return _HIGH_CORR

        # Both in USD shorts
        if s1 in _USD_SHORTS and s2 in _USD_SHORTS:
            return _HIGH_CORR

        # FX majors and USD shorts are related
        if (s1 in _FX_MAJORS and s2 in _USD_SHORTS) or \
           (s1 in _USD_SHORTS and s2 in _FX_MAJORS):
            return _MED_CORR

        return _LOW_CORR