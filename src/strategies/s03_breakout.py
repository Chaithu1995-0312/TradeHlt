"""
s03_breakout.py
================================================================================
S3 — Breakout Strategy

Detects confirmed range breakouts using swing levels and volume.

BUY (bullish breakout):
  1. break_of_structure=True  (price closed above structure)
  2. close > swing_high + atr * breakout_atr_mult  (clear breakout margin)
  3. volume_ratio >= min_volume_ratio  (volume confirms momentum)
  4. trend_bias in ("bullish", "neutral")  (not fading a downtrend)

SELL (bearish breakout):
  1. break_of_structure=True
  2. close < swing_low - atr * breakout_atr_mult
  3. volume_ratio >= min_volume_ratio
  4. trend_bias in ("bearish", "neutral")

Confidence scoring:
  base = 0.55
  + 0.15 if disp_strength > 0.7 (strong displacement)
  + 0.10 if momentum_score > 0.6 (BUY) or < -0.6 (SELL)
  + 0.10 if higher_high (BUY) or lower_low (SELL)
  + 0.05 if ema_fast crosses ema_slow in breakout direction

Config section: strategy_engine.s03_breakout in production JSON.
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
from config_layer.strict_config import ConfigKeyMissingError, require_all
from strategies.base_strategy import BaseStrategy              # type: ignore
from strategies.strategy_result import StrategyResult          # type: ignore
from utils.logging_config import get_flow_logger               # type: ignore

logger = get_flow_logger("STRATEGY_ENGINE")


_S03Breakout_KEYS = ("breakout_atr_mult", "min_volume_ratio", "sl_atr_mult", "tp_rr_ratio", "min_confidence")

def _load_s3_cfg() -> dict:
    se = get_prod_section("strategy_engine")
    if "s03_breakout" not in se:
        raise ConfigKeyMissingError(
            ["s03_breakout"], section="strategy_engine", consumer="S03Breakout",
        )
    return require_all(
        se["s03_breakout"], _S03Breakout_KEYS,
        section_name="strategy_engine.s03_breakout", consumer="S03Breakout",
    )


class S03Breakout(BaseStrategy):
    """
    Strategy S3: Structural Breakout with Volume Confirmation.

    Fires on clear break of a key swing level, confirmed by above-average
    volume, with entry just beyond the breakout point and SL below it.
    """

    _cfg_s3: dict = {}

    def __init__(
        self,
        pair: str,
        timeframe: str,
        config: Optional[dict] = None,
    ) -> None:
        super().__init__(pair, timeframe, config)
        if config is not None:
            self._cfg_s3 = require_all(
                config, _S03Breakout_KEYS,
                section_name="strategy_engine.s03_breakout", consumer="S03Breakout",
            )
        else:
            if not S03Breakout._cfg_s3:
                S03Breakout._cfg_s3 = _load_s3_cfg()
            self._cfg_s3 = S03Breakout._cfg_s3

    @property
    def strategy_id(self) -> str:
        return "S3"

    def compute(self, features: dict, candle: dict) -> StrategyResult:
        cfg = self._cfg_s3
        bo_atr_mult: float = float(cfg["breakout_atr_mult"])
        min_vol: float = float(cfg["min_volume_ratio"])
        sl_mult: float = float(cfg["sl_atr_mult"])
        tp_rr: float = float(cfg["tp_rr_ratio"])
        min_conf: float = float(cfg["min_confidence"])

        bos = bool(features.get("break_of_structure", False))
        if not bos:
            return self._no_trade("UNKNOWN")

        volume_ratio = float(features.get("volume_ratio", 1.0))
        if volume_ratio < min_vol:
            return self._no_trade("UNKNOWN")

        trend = str(features.get("trend_bias", "neutral")).lower()
        swing_high = float(features.get("swing_high", 0.0))
        swing_low = float(features.get("swing_low", 0.0))
        higher_high = bool(features.get("higher_high", False))
        lower_low = bool(features.get("lower_low", False))
        disp_strength = float(features.get("disp_strength", 0.0))
        momentum = float(features.get("momentum_score", 0.0))
        ema_fast = float(features.get("ema_fast", 0.0))
        ema_slow = float(features.get("ema_slow", 0.0))

        close = float(candle["close"])
        atr = self._atr_price(features, close)
        if close <= 0.0 or atr <= 0.0:
            return self._no_trade("UNKNOWN")

        signal: Optional[str] = None
        confidence = 0.55

        # Bullish breakout
        if (trend in ("bullish", "neutral")
                and swing_high > 0.0
                and close > swing_high + atr * bo_atr_mult):
            signal = "BUY"
            if disp_strength > 0.7:
                confidence += 0.15
            if momentum > 0.6:
                confidence += 0.10
            if higher_high:
                confidence += 0.10
            if ema_fast > 0 and ema_slow > 0 and ema_fast > ema_slow:
                confidence += 0.05

        # Bearish breakout
        elif (trend in ("bearish", "neutral")
                and swing_low > 0.0
                and close < swing_low - atr * bo_atr_mult):
            signal = "SELL"
            if disp_strength > 0.7:
                confidence += 0.15
            if momentum < -0.6:
                confidence += 0.10
            if lower_low:
                confidence += 0.10
            if ema_fast > 0 and ema_slow > 0 and ema_fast < ema_slow:
                confidence += 0.05

        if signal is None:
            return self._no_trade("BREAKOUT")

        confidence = min(confidence, 1.0)
        if confidence < min_conf:
            return self._no_trade("BREAKOUT")

        regime = "BREAKOUT"

        if signal == "BUY":
            # SL below the breakout level (swing_high)
            sl = swing_high - atr * sl_mult
            tp = close + (close - sl) * tp_rr
        else:
            # SL above the breakout level (swing_low)
            sl = swing_low + atr * sl_mult
            tp = close - (sl - close) * tp_rr

        sl_pips = self._sl_pips(close, sl)
        lot = self._get_lot_size(sl_pips)
        if lot <= 0.0:
            return self._no_trade(regime)

        sl_inr = self._calc_sl_inr(close, sl, lot)
        tp_inr = self._calc_tp_inr(close, tp, lot)
        score = min(disp_strength, 1.0) if disp_strength > 0.0 else 0.5

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
            "S3 Breakout signal: %s %s vol_ratio=%.2f conf=%.2f sl_inr=INR%.0f",
            signal, self.pair, volume_ratio, confidence, sl_inr,
        )
        return result
