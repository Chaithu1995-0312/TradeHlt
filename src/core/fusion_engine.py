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


# ─────────────────────────────────────────────────────────────────────────────
# FIX 2 — SCORE NORMALIZER
# Rolling min-max normalisation expands the structurally compressed Gaussian
# output (~0.33–0.55) to the full [0, 1] range so static tier thresholds
# become meaningful. Handles constant input (hi==lo) by returning 0.5.
# ─────────────────────────────────────────────────────────────────────────────

class ScoreNormalizer:
    """Rolling min-max normaliser for fusion scores (window default = 1000)."""

    def __init__(self, window: int = 1000) -> None:
        self._window = window
        self._scores: list[float] = []

    def push_and_normalize(self, score: float) -> float:
        self._scores.append(score)
        if len(self._scores) > self._window:
            self._scores.pop(0)
        lo = min(self._scores)
        hi = max(self._scores)
        if hi == lo:
            return 0.5
        return max(0.0, min(1.0, (score - lo) / (hi - lo)))

    @property
    def n_samples(self) -> int:
        return len(self._scores)


# ─────────────────────────────────────────────────────────────────────────────
# FIX 3 — ENGINE HEALTH TRACKER
# Detects dead sub-engines (mean==0 AND variance==0 over a rolling window).
# A dead engine is excluded from the weighted fusion average so it cannot
# silently drag the final score toward zero.
# ─────────────────────────────────────────────────────────────────────────────

class EngineHealthTracker:
    """Detects dead (always-zero) sub-engines via rolling variance check."""

    def __init__(self, window: int = 1000) -> None:
        self._window = window
        self._values: list[float] = []

    def push(self, v: float) -> None:
        self._values.append(v)
        if len(self._values) > self._window:
            self._values.pop(0)

    def is_dead(self) -> bool:
        if len(self._values) < 2:
            return False
        mean = sum(self._values) / len(self._values)
        variance = sum((x - mean) ** 2 for x in self._values) / len(self._values)
        return mean == 0.0 and variance == 0.0

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


# Sentinel for compute(..., regime=...) — distinguishes "no regime argument
# passed" from "regime explicitly set to UNKNOWN". The former preserves the
# pre-patch scalar-weight behaviour; the latter actively selects the UNKNOWN
# regime profile from cfg.regime_fusion_weights.
_REGIME_NOT_PROVIDED: str = "__not_provided__"


# Normalises regime labels from any upstream source (detect_regime returns
# lowercase trend/range/neutral; RegimeClassifier returns uppercase
# TRENDING/RANGING/HIGH_VOLATILITY). Anything not listed falls back to
# "UNKNOWN" inside compute() and triggers a FUSION_UNKNOWN_REGIME event.
_REGIME_NORM = {
    "trend":           "TRENDING",
    "range":           "RANGING",
    "neutral":         "UNKNOWN",
    "high_volatility": "VOLATILE",
    "volatile":        "VOLATILE",
    "trending":        "TRENDING",
    "ranging":         "RANGING",
    "unknown":         "UNKNOWN",
}


# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FusionConfig:
    """
    Controls layer weights and LLM activation band.

    Defaults mirror configs/production/v1_multi_2026_03.json fusion_engine section.
    Override individual fields as needed for testing or experimental configs.
    """
    # Layer weights
    gaussian_weight: float = 0.6
    neural_weight:   float = 0.4
    llm_weight:      float = 0.2
    llm_lower_band:  float = 0.45
    llm_upper_band:  float = 0.65
    enable_llm:      bool  = True

    # Risk tiers — map final_score to risk multiplier
    tier_full:    float = 0.75  # score >= tier_full  → risk 1.0×
    tier_half:    float = 0.60  # score >= tier_half  → risk 0.5×
    tier_quarter: float = 0.50  # score >= tier_quarter → risk 0.25×

    # Per-engine weights used by compute() to aggregate multi-engine scores.
    weight_crt:                  float = 0.30
    weight_gaussian:             float = 0.25
    weight_zone_gate:            float = 0.25
    weight_rr:                   float = 0.20
    # 5th engine — StrategyOrchestrator consensus.  Default 0.0 means disabled;
    # set to e.g. 0.10 in production config to activate.
    weight_strategy_consensus:   float = 0.0

    # Regime-aware weight profiles. compute() looks these up by normalised
    # regime label ONLY when an explicit `regime=` argument is passed.
    # UNKNOWN mirrors the scalar weight_* defaults above so a degraded-regime
    # path matches the no-regime-arg path exactly.
    regime_fusion_weights: dict = field(default_factory=lambda: {
        "TRENDING": {"crt": 0.38, "gaussian": 0.20, "zone_gate": 0.12, "rr": 0.20, "strategy_consensus": 0.10},
        "RANGING":  {"crt": 0.18, "gaussian": 0.32, "zone_gate": 0.15, "rr": 0.25, "strategy_consensus": 0.10},
        "VOLATILE": {"crt": 0.28, "gaussian": 0.14, "zone_gate": 0.12, "rr": 0.16, "strategy_consensus": 0.30},
        "UNKNOWN":  {"crt": 0.30, "gaussian": 0.25, "zone_gate": 0.25, "rr": 0.20, "strategy_consensus": 0.00},
    })

    # Consensus gates for fuse_strategy_results()
    min_consensus_signals:   int   = 2     # completeness gate: minimum actionable strategies
    min_consensus_agreement: float = 0.60  # fraction of actionable that must agree

    # Conflict resolution policy — "conservative" or "majority"
    conflict_resolution_policy: str = "conservative"


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
    # FIX 5 — mandatory logging fields
    normalized_score: float = 0.0   # score after min-max normalisation
    threshold_used:   float = 0.0   # threshold value applied at decision time
    reject_stage:     str   = ""    # "passed" | "score_below_tier_*" | ""

    def to_dict(self) -> dict:
        return {
            "final_score":      round(self.final_score,      4),
            "gaussian":         round(self.gaussian,         4),
            "neural":           round(self.neural,    4) if self.neural is not None else None,
            "llm":              round(self.llm,       4) if self.llm    is not None else None,
            "llm_fired":        self.llm_fired,
            "action":           self.action,
            "risk_mult":        round(self.risk_mult,        4),
            # FIX 5
            "normalized_score": round(self.normalized_score, 4),
            "threshold_used":   round(self.threshold_used,   4),
            "reject_stage":     self.reject_stage,
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
                return _clamp(float(result.get("final", result.get("score", 0.5))))
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
        config:     Optional[FusionConfig] = None,
        convergence_controller=None,
    ) -> None:
        if config is None:
            config = FusionConfig()
        self.gaussian     = gaussian_adapter
        self.neural       = neural_fn
        self.llm_fn       = llm_fn
        self.cfg          = config
        self._convergence = convergence_controller
        if self.llm_fn is None:
            self.cfg.enable_llm = False
        # FIX 2 — rolling score normaliser
        self._normalizer      = ScoreNormalizer()
        # FIX 3 — per-engine dead-engine trackers
        self._health_neural   = EngineHealthTracker()
        self._health_zonegate = EngineHealthTracker()

    def compute(self, engine_results: dict, trade=None, weights=None, regime: str = _REGIME_NOT_PROVIDED) -> dict:
        """
        Aggregate multi-engine outputs only.
        Expects engine_results with keys: crt, gaussian, zone_gate, rr.

        Parameters
        ----------
        weights : optional dict with keys "crt", "gaussian", "zone"|"zone_gate",
                  "rr" (and optionally "strategy_consensus"). If provided,
                  overrides config and regime weights. Must sum to 1.0 ±0.01.
        regime  : optional regime label ("TRENDING" / "RANGING" / "VOLATILE" /
                  "UNKNOWN" — lowercase variants accepted via _REGIME_NORM).
                  When omitted, the static FusionConfig scalar weights are used
                  (backward-compatible path). When set, the matching profile
                  from `cfg.regime_fusion_weights` is selected.
        """
        expected = ("crt", "gaussian", "zone_gate", "rr")
        missing = [name for name in expected if name not in engine_results]
        if missing:
            return {
                "final_score": 0.0,
                "scores": {"crt": 0.0, "gaussian": 0.0, "zone_gate": 0.0, "rr": 0.0},
                "missing_engines": missing,
                "reason": "missing_engine_outputs",
            }

        # Regime-aware weight resolution.
        # Priority: explicit `weights=` override → explicit `regime=` lookup →
        # scalar config defaults (preserved for callers that pass neither).
        regime_weights = None
        if weights is None and regime is not _REGIME_NOT_PROVIDED:
            regime_weights_table = getattr(self.cfg, "regime_fusion_weights", {}) or {}
            regime_key = _REGIME_NORM.get(str(regime).lower().strip(), "UNKNOWN")
            regime_weights = regime_weights_table.get(regime_key)
            if regime_weights is not None:
                weights = regime_weights
                raw = str(regime).strip()
                if raw and raw.lower() not in _REGIME_NORM and regime_key == "UNKNOWN":
                    try:
                        from src.utils.integrity_events import emit_integrity_event
                        emit_integrity_event(
                            "FUSION_UNKNOWN_REGIME", "WARNING", "fusion_engine",
                            {"regime_received": raw, "fallback": "UNKNOWN"},
                        )
                    except Exception:
                        pass  # telemetry must never break fusion

        # Resolve weights
        if weights is None:
            w_crt = self.cfg.weight_crt
            w_gaussian = self.cfg.weight_gaussian
            w_zone = self.cfg.weight_zone_gate
            w_rr = self.cfg.weight_rr
            w_consensus_override = None
        else:
            # Accept either {crt, gaussian, zone, rr} (legacy override shape)
            # or {crt, gaussian, zone_gate, rr, strategy_consensus} (regime profile).
            zone_key = "zone_gate" if "zone_gate" in weights else "zone"
            required = ("crt", "gaussian", zone_key, "rr")
            if not all(k in weights for k in required):
                raise ValueError(f"Weights dict must contain keys: {required}")
            weight_sum = sum(float(v) for v in weights.values())
            if abs(weight_sum - 1.0) > 0.01:
                raise ValueError(f"Weights sum to {weight_sum:.3f}, must be 1.0 ±0.01")
            w_crt = weights["crt"]
            w_gaussian = weights["gaussian"]
            w_zone = weights[zone_key]
            w_rr = weights["rr"]
            w_consensus_override = weights.get("strategy_consensus")  # may be None

        def _extract_score(payload: dict, preferred_keys: tuple[str, ...]) -> float:
            if not isinstance(payload, dict):
                return 0.0
            for key in preferred_keys:
                if key in payload:
                    try:
                        return _clamp(float(payload[key]))
                    except Exception:
                        continue
            return 0.0

        score_crt = _extract_score(engine_results.get("crt", {}), ("score", "final_score", "final"))
        score_gaussian = _extract_score(
            engine_results.get("gaussian", {}),
            ("score", "final_score", "final"),
        )
        score_zonegate = _extract_score(engine_results.get("zone_gate", {}), ("score", "zone", "final_score"))
        score_rr = _extract_score(engine_results.get("rr", {}), ("score", "rr", "final_score"))
        # 5th engine — StrategyOrchestrator consensus score (optional, 0.0 if absent)
        score_consensus = _extract_score(
            engine_results.get("strategy_consensus", {}),
            ("score", "confidence", "final_score"),
        )

        # FIX 3 — track zone_gate health; exclude if always-zero (dead engine)
        self._health_zonegate.push(score_zonegate)
        zone_gate_dead = self._health_zonegate.is_dead()
        if zone_gate_dead:
            logger.warning("zone_gate engine dead (mean=0, var=0) — excluded from fusion weights.")

        # ── Conflict detection ────────────────────────────────────────────────
        # Extract non-zero direction signals (1=BUY, -1=SELL, 0=no opinion).
        # Only engines that express an opinion participate in conflict detection.
        def _dir(payload: dict) -> int:
            if not isinstance(payload, dict):
                return 0
            try:
                return int(payload.get("direction", 0))
            except (TypeError, ValueError):
                return 0

        active_directions = [
            _dir(engine_results.get(k, {}))
            for k in ("crt", "gaussian", "zone_gate", "rr")
        ]
        active_directions = [d for d in active_directions if d != 0]
        has_conflict = bool(active_directions) and (
            any(d > 0 for d in active_directions) and any(d < 0 for d in active_directions)
        )

        if has_conflict:
            policy = self.cfg.conflict_resolution_policy
            if policy == "conservative":
                logger.warning(
                    "FusionEngine: directional conflict detected "
                    "(policy=%s). Rejecting signal.", policy
                )
                return {
                    "final_score": 0.0,
                    "scores": {
                        "crt":       round(score_crt,      4),
                        "gaussian":  round(score_gaussian, 4),
                        "zone_gate": round(score_zonegate, 4),
                        "rr":        round(score_rr,       4),
                    },
                    "missing_engines": [],
                    "conflict_resolution_policy": policy,
                    "reason": "directional_conflict",
                }
            elif policy == "majority":
                majority_dir = 1 if sum(active_directions) > 0 else (-1 if sum(active_directions) < 0 else None)
                if majority_dir is None:
                    # exact tie → fall back to conservative
                    logger.warning(
                        "FusionEngine: directional tie in majority policy — "
                        "falling back to conservative reject."
                    )
                    return {
                        "final_score": 0.0,
                        "scores": {
                            "crt":       round(score_crt,      4),
                            "gaussian":  round(score_gaussian, 4),
                            "zone_gate": round(score_zonegate, 4),
                            "rr":        round(score_rr,       4),
                        },
                        "missing_engines": [],
                        "conflict_resolution_policy": policy,
                        "reason": "directional_conflict_tie",
                    }
                # majority wins — continue with scoring but log the conflict
                logger.info(
                    "FusionEngine: directional conflict resolved by majority "
                    "(majority_dir=%d, policy=%s).", majority_dir, policy
                )
            # unknown policy → conservative default
            else:
                logger.error(
                    "FusionEngine: unknown conflict_resolution_policy '%s'. "
                    "Defaulting to conservative reject.", policy
                )
                return {
                    "final_score": 0.0,
                    "scores": {
                        "crt":       round(score_crt,      4),
                        "gaussian":  round(score_gaussian, 4),
                        "zone_gate": round(score_zonegate, 4),
                        "rr":        round(score_rr,       4),
                    },
                    "missing_engines": [],
                    "conflict_resolution_policy": policy,
                    "reason": "directional_conflict",
                }

        # ── Weighted aggregation (always computed) ───────────────────────────
        # FIX 3: exclude zone_gate weight when it is detected as dead so a
        # permanently-zero engine cannot suppress all signals.
        # 5th engine (strategy_consensus) included only when its weight > 0.
        # Weights come from `weights=` override → regime profile → config defaults.
        w_zonegate  = 0.0 if zone_gate_dead else w_zone
        w_consensus = (
            w_consensus_override if w_consensus_override is not None
            else self.cfg.weight_strategy_consensus
        )
        total_w = (
            w_crt + w_gaussian + w_zonegate + w_rr + w_consensus
        ) or 1.0  # guard: all-zero weights → equal contribution
        weighted_fusion_score = _clamp(
            (
                w_crt       * score_crt +
                w_gaussian  * score_gaussian +
                w_zonegate  * score_zonegate +
                w_rr        * score_rr +
                w_consensus * score_consensus
            ) / total_w
        )

        # ── Convergence Layer (stability gate, injected via __init__) ────────
        # Option B — Layered: weighted score → convergence penalty + threshold.
        # When convergence_controller is None, weighted_fusion_score is the result.
        conv_debug: dict = {}
        if self._convergence is not None:
            raw_scores = {
                "crt":       score_crt,
                "gaussian":  score_gaussian,
                "zone_gate": score_zonegate,
                "rr":        score_rr,
            }
            conv = self._convergence.apply(
                raw_scores,
                debug=True,
                weighted_score=weighted_fusion_score,
            )
            final_score = _clamp(conv["final_score"])
            # Use calibrated scores for the returned scores dict
            cal = conv.get("scores", {})
            score_crt       = cal.get("crt",       score_crt)
            score_gaussian  = cal.get("gaussian",  score_gaussian)
            score_zonegate  = cal.get("zone_gate", score_zonegate)
            score_rr        = cal.get("rr",        score_rr)
            conv_debug = {
                "variance":  conv.get("variance"),
                "entropy":   conv.get("entropy"),
                "threshold": conv.get("threshold"),
                "accepted":  conv.get("accepted"),
            }
        else:
            final_score = weighted_fusion_score

        # FIX 2 — normalise compressed score to [0, 1] before returning
        normalized = self._normalizer.push_and_normalize(final_score)

        scores_dict: dict = {
            "crt":       round(score_crt,       4),
            "gaussian":  round(score_gaussian,  4),
            "zone_gate": round(score_zonegate,  4),
            "rr":        round(score_rr,        4),
        }
        if w_consensus > 0.0:
            scores_dict["strategy_consensus"] = round(score_consensus, 4)

        return {
            "final_score":      round(final_score, 4),
            "normalized_score": round(normalized,  4),   # FIX 5 — always present
            "scores":           scores_dict,
            "missing_engines": [],
            "zone_gate_dead":   zone_gate_dead,           # FIX 5 — signals dead engine state
            **conv_debug,
        }

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
        # Guard: adapter may be None when evaluate() is called in batch
        # compute()-only mode (engine_runner uses compute(), not evaluate()).
        if self.gaussian is None:
            logger.warning("FusionEngine.evaluate(): gaussian_adapter is None — using 0.5 neutral.")
            return FusionResult(
                final_score=0.5, gaussian=0.5, neural=None, llm=None,
                llm_fired=False, action="REJECT", risk_mult=0.0,
            )
        g_score = self.gaussian.score(features, candle_idx)

        # ── Layer 2: Neural (optional) ────────────────────────────────────────
        n_score: Optional[float] = None
        if self.neural is not None:
            try:
                n_score = _clamp(float(self.neural(features)))
            except Exception as e:
                logger.warning(f"Neural layer failed: {e}. Skipping.")

        # FIX 3 — exclude dead neural engine from fusion average
        if n_score is not None:
            self._health_neural.push(n_score)
            if self._health_neural.is_dead():
                logger.warning("Neural engine dead (mean=0, var=0) — excluded from fusion.")
                n_score = None

        # ── Base fusion: weighted blend of available layers ──────────────────
        if n_score is not None:
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

        # FIX 2 — normalise compressed score before risk decision
        normalized = self._normalizer.push_and_normalize(base)

        # ── Risk decision (operates on normalised score) ──────────────────────
        action, risk_mult = self._decide(normalized)

        # FIX 5 — populate reject_stage
        if action == "TRADE":
            reject_stage = "passed"
        elif normalized < self.cfg.tier_quarter:
            reject_stage = "score_below_tier_quarter"
        elif normalized < self.cfg.tier_half:
            reject_stage = "score_below_tier_half"
        else:
            reject_stage = "score_below_tier_full"

        return FusionResult(
            final_score      = base,
            gaussian         = g_score,
            neural           = n_score,
            llm              = l_score,
            llm_fired        = llm_fired,
            action           = action,
            risk_mult        = risk_mult,
            normalized_score = normalized,
            threshold_used   = self.cfg.tier_half,
            reject_stage     = reject_stage,
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

    # ── Multi-strategy fusion (Sprint 4 extension — non-breaking) ─────────────

    def fuse_strategy_results(
        self,
        results: list,
        weights: Optional[dict] = None,
        min_signals: int = 2,
        min_agreement: float = 0.60,
    ) -> dict:
        """
        Aggregate a list of StrategyResult objects into a scored fusion dict.

        Designed to be called with the output of StrategyOrchestrator.compute()
        (all_results list) to produce a score compatible with FusionEngine.compute()
        consumers.

        Parameters
        ----------
        results      : list[StrategyResult] — all strategy outputs for one candle
        weights      : {strategy_id: weight} — defaults to equal weighting
        min_signals  : completeness gate — minimum actionable strategies required
        min_agreement: consensus gate — fraction of actionable that must agree

        Returns
        -------
        dict with keys: final_score, signal, confidence, signal_count,
                        agree_count, agreement_ratio, action, strategy_scores
        """
        actionable = [r for r in results if r.signal in ("BUY", "SELL") and r.confidence > 0.0]
        n_total = len(results)
        n_signal = len(actionable)

        def _reject(reason: str) -> dict:
            return {
                "final_score": 0.0, "signal": "NO_TRADE",
                "confidence": 0.0, "signal_count": n_signal,
                "agree_count": 0, "agreement_ratio": 0.0,
                "action": "REJECT", "reason": reason,
                "strategy_scores": {},
            }

        if n_signal < min_signals:
            return _reject(f"completeness_gate:{n_signal}<{min_signals}")

        buy_r  = [r for r in actionable if r.signal == "BUY"]
        sell_r = [r for r in actionable if r.signal == "SELL"]
        consensus = "BUY" if len(buy_r) >= len(sell_r) else "SELL"
        agree_r = buy_r if consensus == "BUY" else sell_r
        n_agree = len(agree_r)
        agreement_ratio = n_agree / n_signal

        if agreement_ratio < min_agreement:
            return _reject(f"consensus_gate:{agreement_ratio:.0%}<{min_agreement:.0%}")

        # Weighted aggregation over agreeing results
        eq_w = 1.0 / n_agree
        total_w = 0.0
        w_score = 0.0
        w_conf = 0.0
        strategy_scores: dict = {}

        for r in agree_r:
            w = float(weights.get(r.strategy_id, eq_w)) if weights else eq_w
            w_score += r.score * w
            w_conf += r.confidence * w
            total_w += w
            strategy_scores[r.strategy_id] = round(r.score, 4)

        if total_w > 0:
            w_score /= total_w
            w_conf /= total_w

        final_score = _clamp(w_score)
        normalized = self._normalizer.push_and_normalize(final_score)
        action, risk_mult = self._decide(normalized)

        return {
            "final_score":      round(final_score, 4),
            "normalized_score": round(normalized,  4),
            "signal":           consensus,
            "confidence":       round(_clamp(w_conf), 4),
            "signal_count":     n_signal,
            "agree_count":      n_agree,
            "agreement_ratio":  round(agreement_ratio, 4),
            "action":           action,
            "risk_mult":        risk_mult,
            "strategy_scores":  strategy_scores,
        }
