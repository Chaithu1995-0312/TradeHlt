"""
Central execution authority.

Only this module decides execute vs reject.

OWNERSHIP BOUNDARY (F-048 resolved 2026-07-24)
----------------------------------------------
DecisionEngine answers ONE question: "is this a valid market opportunity?" — a SEMANTIC judgment
over market evidence (fused score, p_win, zone validity, weak-component). It does NOT know about,
and MUST NOT gate on, economics: fees / taxes / slippage / brokerage / portfolio / capital, or
reward:risk. Economic reward:risk is owned solely by ``UltronRiskGate`` (Check 2, cost-taxed
``min_rr_ratio``, after ``ExecutionPlanner`` derives SL/TP); concrete SL/TP + sizing by
``ExecutionPlanner``. The prior RR gate here consumed RREngine candle polarity (∈[0.5,1]) against
a reward:risk threshold — a producer/consumer contract mismatch (F-048) that has been REMOVED, not
shimmed. There is no RR term in ``evaluate`` anymore.

FIX 1 — Dynamic Threshold Calibration: threshold = percentile(scores, 85),
         clamped [0.45, 0.65]. Falls back to 0.55 until history is available.
FIX 3 — Dead Engine Neutralization: zone_gate_invalid check is bypassed when
         the zone_gate engine is detected as dead across the scoring window.
FIX 4 — Minimum Acceptance Fallback: decide_batch() promotes top-N signals
         when zero pass, guaranteeing ACCEPT > 0 per batch.
FIX 5 — Logging: threshold_used and reject_stage always present in output.

DynamicThreshold has been extracted to core/dynamic_threshold.py.
It is re-exported here for backward compatibility.
New code should import it from core.dynamic_threshold directly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from core.dynamic_threshold import DynamicThreshold  # noqa: F401 — re-export for backward compat

log = logging.getLogger("DecisionEngine")

# ─────────────────────────────────────────────────────────────────────────────
# FIX 1 — DYNAMIC THRESHOLD (implementation lives in core/dynamic_threshold.py)
# ─────────────────────────────────────────────────────────────────────────────

_FALLBACK_TOP_N = 3  # default; overridden by decision_engine.fallback_top_n in production config


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
    def __init__(self, config=None, threshold_window: int = 1000, fallback_n: int | None = None):
        if config is None:
            raise ValueError(
                "DecisionEngine requires a config dict. "
                "Pass the decision_engine section from v1_multi_2026_03.json."
            )
        self.config = config
        self.score_threshold          = _require_decision_cfg(config, "score_threshold")
        self.p_win_threshold          = _require_decision_cfg(config, "p_win_threshold")
        # rr_threshold intentionally NOT read (F-048 resolved): DecisionEngine owns no economic
        # RR gate. The config key is retained-but-RETIRED; economic RR = ultron_risk_gate.min_rr_ratio.
        self.weak_link_weight         = _require_decision_cfg(config, "weak_link_weight")
        self.weak_component_threshold = _require_decision_cfg(config, "weak_component_threshold")
        # FIX 1 — dynamic threshold replaces static score_threshold for score check.
        # BEHAVIORAL knobs read fail-fast from config (no silent defaults): the percentile
        # + clamp bounds were previously hardcoded module constants in dynamic_threshold.py.
        self._dynamic_threshold = DynamicThreshold(
            threshold_window,
            percentile=int(_require_decision_cfg(config, "threshold_percentile")),
            t_min=_require_decision_cfg(config, "threshold_min"),
            t_max=_require_decision_cfg(config, "threshold_max"),
        )
        # FIX 4 — fallback_top_n: prefer config key, then explicit arg, then module default
        _cfg_fallback_n = int(config.get("fallback_top_n", _FALLBACK_TOP_N)) if isinstance(config, dict) else _FALLBACK_TOP_N
        self._fallback_n = fallback_n if fallback_n is not None else _cfg_fallback_n

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

        # NO economic RR gate here (F-048 resolved 2026-07-24). Reward:risk — polarity (contract
        # A, fused elsewhere) and true SL/TP RR (contract D) — is NOT a DecisionEngine concern.
        # Economic RR is enforced downstream by UltronRiskGate.evaluate (cost-taxed min_rr_ratio),
        # after ExecutionPlanner has built SL/TP. DecisionEngine stays purely semantic.

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
