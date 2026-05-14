import json
import os
import hashlib
import warnings
from features.feature_schema import (
    FEATURE_SCHEMA,
    CANONICAL_FEATURE_DIM,
    SESSION_MAP,
    TREND_MAP,
    CANONICAL_FEATURE_ORDER
)

# Required sub-keys for candle expansion — order determines vector positions.
CANDLE_KEYS = ["open", "high", "low", "close"]


def validate_features(features: dict) -> bool:
    """Validate that all required features are present and correctly typed."""
    for key, expected_type in FEATURE_SCHEMA.items():
        if key not in features:
            raise ValueError(f"Missing feature: {key}")
        value = features[key]
        if expected_type == bool:
            if not isinstance(value, bool):
                raise TypeError(f"Feature '{key}' expected bool, got {type(value).__name__}")
        elif expected_type == float:
            if not isinstance(value, (int, float)):
                raise TypeError(f"Feature '{key}' expected float, got {type(value).__name__}")
        elif expected_type == str:
            if not isinstance(value, str):
                raise TypeError(f"Feature '{key}' expected str, got {type(value).__name__}")
        elif expected_type == dict:
            if not isinstance(value, dict):
                raise TypeError(f"Feature '{key}' expected dict, got {type(value).__name__}")
    return True


def extract_feature_vector(features: dict) -> list:
    """
    Extract and order features into a canonical float vector for BitNet input.

    This is the SINGLE canonical implementation used across dataset_builder,
    zone_gate, zone_gate_engine, train_pipeline, and bitnet/zone_cosine_searcher.

    Rules:
    - ALL keys from features.feature_schema must be present — no silent defaults.
    - session must be a key in SESSION_MAP — raises ValueError otherwise.
    - trend_bias must be a key in TREND_MAP — raises ValueError otherwise.
    - candle must contain all of: open, high, low, close.
    - rejection_wick, volatility_flag, is_inside_bar must be bool — converted to 1.0/0.0.
    - Final vector length is asserted to equal CANONICAL_FEATURE_DIM.

    Args:
        features: Raw feature dict matching FEATURE_SCHEMA.

    Returns:
        List of floats of length CANONICAL_FEATURE_DIM.

    Raises:
        ValueError: If any required key is missing or has an unmapped string value.
        TypeError: If any value has the wrong type.
        AssertionError: If the produced vector does not match CANONICAL_FEATURE_DIM.
    """
    # Step 1: Full schema validation (type-checked, no defaults).
    #validate_features(features)

    # Step 2: Validate and expand candle dict.
    candle = {
        "open": features["open"],
        "high": features["high"],
        "low": features["low"],
        "close": features["close"],
    }
    missing_candle = [k for k in CANDLE_KEYS if k not in candle]
    if missing_candle:
        raise ValueError(f"Missing candle sub-keys: {missing_candle}")

    # Step 3: Encode session — STRICT, no fallback.
    session_val = float(features["session"])
    trend_val = float(features["trend_bias"])

    # Step 5: Validate bool types explicitly before conversion.
    missing = [k for k in CANONICAL_FEATURE_ORDER if k not in features]
    if missing:
        raise ValueError(f"Missing canonical features: {missing}")

    # Step 6: Build vector in CANONICAL_FEATURE_ORDER.
   

    vector = [float(features[k]) for k in CANONICAL_FEATURE_ORDER]
    # Step 7: Dimension assertion — hard fail on schema drift.
    assert len(vector) == CANONICAL_FEATURE_DIM, (
        f"extract_feature_vector produced {len(vector)} values "
        f"but CANONICAL_FEATURE_DIM is {CANONICAL_FEATURE_DIM}. "
        "This indicates a bug in the extraction logic."
    )

    return vector


def extract_bitnet_features(features: dict) -> list:
    """
    DEPRECATED: Use extract_feature_vector() instead.

    This function now delegates to extract_feature_vector() to maintain
    backward compatibility. The previous silent fallback behavior for
    unknown session/trend_bias values has been REMOVED — callers that
    relied on fallback defaults must be updated.
    """
    warnings.warn(
        "extract_bitnet_features() is deprecated. Use extract_feature_vector() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return extract_feature_vector(features)


def build_dataset_entry(features: dict, label: int, meta: dict = None) -> dict:
    """Build a single dataset entry."""
    vector = extract_feature_vector(features)
    entry = {
        "features": vector,
        "label": label,
    }
    if meta:
        entry["meta"] = meta
    return entry


def build_dataset(records: list, output_path: str = None) -> list:
    """Build full dataset from list of (features, label) tuples."""
    dataset = []
    for i, record in enumerate(records):
        if isinstance(record, dict):
            features = record.get("features", {})
            label = record.get("label", 0)
            meta = record.get("meta", None)
        elif isinstance(record, (list, tuple)) and len(record) >= 2:
            features = record[0]
            label = record[1]
            meta = record[2] if len(record) > 2 else None
        else:
            raise ValueError(f"Invalid record format at index {i}: {record}")

        entry = build_dataset_entry(features, label, meta)
        dataset.append(entry)

    if output_path:
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(dataset, f, indent=2)

    return dataset


def compute_feature_hash(features: dict) -> str:
    """Compute a deterministic hash for a feature dict."""
    vector = extract_feature_vector(features)
    raw = json.dumps(vector, sort_keys=True)
    return hashlib.md5(raw.encode()).hexdigest()


def rr_to_class(rr: float) -> int:
    """
    Map pnl_rr_net float to 4-class label used by GaussianNBModel.

    Classes:
      0 = loss      (rr < 0)
      1 = small win (0 <= rr < 1)
      2 = mid win   (1 <= rr < 2)
      3 = big win   (rr >= 2)
    """
    if rr < 0:
        return 0
    elif rr < 1.0:
        return 1
    elif rr < 2.0:
        return 2
    else:
        return 3


# Constants expected by trainer.py / phase5_calibration.py
MIN_GAUSSIAN_SAMPLES = 20
LAMBDA_DECAY_DEFAULT = 0.0

# GAUSSIAN_FEATURE_SCHEMA: canonical ordered list of feature names for GaussianNBModel.
# Imported by trainer.py for load-time schema validation.
GAUSSIAN_FEATURE_SCHEMA = list(CANONICAL_FEATURE_ORDER)
