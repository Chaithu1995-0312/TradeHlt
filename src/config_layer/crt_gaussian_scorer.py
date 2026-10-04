"""
Central CRT Gaussian scorer.

Extracted from backtest_v2.py with logic preserved.
"""

from __future__ import annotations

import logging
import math
from typing import Optional

# ── Load gaussian_scorer section from production config (strict — section is governed) ──
# Fallback sweep / fail-fast: the `except → {}` config mask was removed. The `gaussian_scorer`
# section is present in the active config; a missing section is now a load-time error, not a
# silent empty-dict that would let the scorer degrade to defaults. The ImportError dual-path
# (package vs standalone-script import) is preserved as legitimate optional-import resilience.
try:
    from config_layer.production_config import get_prod_section as _get_section
except ImportError:
    from production_config import get_prod_section as _get_section  # standalone script path
try:
    from config_layer.strict_config import require as _require_cfg
except ImportError:
    from strict_config import require as _require_cfg  # standalone script path
_GS_CFG = _get_section("gaussian_scorer")


def _gs(key: str):
    """Strict read of ``gaussian_scorer.<key>`` (EPIC-84: no code default; absent -> raise)."""
    return _require_cfg(_GS_CFG, key, section_name="gaussian_scorer",
                        consumer="CRTGaussianScorer")


