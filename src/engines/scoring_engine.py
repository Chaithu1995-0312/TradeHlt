# scoring_engine.py

import logging
import math
from typing import Dict, Optional

from features.feature_schema import CANONICAL_FEATURES
from config_layer.llm_scorer import llm_score_safe
from features.schema_validator import validate_feature_values, validate_features
from features.fm_resolve import bind_phase3b_scoring_callables

log = logging.getLogger("ScoringEngine")

# Phase-3b: FM-029 via resolve_fm (identity == derived_math.disp_strength_atr_rescale).
# Bound once at import — same discipline as crt_engine_v2 Phase-2 _FM_CRT.
_FM_SCORING: dict = bind_phase3b_scoring_callables()


def compute_scores(
    body_ratio: float,
    move: float,
    atr: float,
    retest_depth: float,
    candles_since_retest: int,
    sweep_detected: bool,
    double_sweep: bool,
    lambda_decay: float = 0.05,
    score_weights: tuple = (0.35, 0.25, 0.20, 0.20),
) -> dict:
    """
    Canonical CRT scoring function.

    All sub-scores are bounded to [0, 1]. Decay is applied once.
    score_weights: (sweep, breakout, retest, time) — configurable via crt_engine.score_component_weights.
    """
    # FM-029 disp_strength_atr_rescale (GD-004 closure): the caller passes the FM-020 feature as
    # `move`, so this is a DISTINCT rescaled quantity — resolved via FORMULA_REGISTRY (Phase-3b).
    disp_strength_atr_rescale = _FM_SCORING["FM-029"](move, atr)

    if not sweep_detected:
        s_sweep = 0.0
    elif double_sweep:
        s_sweep = 1.0
    else:
        s_sweep = 0.7

    s_breakout = 0.5 * min(body_ratio, 1.0) + 0.5 * min(disp_strength_atr_rescale / 2.0, 1.0)
    s_retest = math.exp(-((retest_depth - 0.5) ** 2) / 0.04)
    s_time = math.exp(-lambda_decay * max(0, candles_since_retest))

    w_sweep, w_breakout, w_retest, w_time = score_weights
    s_final = w_sweep * s_sweep + w_breakout * s_breakout + w_retest * s_retest + w_time * s_time

    return {
        "sweep": round(s_sweep, 4),
        "breakout": round(s_breakout, 4),
        "retest": round(s_retest, 4),
        "time": round(s_time, 4),
        "final": round(s_final, 4),
        "score": round(s_final, 4),
    }


def compute_gaussian_score(features: list, params: dict) -> float:
    """
    Compute weighted Gaussian score from a feature vector and zone params.
    """
    try:
        from bitnet.zone_cosine_searcher import compute_gaussian_score as _cgs

        return _cgs(features, params)
    except ImportError:
        mu = params.get("mu", {})
        sigma = params.get("sigma", {})
        weights = params.get("weights", {})
        fidxs = params.get("feature_indices", {"depth": 0, "body": 1, "disp": 2})

        total = 0.0
        total_w = 0.0
        for fname, fidx in fidxs.items():
            if fidx >= len(features):
                continue
            x = features[fidx]
            m = mu.get(fname, 0.5)
            s = sigma.get(fname, 0.2)
            w = weights.get(fname, 1.0 / max(len(fidxs), 1))
            if s <= 0:
                continue
            g = math.exp(-((x - m) ** 2) / (2.0 * s**2))
            total += w * g
            total_w += w

        return total / total_w if total_w > 0 else 0.0


