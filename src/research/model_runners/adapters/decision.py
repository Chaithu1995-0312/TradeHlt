"""Stage-4 approval adapter (A4) — fusion evidence -> DecisionEngine.evaluate.

Closes the largest observability hole in the harness: ``fusion_compute``
deliberately stops BEFORE Stage 4, so the actual approve/reject decision — the
thing the whole spine exists to produce — had no offline surface.

Call shape is copied from the live spine (``core/engine_runner.py:1011-1050``):

    p_win        = gaussian engine score            <- MIAR-flagged drift, see below
    zone_gate    = {valid: zone.passed, score: zone.score}
    fusion       = {candle_polarity, weak_component: 1 - fusion.final_score}
    score        = fusion final_score

TWO DECLARED DIVERGENCES from the live call (both recorded in artifact_info,
neither silent):

1. ``adaptive_thresholds`` — live merges ``AcceptanceController.get_thresholds()``
   over the config before calling evaluate(). That controller is stateful and
   path-dependent; replaying it offline would make a per-bar observation depend
   on run order. This adapter passes the STATIC ``decision_engine`` section, so
   results are the static-threshold decision. Flagged
   ``adaptive_thresholds_applied: false``.
2. ``regime`` / ``selected_engine`` routing metadata is attached by the spine
   AFTER evaluate() and does not change the decision, so it is not reproduced.

MIAR NOTE (observable drift): MIAR §3.4/§3.14 record that feeding the Gaussian
conformity **score** in as ``p_win`` is a forbidden reinterpretation (a score is
not a calibrated probability). This adapter reproduces the live behaviour
faithfully — including that drift — and emits ``p_win_source`` so the drift is
measurable rather than merely asserted.

Authority: research only. PRODUCTION_BEHAVIOR_CHANGED=false.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from core.decision_engine import DecisionEngine
from research.model_runners.adapters.fusion_compute import FusionComputeAdapter
from research.model_runners.contracts import ModelContract, get_contract
from research.model_runners.require_config import require_key, require_section
from research.model_runners.substrate import BarContext

# Keys DecisionEngine.evaluate() + __init__ require from the section passed as `config`.
_REQUIRED_DECISION_KEYS = (
    "score_threshold",
    "p_win_threshold",
    "weak_link_weight",
    "weak_component_threshold",
)


class DecisionAdapter:
    def __init__(
        self,
        *,
        contract: ModelContract,
        prod_config: dict[str, Any],
        instrument: str,
        repo_root: Path,
    ):
        self.contract = contract
        de = require_section(prod_config, "decision_engine")
        for key in _REQUIRED_DECISION_KEYS:
            require_key(de, key, path="decision_engine")
        self._decision_cfg = dict(de)
        self._engine = DecisionEngine(config=self._decision_cfg)

        # Upstream evidence: the same four live engines fusion_compute composes.
        self._fusion = FusionComputeAdapter(
            contract=get_contract("fusion_compute"),
            prod_config=prod_config,
            instrument=instrument,
            repo_root=repo_root,
        )

        sections = sorted(set(self._fusion.config_sections_read) | {"decision_engine"})
        keys = list(self._fusion.config_keys_read) + [
            f"decision_engine.{k}" for k in _REQUIRED_DECISION_KEYS
        ]
        self.config_sections_read = sections
        self.config_keys_read = keys
        self.artifact_info = {
            "path": None,
            "serve": "core.decision_engine.DecisionEngine.evaluate",
            "composes": "fusion_compute -> DecisionEngine.evaluate",
            "adaptive_thresholds_applied": False,
            "adaptive_thresholds_note": (
                "live merges AcceptanceController.get_thresholds() over config; "
                "omitted offline because that controller is stateful/path-dependent"
            ),
            "p_win_source": "engine_results.gaussian.score",
            "p_win_note": (
                "MIAR-flagged drift: a Gaussian conformity SCORE is fed where a "
                "calibrated PROBABILITY is expected. Reproduced faithfully so the "
                "drift is measurable."
            ),
            "rr_threshold_read": False,
            "rr_threshold_note": "F-048: economic RR owned by ultron_risk_gate.min_rr_ratio",
            "decision_thresholds": {
                k: self._decision_cfg[k] for k in _REQUIRED_DECISION_KEYS
            },
            "fusion_artifact": self._fusion.artifact_info,
        }

    def score_bar(self, bar: BarContext) -> dict[str, Any]:
        fused = self._fusion.score_bar(bar)
        components = fused.get("component_native")
        if not isinstance(components, dict):
            raise RuntimeError(
                "fusion_compute did not return component_native; cannot build "
                "DecisionEngine inputs without inventing them"
            )

        gaussian = components.get("gaussian")
        if not isinstance(gaussian, dict) or "score" not in gaussian:
            raise RuntimeError("gaussian component missing 'score' for p_win")
        p_win = float(gaussian["score"])

        zone = components.get("zone_gate")
        if not isinstance(zone, dict) or "score" not in zone or "passed" not in zone:
            raise RuntimeError(
                "zone_gate component missing 'score'/'passed' for zone_gate context"
            )
        zone_ctx = {"valid": bool(zone["passed"]), "score": float(zone["score"])}

        if "final_score" not in fused:
            raise RuntimeError("fusion result missing 'final_score'")
        final_score = float(fused["final_score"])

        rr = components.get("rr")
        if not isinstance(rr, dict) or "score" not in rr:
            raise RuntimeError("rr component missing 'score' for candle_polarity")
        fusion_ctx = {
            "candle_polarity": float(rr["score"]),  # audit only, not read by evaluate
            "weak_component": max(0.0, 1.0 - final_score),
        }

        result = self._engine.evaluate(
            score=final_score,
            p_win=p_win,
            zone_gate=zone_ctx,
            fusion=fusion_ctx,
            config=self._decision_cfg,
        )
        if not isinstance(result, dict):
            raise TypeError(
                f"DecisionEngine.evaluate must return dict, got {type(result).__name__}"
            )

        out = dict(result)
        # Inputs echoed so a decision is reproducible from its own record.
        out["input_final_score"] = final_score
        out["input_p_win"] = p_win
        out["input_zone_valid"] = zone_ctx["valid"]
        out["input_zone_score"] = zone_ctx["score"]
        out["input_weak_component"] = fusion_ctx["weak_component"]
        out["p_win_source"] = "gaussian.score"
        out["semantic"] = "stage4_approval_decision"
        return out
