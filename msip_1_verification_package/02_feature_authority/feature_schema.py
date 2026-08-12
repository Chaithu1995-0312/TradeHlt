# Canonical feature schema — single source of truth for all feature extraction pipelines.
# Any change to feature names, order, or dimension MUST be made here and propagated.
#
# Schema v3.0 adds 3 features at indices 35-37:
#   Index 35: liquidity_distance       — ATR-normalised distance to nearest liquidity level
#   Index 36: liquidity_pressure_score — composite proximity/directional score [0, 1]
#   Index 37: volume_spike             — promoted from internal, int8 {0, 1}
#
# Models trained on schema v2.0 have n_features=35.
# All model loaders must check n_features against their stored value and
# slice the input vector to model.n_features when there is a mismatch.

import hashlib
import json
import logging as _logging

FEATURE_SCHEMA = {
    "atr": float,
    "rsi": float,
    "macd": float,
    "macd_signal": float,
    "bb_upper": float,
    "bb_lower": float,
    "ema_fast": float,
    "ema_slow": float,
    "volume_ratio": float,
    "session": str,
    "candle": dict,  # Expanded to open, high, low, close
    "zone_strength": float,
    "trend_bias": str,
    "rejection_wick": bool,
    "body_ratio": float,
    "volatility_flag": bool,
    "is_inside_bar": bool,
    "momentum_score": float,
    "spread_pct": float,
    "hour_of_day": float,
    "day_of_week": float,
    "pattern_score": float,
    "sl_distance": float,
    "tp_ratio": float,
}

# Canonical feature order for vector construction.
# Total vector dimension = 38 (== CANONICAL_FEATURE_DIM below; hard-asserted at import).
CANONICAL_FEATURES = tuple([
    # ── indices 0-34 (v2.0, preserved unchanged) ─────────────────────────────
    "open", "high", "low", "close", "volume",
    "volume_ratio",
    "double_sweep",
    "ema_fast", "ema_slow", "ema_spread",
    "trend_bias", "trend_strength",
    "momentum_score",
    "atr", "volatility_ratio",
    "rsi_14",
    "macd_line", "macd_signal", "macd_hist",
    "sweep_detected", "liquidity_sweep", "break_of_structure",
    "swing_high", "swing_low", "higher_high", "lower_low",
    "body_size", "wick_size", "body_ratio",
    "volatility_regime",
    "session", "hour_of_day",
    "disp_strength", "retest_depth", "candles_since_retest",
    # ── indices 35-37 (v3.0, NEW) ─────────────────────────────────────────────
    "liquidity_distance",       # index 35 — ATR-normalised distance to nearest liq level
    "liquidity_pressure_score", # index 36 — composite proximity score [0, 1]
    "volume_spike",             # index 37 — promoted from internal, int8 {0, 1}
])

# v2.0 backward-compat sentinel — model loaders that stored 35 features slice to this.
SCHEMA_V2_FEATURE_DIM: int = 35

CANONICAL_FEATURE_ORDER = list(CANONICAL_FEATURES)

# Total number of floats produced by extract_feature_vector() under schema v3.0.
# MUST equal len(CANONICAL_FEATURES).
CANONICAL_FEATURE_DIM: int = 38

assert len(CANONICAL_FEATURE_ORDER) == CANONICAL_FEATURE_DIM, (
    f"CANONICAL_FEATURE_ORDER has {len(CANONICAL_FEATURE_ORDER)} entries "
    f"but CANONICAL_FEATURE_DIM is set to {CANONICAL_FEATURE_DIM}. "
    "Update one or both to match."
)
assert len(CANONICAL_FEATURES) == CANONICAL_FEATURE_DIM, (
    f"CANONICAL_FEATURES has {len(CANONICAL_FEATURES)} entries "
    f"but CANONICAL_FEATURE_DIM is {CANONICAL_FEATURE_DIM}."
)

# Strict encoding maps. Unknown values are explicitly encoded as SESSION_UNKNOWN
# (NOT silently mapped to 0.0). When STRICT_SESSION_VALIDATION=true the
# encoder (src/features/crt_feature_builder.py) raises ValueError instead.
SESSION_MAP: dict = {
    "london": 0.0,
    "newyork": 1.0,
    "asian": 2.0,
    "overlap": 3.0,
}

# Out-of-band marker for unknown / unrecognized session strings. Chosen so it
# never collides with any mapped session value (all of which are >= 0.0).
SESSION_UNKNOWN: float = -1.0

