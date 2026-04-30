# allocator.py — PortfolioAllocator: orchestrates exposure + correlation + policy
#
import logging

from src.portfolio.exposure_tracker import ExposureTracker
from src.portfolio.correlation_engine import CorrelationEngine
from src.portfolio.capital_policy import CapitalPolicy

log = logging.getLogger(__name__)


class PortfolioAllocator:
    """
    Combines ExposureTracker, CorrelationEngine, and CapitalPolicy to produce
    per-trade allocation decisions.

    Integration point (replaces fixed-risk sizing):
        signal = engine.run(...)
        allocation = PortfolioAllocator().allocate(signal)
        if allocation["action"] == "REJECT":
            skip trade
        signal["risk"] = allocation["risk"]
        UltronRiskGate.check_trade(signal)    ← Ultron is still final authority

    Usage:
        allocator = PortfolioAllocator()
        result = allocator.allocate(signal)
        # result: {"action": "ALLOCATE"|"REJECT", "risk": float, "reason": str}

        # After trade opens:
        allocator.open_position({"trade_id": ..., "symbol": ..., "risk": ...})

        # After trade closes:
        allocator.close_position(trade_id)
    """

    def __init__(
        self,
        exposure_tracker: ExposureTracker = None,
        correlation_engine: CorrelationEngine = None,
        capital_policy: CapitalPolicy = None,
    ):
        self.tracker = exposure_tracker or ExposureTracker()
        self.corr = correlation_engine or CorrelationEngine()
        self.policy = capital_policy or CapitalPolicy()

    # ── Public API ─────────────────────────────────────────────────────────────

    def allocate(self, signal: dict) -> dict:
        """
        Decide whether to allocate capital to this signal and how much.

        Args:
            signal: dict with at minimum:
                    - 'symbol': str
                    - 'confidence': float (0–1)
                    Optional: 'rr', 'regime', etc.

        Returns:
            {
                "action": "ALLOCATE" | "REJECT",
                "risk": float,          ← only present when ALLOCATE
                "reason": str,
            }
        """
        symbol = signal.get("symbol", "UNKNOWN")
        current_exposure = self.tracker.total_risk()

        # Gate 1: portfolio risk capacity
        if self.policy.portfolio_at_capacity(current_exposure):
            reason = (
                "REJECT: portfolio at max risk capacity "
                "(current={:.4f} >= max={:.4f})".format(
                    current_exposure, self.policy.max_portfolio_risk
                )
            )
            log.info("PortfolioAllocator: %s", reason)
            return {"action": "REJECT", "risk": 0.0, "reason": reason}

        # Compute correlation with existing positions
        existing_symbols = [p["symbol"] for p in self.tracker.positions()]
        max_corr = self.corr.max_correlation_with_existing(symbol, existing_symbols)

        # Compute risk size
        risk = self.policy.compute_risk(
            signal=signal,
            current_exposure=current_exposure,
            max_correlation=max_corr,
        )

        # Gate 2: ensure allocation doesn't breach portfolio cap
        if current_exposure + risk > self.policy.max_portfolio_risk:
            # Trim risk to fit within cap
            trimmed = max(0.0, self.policy.max_portfolio_risk - current_exposure)
            log.info(
                "PortfolioAllocator: trimming risk from %.5f to %.5f to fit cap",
                risk, trimmed,
            )
            risk = trimmed

        if risk <= 0:
            return {
                "action": "REJECT",
                "risk": 0.0,
                "reason": "REJECT: trimmed risk is zero (portfolio cap fully consumed)",
            }

        reason = (
            "ALLOCATE: symbol={} risk={:.5f} "
            "exposure_before={:.4f} max_corr={:.2f}".format(
                symbol, risk, current_exposure, max_corr
            )
        )
        log.info("PortfolioAllocator: %s", reason)
        return {"action": "ALLOCATE", "risk": risk, "reason": reason}

    def open_position(self, position: dict) -> None:
        """Register an opened position with the tracker."""
        self.tracker.add_position(position)

    def close_position(self, trade_id: str) -> None:
        """Deregister a closed position from the tracker."""
        self.tracker.remove_position(trade_id)

    def current_exposure(self) -> float:
        """Return current total portfolio risk."""
        return self.tracker.total_risk()

    def exposure_by_symbol(self) -> dict:
        """Return risk breakdown by symbol."""
        return self.tracker.exposure_by_symbol()