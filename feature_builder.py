"""
feature_builder.py
═══════════════════════════════════════════════════════════════════════════════
Single source of truth for feature extraction from CRT cached_features.

WHY THIS EXISTS
───────────────
cached_features is stamped by crt_engine_v2 at RETEST_CONFIRMED with exactly:
  retest_depth, body_ratio, disp_str, retest_index, session, double_confirmed

All other field names suggested by generic ML templates (sweep_strength,
volatility_regime, range_position, etc.) do NOT exist in the real engine.
Using them produces silent zero-padding — the model learns garbage.

This module is the ONLY place that knows the canonical feature schema.
Everything else (FusionEngine, dataset_builder, trainer) imports from here.

FEATURE VECTOR  (length = 6, all floats)
─────────────────────────────────────────
  0  retest_depth      — retrace fraction of displacement move [0, 1]
  1  body_ratio        — displacement candle body / total range [0, 1]
  2  disp_str          — displacement body / ATR (normalised strength)
  3  double_confirmed  — 1.0 if double sweep confirmed, else 0.0
  4  session_encoded   — LONDON=1 NEWYORK=2 ASIA=3 else 0
  5  atr_vol           — ATR / price (passed separately at call site)

When atr_vol is not available (e.g. loading from log), pass 0.0.
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("FeatureBuilder")

# ─────────────────────────────────────────────────────────────────────────────
# SCHEMA
# ─────────────────────────────────────────────────────────────────────────────

FEATURE_NAMES: list[str] = [
    "retest_depth",
    "body_ratio",
    "disp_str",
    "double_confirmed",
    "session_encoded",
    "atr_vol",
]

N_FEATURES: int = len(FEATURE_NAMES)   # 6 — MUST match TradeNet input size

_SESSION_MAP: dict[str, float] = {
    "LONDON":  1.0,
    "NEWYORK": 2.0,
    "ASIA":    3.0,
}


# ─────────────────────────────────────────────────────────────────────────────
# CORE EXTRACTOR
# ─────────────────────────────────────────────────────────────────────────────

def build_feature_vector(
    cached_features: Optional[dict],
    atr: float  = 0.0,
    price: float = 1.0,   # avoid div-zero
) -> list[float]:
    """
    Convert cached_features dict (as stamped by crt_engine_v2) into a
    fixed-length float vector ready for model inference.

    Parameters
    ----------
    cached_features : dict stamped at RETEST_CONFIRMED, or None / {}
    atr             : current ATR value at trade-open time
    price           : current close price (used to normalise ATR → vol)

    Returns
    -------
    list[float] of length N_FEATURES (6).
    Falls back to all-zeros on any error — never raises.
    """
    try:
        if not cached_features:
            return [0.0] * N_FEATURES

        session_raw = cached_features.get("session", "UNKNOWN")
        session_enc = _SESSION_MAP.get(session_raw, 0.0)

        double = 1.0 if cached_features.get("double_confirmed", False) else 0.0

        atr_vol = (atr / price) if price > 0 and atr > 0 else 0.0

        vec = [
            float(_clamp(cached_features.get("retest_depth", 0.0))),
            float(_clamp(cached_features.get("body_ratio",   0.0))),
            float(max(0.0, cached_features.get("disp_str",   0.0))),   # unbounded above
            double,
            session_enc,
            float(atr_vol),
        ]

        if len(vec) != N_FEATURES:
            log.error(f"Feature vector length mismatch: {len(vec)} != {N_FEATURES}")
            return [0.0] * N_FEATURES

        return vec

    except Exception as e:
        log.warning(f"build_feature_vector failed: {e}. Returning zeros.")
        return [0.0] * N_FEATURES


def feature_dict_to_vector(feature_dict: dict) -> list[float]:
    """
    Reconstruct feature vector from a stored log dict
    (where atr_vol was serialised directly as a field).
    Used by dataset_builder when loading from JSONL logs.
    """
    try:
        return [
            float(feature_dict.get(name, 0.0))
            for name in FEATURE_NAMES
        ]
    except Exception as e:
        log.warning(f"feature_dict_to_vector failed: {e}. Returning zeros.")
        return [0.0] * N_FEATURES


def validate_vector(vec: list[float]) -> tuple[bool, str]:
    """
    Returns (is_valid, reason).
    Used by dataset_validator to filter corrupt records before training.
    """
    if len(vec) != N_FEATURES:
        return False, f"wrong length {len(vec)}"
    if any(v is None for v in vec):
        return False, "contains None"
    if not all(isinstance(v, (int, float)) for v in vec):
        return False, "non-numeric value"
    if all(v == 0.0 for v in vec):
        return False, "all-zero vector (likely missing data)"
    return True, "ok"


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    try:
        return max(lo, min(hi, float(x)))
    except (TypeError, ValueError):
        return 0.0
