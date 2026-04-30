"""
schema_validator.py
═══════════════════════════════════════════════════════════════════════════════
STRICT FAIL-FAST validator for the canonical feature contract.

Rules:
  - feature keys MUST exactly match the schema (no missing, no extra)
  - All values MUST be finite floats (no NaN, no None, no inf)
  - Vector length MUST match schema length

ANY violation raises immediately. NO silent fixes. NO fallbacks.
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import math
from typing import List


def validate_features(features: dict, schema: tuple) -> None:
    """
    Strict key-set validator — fail fast on ANY mismatch.

    Args:
        features: dict produced by build_features()
        schema:   CANONICAL_FEATURES tuple from features.feature_schema

    Raises:
        ValueError with structured error dict if ANY key mismatch is detected.
    """
    feature_keys = set(features.keys())
    schema_keys = set(schema)

    if feature_keys != schema_keys:
        missing = [f for f in schema if f not in feature_keys]
        extra = [f for f in feature_keys if f not in schema_keys]

        raise ValueError({
            "error": "FEATURE_SCHEMA_VIOLATION",
            "missing": missing,
            "extra": extra,
        })


def validate_feature_values(features: dict) -> None:
    """
    Validate all feature values are finite floats (no NaN, no None, no inf).

    Args:
        features: canonical feature dict (already key-validated)

    Raises:
        ValueError if any value is None, NaN, or infinite.
    """
    for k, v in features.items():
        if v is None:
            raise ValueError(f"Feature '{k}' is None — invalid feature value")
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            raise ValueError(f"Feature '{k}' = {v} — NaN/inf is not allowed in feature vector")


def validate_vector(vector: list, schema: tuple) -> None:
    """
    Validate a feature vector has the correct length.

    Args:
        vector: ordered list of feature values (from build_feature_vector)
        schema: CANONICAL_FEATURES tuple from features.feature_schema

    Raises:
        AssertionError if length does not match.
        TypeError if vector is not a list.
    """
    if not isinstance(vector, list):
        raise TypeError(f"Feature vector must be list, got {type(vector).__name__}")

    expected_len = len(schema)
    if len(vector) != expected_len:
        raise AssertionError(
            f"Feature vector length mismatch: expected {expected_len}, got {len(vector)}"
        )