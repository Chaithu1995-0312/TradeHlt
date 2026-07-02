"""
s10_trap_strategy.py
================================================================================
S10 — Trap Strategy  (CORE FOCUS)

Detects liquidity traps: price sweeps a key stop-loss level (swing high or low),
then reverses sharply — trapping breakout traders.

Pattern taxonomy:
  TRAP     — classic false-breakout reversal after sweep
  LIQ_SWEEP — liquidity grab with immediate strong reversal body

Detection logic:
  Bull Trap (SELL signal):
    1. higher_high=True AND sweep_detected=True  (price swept above swing_high)
    2. Close < swing_high  (reversal — price returned inside range)
    3. body_ratio >= reversal_body_ratio  (strong reversal candle)
    4. candles_since_retest <= max_candles_since_sweep  (fresh signal)

  Bear Trap (BUY signal):
    1. lower_low=True AND sweep_detected=True  (price swept below swing_low)
    2. Close > swing_low  (reversal — price returned inside range)
    3. body_ratio >= reversal_body_ratio
    4. candles_since_retest <= max_candles_since_sweep

Confidence scoring:
  base = 0.55
  + 0.15 if liquidity_sweep=True
  + 0.10 if disp_strength > trap_min_disp_strength
  + 0.10 if double_sweep=True
  + 0.10 if volume_ratio > 1.5

Config section: strategy_engine.s10_trap in production JSON.
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


def _load_s10_cfg() -> dict:
    se = get_prod_section("strategy_engine") or {}
    cfg = se.get("s10_trap", {})
    if not cfg:
        logger.warning("strategy_engine.s10_trap missing — using defaults")
    return cfg


class S10TrapStrategy(BaseStrategy):
    """
    Strategy S10: Liquidity Trap / Stop Hunt Reversal.

    Identifies bull traps and bear traps by detecting sweep + reversal patterns
    on the current candle against key swing levels from the feature set.
    """

    _cfg_s10: dict = {}

    def __init__(
        self,
        pair: str,
        timeframe: str,
        config: Optional[dict] = None,
    ) -> None:
        super().__init__(pair, timeframe, config)
        if not S10TrapStrategy._cfg_s10:
            S10TrapStrategy._cfg_s10 = _load_s10_cfg()

    @property
    def strategy_id(self) -> str:
        return "S10"

    def compute(self, features: dict, candle: dict) -> StrategyResult:
        cfg = self._cfg_s10
        min_disp: float = float(cfg.get("trap_min_disp_strength", 0.6))
        rev_body: float = float(cfg.get("reversal_body_ratio", 0.5))
        sl_mult: float = float(cfg.get("sl_atr_mult", 1.0))
        tp_rr: float = float(cfg.get("tp_rr_ratio", 2.0))
        min_conf: float = float(cfg.get("min_confidence", 0.60))
        max_age: int = int(cfg.get("max_candles_since_sweep", 3))

        sweep = bool(features.get("sweep_detected", False))
        if not sweep:
            return self._no_trade("UNKNOWN")

        higher_high = bool(features.get("higher_high", False))
        lower_low = bool(features.get("lower_low", False))
        liquidity_sweep = bool(features.get("liquidity_sweep", False))
        double_sweep = bool(features.get("double_sweep", False))
        body_ratio = float(features.get("body_ratio", 0.0))
        disp_strength = float(features.get("disp_strength", 0.0))
        candles_since = int(features.get("candles_since_retest", 0))
        volume_ratio = float(features.get("volume_ratio", 1.0))

        swing_high = float(features.get("swing_high", 0.0))
        swing_low = float(features.get("swing_low", 0.0))
        close = float(candle["close"])
        atr = float(features.get("atr", 0.0))

        if close <= 0.0 or atr <= 0.0:
            return self._no_trade("UNKNOWN")

        # Stale sweep guard
        if candles_since > max_age:
            return self._no_trade("UNKNOWN")

        # Reversal candle strength guard
        if body_ratio < rev_body:
            return self._no_trade("UNKNOWN")

        signal: Optional[str] = None
        intent: str = "TRAP"

        # Bull trap: swept high but closed back below it → SELL
        if higher_high and swing_high > 0.0 and close < swing_high:
            signal = "SELL"

        # Bear trap: swept low but closed back above it → BUY
        elif lower_low and swing_low > 0.0 and close > swing_low:
            signal = "BUY"

        if signal is None:
            return self._no_trade("UNKNOWN")

        # Confidence build-up
        confidence = 0.55
        if liquidity_sweep:
            confidence += 0.15
        if disp_strength > min_disp:
            confidence += 0.10
        if double_sweep:
            confidence += 0.10
        if volume_ratio > 1.5:
            confidence += 0.10
        confidence = min(confidence, 1.0)

        if confidence < min_conf:
            return self._no_trade("VOLATILE")

        # Classify as LIQ_SWEEP when both liquidity_sweep + double_sweep present
        if liquidity_sweep and double_sweep:
            intent = "LIQ_SWEEP"

        # Geometry — SL placed beyond the sweep spike; TP at RR multiple
        if signal == "BUY":
            sl = close - atr * sl_mult
            tp = close + (close - sl) * tp_rr
            regime = "VOLATILE"
        else:
            sl = close + atr * sl_mult
            tp = close - (sl - close) * tp_rr
            regime = "VOLATILE"

        sl_pips = self._sl_pips(close, sl)
        lot = self._get_lot_size(sl_pips)
        if lot <= 0.0:
            return self._no_trade(regime)

        sl_inr = self._calc_sl_inr(close, sl, lot)
        tp_inr = self._calc_tp_inr(close, tp, lot)
        score = min(disp_strength, 1.0) if disp_strength > 0 else body_ratio

        result = StrategyResult(
            score=score,
            intent=intent,
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
            # S10 trap detection uses CRT structure — builder uses CRT-enriched evidence.
            capabilities=frozenset({"transition_path"}),
        )
        result.validate()
        logger.info(
            "S10 TRAP signal: %s %s intent=%s conf=%.2f sl_inr=INR%.0f",
            signal, self.pair, intent, confidence, sl_inr,
        )
        return result
