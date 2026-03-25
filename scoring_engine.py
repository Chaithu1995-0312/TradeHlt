# scoring_engine.py

import logging
import math
from typing import Optional, Dict
from llama_gate import llm_score_safe

log = logging.getLogger("ScoringEngine")

# ─────────────────────────────────────────────────────────────────────────────
# FEATURE SCHEMA (frozen — version-linked to every saved model)
# SINGLE SOURCE OF TRUTH: imported from dataset_builder.
# Never define feature order anywhere else — use this alias everywhere.
# ─────────────────────────────────────────────────────────────────────────────

from dataset_builder import (
    GAUSSIAN_FEATURE_SCHEMA as FEATURE_SCHEMA,
    SESSION_ENCODE,
    REGIME_ENCODE,
    build_feature_vector as build_feature_vector_from_trade,  # alias — same function, no duplication
    validate_feature_vector,
)

# Runtime assertion: ensures dataset_builder and scoring_engine stay in sync.
# Fires at import time — catches schema drift immediately.
_EXPECTED_N_FEATURES = 11
assert len(FEATURE_SCHEMA) == _EXPECTED_N_FEATURES, (
    f"FEATURE_SCHEMA length mismatch: {len(FEATURE_SCHEMA)} != {_EXPECTED_N_FEATURES}. "
    "Update dataset_builder.GAUSSIAN_FEATURE_SCHEMA."
)


# ─────────────────────────────────────────────────────────────────────────────
# FORMALIZED CRT SCORING FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def compute_scores(
    body_ratio: float,
    move: float,
    atr: float,
    retest_depth: float,
    candles_since_retest: int,
    sweep_detected: bool,
    double_sweep: bool,
    lambda_decay: float = 0.05,
) -> dict:
    """
    Canonical CRT scoring function — explicit, deterministic, testable.

    All sub-scores bounded [0, 1].
    Single decay application (fixes double-decay bug from legacy engine).

    Parameters
    ----------
    body_ratio           : displacement candle body / wick (0–1)
    move                 : displacement price move (price units)
    atr                  : current ATR (> 0)
    retest_depth         : retest retrace fraction (0–1)
    candles_since_retest : candles elapsed since retest confirmed
    sweep_detected       : True if ANY sweep was detected
    double_sweep         : True if double sweep confirmed
    lambda_decay         : time decay rate per candle (default 0.05)

    Returns
    -------
    dict: {sweep, breakout, retest, time, final}
    """
    disp_strength = move / atr if atr > 0 else 0.0

    # ── S_sweep: three-state — 0.0 / 0.7 / 1.0 ───────────────────────────
    if not sweep_detected:
        S_sweep = 0.0
    elif double_sweep:
        S_sweep = 1.0
    else:
        S_sweep = 0.7

    # ── S_breakout: body quality + displacement magnitude ────────────────
    S_breakout = (
        0.5 * min(body_ratio, 1.0) +
        0.5 * min(disp_strength / 2.0, 1.0)
    )

    # ── S_retest: Gaussian bell — optimal at depth=0.5, σ=0.2 ────────────
    S_retest = math.exp(-((retest_depth - 0.5) ** 2) / 0.04)

    # ── S_time: exponential decay since retest ────────────────────────────
    S_time = math.exp(-lambda_decay * max(0, candles_since_retest))

    # ── S_final: weighted sum — decay applied ONCE inside S_time ─────────
    S_final = (
        0.35 * S_sweep +
        0.25 * S_breakout +
        0.20 * S_retest +
        0.20 * S_time
    )

    return {
        "sweep":    round(S_sweep,    4),
        "breakout": round(S_breakout, 4),
        "retest":   round(S_retest,   4),
        "time":     round(S_time,     4),
        "final":    round(S_final,    4),
    }


