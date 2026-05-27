"""
tests/features/test_feature_schema_registry.py
===============================================
Tests for FeatureSchemaRegistry and FEATURE_ORDER_HASH (Part 1).

Covers:
    1. FEATURE_ORDER_HASH is a 16-char hex string
    2. register() + check_compatibility() → True when hashes match
    3. Mismatch returns False and logs WARNING
    4. Unregistered version → True (fail-open)
    5. Hash changes when feature order changes
    6. registered_versions() returns registered keys
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

_SRC = str(Path(__file__).parents[2] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from features.feature_schema import (
    FEATURE_ORDER_HASH,
    FeatureSchemaRegistry,
)


# ── Test 1: FEATURE_ORDER_HASH format ────────────────────────────────────────

def test_feature_order_hash_format():
    assert isinstance(FEATURE_ORDER_HASH, str), "FEATURE_ORDER_HASH must be a str"
    assert len(FEATURE_ORDER_HASH) == 16, (
        f"Expected 16-char hash, got {len(FEATURE_ORDER_HASH)} chars: {FEATURE_ORDER_HASH!r}"
    )
    # Must be valid hex
    int(FEATURE_ORDER_HASH, 16)


# ── Test 2: Register + check_compatibility → True on match ───────────────────

def test_register_match():
    version = "_test_match_version_"
    FeatureSchemaRegistry.register(version, FEATURE_ORDER_HASH)
    assert FeatureSchemaRegistry.check_compatibility(version) is True


# ── Test 3: Mismatch returns False + logs WARNING ─────────────────────────────

def test_register_mismatch(caplog):
    version = "_test_mismatch_version_"
    fake_hash = "a" * 16    # deliberately wrong
    FeatureSchemaRegistry.register(version, fake_hash)

    with caplog.at_level(logging.WARNING, logger="FeatureSchemaRegistry"):
        result = FeatureSchemaRegistry.check_compatibility(version)

    assert result is False, "Expected False on hash mismatch"
    assert any("mismatch" in msg.lower() or "schema" in msg.lower()
               for msg in caplog.messages), (
        "Expected a WARNING log mentioning schema mismatch"
    )


# ── Test 4: Unregistered version → True (fail-open) ──────────────────────────

def test_unregistered_fail_open():
    result = FeatureSchemaRegistry.check_compatibility("_never_registered_xyz_")
    assert result is True, "Expected True (fail-open) for unregistered version"


# ── Test 5: Hash changes when feature order changes ───────────────────────────

def test_hash_changes_on_reorder():
    from features.feature_schema import _feature_order_hash, CANONICAL_FEATURES
    original_hash = _feature_order_hash(CANONICAL_FEATURES)

    # Reverse the feature order
    reversed_features = tuple(reversed(CANONICAL_FEATURES))
    reversed_hash = _feature_order_hash(reversed_features)

    assert original_hash != reversed_hash, (
        "Hash should differ when feature order changes"
    )


# ── Test 6: registered_versions() returns registered keys ────────────────────

def test_registered_versions():
    version_a = "_test_versions_a_"
    version_b = "_test_versions_b_"
    FeatureSchemaRegistry.register(version_a, FEATURE_ORDER_HASH)
    FeatureSchemaRegistry.register(version_b, FEATURE_ORDER_HASH)

    versions = FeatureSchemaRegistry.registered_versions()
    assert version_a in versions, f"Expected {version_a} in registered_versions()"
    assert version_b in versions, f"Expected {version_b} in registered_versions()"
