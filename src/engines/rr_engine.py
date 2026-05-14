"""
RREngine — Candle Polarity Index (formerly misnamed "RR Engine").

SEMANTIC NOTE (audit fix 2026-05-14):
  This engine does NOT compute forward-looking Risk:Reward. The entry is at the
  current candle's CLOSE; the High and Low of that same candle are already in
  the past. Computing (high-close)/(close-low) is therefore measuring CANDLE
  STRUCTURE, not tradable future RR.

  Previous formula had a deeper bug: close at candle-LOW → bull_stop=0 →
  div/zero → score=0, AND close at candle-HIGH → bull_target=0 → score=0.
  Only mid-candle closes scored >0, which is the OPPOSITE of what CRT wants
  (CRT entries favour closes near candle extremes = committed directional bars).

  NEW FORMULA — Candle Polarity Index (CPI):
    candle_range = high - low  (+ epsilon for doji protection)
    upper_body   = (high - close) / candle_range   → 1 when close at low  (bullish pin)
    lower_body   = (close - low)  / candle_range   → 1 when close at high (bearish pin)
    score        = max(upper_body, lower_body)

  Score interpretation:
    1.0  → Close at either extreme → strong directional commitment (ideal CRT candle)
    0.5  → Close at midpoint → doji / indecision (lower quality)
    0.0  → Degenerate candle (high == low)

  The UltronRiskGate RR check (Check 2: rr_ratio < min_rr_ratio) is SEPARATE
  and uses CRT-derived forward SL/TP levels, not this engine's output.
  This engine contributes 20% to the fusion score as a candle-quality signal.
"""

import logging

_EPS = 1e-9
logger = logging.getLogger(__name__)


class RREngine:
    """Candle Polarity Index engine. Scores candle structure for directional commitment."""

    def __init__(self, config: dict):
        self.config = config
        # min_rr retained for backward config compat; no longer used in scoring
        self.min_rr = config.get("min_rr", 1.5)

    def compute(self, input_data: dict) -> dict:
        try:
            close = float(input_data["close"])
            high  = float(input_data["high"])
            low   = float(input_data["low"])

            # Sanity: high must be >= close >= low
            if not (high >= close >= low):
                return {
                    "score":           0.0,
                    "candle_polarity": 0.0,
                    "reason":          f"invalid_price_structure:h={high},c={close},l={low}",
                }

            candle_range = high - low
            if candle_range < _EPS:
                # Degenerate doji — no structure to score
                return {
                    "score":           0.0,
                    "candle_polarity": 0.0,
                    "reason":          "doji_zero_range",
                }

            # Fraction of the candle above and below the close
            upper_body = (high  - close) / candle_range  # 1.0 when close at low  (bull pin)
            lower_body = (close - low)   / candle_range  # 1.0 when close at high (bear pin)

            # Polarity: peaks at 1.0 when close is at either extreme
            polarity = max(upper_body, lower_body)

            return {
                "score":           round(polarity, 4),
                "candle_polarity": round(polarity, 4),
                # Keep legacy field name so any callers reading "rr_ratio" still work
                "rr_ratio":        round(polarity, 4),
                "reason":          f"candle_polarity:{round(polarity, 4)}",
                "semantic":        "candle_structure_quality",  # not forward RR
            }

        except KeyError as e:
            logger.error("RREngine missing key: %s", e)
            return {"score": 0.0, "candle_polarity": 0.0, "rr_ratio": 0.0, "reason": f"missing_key:{e}"}
        except (TypeError, ValueError) as e:
            logger.error("RREngine value error: %s", e)
            return {"score": 0.0, "candle_polarity": 0.0, "rr_ratio": 0.0, "reason": f"value_error:{e}"}
