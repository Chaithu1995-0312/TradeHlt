"""
s08_ml_ensemble.py
================================================================================
S8 — ML Ensemble Strategy (BitNet + Feature-Weighted Scorer)

Two-tier design with optional BitNet inference:

  Tier 1 — BitNet score (optional import, fail-open):
    If bitnet_inference is available, calls bitnet_score() with the canonical
    feature vector and blends it with the feature scorer at bitnet_weight.
    If unavailable → falls back to feature scorer alone (weight=1.0).

  Tier 2 — Feature-Weighted Scorer (always available):
    Combines five normalised sub-scores with configurable weights:
      rsi_score      = |rsi_14 − 50| / 50           (distance from neutral)
      momentum_score = |momentum_score|              (from feature)
      macd_score     = tanh(macd_hist / atr)        (normalised MACD)
      volume_score   = min(volume_ratio / 2.0, 1.0) (volume confirmation)
      trend_score    = trend_strength                (from feature)

    Weighted sum → ensemble_score ∈ [0, 1].

Signal direction:
    Determined by majority vote of directional indicators:
      - trend_bias:       bullish → +1,  bearish → -1
      - rsi_14:           < 45   → +1,  > 55    → -1
      - macd_hist:        > 0    → +1,  < 0     → -1
      - momentum_score:   > 0    → +1,  < 0     → -1
    Net vote > 0 → BUY, < 0 → SELL, == 0 → NO_TRADE.

Config section: strategy_engine.s08_ml_ensemble
================================================================================
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

# Optional BitNet import — fail-open per CONVENTIONS.md §error-handling
try:
    from bitnet.bitnet_inference import bitnet_score as _bitnet_score  # type: ignore
    _BITNET_AVAILABLE = True
except Exception:
    _BITNET_AVAILABLE = False

from config_layer.production_config import get_prod_section   # type: ignore
from strategies.base_strategy import BaseStrategy              # type: ignore
from strategies.strategy_result import StrategyResult          # type: ignore
from utils.logging_config import get_flow_logger               # type: ignore

logger = get_flow_logger("STRATEGY_ENGINE")

if not _BITNET_AVAILABLE:
    logger.warning("S8: bitnet_inference unavailable — using feature scorer only")


def _load_s8_cfg() -> dict:
    se = get_prod_section("strategy_engine") or {}
    cfg = se.get("s08_ml_ensemble", {})
    if not cfg:
        logger.warning("strategy_engine.s08_ml_ensemble missing — using defaults")
    return cfg


class S08MLEnsemble(BaseStrategy):
    """
    Strategy S8: ML Ensemble (BitNet + Feature-Weighted).

    Blends BitNet GGUF model output (when available) with a deterministic
    feature-weighted score. Direction from majority vote of four indicators.
    """

    _cfg_s8: dict = {}

    def __init__(
        self,
        pair: str,
        timeframe: str,
        config: Optional[dict] = None,
    ) -> None:
        super().__init__(pair, timeframe, config)
        if not S08MLEnsemble._cfg_s8:
            S08MLEnsemble._cfg_s8 = _load_s8_cfg()

    @property
    def strategy_id(self) -> str:
        return "S8"

    def compute(self, features: dict, candle: dict) -> StrategyResult:
        cfg = self._cfg_s8
        min_score: float = float(cfg.get("min_score", 0.60))
        sl_mult: float = float(cfg.get("sl_atr_mult", 1.5))
        tp_rr: float = float(cfg.get("tp_rr_ratio", 2.0))
        min_conf: float = float(cfg.get("min_confidence", 0.58))
        bn_weight: float = float(cfg.get("bitnet_weight", 0.40))
        feat_weight: float = float(cfg.get("feature_weight", 0.60))

        close = float(candle["close"])
        atr = float(features.get("atr", 0.0))
        if close <= 0.0 or atr <= 0.0:
            return self._no_trade("UNKNOWN")

        feature_score = self._feature_score(features, atr, cfg)

        # Blend with BitNet when available
        if _BITNET_AVAILABLE:
            try:
                # bitnet_score() uses hard key access on 6 canonical keys
                raw = _bitnet_score({
                    "body_ratio":          float(features.get("body_ratio", 0.0)),
                    "retest_depth":        float(features.get("retest_depth", 0.0)),
                    "disp_strength":       float(features.get("disp_strength", 0.0)),
                    "atr":                 atr,
                    "candles_since_retest": int(features.get("candles_since_retest", 0)),
                    "double_sweep":        float(bool(features.get("double_sweep", False))),
                })
                bn_val = float(raw) if isinstance(raw, (int, float)) else float(raw.get("score", 0.5))
                ensemble_score = bn_weight * bn_val + feat_weight * feature_score
            except Exception as exc:
                logger.warning("S8: BitNet call failed (%s) — feature scorer only", exc)
                ensemble_score = feature_score
        else:
            ensemble_score = feature_score

        ensemble_score = min(max(ensemble_score, 0.0), 1.0)

        if ensemble_score < min_score:
            return self._no_trade("UNKNOWN")

        signal = self._vote_signal(features)
        if signal is None:
            return self._no_trade("UNKNOWN")

        trend = str(features.get("trend_bias", "neutral")).lower()
        regime = "TRENDING" if trend in ("bullish", "bearish") else "RANGING"

        confidence = 0.50 + ensemble_score * 0.50
        confidence = min(confidence, 1.0)
        if confidence < min_conf:
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

        result = StrategyResult(
            score=ensemble_score,
            intent="BREAKOUT" if regime == "TRENDING" else "PULLBACK",
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
            "S8 ML signal: %s %s score=%.3f conf=%.2f sl_inr=INR%.0f bitnet=%s",
            signal, self.pair, ensemble_score, confidence, sl_inr, _BITNET_AVAILABLE,
        )
        return result

    # ── Scoring helpers ───────────────────────────────────────────────────────

    def _feature_score(self, features: dict, atr: float, cfg: dict) -> float:
        """Weighted combination of five normalised sub-scores."""
        w_rsi = float(cfg.get("rsi_weight", 0.20))
        w_mom = float(cfg.get("momentum_weight", 0.25))
        w_macd = float(cfg.get("macd_weight", 0.20))
        w_vol = float(cfg.get("volume_weight", 0.15))
        w_trend = float(cfg.get("trend_weight", 0.20))

        rsi = float(features.get("rsi_14", 50.0))
        momentum = float(features.get("momentum_score", 0.0))
        macd_hist = float(features.get("macd_hist_z", 0.0))   # v4.0: v3.0 emitted the z-score under `macd_hist`
        volume_ratio = float(features.get("volume_ratio", 1.0))
        trend_strength = float(features.get("trend_strength", 0.0))

        rsi_score = abs(rsi - 50.0) / 50.0
        mom_score = min(abs(momentum), 1.0)
        # MACD hist is ~100x smaller than ATR; scale divisor accordingly
        macd_score = abs(math.tanh(macd_hist / (atr * 0.1))) if atr > 0 else 0.0
        vol_score = min(volume_ratio / 2.0, 1.0)
        trend_score = min(abs(trend_strength), 1.0)

        return (w_rsi * rsi_score + w_mom * mom_score + w_macd * macd_score
                + w_vol * vol_score + w_trend * trend_score)

    def _vote_signal(self, features: dict) -> Optional[str]:
        """Majority vote across four directional indicators."""
        trend = str(features.get("trend_bias", "neutral")).lower()
        rsi = float(features.get("rsi_14", 50.0))
        macd_hist = float(features.get("macd_hist_z", 0.0))   # v4.0: v3.0 emitted the z-score under `macd_hist`
        momentum = float(features.get("momentum_score", 0.0))

        votes = 0
        votes += 1 if trend == "bullish" else (-1 if trend == "bearish" else 0)
        votes += 1 if rsi < 45.0 else (-1 if rsi > 55.0 else 0)
        votes += 1 if macd_hist > 0 else (-1 if macd_hist < 0 else 0)
        votes += 1 if momentum > 0 else (-1 if momentum < 0 else 0)

        if votes > 0:
            return "BUY"
        if votes < 0:
            return "SELL"
        return None
