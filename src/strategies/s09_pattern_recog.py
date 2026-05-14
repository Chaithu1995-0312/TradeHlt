"""
s09_pattern_recog.py
================================================================================
S9 — Pattern Recognition Strategy

Detects candlestick patterns and maps them to directional signals.

Single-candle patterns (stateless):
  Hammer        — long lower wick, small body, small upper wick → BUY
  Shooting Star — long upper wick, small body, small lower wick → SELL
  Bullish Marubozu — full bull body, no wicks → BUY
  Bearish Marubozu — full bear body, no wicks → SELL

Multi-candle patterns (stateful, 3-candle buffer):
  Bullish Engulfing — bearish candle followed by bull candle that fully engulfs → BUY
  Bearish Engulfing — bullish candle followed by bear candle that fully engulfs → SELL

Confidence is scaled by pattern strength and trend alignment:
  +0.10 if trend_bias matches signal direction
  +0.10 if momentum_score > 0.5 (BUY) or < -0.5 (SELL)
  +0.05 if volume_ratio > 1.2 (confirmation volume)

Config section: strategy_engine.s09_pattern_recog in production JSON.
================================================================================
"""

from __future__ import annotations

import sys
from collections import deque
from pathlib import Path
from typing import Optional, Tuple

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


def _load_s9_cfg() -> dict:
    se = get_prod_section("strategy_engine") or {}
    cfg = se.get("s09_pattern_recog", {})
    if not cfg:
        logger.warning("strategy_engine.s09_pattern_recog missing — using defaults")
    return cfg


