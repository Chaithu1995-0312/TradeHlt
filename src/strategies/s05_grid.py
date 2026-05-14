"""
s05_grid.py
================================================================================
S5 — Grid Strategy

Divides the current swing range (swing_low → swing_high) into N equal price
levels. When the current close is within proximity_atr_mult * ATR of a grid
level, a trade is signalled:

  BUY  — price at or near a grid support level (lower half of grid)
  SELL — price at or near a grid resistance level (upper half of grid)

Guards:
  - Swing range must be >= min_range_atr * ATR (avoid degenerate ranges)
  - Grid levels that are too close to each other (range < 2 * ATR) are skipped
  - Trending regimes are filtered: volatility_regime != "TRENDING" preferred

Confidence:
  base = 0.50
  + 0.10 if zone_strength > 0.6 at the grid level
  + 0.10 if volume_ratio < 0.9 (low volume → exhaustion near level)
  + 0.10 if rejection_wick confirms direction

Config section: strategy_engine.s05_grid
================================================================================
"""

from __future__ import annotations

import sys
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


def _load_s5_cfg() -> dict:
    se = get_prod_section("strategy_engine") or {}
    cfg = se.get("s05_grid", {})
    if not cfg:
        logger.warning("strategy_engine.s05_grid missing — using defaults")
    return cfg


class S05Grid(BaseStrategy):
    """
    Strategy S5: ATR-Grid Mean-Reversion.

    Constructs N grid levels from the current swing range and fires when price
    touches a level with volume/zone confirmation.
    """

    _cfg_s5: dict = {}

    def __init__(
        self,
        pair: str,
        timeframe: str,
        config: Optional[dict] = None,
    ) -> None:
        super().__init__(pair, timeframe, config)
        if not S05Grid._cfg_s5:
            S05Grid._cfg_s5 = _load_s5_cfg()

    @property
    def strategy_id(self) -> str:
        return "S5"

    def compute(self, features: dict, candle: dict) -> StrategyResult:
        cfg = self._cfg_s5
        n_levels: int = int(cfg.get("n_levels", 5))
        prox_mult: float = float(cfg.get("proximity_atr_mult", 0.4))
        sl_mult: float = float(cfg.get("sl_atr_mult", 0.8))
        tp_rr: float = float(cfg.get("tp_rr_ratio", 1.2))
        min_conf: float = float(cfg.get("min_confidence", 0.50))
        min_range_atr: float = float(cfg.get("min_range_atr", 3.0))

        swing_high = float(features.get("swing_high", 0.0))
        swing_low = float(features.get("swing_low", 0.0))
        atr = float(features.get("atr", 0.0))
        close = float(candle.get("close", 0.0))

        if close <= 0.0 or atr <= 0.0 or swing_high <= swing_low:
            return self._no_trade("UNKNOWN")

        swing_range = swing_high - swing_low
        if swing_range < atr * min_range_atr:
            return self._no_trade("RANGING")

        grid_step = swing_range / n_levels
        # Avoid a degenerate grid where levels are closer than 2 ATR
        if grid_step < atr * 0.5:
            return self._no_trade("RANGING")

        # Find closest grid level
        level, signal = self._nearest_grid_level(
            close, swing_low, grid_step, n_levels, atr * prox_mult
        )
        if signal is None or level is None:
            return self._no_trade("RANGING")

        # Confirmation features
        zone_strength = float(features.get("zone_strength", 0.0))
        volume_ratio = float(features.get("volume_ratio", 1.0))
        rejection_wick = bool(features.get("rejection_wick", False))
        volatility_regime = str(features.get("volatility_regime", "UNKNOWN"))

        # Avoid strong trending moves — grid works in ranging markets
        if volatility_regime == "TRENDING":
            return self._no_trade("RANGING")

        confidence = 0.50
        if zone_strength > 0.6:
            confidence += 0.10
        if volume_ratio < 0.9:
            confidence += 0.10
        if rejection_wick:
            confidence += 0.10
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
        score = confidence

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
            "S5 Grid signal: %s %s level=%.5f conf=%.2f sl_inr=INR%.0f",
            signal, self.pair, level, confidence, sl_inr,
        )
        return result

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _nearest_grid_level(
        self,
        close: float,
        swing_low: float,
        grid_step: float,
        n_levels: int,
        proximity: float,
    ) -> Tuple[Optional[float], Optional[str]]:
        """
        Find the grid level closest to close within proximity distance.
        Returns (level_price, signal) or (None, None).
        Levels in the lower half → BUY; upper half → SELL.
        """
        best_dist = float("inf")
        best_level: Optional[float] = None
        best_idx: int = -1

        for i in range(n_levels + 1):
            level = swing_low + i * grid_step
            dist = abs(close - level)
            if dist < best_dist:
                best_dist = dist
                best_level = level
                best_idx = i

        if best_dist > proximity:
            return None, None

        midpoint = n_levels / 2.0
        signal = "BUY" if best_idx <= midpoint else "SELL"
        return best_level, signal
