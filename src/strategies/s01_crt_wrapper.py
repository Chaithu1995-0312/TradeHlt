"""
s01_crt_wrapper.py
================================================================================
S1 — CRT Strategy Wrapper

Adapter pattern: wraps the existing `engines.crt_engine.compute()` module
function and converts its score dict into a StrategyResult.

Zero changes to the existing CRT engine — this is a pure adapter.

Config section: strategy_engine.s01_crt in production JSON.
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

from config_layer.production_config import get_prod_section, get_prod_config   # type: ignore
from engines import crt_engine                                                  # type: ignore
from strategies.base_strategy import BaseStrategy                               # type: ignore
from strategies.strategy_result import StrategyResult                           # type: ignore
from utils.logging_config import get_flow_logger                                # type: ignore

logger = get_flow_logger("STRATEGY_ENGINE")


def _load_s1_cfg() -> dict:
    se = get_prod_section("strategy_engine") or {}
    cfg = se.get("s01_crt", {})
    if not cfg:
        logger.warning("strategy_engine.s01_crt missing — using defaults")
    return cfg


def _load_score_component_weights() -> tuple:
    """PLAN-002: read the HOW-owned engines-path weights from production config.
    Raises KeyError if missing — no CODE defaults permitted."""
    try:
        crt_sec = get_prod_section("crt_engine")
        raw = crt_sec["score_component_weights"]
        return tuple(float(c) for c in raw)
    except Exception as exc:
        logger.error("PLAN-002: score_component_weights not loadable from prod config: %s", exc)
        raise


class S01CRTWrapper(BaseStrategy):
    """
    Strategy S1: Candle Range Theory (CRT).

    Delegates scoring to the existing deterministic CRT engine and maps the
    numeric score + feature flags to a StrategyResult.

    Signal direction is determined by:
      trend_bias + break_of_structure or sweep_detected.
    Entry geometry: close ± ATR * sl_atr_mult; TP at 1:tp_rr_ratio.
    """

    _cfg_s1: dict = {}
    _score_component_weights: tuple = ()

    def __init__(
        self,
        pair: str,
        timeframe: str,
        config: Optional[dict] = None,
    ) -> None:
        super().__init__(pair, timeframe, config)
        if not S01CRTWrapper._cfg_s1:
            S01CRTWrapper._cfg_s1 = _load_s1_cfg()
        if not S01CRTWrapper._score_component_weights:
            S01CRTWrapper._score_component_weights = _load_score_component_weights()

    @property
    def strategy_id(self) -> str:
        return "S1"

    def compute(self, features: dict, candle: dict) -> StrategyResult:
        cfg = self._cfg_s1
        min_score: float = float(cfg.get("min_score", 0.65))
        sl_mult: float = float(cfg.get("sl_atr_mult", 1.5))
        tp_rr: float = float(cfg.get("tp_rr_ratio", 2.0))
        conf_scale: float = float(cfg.get("confidence_scale", 1.0))

        trade_id = f"S1_{self.pair}_{features.get('session', 'UNK')}"
        try:
            result = crt_engine.compute(
                trade_id, features,
                {"score_component_weights": list(self._score_component_weights)},
            )
        except Exception as exc:
            logger.warning("S1 CRT engine error: %s", exc)
            return self._no_trade("UNKNOWN")

        score = float(result.get("score", 0.0))
        if score < min_score:
            return self._no_trade("UNKNOWN")

        trend = str(features.get("trend_bias", "neutral")).lower()
        bos = bool(features.get("break_of_structure", False))
        sweep = bool(features.get("sweep_detected", False))

        if trend == "bullish" and (bos or sweep):
            signal, regime, intent = "BUY", "TRENDING", "BREAKOUT"
        elif trend == "bearish" and (bos or sweep):
            signal, regime, intent = "SELL", "TRENDING", "BREAKOUT"
        elif trend == "bullish" and float(features.get("retest_depth", 0.0)) > 0.3:
            signal, regime, intent = "BUY", "RANGING", "PULLBACK"
        elif trend == "bearish" and float(features.get("retest_depth", 0.0)) > 0.3:
            signal, regime, intent = "SELL", "RANGING", "PULLBACK"
        else:
            return self._no_trade("UNKNOWN")

        close = float(candle["close"])
        atr = float(features.get("atr", 0.0))
        if close <= 0.0 or atr <= 0.0:
            return self._no_trade(regime)

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
        confidence = min(score * conf_scale, 1.0)

        result_obj = StrategyResult(
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
            # S01 understands CRT transition path — builder uses CRT-enriched evidence.
            capabilities=frozenset({"transition_path"}),
        )
        result_obj.validate()
        logger.info(
            "S1 signal: %s %s score=%.3f conf=%.2f sl_inr=INR%.0f",
            signal, self.pair, score, confidence, sl_inr,
        )
        return result_obj