class ScoringEngine:
    def __init__(
        self,
        mode: str = "deterministic",
        neural_fn=None,
        llm_enabled: bool = True,
        llm_trigger_margin: float = 0.05,
        threshold: float = 0.7,
        insight_reporter=None,
    ):
        self.mode = mode
        self.neural_fn = neural_fn
        self.llm_enabled = llm_enabled
        self.llm_trigger_margin = llm_trigger_margin
        self.threshold = threshold
        self._reporter = insight_reporter

    def _should_trigger_llm(self, gaussian: float, neural: float) -> bool:
        """
        Trigger LLM when score is near threshold or models disagree.
        """
        near_threshold = abs(gaussian - self.threshold) <= self.llm_trigger_margin
        disagreement = abs(gaussian - neural) > 0.25
        return near_threshold or disagreement

    def attach_reporter(self, reporter) -> None:
        self._reporter = reporter

    def compute(self, features: dict) -> Dict:
        """
        Canonical scoring path.
        Returns score and p_win in [0,1].
        """
        if not isinstance(features, dict):
            raise TypeError("ScoringEngine input must be dict")

        #validate_features(features, CANONICAL_FEATURES)
        validate_feature_values(features)

        body = max(0.0, min(1.0, float(features["body_ratio"])))
        retest_depth = max(0.0, min(1.0, float(features["retest_depth"])))
        disp_strength = max(0.0, float(features["disp_strength"]))

        disp_score = min(disp_strength / 2.0, 1.0)
        retest_score = math.exp(-((retest_depth - 0.4) ** 2) / 0.08)

        score = 0.4 * body + 0.4 * disp_score + 0.2 * retest_score
        score = max(0.0, min(1.0, float(score)))
        p_win = 1.0 / (1.0 + math.exp(-4.5 * (score - 0.5)))
        p_win = max(0.0, min(1.0, float(p_win)))

        print(f"[SCORE] {score:.4f} p_win={p_win:.4f}")
        return {
            "score": round(score, 6),
            "p_win": round(p_win, 4),
            "components": {
                "body": round(body, 4),
                "disp": round(disp_score, 4),
                "retest": round(retest_score, 4),
            },
        }

    def score(self, features: dict, gaussian_score: float, sub_scores: Optional[Dict] = None) -> Dict:
        """
        Score a trade setup by mode.
        """
        if self.mode == "deterministic":
            result = {
                "final_score": gaussian_score,
                "gaussian": gaussian_score,
                "neural": None,
                "llm": None,
                "decision": "EXECUTE" if gaussian_score >= self.threshold else "BLOCK",
                "reason": "deterministic_rule",
                "override": False,
            }
            self._maybe_report(result, sub_scores)
            return result

        neural = 0.0
        llm = 0.0
        override = False
        decision = "EXECUTE"
        reason = "normal"

        if self.neural_fn:
            try:
                neural = float(self.neural_fn(features))
            except Exception:
                neural = 0.0

        if self.llm_enabled and self._should_trigger_llm(gaussian_score, neural):
            try:
                llm = float(llm_score_safe(features))
            except Exception:
                llm = 1.0

        final_score = 0.6 * gaussian_score + 0.3 * neural + 0.1 * llm

        if llm < 0.2:
            decision = "BLOCK"
            reason = "LLM_low_confidence"
            override = True
        elif neural > 0.8 and gaussian_score < self.threshold:
            decision = "EXECUTE"
            reason = "neural_override_rescue"
            override = True
        elif neural < 0.3 and gaussian_score < self.threshold:
            decision = "BLOCK"
            reason = "weak_confluence"
            override = True
        elif final_score < self.threshold:
            decision = "BLOCK"
            reason = "final_score_below_threshold"
        elif final_score < self.threshold + 0.05:
            decision = "WARN"
            reason = "borderline_trade"

        result = {
            "final_score": round(final_score, 4),
            "gaussian": round(gaussian_score, 4),
            "neural": round(neural, 4),
            "llm": round(llm, 4),
            "decision": decision,
            "reason": reason,
            "override": override,
        }
        self._maybe_report(result, sub_scores)
        return result

    def _maybe_report(self, result: Dict, sub_scores: Optional[Dict]) -> None:
        if self._reporter is None:
            return
        try:
            self._reporter.trade_decision(result, sub_scores or {})
        except Exception as e:
            log.debug(f"ScoringEngine._maybe_report: reporter error (non-fatal): {e}")
