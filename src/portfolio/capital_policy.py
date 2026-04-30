# capital_policy.py — portfolio risk sizing rules
#
# Deterministic rules engine for trade risk sizing.
# No LLM in runtime. Policy parameters configurable via constructor.
#
import logging

log = logging.getLogger(__name__)


class CapitalPolicy:
    """
    Determines per-trade risk size based on:
      - Current portfolio exposure
      - Signal confidence
      - Correlation with existing positions

    Hard limits:
      MAX_PORTFOLIO_RISK: total deployed risk cap (default: 2%)
      MAX_PER_TRADE:      single-trade risk cap (default: 1%)

    Adjustments (multiplicative on BASE_RISK):
      - High exposure (> 1.5%)  → ×0.5
      - High correlation (> 0.7) → ×0.6
      - Strong signal (> 0.75)  → ×1.3

    Adjustments are applied left-to-right and capped at MAX_PER_TRADE.

    Usage:
        policy = CapitalPolicy()
        risk = policy.compute_risk(
            signal={"confidence": 0.8},
            current_exposure=0.01,
            max_correlation=0.3,
        )
    """

    def __init__(
        self,
        max_portfolio_risk: float = 0.02,
        max_per_trade: float = 0.01,
        base_risk: float = 0.005,
        high_exposure_threshold: float = 0.015,
        high_exposure_factor: float = 0.5,
        high_correlation_threshold: float = 0.7,
        high_correlation_factor: float = 0.6,
        confidence_boost_threshold: float = 0.75,
        confidence_boost_factor: float = 1.3,
    ):
        self.max_portfolio_risk = max_portfolio_risk
        self.max_per_trade = max_per_trade
        self.base_risk = base_risk
        self.high_exposure_threshold = high_exposure_threshold
        self.high_exposure_factor = high_exposure_factor
        self.high_correlation_threshold = high_correlation_threshold
        self.high_correlation_factor = high_correlation_factor
        self.confidence_boost_threshold = confidence_boost_threshold
        self.confidence_boost_factor = confidence_boost_factor

    def compute_risk(
        self,
        signal: dict,
        current_exposure: float,
        max_correlation: float,
    ) -> float:
        """
        Compute risk fraction for this trade.

        Args:
            signal: dict with at least 'confidence' key (float 0–1)
            current_exposure: current total portfolio risk (fraction)
            max_correlation: highest correlation with existing positions (0–1)

        Returns:
            float: risk fraction (e.g. 0.005 = 0.5%)
        """
        risk = self.base_risk

        # Reduce risk if portfolio is already heavily exposed
        if current_exposure > self.high_exposure_threshold:
            risk *= self.high_exposure_factor
            log.debug(
                "CapitalPolicy: high exposure=%.4f → risk ×%.1f",
                current_exposure, self.high_exposure_factor,
            )

        # Reduce risk if new trade is correlated with open positions
        if max_correlation > self.high_correlation_threshold:
            risk *= self.high_correlation_factor
            log.debug(
                "CapitalPolicy: high correlation=%.2f → risk ×%.1f",
                max_correlation, self.high_correlation_factor,
            )

        # Boost risk on strong signal
        confidence = float(signal.get("confidence", 0.0))
        if confidence > self.confidence_boost_threshold:
            risk *= self.confidence_boost_factor
            log.debug(
                "CapitalPolicy: high confidence=%.2f → risk ×%.1f",
                confidence, self.confidence_boost_factor,
            )

        # Hard cap at max_per_trade
        final_risk = min(risk, self.max_per_trade)
        log.debug("CapitalPolicy: computed risk=%.5f", final_risk)
        return final_risk

    def portfolio_at_capacity(self, current_exposure: float) -> bool:
        """Return True if portfolio risk cap is reached or exceeded."""
        return current_exposure >= self.max_portfolio_risk