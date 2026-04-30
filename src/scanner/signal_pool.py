# signal_pool.py — selects top-K signals from ranked list
#
# Guardrails:
#   - Hard k limit (max 3 by default)
#   - Optional correlated-asset deduplication
#
import logging
from typing import Optional

log = logging.getLogger(__name__)

_MAX_K = 3          # hard ceiling — never take more than this
_DEFAULT_K = 3


class SignalPool:
    """
    Selects top-K signals from a pre-ranked list.

    Optionally deduplicates correlated assets using CorrelationEngine
    to avoid taking BTCUSDT + ETHUSDT simultaneously.

    Usage:
        pool = SignalPool()
        top = pool.top_k(ranked_signals, k=3)

        # With correlation deduplication:
        pool = SignalPool(correlation_engine=engine, corr_threshold=0.7)
        top = pool.top_k(ranked_signals, k=3)
    """

    def __init__(
        self,
        correlation_engine=None,   # CorrelationEngine instance (optional)
        corr_threshold: float = 0.7,
    ):
        self.corr_engine = correlation_engine
        self.corr_threshold = corr_threshold

    def top_k(self, signals: list, k: int = _DEFAULT_K) -> list:
        """
        Return at most k signals from a ranked (best-first) list.

        If correlation_engine is set, skips signals correlated > threshold
        with already-selected signals.

        Args:
            signals: ranked list (best-first), each with '_score' key
            k: max number of signals to return (capped at _MAX_K)

        Returns:
            List of up to k signal dicts.
        """
        k = min(k, _MAX_K)

        if self.corr_engine is not None:
            return self._top_k_deduplicated(signals, k)

        result = signals[:k]
        log.info("SignalPool.top_k: selected %d from %d signals", len(result), len(signals))
        return result

    # ── Private ────────────────────────────────────────────────────────────────

    def _top_k_deduplicated(self, signals: list, k: int) -> list:
        """Select top-k while skipping signals correlated with already-selected."""
        selected = []
        selected_symbols = []

        for sig in signals:
            if len(selected) >= k:
                break
            symbol = sig.get("symbol", "")
            max_corr = self.corr_engine.max_correlation_with_existing(
                symbol, selected_symbols
            )
            if max_corr > self.corr_threshold:
                log.debug(
                    "SignalPool: skipping correlated symbol=%s corr=%.2f",
                    symbol, max_corr,
                )
                continue
            selected.append(sig)
            selected_symbols.append(symbol)

        log.info(
            "SignalPool.top_k_dedup: selected %d from %d signals (k=%d)",
            len(selected), len(signals), k,
        )
        return selected