def build_feature_vector_from_trade(trade_data: dict, lambda_decay: float = 0.05) -> list:
    """
    Build the 11-feature vector from a trade data dict.
    Used by Gaussian trainer and inference pipeline.

    No raw prices. No leakage features (dynamic_threshold / risk_multiplier excluded).

    Parameters
    ----------
    trade_data : dict with keys matching TradeRecord fields
    lambda_decay : decay rate for time_decay_feature

    Returns
    -------
    list[float] of length len(FEATURE_SCHEMA) = 11
    """
    retest_depth  = float(trade_data.get("retest_depth",      0.0))
    body_ratio    = float(trade_data.get("body_ratio_feat",    0.0))
    disp_strength = float(trade_data.get("disp_str_feat",      0.0))
    volatility    = float(trade_data.get("volatility",         0.0))
    range_size    = float(trade_data.get("range_size",         0.0))
    session       = str(trade_data.get("session",              "LONDON"))
    hour_of_day   = float(trade_data.get("hour_of_day",        0.0))
    candles_since = int(trade_data.get("candles_since_retest", 0))
    regime        = str(trade_data.get("regime",               "NEUTRAL"))

    session_encoded   = float(SESSION_ENCODE.get(session, 1))
    regime_encoded    = float(REGIME_ENCODE.get(regime,   1))
    time_decay_feat   = math.exp(-lambda_decay * max(0, candles_since))
    retest_disp       = retest_depth * disp_strength
    vol_disp          = volatility * disp_strength

    return [
        retest_depth,
        body_ratio,
        disp_strength,
        volatility,
        range_size,
        session_encoded,
        hour_of_day,
        time_decay_feat,
        regime_encoded,
        retest_disp,
        vol_disp,
    ]



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
        # Optional InsightReporter — if provided, trade decisions are narrated
        self._reporter = insight_reporter

    def _should_trigger_llm(self, gaussian: float, neural: float) -> bool:
        """
        Trigger LLM only when:
        - Score is near threshold (uncertain zone)
        - OR Gaussian vs Neural disagree significantly
        """
        near_threshold = abs(gaussian - self.threshold) <= self.llm_trigger_margin
        disagreement = abs(gaussian - neural) > 0.25

        return near_threshold or disagreement

    def attach_reporter(self, reporter) -> None:
        """Attach an InsightReporter for dynamic LLM narration of trade decisions."""
        self._reporter = reporter

    def score(self, features: dict, gaussian_score: float, sub_scores: Optional[Dict] = None) -> Dict:
        """
        Score a trade setup.

        Parameters
        ----------
        features      : feature dict for neural/LLM scoring
        gaussian_score: pre-computed Gaussian score (0-1)
        sub_scores    : optional dict with keys sweep/breakout/retest/time
                        (from compute_scores()) — used by InsightReporter narration

        Returns
        -------
        dict with final_score, gaussian, neural, llm, decision, reason, override
        """
        # ─────────────────────────────────────────────
        # MODE A — Deterministic
        # ─────────────────────────────────────────────
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

        # ─────────────────────────────────────────────
        # MODE B — Hybrid
        # ─────────────────────────────────────────────
        neural = 0.0
        llm = 0.0
        override = False
        decision = "EXECUTE"
        reason = "normal"

        # Neural inference
        if self.neural_fn:
            try:
                neural = float(self.neural_fn(features))
            except Exception:
                neural = 0.0

        # Conditional LLM trigger
        if self.llm_enabled and self._should_trigger_llm(gaussian_score, neural):
            try:
                llm = float(llm_score_safe(features))
            except Exception:
                llm = 1.0  # fail-open

        # ── Soft fusion
        final_score = (
            0.6 * gaussian_score +
            0.3 * neural +
            0.1 * llm
        )

        # ── Hard overrides
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
        """Fire-and-forget narration via InsightReporter (never blocks or raises)."""
        if self._reporter is None:
            return
        try:
            self._reporter.trade_decision(result, sub_scores or {})
        except Exception as e:
            log.debug(f"ScoringEngine._maybe_report: reporter error (non-fatal): {e}")