TREND_MAP: dict = {
    "bullish": 1.0,
    "bearish": -1.0,
    "neutral": 0.0,
}


# --- SCHEMA HASH (CANONICAL) ---
# MD5 of concatenated feature names — legacy; retained for backward compat.
SCHEMA_HASH: str = hashlib.md5("".join(CANONICAL_FEATURES).encode()).hexdigest()

# FEATURE_ORDER_HASH — SHA-256 of the ordered feature name list.
# Detects semantic corruption: if a model was trained on a different ordering,
# its stored hash will differ from this value even if len() matches.
# Used by FeatureSchemaRegistry to catch silent truncation corruption.
def _feature_order_hash(features: tuple) -> str:
    """Stable SHA-256[:16] of feature name ordering. Changes if order or names change."""
    payload = json.dumps(list(features), sort_keys=False).encode()
    return hashlib.sha256(payload).hexdigest()[:16]

FEATURE_ORDER_HASH: str = _feature_order_hash(CANONICAL_FEATURES)


# ── SchemaObject ───────────────────────────────────────────────────────────────
# Wraps a schema to support both attribute access (schema.n_features)
# and dict-style access (schema["n_features"] / schema.get("n_features")).
# Required by training/trainer.py which uses attribute-style access.

class SchemaObject:
    """
    Schema descriptor supporting both attribute and dict-style access.

    Attributes
    ----------
    name          : str   — schema name (e.g. "tradenet", "gaussian")
    n_features    : int   — number of input features
    version       : str   — schema version string
    features      : list  — ordered list of feature names
    feature_names : list  — alias for features (backward-compat)
    checksum      : str   — MD5 hex digest of the feature list
    """

    def __init__(self, name: str, n_features: int, version: str, features: list):
        self._data = {
            "name":       name,
            "n_features": n_features,
            "version":    version,
            "features":   features,
        }
        self.name          = name
        self.n_features    = n_features
        self.version       = version
        self.features      = features
        self.feature_names = features  # alias
        # Stable checksum of the feature list
        self.checksum = hashlib.md5(
            json.dumps(features, sort_keys=True).encode()
        ).hexdigest()

    # Dict-style access
    def __getitem__(self, key):
        return self._data[key]

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __contains__(self, key):
        return key in self._data

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def items(self):
        return self._data.items()

    def __repr__(self):
        return (
            f"SchemaObject(name={self.name!r}, n_features={self.n_features}, "
            f"version={self.version!r})"
        )


# --- BACKWARD COMPATIBILITY (CRITICAL) ---

# ── Schema versioning (required by model_registry.py and training/trainer.py) ──

SCHEMA_VERSION: str = "3.0"   # was "1.0"; v2.0 = 35 features; v3.0 = 38 features

# TradeNet — uses full canonical vector (n_features computed dynamically from CANONICAL_FEATURES).
TRADENET_SCHEMA = SchemaObject(
    name="tradenet",
    n_features=len(CANONICAL_FEATURES),   # 38 (schema v3.0)
    version="3.0",
    features=list(CANONICAL_FEATURES),
)

# Gaussian NB — uses full canonical vector.
GAUSSIAN_SCHEMA = SchemaObject(
    name="gaussian",
    n_features=len(CANONICAL_FEATURES),   # 38 (schema v3.0)
    version="3.0",
    features=list(CANONICAL_FEATURES),
)

_SCHEMA_REGISTRY: dict = {
    "tradenet": TRADENET_SCHEMA,
    "gaussian": GAUSSIAN_SCHEMA,
}


class SchemaVersionError(Exception):
    """Raised when a model's schema version does not match the expected version."""
    pass


