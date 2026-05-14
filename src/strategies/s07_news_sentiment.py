"""
s07_news_sentiment.py
================================================================================
S7 — News / Sentiment Filter + Trend Follower

Two-layer design:

  Layer 1 — News Guard (veto):
    Detects elevated volatility and wide spreads that proxy news events.
    If either trigger fires → NO_TRADE.  Protects all downstream signals.

    Triggers:
      volatility_ratio  >= news_volatility_ratio  (e.g., 2.0×)
      spread_pct        >  max_spread_pct          (e.g., 0.05%)

  Layer 2 — Zone-Confirmed Trend Follow (when guard passes):
    trend_bias="bullish" + zone_strength >= zone_strength_min → BUY
    trend_bias="bearish" + zone_strength >= zone_strength_min → SELL
    trend_bias="neutral"                                       → NO_TRADE

Confidence:
  base = 0.55
  + 0.15 if trend_strength > 0.7
  + 0.10 if momentum_score confirms direction
  + 0.10 if break_of_structure=True
  + 0.05 if volume_ratio > 1.2

Config section: strategy_engine.s07_news_sentiment
================================================================================
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from config_layer.production_config import get_prod_section   # type: ignore
from strategies.base_strategy import BaseStrategy              # type: ignore
from strategies.strategy_result import StrategyResult          # type: ignore
from utils.logging_config import get_flow_logger               # type: ignore

logger = get_flow_logger("STRATEGY_ENGINE")


def _load_s7_cfg() -> dict:
    se = get_prod_section("strategy_engine") or {}
    cfg = se.get("s07_news_sentiment", {})
    if not cfg:
        logger.warning("strategy_engine.s07_news_sentiment missing — using defaults")
    return cfg


class S07NewsSentiment(BaseStrategy):
    """
    Strategy S7: News-Filtered Zone-Trend Follower.

    Blocks all entries during detected high-volatility / wide-spread windows
    (proxy for economic news releases). Passes clean windows through a
    zone-strength-confirmed trend-following signal.
    """

    _cfg_s7: dict = {}

    def __init__(
        self,
        pair: str,
        timeframe: str,
        config: Optional[dict] = None,
    ) -> None:
        super().__init__(pair, timeframe, config)
        if not S07NewsSentiment._cfg_s7:
            S07NewsSentiment._cfg_s7 = _load_s7_cfg()

    @property
    def strategy_id(self) -> str:
        return "S7"

    def compute(self, features: dict, candle: dict) -> StrategyResult:
        cfg = self._cfg_s7
        news_vol_ratio: float = float(cfg.get("news_volatility_ratio", 2.0))
        max_spread: float = float(cfg.get("max_spread_pct", 0.0005))
        zone_min: float = float(cfg.get("zone_strength_min", 0.55))
        sl_mult: float = float(cfg.get("sl_atr_mult", 1.5))
        tp_rr: float = float(cfg.get("tp_rr_ratio", 1.5))
        min_conf: float = float(cfg.get("min_confidence", 0.55))

        volatility_ratio = float(features.get("volatility_ratio", 1.0))
        spread_pct = float(features.get("spread_pct", 0.0))

        # Layer 1: news veto
        if volatility_ratio >= news_vol_ratio:
            logger.debug(
                "S7 news guard: vol_ratio=%.2f >= %.2f — NO_TRADE",
                volatility_ratio, news_vol_ratio,
            )
            return self._no_trade("VOLATILE")
        if spread_pct > max_spread:
            logger.debug(
                "S7 news guard: spread=%.5f > %.5f — NO_TRADE",
                spread_pct, max_spread,
            )
            return self._no_trade("VOLATILE")

        # Layer 2: zone-confirmed trend
        trend = str(features.get("trend_bias", "neutral")).lower()
        zone_strength = float(features.get("zone_strength", 0.0))
        trend_strength = float(features.get("trend_strength", 0.0))
        momentum = float(features.get("momentum_score", 0.0))
        bos = bool(features.get("break_of_structure", False))
        volume_ratio = float(features.get("volume_ratio", 1.0))

        if trend == "neutral" or zone_strength < zone_min:
            return self._no_trade("RANGING")

        signal: Optional[str] = None
        if trend == "bullish":
            signal = "BUY"
        elif trend == "bearish":
            signal = "SELL"
        else:
            return self._no_trade("RANGING")

        confidence = 0.55
        if trend_strength > 0.7:
            confidence += 0.15
        if signal == "BUY" and momentum > 0.3:
            confidence += 0.10
        elif signal == "SELL" and momentum < -0.3:
            confidence += 0.10
        if bos:
            confidence += 0.10
        if volume_ratio > 1.2:
            confidence += 0.05
        confidence = min(confidence, 1.0)

        if confidence < min_conf:
            return self._no_trade("RANGING")

        close = float(candle.get("close", 0.0))
        atr = float(features.get("atr", 0.0))
        if close <= 0.0 or atr <= 0.0:
            return self._no_trade("RANGING")

        regime = "TRENDING"

        if signal == "BUY":
            sl = close - atr * sl_mult
            tp = close + (close - sl) * tp_rr
        else:
            sl = close + atr * sl_mult
            tp = close - (sl - close) * tp_rr

        sl_pips = self._sl_pips(close, sl)
        lot = self._get_lot_size(sl_pips)
        if lot <= 0.0:
            return self._no_trade(regime)

        sl_inr = self._calc_sl_inr(close, sl, lot)
        tp_inr = self._calc_tp_inr(close, tp, lot)
        score = min(zone_strength * trend_strength, 1.0) if trend_strength > 0 else zone_strength

        result = StrategyResult(
            score=score,
            intent="PULLBACK",
            regime=regime,
            signal=signal,
            confidence=confidence,
            entry=close,
            sl=sl,
            tp=tp,
            sl_inr=sl_inr,
            tp_inr=tp_inr,
            roi_min=self._calc_roi(close, tp, 0.4),
            roi_max=self._calc_roi(close, tp, 1.0),
            strategy_id=self.strategy_id,
            pair=self.pair,
            timeframe=self.timeframe,
        )
        result.validate()
        logger.info(
            "S7 News+Trend signal: %s %s zone=%.2f conf=%.2f sl_inr=INR%.0f",
            signal, self.pair, zone_strength, confidence, sl_inr,
        )
        return result