class S09PatternRecog(BaseStrategy):
    """
    Strategy S9: Candlestick Pattern Recognition.

    Maintains a 3-candle rolling buffer to detect both single-candle and
    two-candle reversal patterns. Falls back to single-candle only until
    buffer is warm (>= 2 candles).
    """

    _cfg_s9: dict = {}

    def __init__(
        self,
        pair: str,
        timeframe: str,
        config: Optional[dict] = None,
    ) -> None:
        super().__init__(pair, timeframe, config)
        self._candle_buf: deque = deque(maxlen=3)
        if not S09PatternRecog._cfg_s9:
            S09PatternRecog._cfg_s9 = _load_s9_cfg()

    @property
    def strategy_id(self) -> str:
        return "S9"

    # ── Public interface ───────────────────────────────────────────────────────

    def compute(self, features: dict, candle: dict) -> StrategyResult:
        self._candle_buf.append(candle)

        cfg = self._cfg_s9
        wick_mult: float = float(cfg.get("hammer_wick_mult", 2.0))
        engulf_mult: float = float(cfg.get("engulf_body_mult", 1.1))
        sl_mult: float = float(cfg.get("sl_atr_mult", 1.2))
        tp_rr: float = float(cfg.get("tp_rr_ratio", 1.8))
        min_conf: float = float(cfg.get("min_confidence", 0.50))

        pattern, signal, base_conf = self._detect_pattern(
            candle, features, wick_mult, engulf_mult
        )
        if signal is None or pattern is None:
            return self._no_trade("UNKNOWN")

        # Confidence adjustments
        trend = str(features.get("trend_bias", "neutral")).lower()
        momentum = float(features.get("momentum_score", 0.0))
        volume_ratio = float(features.get("volume_ratio", 1.0))

        confidence = base_conf
        if signal == "BUY" and trend == "bullish":
            confidence += 0.10
        elif signal == "SELL" and trend == "bearish":
            confidence += 0.10
        if signal == "BUY" and momentum > 0.5:
            confidence += 0.10
        elif signal == "SELL" and momentum < -0.5:
            confidence += 0.10
        if volume_ratio > 1.2:
            confidence += 0.05
        confidence = min(confidence, 1.0)

        if confidence < min_conf:
            return self._no_trade("UNKNOWN")

        close = float(candle.get("close", 0.0))
        atr = float(features.get("atr", 0.0))
        if close <= 0.0 or atr <= 0.0:
            return self._no_trade("UNKNOWN")

        regime = "TRENDING" if trend in ("bullish", "bearish") else "RANGING"

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

        result = StrategyResult(
            score=float(features.get("pattern_score", base_conf)),
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
            "S9 pattern=%s signal=%s %s conf=%.2f sl_inr=INR%.0f",
            pattern, signal, self.pair, confidence, sl_inr,
        )
        return result

    # ── Pattern detection ──────────────────────────────────────────────────────

    def _detect_pattern(
        self,
        candle: dict,
        features: dict,
        wick_mult: float,
        engulf_mult: float,
    ) -> Tuple[Optional[str], Optional[str], float]:
        """
        Returns (pattern_name, signal, base_confidence) or (None, None, 0.0).
        Checks multi-candle patterns first (higher priority), then single.
        """
        # Multi-candle: requires >= 2 candles in buffer
        if len(self._candle_buf) >= 2:
            prev = self._candle_buf[-2]
            result = self._check_engulfing(prev, candle, engulf_mult)
            if result[0]:
                return result

        # Single-candle patterns from features or raw OHLCV
        return self._check_single_candle(candle, features, wick_mult)

    def _check_engulfing(
        self,
        prev: dict,
        curr: dict,
        engulf_mult: float,
    ) -> Tuple[Optional[str], Optional[str], float]:
        p_open = float(prev.get("open", 0.0))
        p_close = float(prev.get("close", 0.0))
        c_open = float(curr.get("open", 0.0))
        c_close = float(curr.get("close", 0.0))

        if any(v <= 0.0 for v in [p_open, p_close, c_open, c_close]):
            return None, None, 0.0

        prev_body = abs(p_close - p_open)
        curr_body = abs(c_close - c_open)

        if prev_body <= 0.0:
            return None, None, 0.0

        # Bullish engulfing: prev bearish, curr bullish, curr body > prev body
        if (p_close < p_open
                and c_close > c_open
                and c_close >= p_open
                and c_open <= p_close
                and curr_body >= prev_body * engulf_mult):
            return "BULLISH_ENGULFING", "BUY", 0.60

        # Bearish engulfing: prev bullish, curr bearish, curr body > prev body
        if (p_close > p_open
                and c_close < c_open
                and c_close <= p_open
                and c_open >= p_close
                and curr_body >= prev_body * engulf_mult):
            return "BEARISH_ENGULFING", "SELL", 0.60

        return None, None, 0.0

    def _check_single_candle(
        self,
        candle: dict,
        features: dict,
        wick_mult: float,
    ) -> Tuple[Optional[str], Optional[str], float]:
        o = float(candle.get("open", 0.0))
        h = float(candle.get("high", 0.0))
        l = float(candle.get("low", 0.0))
        c = float(candle.get("close", 0.0))

        if any(v <= 0.0 for v in [o, h, l, c]) or h <= l:
            return None, None, 0.0

        body = abs(c - o)
        upper_wick = h - max(o, c)
        lower_wick = min(o, c) - l
        total_range = h - l

        if total_range <= 0.0:
            return None, None, 0.0

        body_pct = body / total_range

        # Bullish Marubozu — strong bull candle, minimal wicks
        if c > o and body_pct > 0.85 and upper_wick < body * 0.1:
            return "BULL_MARUBOZU", "BUY", 0.55

        # Bearish Marubozu — strong bear candle, minimal wicks
        if c < o and body_pct > 0.85 and lower_wick < body * 0.1:
            return "BEAR_MARUBOZU", "SELL", 0.55

        # Hammer — small body, long lower wick, small upper wick (< 15% range)
        if (body > 0.0
                and lower_wick >= body * wick_mult
                and upper_wick <= total_range * 0.15
                and body_pct < 0.4):
            return "HAMMER", "BUY", 0.55

        # Shooting star — small body, long upper wick, small lower wick (< 15% range)
        if (body > 0.0
                and upper_wick >= body * wick_mult
                and lower_wick <= total_range * 0.15
                and body_pct < 0.4):
            return "SHOOTING_STAR", "SELL", 0.55

        return None, None, 0.0
