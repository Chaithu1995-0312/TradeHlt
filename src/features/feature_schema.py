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

from features.registry import _ITERATED_SECTIONS, load_ontology

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
# Total vector dimension = 48 (== CANONICAL_FEATURE_DIM below; hard-asserted at import).
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
# ── SCHEMA v5.0 (2026-08-15, program CH-htfcrt-parent-candle-smc-v1, USER-AUTHORIZED) ──────────
# Adds 9 features at indices 39-47: the SMC (smart-money-concepts) primitives that were
# GENUINELY ABSENT from the codebase before this program (verified by repo-wide grep during the
# preceding study — see docs/implementation_plan/study-sujantrader-docs-composed-snowflake.md).
# All 9 are produced by the new src/features/smc/ package (pure geometry, window-bounded, no
# spine import). Unlike v4.0's renames/splits, this is a PURE ADDITION — no existing index
# changes meaning, so SCHEMA_V4_FEATURE_DIM=39 model artifacts remain sliceable/compatible via
# the same truncation discipline FeatureSchemaRegistry already applies for v2/v3.
#   Index 39: order_block_distance        — signed ATR distance to nearest unmitigated OB
#   Index 40: fvg_distance                — signed ATR distance to nearest unfilled FVG
#   Index 41: breaker_distance            — signed ATR distance to nearest un-retested breaker
#   Index 42: mitigation_block_distance   — signed ATR distance to nearest live mitigation block
#   Index 43: pdh_distance                — signed ATR distance to previous-day high
#   Index 44: pdl_distance                — signed ATR distance to previous-day low
#   Index 45: eqh_distance                — signed ATR distance to nearest equal-highs cluster
#   Index 46: eql_distance                — signed ATR distance to nearest equal-lows cluster
#   Index 47: change_of_character         — signed {-1,0,+1}, derived from break_of_structure x trend_bias
# The v2.0/v3.0/v4.0 index comments above are NOT updated in place: they record what the layout WAS.
#
# ── SCHEMA v6.0+ (2026-09-16, FEATURE-NAME-IDENTITY-BINDING Step 1) — GENERATED, not literal ──
# CANONICAL_FEATURES is now DERIVED from configs/formulas/market_ontology.yaml: every ontology
# entry across `_ITERATED_SECTIONS` (including the new `source_inputs` section registering
# open/high/low/close/volume as first-class identities, closing a prior gap — those 5 slots had
# NO ontology identity before this change) that declares a string `lineage.vector_key` is placed
# at its declared `lineage.vector_index`. A hand-written literal tuple could silently drift from
# the ontology it claims to mirror (caught only by a test that compares the two, and only if that
# test is run); a GENERATED tuple cannot drift from its own source by construction.
#
# Fail-closed at import: indices must be exactly 0..N-1 with no gaps or duplicates, and no two
# entries may claim the same vector_key (both already guarded at the ontology level by
# tests/test_feature_spec_schema.py::test_vector_keys_are_unique, re-asserted here because this
# module has no dependency on the test suite running first).
#
# PARITY PROOF (verified 2026-09-16, before this change shipped): the generated tuple is
# BYTE-IDENTICAL, name-for-name and position-for-position, to the literal tuple it replaces.
# SCHEMA_HASH and FEATURE_ORDER_HASH (both derived from these names below) are therefore
# unchanged by this step — this is a construction-method change, not a schema change.
def _generate_canonical_features() -> tuple:
    ont = load_ontology()
    slots: dict = {}
    for section in _ITERATED_SECTIONS:
        for name, spec in (ont.get(section) or {}).items():
            lin = spec.get("lineage") or {}
            vk, vi = lin.get("vector_key"), lin.get("vector_index")
            if not isinstance(vk, str) or not vk:
                continue
            if not isinstance(vi, int):
                raise RuntimeError(
                    f"feature_schema: ontology entry {section}.{name} declares vector_key "
                    f"{vk!r} but vector_index is not an int ({vi!r})."
                )
            if vi in slots:
                raise RuntimeError(
                    f"feature_schema: vector_index {vi} claimed by both "
                    f"{slots[vi]!r} ({section}.{name}'s predecessor) and {vk!r} ({section}.{name})."
                )
            slots[vi] = vk
    n = len(slots)
    missing = [i for i in range(n) if i not in slots]
    if missing:
        raise RuntimeError(
            f"feature_schema: ontology vector_index is not contiguous 0..{n - 1} — "
            f"missing indices {missing}. Every canonical slot must declare a vector_key."
        )
    return tuple(slots[i] for i in range(n))


CANONICAL_FEATURES = _generate_canonical_features()

# Read-side aliases: v3.0 name -> v4.0 canonical name. For DECODING historical records
# (opportunities.jsonl, stored training sets, old model metadata) only. NEVER emit these names.
SCHEMA_V3_ALIASES: dict = {
    "wick_size": "candle_range",
    "macd_hist": "macd_hist_z",   # v3.0's emitted value was the z-scored one, not the raw diff
}