class FeatureSchemaRegistry:
    """
    Maps model instances to the schema they were trained on.

    Every model loader that calls register() can detect at inference time
    whether its stored feature_order_hash matches the current runtime hash.
    This prevents silent semantic corruption when a 38-dim vector is truncated
    to 35 dims — the *shape* is preserved but features[31] may mean something
    different in the old model than in the new schema.

    Usage
    -----
    # At model save time (in trainer.py):
        FeatureSchemaRegistry.register(version="gaussian_v6", hash=FEATURE_ORDER_HASH)

    # At inference time (in ml_gaussian_engine.py, zone_gate_engine.py, etc.):
        compatible = FeatureSchemaRegistry.check_compatibility("gaussian_v6")
        if not compatible:
            vec = vec[:SCHEMA_V2_FEATURE_DIM]   # truncate to model's training dim
    """
    _registry: dict[str, str] = {}  # version → stored feature_order_hash

    @classmethod
    def register(cls, version: str, feature_order_hash: str) -> None:
        """Record the feature_order_hash a model was trained on."""
        cls._registry[version] = feature_order_hash

    @classmethod
    def check_compatibility(cls, version: str, fail_closed: bool = True) -> bool:
        """
        Returns True  if stored hash == runtime hash (same schema, no truncation needed).
        Returns False if mismatch (schema migration; caller should truncate to model dim).
        Returns False if version was never registered and fail_closed=True (default).
        Returns True  if version was never registered and fail_closed=False (legacy opt-in).
        """
        stored = cls._registry.get(version)
        if stored is None:
            if fail_closed:
                _logging.getLogger("FeatureSchemaRegistry").warning(
                    "Unknown model version=%s has no registered schema hash — "
                    "rejecting (fail_closed=True). Register with FeatureSchemaRegistry.register().",
                    version,
                )
                return False
            return True  # explicit opt-in to fail-open (legacy callers only)
        if stored != FEATURE_ORDER_HASH:
            _logging.getLogger("FeatureSchemaRegistry").warning(
                "Schema mismatch for model=%s: stored_hash=%s runtime_hash=%s "
                "— model was trained on a different feature ordering; "
                "truncation will be applied.",
                version, stored, FEATURE_ORDER_HASH,
            )
            return False
        return True

    @classmethod
    def registered_versions(cls) -> list:
        """Return all registered version strings."""
        return list(cls._registry.keys())


def schema_for_model(model_type: str):
    """
    Return the SchemaObject for a given model type.

    Parameters
    ----------
    model_type : str
        One of "tradenet", "gaussian".

    Raises
    ------
    KeyError
        If model_type is not registered.
    """
    if model_type not in _SCHEMA_REGISTRY:
        raise KeyError(f"Unknown model_type '{model_type}'. Registered: {list(_SCHEMA_REGISTRY)}")
    return _SCHEMA_REGISTRY[model_type]


def assert_schema_version(model_type: str, version: str) -> None:
    """
    Assert that the registered schema for model_type matches the given version.

    Raises
    ------
    SchemaVersionError
        If the versions do not match.
    """
    schema = schema_for_model(model_type)
    registered = schema.get("version", "unknown")
    if registered != version:
        raise SchemaVersionError(
            f"Schema version mismatch for '{model_type}': "
            f"expected '{version}', got '{registered}'"
        )


# ── FEATURE_INDEX_MAP: maps each canonical feature name to its index ──────────
FEATURE_INDEX_MAP: dict = {name: i for i, name in enumerate(CANONICAL_FEATURES)}

# ── Session ordinal encoding ───────────────────────────────────────────────────
SESSION_ORDINAL: dict = {
    "ASIA": 0,
    "LONDON": 1,
    "NEWYORK": 2,
}


def encode_session_ordinal(session) -> int:
    """
    Encode a session string to its canonical 0-indexed ordinal value.

    Parameters
    ----------
    session : str or None
        Session name. Case-insensitive. Returns -1 for unknown/None.

    Returns
    -------
    int : 0 (ASIA), 1 (LONDON), 2 (NEWYORK), or -1 (unknown)
    """
    if session is None:
        return -1
    return SESSION_ORDINAL.get(str(session).upper(), -1)


def validate_vector(vec, schema, label: str = "") -> bool:
    """
    Validate that a feature vector has the expected number of features.

    Parameters
    ----------
    vec    : sequence of floats
    schema : SchemaObject or dict
    label  : optional context label for error messages

    Returns
    -------
    bool — True if length matches schema n_features.

    Raises
    ------
    ValueError
        If the vector length does not match.
    """
    if isinstance(schema, dict):
        expected = schema.get("n_features", 0)
    else:
        expected = schema.n_features

    if len(vec) != expected:
        ctx = f" [{label}]" if label else ""
        raise ValueError(
            f"validate_vector{ctx}: expected {expected} features, got {len(vec)}."
        )
    return True


def validate_features(features: dict) -> None:
    """
    Validate that a feature dict exactly matches CANONICAL_FEATURES.
    Raises ValueError with structured dict payload on any mismatch.
    Delegates to schema_validator.validate_features with CANONICAL_FEATURES.
    """
    from features.schema_validator import validate_features as _sv
    _sv(features, CANONICAL_FEATURES)