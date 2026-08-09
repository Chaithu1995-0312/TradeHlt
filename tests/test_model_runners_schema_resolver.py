"""Floor: model_runners schema_resolver is the single live->trained authority (R1/A8).

The point of this floor is that the three previously-independent schema mappings
must remain reproducible from ONE module, and that every failure mode fails
CLOSED (no zero-fill, no pad/truncate, no default generation).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from features.feature_schema import (  # noqa: E402
    CANONICAL_FEATURE_DIM,
    CANONICAL_FEATURES,
)
from research.model_runners.schema_resolver import (  # noqa: E402
    SCHEMA_REGISTRY,
    ResolvedSchema,
    SchemaResolutionError,
    identify_registered,
    resolve_declared,
    resolve_named,
    resolve_trained_name,
)


def _full_features() -> dict[str, float]:
    return {name: float(i + 1) for i, name in enumerate(CANONICAL_FEATURES)}


# ── registry shape ───────────────────────────────────────────────────────────

def test_registry_has_the_three_known_generations():
    assert set(SCHEMA_REGISTRY) == {
        "canonical_39",
        "legacy_38_env",
        "canonical_38_v3",
    }


def test_canonical_39_is_the_live_schema():
    s = resolve_named("canonical_39")
    assert s.dim == CANONICAL_FEATURE_DIM == 39
    assert list(s.live_names) == list(CANONICAL_FEATURES)
    assert s.renames == {}


def test_both_38_dim_schemas_share_live_names_but_differ_on_trained_names():
    """The exact confusion that motivated R1: same dim, different convention."""
    env = resolve_named("legacy_38_env")
    v3 = resolve_named("canonical_38_v3")
    assert env.dim == v3.dim == 38
    # Same underlying live features...
    assert list(env.live_names) == list(v3.live_names)
    # ...but the trained-name conventions genuinely differ.
    assert list(env.trained_names) != list(v3.trained_names)
    assert env.renames == {}
    assert v3.renames == {
        "macd_hist": "macd_hist_z",
        "wick_size": "candle_range",
    }


# ── parity with the implementations this module replaced ─────────────────────

def test_parity_with_legacy_feature_names_from_clean_labels():
    """legacy_38_env must equal research.clean_labels.builder.LEGACY_FEATURE_NAMES."""
    from research.clean_labels.builder import (
        LEGACY_FEATURE_DIM,
        LEGACY_FEATURE_NAMES,
    )

    s = resolve_named("legacy_38_env")
    assert list(s.live_names) == list(LEGACY_FEATURE_NAMES)
    assert s.dim == LEGACY_FEATURE_DIM


def test_parity_with_the_removed_rr_trained_v3_mapping():
    """canonical_38_v3 must reproduce the old hardcoded _v3_order_from_v4()."""

    def _old_v3_order_from_v4(canonical_v4):
        v3 = []
        for n in canonical_v4:
            if n == "macd_hist_raw":
                continue
            if n == "macd_hist_z":
                v3.append("macd_hist")
            elif n == "candle_range":
                v3.append("wick_size")
            else:
                v3.append(n)
        return v3

    expected = _old_v3_order_from_v4(CANONICAL_FEATURES)
    assert list(resolve_named("canonical_38_v3").trained_names) == expected


# ── fail-closed behaviour (no defaults anywhere) ─────────────────────────────

def test_unknown_schema_id_raises_rather_than_defaulting():
    with pytest.raises(SchemaResolutionError, match="unknown trained_schema_id"):
        resolve_named("canonical_37_imaginary")


def test_missing_live_feature_raises_never_zero_fills():
    s = resolve_named("canonical_39")
    feats = _full_features()
    del feats["atr"]
    with pytest.raises(SchemaResolutionError, match="No zero-fill"):
        s.build_vector(feats)


def test_width_mismatch_fails_closed():
    s = resolve_named("canonical_38_v3")
    with pytest.raises(SchemaResolutionError, match="Refusing silent pad/truncate"):
        s.assert_model_width(39)
    s.assert_model_width(38)  # correct width does not raise


def test_unresolvable_trained_name_raises():
    with pytest.raises(SchemaResolutionError):
        resolve_trained_name("a_feature_that_never_existed")


def test_v3_alias_names_resolve_to_live_names():
    assert resolve_trained_name("macd_hist") == "macd_hist_z"
    assert resolve_trained_name("wick_size") == "candle_range"
    assert resolve_trained_name("atr") == "atr"


def test_declared_schema_with_duplicate_resolution_is_rejected():
    """Two trained names collapsing onto one live slot would drop a dimension."""
    with pytest.raises(SchemaResolutionError, match="duplicate live"):
        resolve_declared(["atr", "macd_hist_z", "macd_hist"])


def test_declared_empty_schema_rejected():
    with pytest.raises(SchemaResolutionError, match="empty feature_schema"):
        resolve_declared([])


# ── vector building ──────────────────────────────────────────────────────────

def test_build_vector_is_name_anchored_not_positional():
    """Reordering the source dict must not change the produced vector."""
    s = resolve_named("canonical_38_v3")
    feats = _full_features()
    reversed_feats = dict(reversed(list(feats.items())))
    assert s.build_vector(feats) == s.build_vector(reversed_feats)


def test_build_vector_drops_only_the_v4_only_feature():
    s = resolve_named("legacy_38_env")
    feats = _full_features()
    vec = s.build_vector(feats)
    assert len(vec) == 38
    assert feats["macd_hist_raw"] not in vec or "macd_hist_raw" not in s.live_names


def test_identify_registered_matches_known_generation():
    s = resolve_named("legacy_38_env")
    assert identify_registered(s.live_names) == "legacy_38_env"
    assert identify_registered(["atr", "close"]) is None


# ── manifest stamp (A8) ──────────────────────────────────────────────────────

def test_to_manifest_carries_the_versioning_answer():
    m = resolve_named("canonical_38_v3").to_manifest()
    assert m["trained_schema_id"] == "canonical_38_v3"
    assert m["trained_schema_dim"] == 38
    assert m["trained_schema_source"] == "registry"
    assert m["trained_schema_renames"]["macd_hist"] == "macd_hist_z"


def test_resolved_schema_rejects_length_mismatch_at_construction():
    with pytest.raises(SchemaResolutionError, match="length mismatch"):
        ResolvedSchema(
            schema_id="bad",
            trained_names=("atr", "close"),
            live_names=("atr",),
            source="registry",
        )
