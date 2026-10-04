"""Floor for the Market Context layer (src/features/market_context.py, roadmap Phase 3).

Proves the aggregator is a pure regrouping of encoder output along the ontology's declared
`taxonomy.category` axis: no second taxonomy, no priority rules, no defaults; X_ markers
propagate; signature/hash are deterministic and injective over differing state sets.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from features.feature_states import FeatureStateEncoder, X_PREFIX
from features.feature_schema import CANONICAL_FEATURES, FEATURE_INDEX_MAP
from features.market_context import MarketContextBuilder
from features.registry import load_ontology


@pytest.fixture(scope="module")
def builder() -> MarketContextBuilder:
    return MarketContextBuilder()


@pytest.fixture(scope="module")
def enc(builder) -> FeatureStateEncoder:
    return FeatureStateEncoder()


def _zero_states(enc):
    """A legal all-zeros state mapping (every vector-bound feature at value 0)."""
    return {n: enc.spec(n).value_to_state[0] for n in enc.vector_bound_features}


# ── dimension derivation: ontology axis, nothing else ────────────────────────

def test_dimensions_follow_vocabulary_order_and_membership(builder):
    ont = load_ontology()
    vocab = ont["spec_schema"]["category_vocabulary"]
    assert list(builder.dimensions) == [c for c in vocab if c in builder.dimensions]
    # every stateful identity appears in exactly one dimension
    enc = FeatureStateEncoder()
    placed = [f for c in builder.dimensions for f in builder.features_of(c)]
    assert sorted(placed) == sorted(enc.stateful_features)


def test_expected_dimensions_exist(builder):
    for dim in ("Trend", "Liquidity", "MarketStructure", "Volatility", "Volume", "Time"):
        assert dim in builder.dimensions, f"dimension {dim} missing"
    assert "liquidity_sweep" in builder.features_of("Liquidity")
    assert "trend_bias" in builder.features_of("Trend")
    assert "session" in builder.features_of("Time")


# ── strict contract ──────────────────────────────────────────────────────────

def test_unknown_key_raises(builder, enc):
    states = _zero_states(enc)
    states["not_a_feature"] = "Bullish"
    with pytest.raises(KeyError):
        builder.build(states)


def test_missing_required_state_raises_listing_them(builder, enc):
    states = _zero_states(enc)
    del states["session"], states["trend_bias"]
    with pytest.raises(KeyError) as e:
        builder.build(states)
    assert "session" in str(e.value) and "trend_bias" in str(e.value)


def test_undeclared_state_string_raises(builder, enc):
    states = _zero_states(enc)
    states["trend_bias"] = "SortOfBullish"  # neither declared nor an X_ marker
    with pytest.raises(ValueError):
        builder.build(states)


def test_nonvector_states_are_allowed_and_placed(builder, enc):
    states = _zero_states(enc)
    states["rsi_state"] = "Overbought"
    ctx = builder.build(states)
    assert ctx.dimensions["Momentum"]["rsi_state"] == "Overbought"


# ── X_ propagation ───────────────────────────────────────────────────────────

def test_x_markers_propagate_and_surface(builder, enc):
    states = _zero_states(enc)
    states["session"] = f"{X_PREFIX}UNMAPPED(-1.0)"
    ctx = builder.build(states)
    assert ctx.x_markers == (f"session={X_PREFIX}UNMAPPED(-1.0)",)
    assert ctx.dimensions["Time"]["session"].startswith(X_PREFIX)
    assert X_PREFIX in ctx.signature  # drift stays visible in the clustering substrate


def test_clean_context_has_no_x_markers(builder, enc):
    assert builder.build(_zero_states(enc)).x_markers == ()


# ── signature / hash determinism ─────────────────────────────────────────────

def test_signature_deterministic_and_state_sensitive(builder, enc):
    a = builder.build(_zero_states(enc))
    b = builder.build(_zero_states(enc))
    assert a.signature == b.signature and a.context_hash == b.context_hash

    bull = _zero_states(enc)
    bull["trend_bias"] = "Bullish"
    c = builder.build(bull)
    assert c.signature != a.signature and c.context_hash != a.context_hash
    assert "Trend[trend_bias=Bullish]" in c.signature


def test_describe_renders_every_dimension(builder, enc):
    text = builder.build(_zero_states(enc)).describe()
    for dim in ("Trend", "Liquidity", "Time"):
        assert f"{dim}:" in text
    assert "(trend_bias)" in text


# ── pipeline-truth round trip ────────────────────────────────────────────────

def _synthetic(n: int = 400, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.5, n))
    open_ = close + rng.normal(0, 0.1, n)
    body_top = np.maximum(open_, close)
    body_bot = np.minimum(open_, close)
    high = body_top + rng.uniform(0.05, 0.8, n)
    low = body_bot - rng.uniform(0.05, 0.8, n)
    volume = rng.uniform(100, 1000, n)
    ts = pd.date_range("2024-01-01", periods=n, freq="15min")
    return pd.DataFrame({"timestamp": ts, "open": open_, "high": high, "low": low,
                         "close": close, "volume": volume})


def test_contexts_from_a_real_pipeline_run(builder):
    from features.feature_pipeline import FeaturePipeline

    _df, vectors = FeaturePipeline(_synthetic()).run()
    assert len(vectors) > 100

    hashes = set()
    for row in vectors[:: max(1, len(vectors) // 50)]:
        ctx = builder.build_from_vector(row)
        assert ctx.x_markers == (), f"real pipeline bar produced domain drift: {ctx.x_markers}"
        # vector path and dict path agree
        as_dict = {f: row[i] for f, i in FEATURE_INDEX_MAP.items()}
        assert builder.build_from_features(as_dict).context_hash == ctx.context_hash
        hashes.add(ctx.context_hash)
        # L4 closure: structured fields present; no invented magnitude states
        assert ctx.completeness in ("COMPLETE", "PARTIAL")
        assert ctx.temporal is not None
        assert ctx.temporal.causality == "UNKNOWN"
        assert "body_commitment" not in (
            (ctx.dimensions.get("CandleGeometry") or {})
        ), "vector-only build must not fabricate magnitude states"
    # a real market produces multiple distinct contexts, not one constant
    assert len(hashes) > 3, f"only {len(hashes)} distinct contexts across the run — suspicious"


# ── L4 structured closure contract ───────────────────────────────────────────

def test_dimension_records_map_from_authoritative_states(builder, enc):
    """Every populated dimension feature is an ontology-declared stateful identity."""
    states = _zero_states(enc)
    ctx = builder.build(states)
    for cat, rec in ctx.dimension_records.items():
        assert cat in builder.dimensions or rec.status == "EMPTY"
        for feat, dfr in rec.features.items():
            assert feat in enc.stateful_features
            assert dfr.category == cat
            assert dfr.fm_id  # ontology id present
            if dfr.known:
                assert dfr.state in enc.spec(feat).value_to_state.values()
            else:
                assert dfr.state.startswith(X_PREFIX)


def test_unknown_x_state_remains_unknown_not_fabricated(builder, enc):
    states = _zero_states(enc)
    states["trend_bias"] = f"{X_PREFIX}UNMAPPED(9.0)"
    ctx = builder.build(states)
    assert ctx.dimensions["Trend"]["trend_bias"].startswith(X_PREFIX)
    assert ctx.dimension_records["Trend"].features["trend_bias"].known is False
    assert "Trend" in ctx.unknown_dimensions or ctx.dimension_records["Trend"].status == "DRIFT"
    # Completeness must be PARTIAL when any X_ is present
    assert ctx.completeness == "PARTIAL"


def test_absent_optional_magnitude_is_not_fabricated(builder, enc):
    """Without magnitude states, CandleGeometry stays EMPTY — never LowCommitment."""
    ctx = builder.build(_zero_states(enc))
    assert ctx.dimension_records["CandleGeometry"].status == "EMPTY"
    assert "CandleGeometry" in ctx.unknown_dimensions
    assert "body_commitment" not in (ctx.dimensions.get("CandleGeometry") or {})


def test_magnitude_states_merge_when_supplied(builder, enc):
    states = _zero_states(enc)
    mag = {
        "body_commitment": "MediumCommitment",
        "atr_magnitude": "HighAtrMagnitude",
        "momentum_magnitude": "LowMomentumMagnitude",
    }
    ctx = builder.build_with_magnitude(states, mag)
    assert ctx.dimensions["CandleGeometry"]["body_commitment"] == "MediumCommitment"
    assert ctx.dimensions["Volatility"]["atr_magnitude"] == "HighAtrMagnitude"
    assert ctx.dimensions["Momentum"]["momentum_magnitude"] == "LowMomentumMagnitude"
    assert ctx.dimension_records["CandleGeometry"].features["body_commitment"].source == (
        "magnitude_states"
    )
    assert "features.magnitude_states.MagnitudeStateEncoder" in ctx.provenance


def test_context_deterministic_with_structure(builder, enc):
    a = builder.build(_zero_states(enc))
    b = builder.build(_zero_states(enc))
    assert a.context_hash == b.context_hash
    assert a.completeness == b.completeness
    assert a.completeness_ratio == b.completeness_ratio
    assert a.unknown_dimensions == b.unknown_dimensions
    assert a.temporal.causality == b.temporal.causality == "UNKNOWN"


def test_context_does_not_alter_canonical_feature_values(builder, enc):
    """Context is pure regrouping — input states pass through unmodified."""
    states = _zero_states(enc)
    states["trend_bias"] = "Bullish"
    ctx = builder.build(states)
    assert ctx.dimensions["Trend"]["trend_bias"] == "Bullish"
    assert states["trend_bias"] == "Bullish"  # input unchanged


def test_session_uses_single_session_owner(builder, enc):
    ctx = builder.build(_zero_states(enc))
    assert ctx.temporal is not None
    assert ctx.temporal.session_owner == "features.session_classifier"
    assert "session_classifier" in " ".join(ctx.provenance) or any(
        "session" in p for p in ctx.provenance
    )
    # Time dimension carries session from feature_states, not a reimplementation
    assert ctx.dimension_records["Time"].features["session"].source == "session_classifier"


def test_temporal_causality_is_unknown_unless_defined(builder, enc):
    ctx = builder.build(_zero_states(enc))
    assert ctx.temporal.causality == "UNKNOWN"
    assert ctx.temporal.to_dict()["inferred_episode_causality"] == "UNKNOWN"
    # Session may still be known as observed_time_context
    assert ctx.temporal.session_known is True
    assert ctx.temporal.session_state is not None


def test_completeness_deterministic_vector_only_complete(builder, enc):
    ctx = builder.build(_zero_states(enc))
    # All vector-bound known, no X_ → COMPLETE even if optional magnitude EMPTY
    assert ctx.completeness == "COMPLETE"
    assert ctx.completeness_ratio == 1.0


def test_unresolved_continuous_listed_not_banded(builder, enc):
    ctx = builder.build(_zero_states(enc))
    assert len(ctx.unresolved_continuous) == len(enc.continuous_features)
    assert "body_ratio" in ctx.unresolved_continuous
    assert "atr" in ctx.unresolved_continuous
    # These continuous features must NOT appear as fabricated context states
    flat_feats = {f for feats in ctx.dimensions.values() for f in feats}
    assert "body_ratio" not in flat_feats
    assert "atr" not in flat_feats


def test_to_dict_contract_shape(builder, enc):
    ctx = builder.build(_zero_states(enc))
    d = ctx.to_dict()
    for key in (
        "dimensions", "dimensions_flat", "completeness", "unknown_dimensions",
        "unresolved_continuous", "provenance", "temporal", "signature", "context_hash",
    ):
        assert key in d
    assert d["temporal"]["causality"] == "UNKNOWN"
