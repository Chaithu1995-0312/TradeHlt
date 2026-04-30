"""
RREngine — Risk-Reward scoring engine.

Computes the best achievable Risk-Reward ratio from actual price levels
(close, high, low) rather than fixed ATR multiples.

Bull scenario:  entry=close, stop=low,  target=high
Bear scenario:  entry=close, stop=high, target=low

The best of the two scenarios is used as the score driver.

FIX NOTE (vs previous implementation):
  Previously: stop=atr*1.5, target=atr*3.0 → rr=2.0 always (constant).
  Now: stop and target are derived from real price-level distances.
"""

import logging

logger = logging.getLogger(__name__)


class RREngine:
    def __init__(self, config: dict):
        self.config = config
        self.min_rr = config.get("min_rr", 1.5)

    def compute(self, input_data: dict) -> dict:
        try:
            close = input_data["close"]
            high = input_data["high"]
            low = input_data["low"]
            # atr kept for context / future extensions but NOT used in ratio calc
            atr = input_data["atr"]  # noqa: F841

            # Sanity: high must be >= close >= low
            if not (high >= close >= low):
                return {
                    "score": 0.0,
                    "reason": f"invalid_price_structure:high={high},close={close},low={low}"
                }

            # --- Bull scenario ---
            bull_stop = close - low       # risk: distance from entry down to support
            bull_target = high - close    # reward: distance from entry up to resistance

            # --- Bear scenario ---
            bear_stop = high - close      # risk: distance from entry up to resistance
            bear_target = close - low     # reward: distance from entry down to support

            # Best RR across both scenarios
            bull_rr = bull_target / bull_stop if bull_stop > 0 else 0.0
            bear_rr = bear_target / bear_stop if bear_stop > 0 else 0.0
            rr_ratio = max(bull_rr, bear_rr)

            if rr_ratio <= 0:
                return {"score": 0.0, "rr_ratio": 0.0, "reason": "zero_rr_ratio"}

            if rr_ratio >= self.min_rr:
                # Normalize: score=0.5 at exactly min_rr, approaches 1.0 as rr → ∞
                score = min(1.0, rr_ratio / (self.min_rr * 2))
            else:
                score = 0.0

            return {
                "score": round(score, 4),
                "rr_ratio": round(rr_ratio, 4),
                "reason": f"rr_ratio:{round(rr_ratio, 4)}",
            }

        except KeyError as e:
            logger.error(f"RREngine missing key: {e}")
            return {"score": 0.0, "rr_ratio": 0.0, "reason": f"missing_key:{e}"}
        except ZeroDivisionError:
            return {"score": 0.0, "rr_ratio": 0.0, "reason": "zero_division"}
