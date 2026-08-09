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
# Total vector dimension = 39 (== CANONICAL_FEATURE_DIM below; hard-asserted at import).
#
# ── SCHEMA v4.0 (2026-07-22, program SCHEMA-V4-VECTOR-MIGRATION) ──────────────────────────────
# THREE changes from v3.0, all name-level and therefore all hash-invalidating (SCHEMA_HASH and
# FEATURE_ORDER_HASH are computed over the NAMES below, not the values):
#
#   1. `macd_hist` -> `macd_hist_raw` + `macd_hist_z`  (indices 18, 19; +1 dim, tail shifts +1)
#      v3.0 emitted ONE column whose value was not what its declared formula said: the pipeline
#      computed `macd_line - macd_signal` and then compute_normalization OVERWROTE it in place with
#      a rolling z-score. FM-049's own ontology note warned "Easy to misread from the formula line
#      alone." Both quantities are legitimate; the defect was that one name carried the other's
#      value. Now each has its own slot and models choose explicitly.
#
#   2. `wick_size` -> `candle_range`  (index 28)
#      Pure rename, ZERO math change: the column always held `high - low`, i.e. the full candle
#      range, never a wick. The ontology already declared this (FM-002 `candle_range`, with
#      `misnomer_alias: wick_size`); v4.0 makes the vector agree with the ontology. Actual wick
#      magnitudes are `upper_wick` / `lower_wick`, which are separate primitives.
#
#   3. `session` VALUES change (index 31, name unchanged)
#      FM-052 moves from a 3-value hour PARTITION to a 5-value WINDOW model that can express the
#      London/New-York OVERLAP and a CLOSED (no-major-session) state. See
#      features/session_classifier.py — it is the single owner, and it deliberately keeps the
#      FEATURE separate from the session FILTER policy.
#
# The v2.0/v3.0 index comments below are NOT updated in place: they record what the layout WAS.
CANONICAL_FEATURES = tuple([
    # ── indices 0-17 (unchanged since v2.0) ──────────────────────────────────
    "open", "high", "low", "close", "volume",
    "volume_ratio",
    "double_sweep",
    "ema_fast", "ema_slow", "ema_spread",
    "trend_bias", "trend_strength",
    "momentum_score",
    "atr", "volatility_ratio",
    "rsi_14",
    "macd_line", "macd_signal",
    # ── v4.0: the MACD histogram split (was the single `macd_hist` at index 18) ──
    "macd_hist_raw",            # index 18 — macd_line - macd_signal (the DECLARED formula)
    "macd_hist_z",              # index 19 — rolling z-score of the above (what v3.0 actually emitted)
    # ── indices 20-35 (v2.0 tail, shifted +1 by the MACD split) ──────────────
    "sweep_detected", "liquidity_sweep", "break_of_structure",
    "swing_high", "swing_low", "higher_high", "lower_low",
    "body_size",
    "candle_range",             # index 28 — v4.0 rename of `wick_size`; always was high - low
    "body_ratio",
    "volatility_regime",
    "session", "hour_of_day",   # index 31 — v4.0 domain {0..4}, see session_classifier
    "disp_strength", "retest_depth", "candles_since_retest",
    # ── indices 36-38 (added in v3.0) ─────────────────────────────────────────
    "liquidity_distance",       # ATR-normalised distance to nearest liq level
    "liquidity_pressure_score", # composite proximity score [0, 1]
    "volume_spike",             # promoted from internal, int8 {0, 1}
])

# Read-side aliases: v3.0 name -> v4.0 canonical name. For DECODING historical records
# (opportunities.jsonl, stored training sets, old model metadata) only. NEVER emit these names.
SCHEMA_V3_ALIASES: dict = {
    "wick_size": "candle_range",
    "macd_hist": "macd_hist_z",   # v3.0's emitted value was the z-scored one, not the raw diff
}

# v2.0 backward-compat sentinel — model loaders that stored 35 features slice to this.
SCHEMA_V2_FEATURE_DIM: int = 35

CANONICAL_FEATURE_ORDER = list(CANONICAL_FEATURES)

# Total number of floats produced by extract_feature_vector() under schema v4.0.
# MUST equal len(CANONICAL_FEATURES).
CANONICAL_FEATURE_DIM: int = 39

