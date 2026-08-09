"""
s06_scalping.py
================================================================================
S6 — Scalping Strategy (MACD + Momentum, session-filtered)

Targets short-duration moves using MACD histogram direction + momentum
confirmation. Session and spread filters ensure only high-liquidity, low-cost
windows are traded.

Signal logic:
  BUY:  macd_hist > macd_hist_min  AND  momentum_score > momentum_min
  SELL: macd_hist < -macd_hist_min AND  momentum_score < -momentum_min

Guards (all must pass):
  1. hour_of_day in [session_hours_start, session_hours_end]   (London/NY only)
  2. spread_pct <= max_spread_pct                              (avoid wide spreads)
  3. volatility_ratio < 2.0                                    (avoid news spikes)

State buffer (maxlen=2):
  Detects MACD histogram sign-flip (cross) for higher-confidence entries.
  Cross detected → confidence += 0.15.

Confidence:
  base = 0.55
  + 0.15 if MACD histogram sign-flip on this bar
  + 0.10 if body_ratio > 0.6 (decisive bar)
  + 0.05 if volume_ratio > 1.1

Config section: strategy_engine.s06_scalping
================================================================================
"""

from __future__ import annotations

import sys
from collections import deque
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


def _load_s6_cfg() -> dict:
    se = get_prod_section("strategy_engine") or {}
    cfg = se.get("s06_scalping", {})
    if not cfg:
        logger.warning("strategy_engine.s06_scalping missing — using defaults")
    return cfg


class S06Scalping(BaseStrategy):
    """
    Strategy S6: MACD-Momentum Scalping with session + spread filters.

    Maintains a 2-bar MACD histogram history to detect fresh cross events.
    Tight SL (0.5 ATR) with 1:1.5 RR — designed for frequent small wins.
    """

    _cfg_s6: dict = {}

    def __init__(
        self,
        pair: str,
        timeframe: str,
        config: Optional[dict] = None,
    ) -> None:
        super().__init__(pair, timeframe, config)
        self._macd_buf: deque = deque(maxlen=2)
        if not S06Scalping._cfg_s6:
            S06Scalping._cfg_s6 = _load_s6_cfg()

    @property
    def strategy_id(self) -> str:
        return "S6"

    def compute(self, features: dict, candle: dict) -> StrategyResult:
        cfg = self._cfg_s6
        macd_min: float = float(cfg.get("macd_hist_min", 0.00002))
        mom_min: float = float(cfg.get("momentum_min", 0.3))
        sl_mult: float = float(cfg.get("sl_atr_mult", 0.5))
        tp_rr: float = float(cfg.get("tp_rr_ratio", 1.5))
        min_conf: float = float(cfg.get("min_confidence", 0.55))
        hour_start: int = int(cfg.get("session_hours_start", 7))
        hour_end: int = int(cfg.get("session_hours_end", 17))
        max_spread: float = float(cfg.get("max_spread_pct", 0.0003))

        hour = float(features.get("hour_of_day", 12.0))
        spread_pct = float(features.get("spread_pct", 0.0))
        volatility_ratio = float(features.get("volatility_ratio", 1.0))

        # Session + quality guards
        if not (hour_start <= hour <= hour_end):
            return self._no_trade("UNKNOWN")
        if spread_pct > max_spread:
            return self._no_trade("UNKNOWN")
        if volatility_ratio > 2.0:
            return self._no_trade("VOLATILE")

        macd_hist = float(features.get("macd_hist_z", 0.0))   # v4.0: v3.0 emitted the z-score under `macd_hist`
        momentum = float(features.get("momentum_score", 0.0))

        self._macd_buf.append(macd_hist)
        cross_detected = self._detect_cross()

        signal: Optional[str] = None

        if macd_hist > macd_min and momentum > mom_min:
            signal = "BUY"
        elif macd_hist < -macd_min and momentum < -mom_min:
            signal = "SELL"

        if signal is None:
            return self._no_trade("RANGING")

        body_ratio = float(features.get("body_ratio", 0.0))
        volume_ratio = float(features.get("volume_ratio", 1.0))
        atr = float(features.get("atr", 0.0))
        close = float(candle["close"])

        if close <= 0.0 or atr <= 0.0:
            return self._no_trade("RANGING")

        confidence = 0.55
        if cross_detected:
            confidence += 0.15
        if body_ratio > 0.6:
            confidence += 0.10
        if volume_ratio > 1.1:
            confidence += 0.05
        confidence = min(confidence, 1.0)

        if confidence < min_conf:
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
        score = min(abs(macd_hist) / (macd_min * 5), 1.0)

        result = StrategyResult(
            score=score,
            intent="BREAKOUT",
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
            "S6 Scalp signal: %s %s macd_hist=%.5f cross=%s conf=%.2f sl_inr=INR%.0f",
            signal, self.pair, macd_hist, cross_detected, confidence, sl_inr,
        )
        return result

    def _detect_cross(self) -> bool:
        """True when MACD histogram changed sign this bar (fresh cross)."""
        if len(self._macd_buf) < 2:
            return False
        prev, curr = self._macd_buf[0], self._macd_buf[1]
        return (prev >= 0.0) != (curr >= 0.0)
