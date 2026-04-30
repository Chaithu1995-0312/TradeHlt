"""
zone_gate_engine.py – BitNet Zone Gate with strict schema validation but fail‑open on registry errors.

Added instrumentation (2026-04-09):
  - execution_mode: "normal" | "force_pass"
      force_pass always returns passed=True but records the real decision.
  - zone_debug_config: optional dict with per-bar debug metadata logged as JSON.
  - Module-level counters: total_pass / total_block / block_reason_dist.
  - get_zone_gate_counters() — read-only access to session counters.
  - _compute_soft_zone_score() — soft scoring helper for zone_mode="soft".
"""

from __future__ import annotations

import json
import logging
import math
from typing import Callable, List, Optional

from features.feature_schema import CANONICAL_FEATURE_ORDER, CANONICAL_FEATURE_DIM
from utils.zone_schema_migrator import validate_zone_schema, ZoneSchemaError

logger = logging.getLogger(__name__)
_debug_logger = logging.getLogger("ZONE_GATE_DEBUG")

CANONICAL_KEYS: List[str] = list(CANONICAL_FEATURE_ORDER)

# ------------------------------------------------------------------
# Session-lifetime counters (module-level, reset on process restart)
# ------------------------------------------------------------------
_ZONE_COUNTERS: dict = {
    "total_pass":       0,
    "total_block":      0,
    "block_reason_dist": {},
}


def get_zone_gate_counters() -> dict:
    """Return a copy of the current session counters (read-only)."""
    return {
        "total_pass":        _ZONE_COUNTERS["total_pass"],
        "total_block":       _ZONE_COUNTERS["total_block"],
        "block_reason_dist": dict(_ZONE_COUNTERS["block_reason_dist"]),
    }


def reset_zone_gate_counters() -> None:
    """Reset counters (useful between backtests)."""
    _ZONE_COUNTERS["total_pass"]       = 0
    _ZONE_COUNTERS["total_block"]      = 0
    _ZONE_COUNTERS["block_reason_dist"] = {}


# ------------------------------------------------------------------
# Helper: structured JSON debug log per bar
# ------------------------------------------------------------------

def _log_zone_debug(
    raw_features: dict,
    zone_debug_config: dict,
    score: float,
    passed: bool,
    threshold: float,
    execution_mode: str,
) -> None:
    """Log a structured JSON debug record at DEBUG level."""
    record = {
        "price":              float(raw_features.get("close", raw_features.get("price", 0.0))),
        "zones_loaded":       int(zone_debug_config.get("zones_loaded_count", 0)),
        "distance_to_nearest":zone_debug_config.get("distance_to_nearest"),
        "inside_zone":        bool(zone_debug_config.get("inside_zone", False)),
        "zone_strength":      float(zone_debug_config.get("zone_strength", 0.0)),
        "zone_freshness":     float(zone_debug_config.get("zone_freshness", 0.0)),
        "score":              round(score, 4),
        "threshold":          round(threshold, 4),
        "passed":             passed,
        "execution_mode":     execution_mode,
    }
    _debug_logger.debug(json.dumps(record))


# ------------------------------------------------------------------
# Soft zone score helper (called from EngineRunner when zone_mode="soft")
# ------------------------------------------------------------------

def _compute_soft_zone_score(
    raw_features: dict,
    w1: float = 0.5,
    w2: float = 0.3,
    w3: float = 0.2,
) -> float:
    """
    Soft zone score: Z = w1*exp(-distance) + w2*freshness + w3*strength
    Returns float clamped to [0, 1].
    """
    distance  = float(raw_features.get("zone_distance",  1.0))
    freshness = float(raw_features.get("zone_freshness", 0.5))
    strength  = float(raw_features.get("zone_strength",  0.5))
    Z = w1 * math.exp(-max(distance, 0.0)) + w2 * freshness + w3 * strength
    return max(0.0, min(1.0, Z))


def compute_weighted_cluster_score(similarity_scores: List[float]) -> float:
    """
    Nearest-neighbour interpolation for zone gate: weighted cluster score using top 3 nearest zones.
    
    Logic:
    - If less than 2 valid neighbours → fallback to max score
    - If spread between max and min > 0.15 → reject cluster (return 0.0)
    - Otherwise compute weighted score: sum( (s_i / total) * s_i )
    - Output is always clamped to [0.0, 1.0]
    
    Args:
        similarity_scores: List of similarity scores from nearest neighbours (0.0 - 1.0)
        
    Returns:
        float: Final cluster score, 0.0 = rejected
    """
    EPS = 1e-12
    
    # Filter valid scores
    valid = [max(0.0, min(1.0, float(s))) for s in similarity_scores if math.isfinite(s)]
    
    # Empty input
    if not valid:
        return 0.0
    
    # Fallback path: < 2 neighbours
    if len(valid) < 2:
        return max(valid)
    
    # Spread filter: reject unstable clusters
    min_s = min(valid)
    max_s = max(valid)
    if (max_s - min_s) > 0.15:
        return 0.0
    
    # Weighted calculation
    total = sum(valid)
    if total < EPS:
        return 0.0
    
    weighted_score = sum( (s / total) * s for s in valid )
    
    # Clamp output
    return max(0.0, min(1.0, weighted_score))


