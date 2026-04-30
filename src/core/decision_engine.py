"""
Central execution authority.

Only this module decides execute vs reject.

FIX 1 — Dynamic Threshold Calibration: threshold = percentile(scores, 85),
         clamped [0.45, 0.65]. Falls back to 0.55 until history is available.
FIX 3 — Dead Engine Neutralization: zone_gate_invalid check is bypassed when
         the zone_gate engine is detected as dead across the scoring window.
FIX 4 — Minimum Acceptance Fallback: decide_batch() promotes top-N signals
         when zero pass, guaranteeing ACCEPT > 0 per batch.
FIX 5 — Logging: threshold_used and reject_stage always present in output.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from typing import Any

log = logging.getLogger("DecisionEngine")

# ─────────────────────────────────────────────────────────────────────────────
# FIX 1 — DYNAMIC THRESHOLD
# ─────────────────────────────────────────────────────────────────────────────

_THRESHOLD_PERCENTILE = 85
_THRESHOLD_MIN        = 0.45
_THRESHOLD_MAX        = 0.65
_FALLBACK_TOP_N       = 3


class DynamicThreshold:
    """
    Percentile-based threshold: threshold = percentile(scores, 85),
    clamped to [0.45, 0.65]. Returns 0.55 (midpoint) until history exists.
    """

    def __init__(self, window: int = 1000) -> None:
        self._scores: deque[float] = deque(maxlen=window)

    def update(self, score: float) -> None:
        self._scores.append(score)

    def compute(self) -> float:
        if not self._scores:
            return (_THRESHOLD_MIN + _THRESHOLD_MAX) / 2.0
        sorted_scores = sorted(self._scores)
        n   = len(sorted_scores)
        idx = min(int(n * _THRESHOLD_PERCENTILE / 100), n - 1)
        raw = sorted_scores[idx]
        return max(_THRESHOLD_MIN, min(_THRESHOLD_MAX, raw))

    @property
    def n_samples(self) -> int:
        return len(self._scores)


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT CONTRACT (unchanged frozen dataclass)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DecisionResult:
    decision:        str
    reason:          str
    confidence:      float
    threshold_used:  float = 0.0   # FIX 5
    reject_stage:    str   = ""    # FIX 5

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision":       self.decision,
            "reason":         self.reason,
            "confidence":     round(float(self.confidence),     4),
            "threshold_used": round(float(self.threshold_used), 4),  # FIX 5
            "reject_stage":   self.reject_stage,                      # FIX 5
        }


def _require_decision_cfg(config: Any, key: str) -> float:
    """Strict config accessor — raises if key missing."""
    if isinstance(config, dict):
        if key not in config:
            raise KeyError(
                f"Required config key '{key}' missing from decision_engine config. "
                f"Add it to configs/production/v1_multi_2026_03.json."
            )
        return float(config[key])
    val = getattr(config, key, _MISSING := object())
    if val is _MISSING:
        raise KeyError(
            f"Required config attribute '{key}' missing from DecisionEngine config. "
            f"Add it to configs/production/v1_multi_2026_03.json."
        )
    return float(val)


# ─────────────────────────────────────────────────────────────────────────────
# DECISION ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class DecisionEngine:
    def __init__(self, config=None, threshold_window: int = 1000, fallback_n: int = _FALLBACK_TOP_N):
        if config is None:
            raise ValueError(
                "DecisionEngine requires a config dict. "
                "Pass the decision_engine section from v1_multi_2026_03.json."
            )
        self.config = config
        self.score_threshold          = _require_decision_cfg(config, "score_threshold")
        self.p_win_threshold          = _require_decision_cfg(config, "p_win_threshold")
        self.rr_threshold             = _require_decision_cfg(config, "rr_threshold")
        self.weak_link_weight         = _require_decision_cfg(config, "weak_link_weight")
        self.weak_component_threshold = _require_decision_cfg(config, "weak_component_threshold")
        # FIX 1 — dynamic threshold replaces static score_threshold for score check
        self._dynamic_threshold = DynamicThreshold(threshold_window)
        self._fallback_n        = fallback_n

    # ── Single-signal evaluation ──────────────────────────────────────────────

    def evaluate(
        self,
        score: float,
        p_win: float,
        zone_gate: dict,
        fusion: dict,
        config: Any,
    ) -> dict:
        weak_component_threshold = _require_decision_cfg(config, "weak_component_threshold")
        p_win_threshold          = _require_decision_cfg(config, "p_win_threshold")
        rr_threshold             = _require_decision_cfg(config, "rr_threshold")

        # Use the normalised score from fusion if present (FIX 2 output)
        effective_score = float(fusion.get("normalized_score", score))

        # FIX 1 — compute dynamic threshold; update AFTER decision so signal
        # is decided against historical distribution, not itself
        threshold = self._dynamic_threshold.compute()

        # FIX 3 — bypass zone_gate_invalid rejection when engine is dead
        zone_gate_dead = bool(fusion.get("zone_gate_dead", False))
        if not zone_gate_dead and not bool(zone_gate.get("valid", False)):
            result = self._reject("zone_gate_invalid", threshold)
            self._dynamic_threshold.update(effective_score)
            return result

        if effective_score < threshold:
            result = self._reject("low_score", threshold)
            self._dynamic_threshold.update(effective_score)
            return result

        if float(p_win) < float(p_win_threshold):
            result = self._reject("low_probability", threshold)
            self._dynamic_threshold.update(effective_score)
            return result

        if float(fusion.get("rr", 0.0)) < float(rr_threshold):
            result = self._reject("low_rr", threshold)
            self._dynamic_threshold.update(effective_score)
            return result

        if float(fusion.get("weak_component", 0.0)) > float(weak_component_threshold):
            result = self._reject("weak_setup", threshold)
            self._dynamic_threshold.update(effective_score)
            return result

        self._dynamic_threshold.update(effective_score)
        log.debug("execute | score=%.4f threshold=%.4f", effective_score, threshold)
        return DecisionResult(
            decision       = "execute",
            reason         = "all_conditions_met",
            confidence     = max(0.0, min(1.0, float(p_win))),
            threshold_used = threshold,
            reject_stage   = "passed",
        ).to_dict()

    # ── Batch decision (FIX 4 — minimum acceptance fallback) ─────────────────

    def decide_batch(self, signals: list[dict]) -> list[dict]:
        """
        Decide on a batch of pre-scored signals.
        Each signal dict must contain: score, p_win, zone_gate, fusion, config.
        FIX 4: if zero signals pass, promote top-N by score to ACCEPT.

        Returns list of evaluate() dicts with an added 'input_score' key.
        """
        if not signals:
            return []

        results = []
        for s in signals:
            r = self.evaluate(
                score     = s.get("score", 0.0),
                p_win     = s.get("p_win", 0.0),
                zone_gate = s.get("zone_gate", {}),
                fusion    = s.get("fusion", {}),
                config    = s.get("config", self.config),
            )
            r["input_score"] = s.get("score", 0.0)
            results.append(r)

        # FIX 4 — minimum acceptance fallback
        accepted = sum(1 for r in results if r["decision"] == "execute")
        if accepted == 0:
            top_n = sorted(range(len(results)), key=lambda i: results[i]["input_score"], reverse=True)
            for i in top_n[: self._fallback_n]:
                results[i]["decision"]     = "execute"
                results[i]["reason"]       = "fallback_top_n"
                results[i]["reject_stage"] = "fallback_top_n"
            log.warning(
                "FIX4 fallback: 0 signals accepted — promoted top-%d by score.",
                min(self._fallback_n, len(results)),
            )

        accepted_final = sum(1 for r in results if r["decision"] == "execute")
        log.info("decide_batch | n=%d accepted=%d", len(results), accepted_final)
        return results

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _reject(self, reason: str, threshold: float) -> dict:
        log.debug("reject | reason=%s threshold=%.4f", reason, threshold)
        return DecisionResult(
            decision       = "reject",
            reason         = reason,
            confidence     = 0.0,
            threshold_used = threshold,
            reject_stage   = reason,
        ).to_dict()

    @staticmethod
    def reject(reason: str) -> dict:
        """Legacy static helper — preserved for backward compatibility."""
        return DecisionResult(
            decision   = "reject",
            reason     = reason,
            confidence = 0.0,
        ).to_dict()

    @property
    def current_threshold(self) -> float:
        return self._dynamic_threshold.compute()
