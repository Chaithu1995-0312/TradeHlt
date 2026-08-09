"""Floor for the Feature State layer (src/features/feature_states.py, roadmap Phase 2C).

Proves the encoder is a PURE interpreter of the ontology's declared states:
  - it binds exactly the states-bearing identities (no invented bands, no thresholds in code),
  - out-of-domain values surface as greppable X_ markers instead of being coerced or dropped,
  - missing inputs RAISE (no defaults, no fallbacks),
  - and on a real pipeline run, every emitted state round-trips the raw column value exactly.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from features.feature_states import FeatureStateEncoder, X_PREFIX
from features.feature_schema import CANONICAL_FEATURES, FEATURE_INDEX_MAP
from features.registry import load_ontology


@pytest.fixture(scope="module")
def enc() -> FeatureStateEncoder:
    return FeatureStateEncoder()


# ── binding: encoder ⇄ ontology, nothing more, nothing less ──────────────────

def test_vector_bound_set_is_exactly_the_declared_one(enc):
    expected = {
        "double_sweep", "trend_bias", "sweep_detected", "liquidity_sweep",
        "break_of_structure", "swing_high", "swing_low", "higher_high", "lower_low",
        "volatility_regime", "session", "volume_spike",
    }
    assert set(enc.vector_bound_features) == expected


def test_nonvector_stateful_identities_are_known_but_not_vector_bound(enc):
    for name in ("retest_flag", "rsi_state", "displacement_flag"):
        assert name in enc.stateful_features
        assert enc.spec(name).vector_index is None


def test_bindings_derive_from_ontology_not_a_local_list(enc):
    """Every binding must trace to a non-empty ontology states block — the encoder may not know
    anything the ontology does not declare."""
    ont = load_ontology()
    for name in enc.stateful_features:
        sf = enc.spec(name)
        assert (ont[sf.section][name].get("states")), f"{name}: bound without declared states"
        declared = {s["value"]: s["name"] for s in ont[sf.section][name]["states"]}
        assert sf.value_to_state == declared, f"{name}: encoder map diverged from ontology"


def test_continuous_features_partition_the_vector(enc):
    bound = set(enc.vector_bound_features)
    cont = set(enc.continuous_features)
    assert bound | cont == set(CANONICAL_FEATURES)
    assert not (bound & cont)
    # The features whose banding is deliberately absent stay continuous (F-061 blocks ema_spread
    # magnitude bands; the others have no cut anywhere in code to declare).
    for f in ("rsi_14", "ema_spread", "momentum_score", "retest_depth", "disp_strength", "close"):
        assert f in cont, f"{f} unexpectedly acquired states — was a banding added deliberately?"


def test_vector_bound_emission_order_is_canonical_index_order(enc):
    idx = [FEATURE_INDEX_MAP[n] for n in enc.vector_bound_features]
    assert idx == sorted(idx)


# ── classification semantics ─────────────────────────────────────────────────

def test_known_values_map_to_declared_names(enc):
    assert enc.classify_value("trend_bias", 1.0) == "Bullish"
    assert enc.classify_value("trend_bias", -1.0) == "Bearish"
    assert enc.classify_value("trend_bias", 0.0) == "Neutral"
    assert enc.classify_value("session", 3) == "OVERLAP"
    assert enc.classify_value("session", 4) == "CLOSED"
    assert enc.classify_value("volatility_regime", 2) == "HighVolatility"
    assert enc.classify_value("liquidity_sweep", -1) == "SellSideSweep"
    assert enc.classify_value("volume_spike", 1) == "VolumeSpike"
    assert enc.classify_value("rsi_state", -1) == "Oversold"
    assert enc.classify_value("displacement_flag", 1) == "Displacement"
    assert enc.classify_value("retest_flag", 0) == "NoRetest"


def test_out_of_domain_values_become_greppable_x_markers(enc):
    # a fractional value between states: never coerced to a neighbour
    assert enc.classify_value("trend_bias", 0.5).startswith(f"{X_PREFIX}UNMAPPED")
    # an integer outside the domain (session sentinel -1 is deliberately NOT a session state)
    assert enc.classify_value("session", -1).startswith(f"{X_PREFIX}UNMAPPED")
    assert enc.classify_value("volatility_regime", 7).startswith(f"{X_PREFIX}UNMAPPED")
    # non-finite
    assert enc.classify_value("trend_bias", float("nan")).startswith(f"{X_PREFIX}NON_FINITE")
    assert enc.classify_value("trend_bias", math.inf).startswith(f"{X_PREFIX}NON_FINITE")
    # the marker carries the offending value — that is what makes it findable
    assert "0.5" in enc.classify_value("trend_bias", 0.5)


def test_float_representation_of_a_declared_value_still_maps(enc):
    # float32 round-trips (the vector is float32) must not degrade to X markers
    assert enc.classify_value("trend_bias", np.float32(1.0)) == "Bullish"
    assert enc.classify_value("session", np.float32(2.0)) == "NEWYORK"


# ── no defaults, no fallbacks ────────────────────────────────────────────────

def test_unknown_feature_name_raises(enc):
    with pytest.raises(KeyError):
        enc.classify_value("no_such_feature", 1.0)
    with pytest.raises(KeyError):
        enc.classify_value("rsi_14", 55.0)  # continuous: has no states, must not silently band


def test_classify_raises_on_missing_inputs_listing_them_all(enc):
    with pytest.raises(KeyError) as e:
        enc.classify({"trend_bias": 1.0})  # everything else absent
    msg = str(e.value)
    assert "session" in msg and "volatility_regime" in msg


def test_classify_vector_rejects_wrong_dimension(enc):
    with pytest.raises(ValueError):
        enc.classify_vector([0.0] * 38)  # v3.0 dim — must not be silently accepted


def test_malformed_ontology_states_fail_at_construction():
    ont = load_ontology()
    bad = {**ont, "structural_states": {
        "broken": {**ont["structural_states"]["trend_bias"],
                   "states": [{"name": "OnlyName"}]},  # missing 'value'
    }}
    with pytest.raises(ValueError):
        FeatureStateEncoder(bad)


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


def test_states_round_trip_a_real_pipeline_run(enc):
    """For every bound feature: encoder(state) of the emitted value equals the ontology name for
    that exact raw value — across a full FeaturePipeline run, no X markers on real output."""
    from features.feature_pipeline import FeaturePipeline

    df, vectors = FeaturePipeline(_synthetic()).run()
    assert len(vectors) > 100

    for row in vectors[:: max(1, len(vectors) // 50)]:  # ~50 sampled bars
        states = enc.classify_vector(row)
        for name, state in states.items():
            raw = row[FEATURE_INDEX_MAP[name]]
            assert not state.startswith(X_PREFIX), (
                f"{name}: real pipeline value {raw!r} fell outside its declared domain — "
                "either the domain declaration or the pipeline is wrong"
            )
            assert enc.spec(name).value_to_state[int(round(float(raw)))] == state

    # dict path and vector path agree
    last = vectors[-1]
    as_dict = {f: last[i] for f, i in FEATURE_INDEX_MAP.items()}
    assert enc.classify(as_dict) == enc.classify_vector(last)


def test_encoder_is_deterministic(enc):
    vec = [0.0] * len(CANONICAL_FEATURES)
    assert enc.classify_vector(vec) == enc.classify_vector(vec)
