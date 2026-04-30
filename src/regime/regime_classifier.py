# regime_classifier.py — deterministic market regime detection
#
# HARD RULES:
# - Pure deterministic — no LLM in runtime
# - Cooldown: min 5 candles between regime switches
# - Fallback: always returns SAFE-compatible regime if detection fails
#
import logging
from typing import Optional

log = logging.getLogger(__name__)

# Regime constants
REGIME_TRENDING = "TRENDING"
REGIME_RANGING = "RANGING"
REGIME_HIGH_VOLATILITY = "HIGH_VOLATILITY"
REGIME_UNKNOWN = "RANGING"  # safe fallback

# Classification thresholds (tunable via config injection)
_DEFAULT_ATR_HIGH_THRESHOLD = 0.8   # ATR > this → HIGH_VOLATILITY
_DEFAULT_TREND_THRESHOLD = 0.7       # trend_score > this → TRENDING
_DEFAULT_COOLDOWN_CANDLES = 5        # min candles between switches


class RegimeClassifier:
    """
    Classifies market regime from features dict.

    Input features (required):
      - atr: float          — normalised ATR (0–1 range preferred)
      - trend_score: float  — directional strength (0–1)

    Optional features (used when available):
      - volatility: float   — alternate volatility signal
      - adx: float          — ADX directional indicator (0–100)

    Output: str — one of TRENDING | RANGING | HIGH_VOLATILITY

    Guardrails:
      - Cooldown prevents switching more often than every N candles
      - All exceptions return RANGING (safe default)
      - Thresholds configurable via constructor
    """

    def __init__(
        self,
        atr_high_threshold: float = _DEFAULT_ATR_HIGH_THRESHOLD,
        trend_threshold: float = _DEFAULT_TREND_THRESHOLD,
        cooldown_candles: int = _DEFAULT_COOLDOWN_CANDLES,
    ):
        self.atr_high_threshold = atr_high_threshold
        self.trend_threshold = trend_threshold
        self.cooldown_candles = cooldown_candles

        self._last_regime: Optional[str] = None
        self._candles_since_switch: int = 0

    def classify(self, features: dict) -> str:
        """
        Classify current market regime from feature dict.

        Args:
            features: dict with at minimum 'atr' and 'trend_score'

        Returns:
            Regime string: TRENDING | RANGING | HIGH_VOLATILITY
        """
        try:
            new_regime = self._classify_raw(features)
        except Exception as exc:
            log.warning("RegimeClassifier: classification error (%s) — returning RANGING", exc)
            return REGIME_RANGING

        # Apply cooldown guard
        if self._last_regime is not None and self._last_regime != new_regime:
            self._candles_since_switch += 1
            if self._candles_since_switch < self.cooldown_candles:
                log.debug(
                    "RegimeClassifier: cooldown active (%d/%d candles) — keeping %s",
                    self._candles_since_switch, self.cooldown_candles, self._last_regime,
                )
                return self._last_regime
            else:
                self._candles_since_switch = 0
        else:
            self._candles_since_switch = 0

        if new_regime != self._last_regime:
            log.info(
                "RegimeClassifier: regime switch %s → %s",
                self._last_regime, new_regime,
            )
        self._last_regime = new_regime
        return new_regime

    def _classify_raw(self, features: dict) -> str:
        """Deterministic regime detection without cooldown logic."""
        atr = float(features.get("atr", 0.5))
        trend_score = float(features.get("trend_score", 0.5))

        # Priority 1: High volatility overrides trend detection
        if atr > self.atr_high_threshold:
            return REGIME_HIGH_VOLATILITY

        # Priority 2: Strong directional trend
        if trend_score > self.trend_threshold:
            return REGIME_TRENDING

        # Default: ranging / sideways
        return REGIME_RANGING

    def reset_cooldown(self) -> None:
        """Reset cooldown state (useful for testing or session start)."""
        self._last_regime = None
        self._candles_since_switch = 0

    @property
    def current_regime(self) -> Optional[str]:
        """Return the last classified regime (None if never classified)."""
        return self._last_regime