class CRTGaussianScorer:
    """
    Scores a CRT setup using Gaussian (bell-curve) proximity scoring.

    Key insight from statistical analysis:
      - retest_depth: optimal 37-65%, NOT "more/less is better"
      - body_ratio:   optimal 65-85%, full bodies (100%) underperform
      - disp_str:     optimal 1.0-1.2x ATR, massive moves exhaust momentum

    Formula: final = (s_retest^0.35) * (s_body^0.30) * (s_disp^0.20) * (s_time^0.15)
    P(win) mapped via calibrated sigmoid: 1 / (1 + exp(-4.5*(score - 0.5)))
    """

    # Real EURCAD M15 calibration (200 retest observations 2024-2025)
    # Replaces theoretical priors. All parameters computed from empirical distribution.
    RETEST_MU = _gs("retest_mu")
    RETEST_S2 = _gs("retest_s2")  # real mean/variance of retest_depth
    BODY_MU   = _gs("body_mu")
    BODY_S2   = _gs("body_s2")  # real mean/variance of body_ratio
    DISP_MU   = _gs("disp_mu")
    DISP_S2   = _gs("disp_s2")  # real mean/variance of disp_str ATR mult

    # Hard filters: 5th/95th percentile of real observed feature range
    RETEST_MIN = 0.025
    RETEST_MAX = 1.0
    DISP_MAX   = 3.670  # 95th pct; 1.80 rejected 100% of real trades

    # Sigmoid calibration
    SIGMOID_K  = _gs("sigmoid_k")
    SIGMOID_X0 = _gs("sigmoid_x0")

    # Execution threshold (dynamic threshold overrides this per-trade)
    EXECUTE_P = _gs("execute_p")

    def __init__(self, decay_lambda: Optional[float] = None):
        # None = "use the declared config value" (strict read), not a code literal.
        self.decay_lambda = _gs("decay_lambda") if decay_lambda is None else decay_lambda
        self._log = logging.getLogger("CRT.GaussianScorer")
        from engines.scoring_engine import ScoringEngine

        self.scoring_engine = ScoringEngine()

    @staticmethod
    def _gaussian(x: float, mu: float, sigma2: float) -> float:
        return math.exp(-((x - mu) ** 2) / sigma2)

    def _p_win(self, score: float) -> float:
        """Sigmoid probability mapping: calibrated against historical outcomes."""
        return 1.0 / (1.0 + math.exp(-self.SIGMOID_K * (score - self.SIGMOID_X0)))

    def compute(
        self,
        features: dict,
        candle_idx: int = 0,
        current_index: Optional[int] = None,
    ) -> dict:
        """
        features = {
            displacement_retrace (FM-027) or legacy retest_depth:
                float — fraction of displacement body retraced (0-1)
            body_ratio:    float  - body / range of displacement candle (0-1)
            displacement_atr_ratio (FM-028) or legacy disp_str/disp_strength:
                float — displacement range in ATR multiples
            retest_index:  int    - candle index when retest was confirmed (cached)
        }
        candle_idx/current_index: current candle index for time-decay computation.
        Returns dict with score, p_win, components, decision, reject_reason.
        """
        if current_index is not None:
            candle_idx = current_index
        # CH-002 / F-050: prefer governed CRT emission keys; accept legacy aliases
        r = features.get(
            "displacement_retrace",
            features.get("retest_depth", 0.0),
        )
        b = features.get("body_ratio", 0.0)
        d = features.get(
            "displacement_atr_ratio",
            features.get("disp_str", features.get("disp_strength", 0.0)),
        )
        self._log.debug("r=%.3f, b=%.3f, d=%.3f", r, b, d)
        # Use retest_index from cached features; fall back to candles_since_sweep
        retest_idx = features.get("retest_index", 0)
        t = (
            max(0, candle_idx - retest_idx)
            if candle_idx > 0
            else features.get("candles_since_sweep", 0)
        )

        # Hard filters - capital protection
        if r < self.RETEST_MIN or r > self.RETEST_MAX:
            return self._reject(
                "filter_retest_depth_invalid",
                f"retest={r:.3f} outside [{self.RETEST_MIN},{self.RETEST_MAX}]",
            )
        if d > self.DISP_MAX:
            return self._reject(
                "filter_displacement_exhaustion",
                f"disp_str={d:.2f} > {self.DISP_MAX}",
            )

        # Gaussian component scores (all 0-1)
        s_retest = self._gaussian(r, self.RETEST_MU, self.RETEST_S2)
        s_body = self._gaussian(b, self.BODY_MU, self.BODY_S2)
        s_disp = self._gaussian(d, self.DISP_MU, self.DISP_S2)
        s_time = math.exp(-self.decay_lambda * t)
        # Multiplicative aggregation (weighted exponents)
        # Using weighted geometric mean - penalises weak links harder than linear addition.
        final_score = (
            (s_retest ** 0.35)
            * (s_body ** 0.30)
            * (s_disp ** 0.20)
            * (s_time ** 0.15)
        )
        self._log.debug(
            "s_r=%.3f, s_b=%.3f, s_d=%.3f, final=%.4f",
            s_retest, s_body, s_disp, final_score,
        )

        components = {
            "retest": round(s_retest, 4),
            "body": round(s_body, 4),
            "disp": round(s_disp, 4),
            "time": round(s_time, 4),
        }

        # Pure Gaussian scoring only.
        # Final execute/reject is decided in BacktestRunner by DecisionEngine.
        p_win = self._p_win(final_score)
        decision = "advisory"
        self._log.debug(
            f"Gaussian | r={r:.3f} b={b:.3f} d={d:.2f} t={t} "
            f"-> score={final_score:.4f} p_win={p_win:.3f} -> {decision}"
        )

        return {
            "score": round(final_score, 6),
            "p_win": round(p_win, 4),
            "components": components,
            "decision": decision,
            "reject_reason": None,
        }

    @staticmethod
    def _reject(reason: str, detail: str = "") -> dict:
        return {
            "score": 0.0,
            "p_win": 0.0,
            "components": {"retest": 0.0, "body": 0.0, "disp": 0.0, "time": 0.0},
            "decision": "reject",
            "reject_reason": reason,
        }

    @staticmethod
    def extract_features(state, candle_idx: int) -> Optional[dict]:
        """
        Returns cached_features if available (set at RETEST_CONFIRMED).
        Falls back to live extraction if cache is missing.
        Returns None on failure - safe no-op.
        """
        # Primary: use features cached at RETEST_CONFIRMED time
        if state.cached_features is not None:
            return state.cached_features

        # Fallback: live extraction (less reliable through confirmation window)
        if state.displacement_candle is None or state.retest_candle is None:
            return None
        if state.active_range is None or state.active_range.size == 0:
            return None

        disp = state.displacement_candle
        retest = state.retest_candle
        disp_move = abs(disp.close - disp.open)
        if disp_move == 0 or state.atr_abs == 0:
            return None
        # CH-002 / F-050: emit FM-027 / FM-028 identities (match crt_engine_v2 cache)
        from features import derived_math as _dm
        return {
            "displacement_retrace": _dm.displacement_retrace(
                retest_close=float(retest.close),
                disp_open=float(disp.open),
                disp_close=float(disp.close),
            ),
            "body_ratio": disp.body_ratio,
            "displacement_atr_ratio": _dm.displacement_atr_ratio(
                candle_range=float(disp.wick_size),
                atr=float(state.atr_abs),
            ),
            "retest_index": state.retest_candle_index,
        }