# v3.0 sentinel — artifacts trained on the 38-dim layout slice/reject against this.
SCHEMA_V3_FEATURE_DIM: int = 38

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
#
# ── SESSION_MAP CORRECTED IN v4.0 (2026-07-22) — this was a real permutation defect ───────────
# v3.0 declared, right here:
#     {"london": 0.0, "newyork": 1.0, "asian": 2.0, "overlap": 3.0}
# while `compute_context` in the pipeline emitted Asia=0, London=1, NY=2 and `SESSION_ORDINAL`
# agreed with the PIPELINE. So the two maps in THIS FILE disagreed with each other by a
# permutation: a record encoded "london" got 0.0 here and 1.0 from the pipeline. Consumers split
# along that line — `dataset_builder` / `stage1_dataset_builder:453` / `strategy_backtest:271`
# read the SESSION_MAP convention, everything on the feature-vector path read the pipeline's.
# This is the defect `M16-WU-SESSION-ENCODING` recorded as "a canonical-vs-consumer encoding
# permutation against SESSION_MAP/dashboard" (BLOCKS_ACTIVATION).
#
# Both maps are now DERIVED from the single owner, so they cannot disagree again. Values follow
# session_classifier.SessionOrdinal (ASIA=0, LONDON=1, NEWYORK=2, OVERLAP=3, CLOSED=4) — i.e. the
# PIPELINE's convention wins, because that is what the trained feature vectors actually contain.
# NOTE this CHANGES the numbers `dataset_builder` and friends encode; historical datasets built
# under the old map carry the old permutation and must be rebuilt, not reinterpreted.
from features.session_classifier import (          # noqa: E402  (deliberate: single owner)
    SESSION_NAME_TO_ORDINAL as _SESSION_NAME_TO_ORDINAL,
    canonical_session_name as _canonical_session_name,
    encode_session_ordinal as _encode_session_ordinal,
)

SESSION_MAP: dict = {
    name.lower(): float(ordinal) for name, ordinal in _SESSION_NAME_TO_ORDINAL.items()
}
# Legacy spellings accepted on the READ side only (callers pass "asian"/"new_york"/"off_session").
SESSION_MAP.update({
    "asian": float(_SESSION_NAME_TO_ORDINAL["ASIA"]),
    "new_york": float(_SESSION_NAME_TO_ORDINAL["NEWYORK"]),
    "off_session": float(_SESSION_NAME_TO_ORDINAL["CLOSED"]),
})

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

SCHEMA_VERSION: str = "4.0"   # v2.0 = 35 feats; v3.0 = 38; v4.0 = 39 (MACD split + candle_range rename + FM-052 domain)

# TradeNet — uses full canonical vector (n_features computed dynamically from CANONICAL_FEATURES).
TRADENET_SCHEMA = SchemaObject(
    name="tradenet",
    n_features=len(CANONICAL_FEATURES),   # 39 (schema v4.0)
    version="3.0",
    features=list(CANONICAL_FEATURES),
)

# Gaussian NB — uses full canonical vector.
GAUSSIAN_SCHEMA = SchemaObject(
    name="gaussian",
    n_features=len(CANONICAL_FEATURES),   # 39 (schema v4.0)
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
    This prevents silent semantic corruption when a canonical vector is truncated
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
# DERIVED from features/session_classifier.py, the single owner (v4.0). Previously a hand-written
# 3-entry literal here, which is how it silently drifted out of step with SESSION_MAP above.
# Re-exported under the historical names so existing importers keep working.
SESSION_ORDINAL: dict = dict(_SESSION_NAME_TO_ORDINAL)


def encode_session_ordinal(session) -> int:
    """
    Encode a session name (or an already-encoded ordinal) to its canonical ordinal.

    Delegates to `session_classifier.encode_session_ordinal`; kept here as a stable re-export
    because several modules import it from this path. Case-insensitive; accepts the legacy
    spellings ("new_york", "asian", "off_session"). Returns -1 for unknown/None — the v3.0
    sentinel contract is preserved.

    Domain is now {0..4} (ASIA, LONDON, NEWYORK, OVERLAP, CLOSED), not {0..2}: a caller that
    branches exhaustively on the old three values will silently miss OVERLAP/CLOSED bars.
    """
    return _encode_session_ordinal(session)


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