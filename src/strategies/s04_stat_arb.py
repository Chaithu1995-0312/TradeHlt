"""
s04_stat_arb.py
================================================================================
S4 — Statistical Arbitrage (EMA-Spread Z-Score)

Uses the normalised EMA spread (ema_fast − ema_slow) as a mean-reversion
signal. When the spread deviates beyond a Z-threshold relative to ATR, it
signals over-extension and an expected reversion to the mean.

BUY:  ema_spread / atr < −z_entry_threshold  (fast EMA below slow EMA by >1.5 ATR)
SELL: ema_spread / atr >  z_entry_threshold  (fast EMA above slow EMA by >1.5 ATR)

trend_filter=True blocks signals that oppose the dominant trend_bias.

Confidence scaling:
  base = 0.55
  + 0.10 per full ATR unit beyond z_entry (capped at +0.20)
  + 0.05 if rsi_14 confirms direction (< 45 BUY | > 55 SELL)
  + 0.05 if momentum_score confirms direction

Config section: strategy_engine.s04_stat_arb
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


def _load_s4_cfg() -> dict:
    se = get_prod_section("strategy_engine") or {}
    cfg = se.get("s04_stat_arb", {})
    if not cfg:
        logger.warning("strategy_engine.s04_stat_arb missing — using defaults")
    return cfg


class S04StatArb(BaseStrategy):
    """
    Strategy S4: EMA-Spread Statistical Arbitrage.

    Measures how far the fast EMA has deviated from the slow EMA, normalised
    by ATR. Extreme deviations revert — trade the reversion.
    """

    _cfg_s4: dict = {}

    def __init__(
        self,
        pair: str,
        timeframe: str,
        config: Optional[dict] = None,
    ) -> None:
        super().__init__(pair, timeframe, config)
        if not S04StatArb._cfg_s4:
            S04StatArb._cfg_s4 = _load_s4_cfg()

    @property
    def strategy_id(self) -> str:
        return "S4"

    def compute(self, features: dict, candle: dict) -> StrategyResult:
        cfg = self._cfg_s4
        z_entry: float = float(cfg.get("z_entry_threshold", 1.5))
        sl_mult: float = float(cfg.get("sl_atr_mult", 1.5))
        tp_rr: float = float(cfg.get("tp_rr_ratio", 1.5))
        min_conf: float = float(cfg.get("min_confidence", 0.55))
        trend_filter: bool = bool(cfg.get("trend_filter", True))

        ema_fast = float(features.get("ema_fast", 0.0))
        ema_slow = float(features.get("ema_slow", 0.0))
        atr = float(features.get("atr", 0.0))
        close = float(candle["close"])

        if close <= 0.0 or atr <= 0.0 or ema_fast <= 0.0 or ema_slow <= 0.0:
            return self._no_trade("UNKNOWN")

        ema_spread = ema_fast - ema_slow
        z_score = ema_spread / atr

        if abs(z_score) < z_entry:
            return self._no_trade("RANGING")

        trend = str(features.get("trend_bias", "neutral")).lower()
        rsi = float(features.get("rsi_14", 50.0))
        momentum = float(features.get("momentum_score", 0.0))

        signal: Optional[str] = None

        # Spread overextended upward → expect reversion → SELL
        if z_score > z_entry:
            # Trend filter: don't fade a strong bullish trend
            if trend_filter and trend == "bullish":
                return self._no_trade("RANGING")
            signal = "SELL"

        # Spread overextended downward → expect reversion → BUY
        elif z_score < -z_entry:
            if trend_filter and trend == "bearish":
                return self._no_trade("RANGING")
            signal = "BUY"

        if signal is None:
            return self._no_trade("RANGING")

        # Confidence
        excess = max(abs(z_score) - z_entry, 0.0)
        confidence = 0.55 + min(excess * 0.10, 0.20)
        if signal == "BUY" and rsi < 45.0:
            confidence += 0.05
        elif signal == "SELL" and rsi > 55.0:
            confidence += 0.05
        if signal == "BUY" and momentum < -0.2:
            confidence += 0.05
        elif signal == "SELL" and momentum > 0.2:
            confidence += 0.05
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
        score = min(abs(z_score) / (z_entry * 2), 1.0)

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
            "S4 StatArb signal: %s %s z=%.2f conf=%.2f sl_inr=INR%.0f",
            signal, self.pair, z_score, confidence, sl_inr,
        )
        return result
