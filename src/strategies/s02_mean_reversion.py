"""
s02_mean_reversion.py
================================================================================
S2 — Mean Reversion Strategy

Signals based on RSI extremes + Bollinger Band proximity.

BUY conditions (all required):
  1. rsi_14 < rsi_oversold threshold (default 30)
  2. close within bb_proximity_pct of bb_lower (price near lower band)
  3. trend_bias != "bearish"  (avoid trading into strong downtrend)

SELL conditions (all required):
  1. rsi_14 > rsi_overbought threshold (default 70)
  2. close within bb_proximity_pct of bb_upper (price near upper band)
  3. trend_bias != "bullish"  (avoid trading into strong uptrend)

Confidence scoring:
  base = 0.55
  + 0.10 if RSI extreme (< 20 BUY | > 80 SELL)
  + 0.10 if rejection_wick present (from feature set)
  + 0.10 if volume_ratio < 0.8 (low volume = exhaustion)
  + 0.05 if is_inside_bar (compression before reversal)

Config section: strategy_engine.s02_mean_reversion in production JSON.
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


def _load_s2_cfg() -> dict:
    se = get_prod_section("strategy_engine") or {}
    cfg = se.get("s02_mean_reversion", {})
    if not cfg:
        logger.warning("strategy_engine.s02_mean_reversion missing — using defaults")
    return cfg


class S02MeanReversion(BaseStrategy):
    """
    Strategy S2: RSI + Bollinger Band Mean Reversion.

    Trades exhaustion moves — RSI at extremes, price at band boundaries.
    Avoids fading strong trends by checking trend_bias.
    """

    _cfg_s2: dict = {}

    def __init__(
        self,
        pair: str,
        timeframe: str,
        config: Optional[dict] = None,
    ) -> None:
        super().__init__(pair, timeframe, config)
        if not S02MeanReversion._cfg_s2:
            S02MeanReversion._cfg_s2 = _load_s2_cfg()

    @property
    def strategy_id(self) -> str:
        return "S2"

    def compute(self, features: dict, candle: dict) -> StrategyResult:
        cfg = self._cfg_s2
        rsi_os: float = float(cfg.get("rsi_oversold", 30.0))
        rsi_ob: float = float(cfg.get("rsi_overbought", 70.0))
        bb_prox: float = float(cfg.get("bb_proximity_pct", 0.002))
        sl_mult: float = float(cfg.get("sl_atr_mult", 1.5))
        tp_rr: float = float(cfg.get("tp_rr_ratio", 1.5))
        min_conf: float = float(cfg.get("min_confidence", 0.55))

        rsi = float(features.get("rsi_14", 50.0))
        trend = str(features.get("trend_bias", "neutral")).lower()
        bb_upper = float(features.get("bb_upper", 0.0))
        bb_lower = float(features.get("bb_lower", 0.0))
        rejection_wick = bool(features.get("rejection_wick", False))
        volume_ratio = float(features.get("volume_ratio", 1.0))
        is_inside_bar = bool(features.get("is_inside_bar", False))

        close = float(candle["close"])
        atr = float(features.get("atr", 0.0))
        if close <= 0.0 or atr <= 0.0:
            return self._no_trade("UNKNOWN")

        signal: Optional[str] = None
        confidence = 0.55

        # BUY: RSI oversold + price near lower BB + not in strong downtrend
        if (rsi < rsi_os
                and bb_lower > 0.0
                and abs(close - bb_lower) / close <= bb_prox
                and trend != "bearish"):
            signal = "BUY"
            if rsi < 20.0:
                confidence += 0.10
            if rejection_wick:
                confidence += 0.10
            if volume_ratio < 0.8:
                confidence += 0.10
            if is_inside_bar:
                confidence += 0.05

        # SELL: RSI overbought + price near upper BB + not in strong uptrend
        elif (rsi > rsi_ob
                and bb_upper > 0.0
                and abs(close - bb_upper) / close <= bb_prox
                and trend != "bullish"):
            signal = "SELL"
            if rsi > 80.0:
                confidence += 0.10
            if rejection_wick:
                confidence += 0.10
            if volume_ratio < 0.8:
                confidence += 0.10
            if is_inside_bar:
                confidence += 0.05

        if signal is None:
            return self._no_trade("RANGING")

        confidence = min(confidence, 1.0)
        if confidence < min_conf:
            return self._no_trade("RANGING")

        regime = "RANGING"

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

        # Normalised score: distance from RSI neutral (50) → 0..1
        score = min(abs(rsi - 50.0) / 50.0, 1.0)

        result = StrategyResult(
            score=score,
            intent="REVERSAL",
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
            "S2 MeanRev signal: %s %s rsi=%.1f conf=%.2f sl_inr=INR%.0f",
            signal, self.pair, rsi, confidence, sl_inr,
        )
        return result