# ------------------------------------------------------------------
# Core helpers (unchanged)
# ------------------------------------------------------------------

def filter_canonical_inputs(raw: dict) -> dict:
    missing = [k for k in CANONICAL_KEYS if k not in raw]
    if missing:
        raise ValueError(f"Missing canonical keys: {missing}")
    return {k: raw[k] for k in CANONICAL_KEYS}


def _extract_vector(features: dict) -> list:
    try:
        vector = [float(features[k]) for k in CANONICAL_KEYS]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Feature value coercion failed: {exc}") from exc
    assert len(vector) == CANONICAL_FEATURE_DIM, (
        f"Vector length mismatch: expected {CANONICAL_FEATURE_DIM}, got {len(vector)}"
    )
    return vector


# ------------------------------------------------------------------
# Main gate function
# ------------------------------------------------------------------

def run_zone_gate_engine(
    raw_features: dict,
    model_fn: Callable,
    threshold: float = 0.5,
    zone_registry: dict | None = None,
    execution_mode: str = "normal",
    zone_debug_config: Optional[dict] = None,
) -> dict:
    """
    Parameters
    ----------
    raw_features      : canonical feature dict
    model_fn          : callable (vector → float score)
    threshold         : pass threshold (default 0.5)
    zone_registry     : optional registry for schema validation
    execution_mode    : "normal" | "force_pass"
                        force_pass always returns passed=True but still
                        computes and logs the real decision.
    zone_debug_config : optional dict with per-bar debug metadata:
                        {zones_loaded_count, distance_to_nearest,
                         inside_zone, zone_strength, zone_freshness}
                        Pass None to disable all debug logging.

    Returns
    -------
    dict with keys: score, passed, vector, valid
    Additional keys when force_pass active: force_pass_override, real_passed
    """
    # Step 1: Canonical input validation – fail closed
    try:
        features = filter_canonical_inputs(raw_features)
    except (ValueError, TypeError, AssertionError) as e:
        logger.error("ZoneGate: canonical input error – %s. Blocking.", e)
        _ZONE_COUNTERS["total_block"] += 1
        reason = "canonical_error"
        _ZONE_COUNTERS["block_reason_dist"][reason] = (
            _ZONE_COUNTERS["block_reason_dist"].get(reason, 0) + 1
        )
        return {"score": 0.0, "passed": False, "vector": [], "valid": False}

    # Step 2: Registry validation – fail‑open (neutral) on any error
    if zone_registry is not None:
        try:
            validate_zone_schema(zone_registry)
        except (ZoneSchemaError, FileNotFoundError, TypeError, ValueError) as e:
            logger.warning("ZoneGate: zone registry error – %s. Returning neutral 0.5, passed=True.", e)
            _ZONE_COUNTERS["total_pass"] += 1
            return {
                "score": 0.5,
                "passed": True,
                "vector": [],
                "valid": True,
            }

    # Step 3: Extract vector and score – fail closed on extraction errors
    try:
        vector = _extract_vector(features)
        score  = float(model_fn(vector))
        passed = score >= threshold
    except (ValueError, TypeError, AssertionError) as e:
        logger.error("ZoneGate: vector extraction or scoring error – %s. Blocking.", e)
        _ZONE_COUNTERS["total_block"] += 1
        reason = "scoring_error"
        _ZONE_COUNTERS["block_reason_dist"][reason] = (
            _ZONE_COUNTERS["block_reason_dist"].get(reason, 0) + 1
        )
        return {"score": 0.0, "passed": False, "vector": [], "valid": False}

    # --- Debug logging (no-op if zone_debug_config is None) ---
    if zone_debug_config is not None:
        _log_zone_debug(raw_features, zone_debug_config, score, passed, threshold, execution_mode)

    # --- Execution mode: force_pass ---
    if execution_mode == "force_pass":
        _ZONE_COUNTERS["total_pass"] += 1
        return {
            "score":               score,
            "passed":              True,
            "vector":              vector,
            "valid":               True,
            "force_pass_override": True,
            "real_passed":         passed,
        }

    # --- Normal mode: update counters and return real result ---
    if passed:
        _ZONE_COUNTERS["total_pass"] += 1
    else:
        _ZONE_COUNTERS["total_block"] += 1
        reason = zone_debug_config.get("block_reason", "score_below_threshold") \
            if zone_debug_config else "score_below_threshold"
        _ZONE_COUNTERS["block_reason_dist"][reason] = (
            _ZONE_COUNTERS["block_reason_dist"].get(reason, 0) + 1
        )

    return {
        "score":  score,
        "passed": passed,
        "vector": vector,
        "valid":  passed,
    }