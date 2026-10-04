"""Phase 2A magnitude states — continuous VALUE → STATE (shadow; no spine)."""
from __future__ import annotations

import math

import numpy as np
import pytest

from features.feature_states import FeatureStateEncoder, X_PREFIX
from features.magnitude_states import (
    MAGNITUDE_STATE_NAMES,
    MagnitudeStateEncoder,
    bin_ordered,
    percentile_rank,
)
from features.registry import load_ontology, validate_registry


@pytest.fixture(scope="module")
def ont():
    return load_ontology()


@pytest.fixture(scope="module")
def mag(ont) -> MagnitudeStateEncoder:
    return MagnitudeStateEncoder(ont)


def test_registry_accepts_phase2a_magnitude_identities():
    assert validate_registry() == []


def test_ontology_declares_all_magnitude_identities(ont):
    ss = ont["structural_states"]
    for name in MAGNITUDE_STATE_NAMES:
        assert name in ss
        assert ss[name].get("band_edges")
        assert ss[name].get("source_feature")
        assert ss[name].get("states")
        assert ss[name]["lifecycle"] == "research"
        assert ss[name]["lineage"]["vector_key"] in ([], None) or ss[name]["lineage"]["vector_key"] == []


def test_bin_ordered_half_open_edges():
    edges = (0.33, 0.70)
    assert bin_ordered(0.0, edges) == 0
    assert bin_ordered(0.329999, edges) == 0
    assert bin_ordered(0.33, edges) == 1
    assert bin_ordered(0.699, edges) == 1
    assert bin_ordered(0.70, edges) == 2
    assert bin_ordered(1.0, edges) == 2


def test_body_commitment_identity_bins_crt_coherent(mag):
    # High edge 0.70 matches CRT displacement gate coherence note on FM-010
    assert mag.classify_value("body_commitment", 0.20) == "LowCommitment"
    assert mag.classify_value("body_commitment", 0.50) == "MediumCommitment"
    assert mag.classify_value("body_commitment", 0.70) == "HighCommitment"
    assert mag.classify_value("body_commitment", 0.90) == "HighCommitment"


def test_body_ratio_vector_slot_remains_continuous():
    enc = FeatureStateEncoder()
    assert "body_ratio" in enc.continuous_features
    assert "body_commitment" in enc.stateful_features
    assert enc.spec("body_commitment").vector_index is None


def test_atr_and_momentum_require_series_for_percentile(mag):
    # Without series → X_ (fail closed; no invented ranks)
    assert mag.classify_value("atr_magnitude", 0.002).startswith(X_PREFIX)
    assert mag.classify_value("momentum_magnitude", 100.0).startswith(X_PREFIX)

    atr_series = [0.001, 0.002, 0.003, 0.004, 0.005]
    # 0.005 is max → high percentile
    assert mag.classify_value("atr_magnitude", 0.005, series=atr_series) == "HighAtrMagnitude"
    assert mag.classify_value("atr_magnitude", 0.001, series=atr_series) == "LowAtrMagnitude"

    mom_series = [-10.0, 0.0, 10.0, 100.0, -200.0]
    # | -200 | is largest abs → High
    assert (
        mag.classify_value("momentum_magnitude", -200.0, series=mom_series)
        == "HighMomentumMagnitude"
    )
    assert (
        mag.classify_value("momentum_magnitude", 0.0, series=mom_series)
        == "LowMomentumMagnitude"
    )


def test_f061_no_fixed_absolute_momentum_edges_in_ontology(ont):
    """Momentum bands must be percentile-based, not raw absolute cuts on FM-023."""
    m = ont["structural_states"]["momentum_magnitude"]
    assert m["source_transform"] == "abs_series_percentile"
    # edges live on [0,1] percentile domain
    for e in m["band_edges"]:
        assert 0.0 < float(e) < 1.0


def test_classify_features_full_map(mag):
    features = {
        "body_ratio": 0.80,
        "atr": 0.004,
        "momentum_score": 50.0,
    }
    series_context = {
        "atr": [0.001, 0.002, 0.003, 0.004, 0.005],
        "momentum_score": [0.0, 10.0, 20.0, 50.0, 100.0],
    }
    out = mag.classify_features(features, series_context=series_context)
    assert set(out) == set(MAGNITUDE_STATE_NAMES)
    assert out["body_commitment"] == "HighCommitment"
    assert not any(v.startswith(X_PREFIX) for v in out.values())


def test_classify_features_missing_source_raises(mag):
    with pytest.raises(KeyError):
        mag.classify_features({"body_ratio": 0.5})  # atr + momentum absent


def test_percentile_rank_midrank():
    s = [1.0, 2.0, 3.0, 4.0]
    assert math.isclose(percentile_rank(1.0, s), 0.125)
    assert math.isclose(percentile_rank(4.0, s), 0.875)
    assert math.isnan(percentile_rank(1.0, []))


def test_non_finite_continuous_is_x_marker(mag):
    assert mag.classify_value("body_commitment", float("nan")).startswith(X_PREFIX)
    assert mag.classify_value("body_commitment", math.inf).startswith(X_PREFIX)


def test_encoder_deterministic(mag):
    a = mag.classify_value("body_commitment", 0.55)
    b = mag.classify_value("body_commitment", 0.55)
    assert a == b == "MediumCommitment"
