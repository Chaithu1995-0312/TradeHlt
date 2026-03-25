"""
fusion_engine.py
═══════════════════════════════════════════════════════════════════════════════
Unified multi-layer scoring engine.

Layer stack (in evaluation order):
  1. Gaussian scorer  — primary anchor (CRTGaussianScorer / CRTCalibratedScorer)
  2. Neural model     — adaptive layer (stubbed; plug TradeNet GGUF here)
  3. LLM gate         — uncertainty arbiter, fires ONLY when Gaussian score
                        falls in [llm_lower_band, llm_upper_band] (default 0.45–0.65)

Designed for:
  - Backtest integration (via BacktestRunner)
  - Live trading pipeline (low-latency, fail-open)
  - Training data generation (every decision logged via FusionLogger)

Architecture principle:
  LLM is NOT a replacement for Gaussian — it is a tie-breaker in the
  uncertainty zone where the Gaussian score alone is insufficiently confident.
  Clear signals (score < 0.45 or > 0.65) never touch the LLM.
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from typing import Optional, Callable

logger = logging.getLogger("FusionEngine")

# feature_builder is the single source of truth for the canonical feature vector
try:
    from feature_builder import build_feature_vector, feature_dict_to_vector, N_FEATURES
    _FEATURE_BUILDER_AVAILABLE = True
except ImportError:
    _FEATURE_BUILDER_AVAILABLE = False

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FusionConfig:
    """
    Controls layer weights and LLM activation band.

    gaussian_weight / neural_weight: relative contribution when both layers
    are active (normalised internally).

    llm_lower_band / llm_upper_band: Gaussian score range that triggers LLM.
    Scores outside this band are decided by Gaussian alone — LLM never called.

    llm_weight: how strongly LLM adjusts the base score when it does fire.
    A value of 0.2 means LLM can move the final score ±10% max.

    enable_llm: master switch; set False to disable LLM globally (e.g. latency
    benchmarking, backtest replay without server).
    """
    gaussian_weight: float = 0.6
    neural_weight:   float = 0.4
    llm_weight:      float = 0.2
    llm_lower_band:  float = 0.45
    llm_upper_band:  float = 0.65
    enable_llm:      bool  = True

    # Risk tiers — map final_score to risk multiplier
    tier_full:   float = 0.75   # score >= tier_full  → risk 1.0×
    tier_half:   float = 0.60   # score >= tier_half  → risk 0.5×
    tier_quarter: float = 0.50  # score >= tier_quarter → risk 0.25×
    # Below tier_quarter → REJECT


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT CONTRACT
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FusionResult:
    """
    Complete scoring breakdown for one trade signal.
    Stored on TradeRecord and written to trade log for every decision.
    """
    final_score:    float
    gaussian:       float
    neural:         Optional[float]
    llm:            Optional[float]
    llm_fired:      bool            # True = LLM was in uncertainty band and called
    action:         str             # "TRADE" | "REJECT"
    risk_mult:      float           # risk multiplier applied to base risk_pct

    def to_dict(self) -> dict:
        return {
            "final_score": round(self.final_score, 4),
            "gaussian":    round(self.gaussian,    4),
            "neural":      round(self.neural, 4) if self.neural is not None else None,
            "llm":         round(self.llm,    4) if self.llm    is not None else None,
            "llm_fired":   self.llm_fired,
            "action":      self.action,
            "risk_mult":   round(self.risk_mult, 4),
        }


# ─────────────────────────────────────────────────────────────────────────────
# GAUSSIAN ADAPTER
# Wraps CRTGaussianScorer / CRTCalibratedScorer behind a uniform interface.
# ─────────────────────────────────────────────────────────────────────────────

class GaussianAdapter:
    """
    Thin adapter so FusionEngine doesn't care which scorer generation is active.
    Accepts CRTGaussianScorer, CRTCalibratedScorer, or any object with .compute().
    """

    def __init__(self, scorer) -> None:
        self._scorer = scorer

    def score(self, features: dict, candle_idx: int = 0) -> float:
        """
        Returns a float in [0, 1].
        features : raw cached_features dict from crt_engine_v2 (may include atr_vol).
        Falls back to 0.5 (neutral) if scorer returns None or raises.

        CRTGaussianScorer.compute() and CRTCalibratedScorer.compute() both
        accept the raw dict directly — no conversion needed for the Gaussian path.
        The feature_builder is used only by the neural layer (via neural_fn).
        """
        try:
            result = self._scorer.compute(features, candle_idx)
            if result is None:
                return 0.5
            if isinstance(result, dict):
                return _clamp(float(result.get("score", 0.5)))
            return _clamp(float(result))
        except Exception as e:
            logger.warning(f"GaussianAdapter.score() failed: {e}. Returning 0.5.")
            return 0.5


# ─────────────────────────────────────────────────────────────────────────────
# FUSION ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class FusionEngine:
    """
    Multi-layer scoring engine.

    Parameters
    ----------
    gaussian_adapter : GaussianAdapter wrapping your CRT scorer
    neural_fn        : callable(features: dict) -> float, or None
    llm_fn           : callable(signal: dict) -> float, or None
                       Receives the raw signal dict (not backtest metrics).
                       Use llm_gate_live.llm_gate for live trading.
    config           : FusionConfig
    """

    def __init__(
        self,
        gaussian_adapter: GaussianAdapter,
        neural_fn:  Optional[Callable[[dict], float]] = None,
        llm_fn:     Optional[Callable[[dict], float]] = None,
        config:     FusionConfig = None,
    ) -> None:
        self.gaussian = gaussian_adapter
        self.neural   = neural_fn
        self.llm_fn   = llm_fn
        self.cfg      = config or FusionConfig()
        # Guard: auto-disable LLM when no function is wired — prevents the
        # uncertainty-band check reaching a None callable and silently failing
        if self.llm_fn is None:
            self.cfg.enable_llm = False

    # ──────────────────────────────────────────────────────────────────────────

    def evaluate(
        self,
        features:   dict,
        signal:     dict,
        candle_idx: int = 0,
    ) -> FusionResult:
        """
        Full pipeline: features → score → risk decision.

        Parameters
        ----------
        features   : raw CRT feature dict (retest_depth, body_ratio, disp_str, ...)
                     as stamped by crt_engine_v2 at RETEST_CONFIRMED
        signal     : context dict for LLM (symbol, direction, session, ...)
        candle_idx : current candle index for scorer decay

        Returns
        -------
        FusionResult with final_score, per-layer scores, action, risk_mult
        """

        # ── Layer 1: Gaussian (mandatory) ────────────────────────────────────
        g_score = self.gaussian.score(features, candle_idx)

        # ── Layer 2: Neural (optional) ────────────────────────────────────────
        n_score: Optional[float] = None
        if self.neural is not None:
            try:
                n_score = _clamp(float(self.neural(features)))
            except Exception as e:
                logger.warning(f"Neural layer failed: {e}. Skipping.")

        # ── Base fusion: weighted blend of available layers ──────────────────
        if n_score is not None:
            # Both layers active — normalise weights
            total_w = self.cfg.gaussian_weight + self.cfg.neural_weight
            base    = (
                self.cfg.gaussian_weight * g_score +
                self.cfg.neural_weight   * n_score
            ) / total_w
        else:
            base = g_score  # Gaussian alone

        base = _clamp(base)

        # ── Layer 3: LLM — uncertainty band arbiter ───────────────────────────
        # Only fires when Gaussian score is in [lower_band, upper_band].
        # Clear high/low confidence signals bypass LLM entirely.
        l_score:   Optional[float] = None
        llm_fired: bool            = False

        if (
            self.cfg.enable_llm
            and self.llm_fn is not None
            and self.cfg.llm_lower_band <= g_score <= self.cfg.llm_upper_band
        ):
            try:
                l_score   = _clamp(float(self.llm_fn(signal)))
                llm_fired = True
                base      = _clamp(
                    (1.0 - self.cfg.llm_weight) * base +
                    self.cfg.llm_weight          * l_score
                )
                logger.debug(
                    f"LLM fired in uncertainty band | "
                    f"g={g_score:.3f} llm={l_score:.3f} → base={base:.3f}"
                )
            except Exception as e:
                logger.warning(f"LLM layer failed (fail-open): {e}.")

        # ── Risk decision ─────────────────────────────────────────────────────
        action, risk_mult = self._decide(base)

        return FusionResult(
            final_score = base,
            gaussian    = g_score,
            neural      = n_score,
            llm         = l_score,
            llm_fired   = llm_fired,
            action      = action,
            risk_mult   = risk_mult,
        )

    # ──────────────────────────────────────────────────────────────────────────

    def _decide(self, score: float) -> tuple[str, float]:
        """Map final score to (action, risk_mult)."""
        if score >= self.cfg.tier_full:
            return "TRADE", 1.0
        elif score >= self.cfg.tier_half:
            return "TRADE", 0.5
        elif score >= self.cfg.tier_quarter:
            return "TRADE", 0.25
        else:
            return "REJECT", 0.0