# Read-side aliases: <=v5.0 name -> v6.0 canonical name. Same contract as SCHEMA_V3_ALIASES —
# for DECODING records written before the v6.0 rename (opportunities.jsonl, stored training sets
# such as data/master_crypto_training.jsonl, prior bar_matrix/features parquet builds, archived
# model metadata). NEVER emit these names. Both are pure renames: the VALUE under the old name is
# the value under the new one (proved by a by-position vector comparison over the XAUUSD M15
# corpus), so decoding needs no transformation, only relabelling.
SCHEMA_V5_ALIASES: dict = {
    "trend_strength": "trend_strength_z",         # the emitted value was always the rolling z-score
    "candles_since_retest": "candles_since_sweep",  # always counted bars since the last liquidity sweep
}

# v2.0 backward-compat sentinel — model loaders that stored 35 features slice to this.
SCHEMA_V2_FEATURE_DIM: int = 35

CANONICAL_FEATURE_ORDER = list(CANONICAL_FEATURES)

# Total number of floats produced by extract_feature_vector() under schema v5.0.
# MUST equal len(CANONICAL_FEATURES).
CANONICAL_FEATURE_DIM: int = 48

# v3.0 sentinel — artifacts trained on the 38-dim layout slice/reject against this.
SCHEMA_V3_FEATURE_DIM: int = 38

# v4.0 sentinel — artifacts trained on the 39-dim layout (pre-SMC) slice/reject against this.
# CH-htfcrt-parent-candle-smc-v1 (2026-08-15): every model family trained before this program
# carries n_features=39; FeatureSchemaRegistry.check_compatibility uses this to detect and
# truncate/degrade gracefully rather than silently misaligning a 48-dim vector against a
# 39-dim model.
SCHEMA_V4_FEATURE_DIM: int = 39

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

SCHEMA_VERSION: str = "6.0"   # v2.0 = 35 feats; v3.0 = 38; v4.0 = 39 (MACD split + candle_range rename + FM-052 domain); v5.0 = 48 (+9 SMC primitives, CH-htfcrt-parent-candle-smc-v1); v6.0 = 48 (NAMES ONLY: trend_strength -> trend_strength_z, candles_since_retest -> candles_since_sweep; CH-schema-v6-normalization-identity)

# TradeNet — uses full canonical vector (n_features computed dynamically from CANONICAL_FEATURES).
TRADENET_SCHEMA = SchemaObject(
    name="tradenet",
    n_features=len(CANONICAL_FEATURES),   # 48 (schema v5.0)
    version="3.0",
    features=list(CANONICAL_FEATURES),
)

# Gaussian NB — uses full canonical vector.
GAUSSIAN_SCHEMA = SchemaObject(
    name="gaussian",
    n_features=len(CANONICAL_FEATURES),   # 48 (schema v5.0)
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

# ── Identity namespace (2026-09-16, FEATURE-NAME-IDENTITY-BINDING Step 1) ─────
# `F.FM_021` resolves to the CURRENT name of a canonical (vector-bound) feature identity,
# by its stable ontology id rather than its current name. A production call site written as
# `features[F.FM_021]` survives a future rename of that identity's NAME without editing the
# call site — only the ontology moves. User-selected over a readable alias (whose own NAME would
# go stale the same way the old string literal did) and over a bare `feature_name(...)` call at
# every site (this is the same value, computed once at import instead of on every access).
#
# Scope: ONLY identities bound to a canonical vector slot (the 48 in CANONICAL_FEATURES). A
# non-vector identity (e.g. FM-027, EPISODE-scoped, `lineage.vector_key: []`) has no schema NAME
# to hand out here — it is not a feature_schema concept, and Step 2 does not migrate its readers.
def _build_fm_id_to_name() -> dict:
    ont = load_ontology()
    out: dict = {}
    for section in _ITERATED_SECTIONS:
        for name, spec in (ont.get(section) or {}).items():
            vk = (spec.get("lineage") or {}).get("vector_key")
            fid = spec.get("id")
            if isinstance(vk, str) and vk and isinstance(fid, str) and fid:
                out[fid] = vk
    return out


_FM_ID_TO_NAME: dict = _build_fm_id_to_name()
assert set(_FM_ID_TO_NAME.values()) == set(CANONICAL_FEATURES), (
    "feature_schema: every canonical feature must have exactly one FM id bound to it — "
    f"mismatch: {set(CANONICAL_FEATURES) ^ set(_FM_ID_TO_NAME.values())}"
)


def feature_name(fm_id: str) -> str:
    """Current canonical name for a vector-bound feature identity, e.g. feature_name('FM-021').

    Raises KeyError (loud, not a default) if `fm_id` is unknown or is not bound to a vector slot —
    a caller reaching for a name that does not exist has a bug, not a value to fall back on.
    """
    try:
        return _FM_ID_TO_NAME[fm_id]
    except KeyError:
        raise KeyError(
            f"feature_name: {fm_id!r} is not a vector-bound canonical feature identity "
            f"(known: {sorted(_FM_ID_TO_NAME)})"
        ) from None


class _FeatureIdentity:
    """Attribute access to `feature_name`, e.g. `F.FM_021 == 'retest_depth'`.

    Built once at import from `_FM_ID_TO_NAME`; read-only in spirit (nothing writes to it after
    construction). `F.FM_021` is a plain string — safe to use as a dict key, an f-string, or a
    dataframe column selector exactly like the literal it replaces.
    """

    def __init__(self, mapping: dict):
        for fid, name in mapping.items():
            setattr(self, fid.replace("-", "_"), name)


F = _FeatureIdentity(_FM_ID_TO_NAME)

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