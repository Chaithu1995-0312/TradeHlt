"""
zone_cluster_score.py — pure zone cluster scoring shared by EngineRunner and
HistoricalZoneMapper.

Semantics (hard path, identical to EngineRunner zone stage):
  BitNetZoneGate.check(vector) → top_scores
  → compute_weighted_cluster_score when len(top_scores) >= cluster_min_n
  → else best zone score
  → run_zone_gate_engine pass/fail vs zone_cluster_threshold

Soft zone_mode override stays in EngineRunner (outside this helper).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from engines.zone_gate_engine import (
    compute_weighted_cluster_score,
    run_zone_gate_engine,
)

logger = logging.getLogger(__name__)


def score_zone_cluster(
    raw_features: dict,
    zone_gate: Any,
    *,
    zone_cluster_threshold: float,
    cluster_min_n: int,
    cluster_spread_max: float,
    execution_mode: str = "normal",
    zone_debug_config: Optional[dict] = None,
) -> dict:
    """
    Score one feature dict against a loaded BitNetZoneGate.

    Returns a dict with at least:
      score / cluster_score  — float (same value as EngineRunner zone_raw.score)
      passed                 — bool
      vector                 — list[float]
      best_zone_id           — str | None
      best_zone_score        — float | None
      top_scores             — list[float]
      meta                   — full run_zone_gate_engine result
    """
    check_holder: dict = {}

    def _model_fn(vector: list) -> float:
        """Same body as former EngineRunner._zone_model_fn (mechanical extract)."""
        try:
            result = zone_gate.check(vector)
            check_holder["check"] = result
            top_scores = result.get("top_scores")
            if top_scores and len(top_scores) >= cluster_min_n:
                return compute_weighted_cluster_score(
                    top_scores, spread_max=cluster_spread_max
                )
            return float(result.get("score", 0.5))
        except Exception as exc:
            logger.debug("ZoneGate scoring fallback (0.5): %s", exc)
            return 0.5

    zone_raw = run_zone_gate_engine(
        raw_features=raw_features,
        model_fn=_model_fn,
        threshold=float(zone_cluster_threshold),
        execution_mode=str(execution_mode),
        zone_debug_config=zone_debug_config,
        # Schema-v4 safety net: score in the order the loaded registry was TRAINED on, not the
        # ambient canonical order. `None` on legacy registries with no `feature_order` field.
        feature_order=getattr(zone_gate, "feature_order", None),
    )

    check = check_holder.get("check") or {}
    score = float(zone_raw.get("score", 0.0))
    return {
        "score": score,
        "cluster_score": score,
        "passed": bool(zone_raw.get("passed", False)),
        "vector": list(zone_raw.get("vector") or []),
        "valid": zone_raw.get("valid"),
        "best_zone_id": check.get("zone_id"),
        "best_zone_score": (
            float(check["score"]) if check.get("score") is not None else None
        ),
        "top_scores": [float(s) for s in (check.get("top_scores") or [])],
        "meta": zone_raw,
    }
