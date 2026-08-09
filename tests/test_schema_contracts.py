"""
test_schema_contracts.py
═══════════════════════════════════════════════════════════════════════════════
CI schema contract test suite — v5 (canonical-only).

Tests the single canonical schema defined in feature_schema.py.

Tests:
  1. CANONICAL_FEATURES is a tuple (immutable)
  2. CANONICAL_FEATURES has no duplicates
  3. CANONICAL_FEATURES has exactly 32 features
  4. FEATURE_INDEX_MAP is consistent with CANONICAL_FEATURES
  5. SCHEMA_HASH is deterministic
  6. Session encoding returns canonical 0-indexed values
  7. validate_features: exact match passes
  8. validate_features: missing key raises ValueError
  9. validate_features: extra key raises ValueError
 10. validate_features: schema violation has structured error dict

Run:
    python test_schema_contracts.py
    # or via pytest: pytest test_schema_contracts.py -v

Exit 0 = all tests pass. Non-zero = contract violation found.
═══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import sys


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

# ── 1. CANONICAL_FEATURES is a tuple ─────────────────────────────────────────
def test_canonical_features_is_tuple():
    from features.feature_schema import CANONICAL_FEATURES
    assert isinstance(CANONICAL_FEATURES, tuple), (
        f"CANONICAL_FEATURES must be tuple (immutable), got {type(CANONICAL_FEATURES).__name__}"
    )


# ── 2. No duplicates ──────────────────────────────────────────────────────────
def test_no_duplicates():
    from features.feature_schema import CANONICAL_FEATURES
    seen = set()
    for f in CANONICAL_FEATURES:
        assert f not in seen, f"Duplicate feature name: '{f}'"
        seen.add(f)


# ── 3. Exactly 39 features (schema v4.0 — the MACD histogram split adds
#          macd_hist_raw at index 18 alongside macd_hist_z at 19; v3.0 was 38)
def test_feature_count():
    from features.feature_schema import CANONICAL_FEATURES, CANONICAL_FEATURE_DIM
    assert len(CANONICAL_FEATURES) == 39, (
        f"Expected 39 canonical features (schema v4.0), got {len(CANONICAL_FEATURES)}"
    )
    assert CANONICAL_FEATURE_DIM == 39


# ── 4. FEATURE_INDEX_MAP consistency ─────────────────────────────────────────
def test_feature_index_map():
    from features.feature_schema import CANONICAL_FEATURES, FEATURE_INDEX_MAP
    assert len(FEATURE_INDEX_MAP) == len(CANONICAL_FEATURES), (
        f"FEATURE_INDEX_MAP has {len(FEATURE_INDEX_MAP)} entries, "
        f"expected {len(CANONICAL_FEATURES)}"
    )
    for i, name in enumerate(CANONICAL_FEATURES):
        assert name in FEATURE_INDEX_MAP, f"'{name}' missing from FEATURE_INDEX_MAP"
        assert FEATURE_INDEX_MAP[name] == i, (
            f"FEATURE_INDEX_MAP['{name}'] = {FEATURE_INDEX_MAP[name]}, expected {i}"
        )


# ── 5. SCHEMA_HASH is deterministic ──────────────────────────────────────────
def test_schema_hash_stable():
    import hashlib
    from features.feature_schema import CANONICAL_FEATURES, SCHEMA_HASH
    expected = hashlib.md5("".join(CANONICAL_FEATURES).encode()).hexdigest()
    assert SCHEMA_HASH == expected, (
        f"SCHEMA_HASH mismatch: expected {expected}, got {SCHEMA_HASH}. "
        "Schema may have been modified without updating the hash."
    )


# ── 6. Session encoding — canonical 0-indexed ────────────────────────────────
def test_session_encoding():
    from features.feature_schema import encode_session_ordinal, SESSION_ORDINAL
    assert encode_session_ordinal("ASIA")    == 0
    assert encode_session_ordinal("LONDON")  == 1
    assert encode_session_ordinal("NEWYORK") == 2
    assert encode_session_ordinal("UNKNOWN") == -1
    assert encode_session_ordinal(None)      == -1
    # Case insensitive
    assert encode_session_ordinal("london")  == 1
    assert encode_session_ordinal("asia")    == 0


# ── 7. validate_features: exact match passes ─────────────────────────────────
def test_validate_features_exact_match():
    from features.feature_schema import CANONICAL_FEATURES, validate_features
    features = {f: 0.0 for f in CANONICAL_FEATURES}
    validate_features(features)  # must not raise


# ── 8. validate_features: missing key raises ValueError ──────────────────────
def test_validate_features_missing_key():
    from features.feature_schema import CANONICAL_FEATURES, validate_features
    import pytest
    features = {f: 0.0 for f in CANONICAL_FEATURES}
    del features["atr"]
    with pytest.raises(ValueError):
        validate_features(features)


# ── 9. validate_features: extra key raises ValueError ────────────────────────
def test_validate_features_extra_key():
    from features.feature_schema import CANONICAL_FEATURES, validate_features
    import pytest
    features = {f: 0.0 for f in CANONICAL_FEATURES}
    features["non_canonical_rsi"] = 50.0
    with pytest.raises(ValueError):
        validate_features(features)


# ── 10. validate_features: error has structured dict payload ─────────────────
def test_validate_features_error_structure():
    from features.feature_schema import CANONICAL_FEATURES, validate_features
    features = {f: 0.0 for f in CANONICAL_FEATURES}
    del features["close"]
    features["rsi"] = 50.0  # extra

    try:
        validate_features(features)
        raise AssertionError("Expected ValueError was not raised")
    except ValueError as e:
        err = e.args[0]
        assert isinstance(err, dict), f"Error payload must be dict, got {type(err)}"
        assert err["error"] == "FEATURE_SCHEMA_VIOLATION", f"Wrong error code: {err['error']}"
        assert "close" in err["missing"], f"'close' not in missing: {err['missing']}"
        assert "rsi" in err["extra"], f"'rsi' not in extra: {err['extra']}"


# ── 11. schema_validator.validate_features consistent with feature_schema ────
def test_schema_validator_consistent():
    from features.feature_schema import CANONICAL_FEATURES
    from features.schema_validator import validate_features as sv_validate
    import pytest

    # Exact match — must pass
    features = {f: 0.0 for f in CANONICAL_FEATURES}
    sv_validate(features, CANONICAL_FEATURES)

    # Missing — must raise
    bad = dict(features)
    del bad["body_ratio"]
    with pytest.raises(ValueError):
        sv_validate(bad, CANONICAL_FEATURES)


# ─────────────────────────────────────────────────────────────────────────────
# Standalone runner (not used by pytest)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n╔══════════════════════════════════════════════════════════╗")
    print("║  CRT Schema Contract Test Suite — v5 (canonical-only)  ║")
    print("╚══════════════════════════════════════════════════════════╝\n")

    _tests = [
        ("1. CANONICAL_FEATURES is a tuple (immutable)", test_canonical_features_is_tuple),
        ("2. CANONICAL_FEATURES has no duplicates", test_no_duplicates),
        ("3. CANONICAL_FEATURES has exactly 35 features", test_feature_count),
        ("4. FEATURE_INDEX_MAP is consistent with CANONICAL_FEATURES", test_feature_index_map),
        ("5. SCHEMA_HASH is deterministic and matches current schema", test_schema_hash_stable),
        ("6. encode_session_ordinal returns canonical 0-indexed values", test_session_encoding),
        ("7. validate_features: exact match passes without error", test_validate_features_exact_match),
        ("8. validate_features: missing key raises ValueError", test_validate_features_missing_key),
        ("9. validate_features: extra key raises ValueError", test_validate_features_extra_key),
        ("10. validate_features: error carries structured dict payload", test_validate_features_error_structure),
        ("11. schema_validator.validate_features is consistent with feature_schema", test_schema_validator_consistent),
    ]

    _pass, _fail = 0, []
    for name, fn in _tests:
        try:
            fn()
            _pass += 1
            print(f"  ✓  {name}")
        except Exception as e:
            _fail.append((name, str(e)))
            print(f"  ✗  {name}\n       {e}")

    print(f"\n{'─'*58}")
    print(f"  Results: {_pass} passed, {len(_fail)} failed out of {len(_tests)} tests")
    print(f"{'─'*58}")
    sys.exit(1 if _fail else 0)