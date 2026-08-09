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
    # a real market produces multiple distinct contexts, not one constant
    assert len(hashes) > 3, f"only {len(hashes)} distinct contexts across the run — suspicious"
