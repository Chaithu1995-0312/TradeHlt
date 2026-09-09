"""
P0 2026-07-22 — Gaussian NB schema contract (name-anchored, no silent truncate).

Closes the FAIL_OPEN path where MLGaussianEngine truncated ambient 39-dim
vectors to model.n_features by index under schema v4.

Also replaces load-time exact-list equality against GAUSSIAN_FEATURE_SCHEMA
with alias-aware name resolution (macd_hist→macd_hist_z, wick_size→candle_range).
"""
from __future__ import annotations

import pytest

from features.feature_schema import (
    CANONICAL_FEATURE_ORDER,
    CANONICAL_FEATURE_DIM,
    SCHEMA_V3_ALIASES,
)
from features.gaussian_schema_contract import (
    GaussianSchemaError,
    assert_model_schema_compatible,
    extract_model_feature_vector,
    resolve_trained_feature_name,
    resolve_trained_feature_schema,
    schema_alignment_report,
)


def test_aliases_match_schema_v3_contract():
    assert SCHEMA_V3_ALIASES["macd_hist"] == "macd_hist_z"
    assert SCHEMA_V3_ALIASES["wick_size"] == "candle_range"


def test_resolve_trained_feature_name_aliases_and_live():
    assert resolve_trained_feature_name("ema_fast") == "ema_fast"
    assert resolve_trained_feature_name("macd_hist") == "macd_hist_z"
    assert resolve_trained_feature_name("wick_size") == "candle_range"
    with pytest.raises(GaussianSchemaError):
        resolve_trained_feature_name("feature_that_never_existed")


def test_resolve_v3_38_schema_is_alignable_subset():
    # Typical BNB p5 checkpoint order fragment + full 38 from a real-ish list
    from pathlib import Path
    import json

    path = Path("models/BNBUSDT/bnbusdt_balanced_20260524/gaussian_p5_20260524T120449.json")
    if not path.is_file():
        pytest.skip("BNB gaussian checkpoint absent")
    saved = json.loads(path.read_text(encoding="utf-8"))["feature_schema"]
    resolved = resolve_trained_feature_schema(saved)
    assert len(resolved) == 38 == len(saved)
    assert "macd_hist_z" in resolved and "macd_hist" not in resolved
    assert "candle_range" in resolved and "wick_size" not in resolved
    assert "macd_hist_raw" not in resolved  # subset — no trained stats for raw
    assert set(resolved) <= set(CANONICAL_FEATURE_ORDER)
    report = schema_alignment_report(saved)
    assert report["alignable"] is True
    assert report["is_strict_subset"] is True


def test_assert_model_schema_compatible_width():
    order = ["ema_fast", "ema_slow", "momentum_score"]
    assert assert_model_schema_compatible(order, model_n_features=3) == order
    with pytest.raises(GaussianSchemaError, match="n_features"):
        assert_model_schema_compatible(order, model_n_features=2)


def test_extract_model_feature_vector_order_and_missing():
    order = ["ema_fast", "ema_slow", "momentum_score"]
    feats = {k: float(i) for i, k in enumerate(CANONICAL_FEATURE_ORDER)}
    vec = extract_model_feature_vector(feats, order)
    assert vec == [
        float(CANONICAL_FEATURE_ORDER.index("ema_fast")),
        float(CANONICAL_FEATURE_ORDER.index("ema_slow")),
        float(CANONICAL_FEATURE_ORDER.index("momentum_score")),
    ]
    bad = dict(feats)
    del bad["ema_slow"]
    with pytest.raises(GaussianSchemaError, match="ema_slow"):
        extract_model_feature_vector(bad, order)


def test_load_gaussian_bnb_38_succeeds_with_resolved_schema():
    from training.trainer import load_gaussian_model

    model, scaler, meta = load_gaussian_model(
        "BNBUSDT/bnbusdt_balanced_20260524/gaussian_p5_20260524T120449.json"
    )
    assert model.n_features == 38
    assert meta["name_anchored"] is True
    assert meta["schema_alignment"] == "named_subset"
    assert len(meta["feature_schema_resolved"]) == 38
    assert "macd_hist_z" in meta["feature_schema_resolved"]
    assert "candle_range" in meta["feature_schema_resolved"]
    assert scaler is not None


def test_load_gaussian_eth_35_succeeds_with_resolved_schema():
    from training.trainer import load_gaussian_model

    model, scaler, meta = load_gaussian_model(
        "ETHUSDT/20260519_113806/gaussian_v5_auto_2026_06_eth.json"
    )
    assert model.n_features == 35
    assert meta["schema_alignment"] == "named_subset"
    assert len(meta["feature_schema_resolved"]) == 35


def test_ml_gaussian_compute_name_anchored_no_truncate():
    """Forced load of BNB model; compute on full live feature dict must score (not 0.5 schema fail)."""
    from engines.ml_gaussian_engine import MLGaussianEngine
    from training.trainer import load_gaussian_model

    model, scaler, meta = load_gaussian_model(
        "BNBUSDT/bnbusdt_balanced_20260524/gaussian_p5_20260524T120449.json"
    )
    eng = MLGaussianEngine({"instrument": "BNBUSDT"}, preload=False)
    eng._model = model
    eng._scaler = scaler
    eng._model_version = "p5_20260524T120449"
    eng._load_failed = False
    eng._feature_schema_resolved = list(meta["feature_schema_resolved"])
    eng._schema_alignment = meta["schema_alignment"]

    feats = {k: 0.1 for k in CANONICAL_FEATURE_ORDER}
    feats["ema_fast"] = 1.01
    feats["ema_slow"] = 1.00
    feats["momentum_score"] = 0.05
    # distinctive values for aliased slots
    feats["macd_hist_z"] = 0.3
    feats["candle_range"] = 2.5
    out = eng.compute(feats)
    assert out["reason"] == "ml_gaussian", out
    assert 0.0 <= float(out["score"]) <= 1.0
    assert out["meta"]["n_features"] == 38
    assert out["meta"]["schema_alignment"] == "named_subset"


def test_ml_gaussian_refuses_missing_required_feature():
    from engines.ml_gaussian_engine import MLGaussianEngine
    from training.trainer import load_gaussian_model

    model, scaler, meta = load_gaussian_model(
        "BNBUSDT/bnbusdt_balanced_20260524/gaussian_p5_20260524T120449.json"
    )
    eng = MLGaussianEngine({}, preload=False)
    eng._model = model
    eng._scaler = scaler
    eng._load_failed = False
    eng._feature_schema_resolved = list(meta["feature_schema_resolved"])
    eng._schema_alignment = "named_subset"

    feats = {k: 0.1 for k in CANONICAL_FEATURE_ORDER}
    del feats["macd_hist_z"]  # required via macd_hist remap
    out = eng.compute(feats)
    assert out["reason"] == "ml_gaussian_schema_extract_failed"
    assert out["score"] == 0.5


def test_no_silent_truncate_helper_exists_not_used_for_overlong_ambient():
    """Ambient 39-vector must not be index-sliced to 38 for scoring.

    Name-anchored extract of the trained 38-subset is the only legal path.
    """
    from features.dataset_builder import extract_feature_vector

    feats = {k: float(i) for i, k in enumerate(CANONICAL_FEATURE_ORDER)}
    ambient = extract_feature_vector(feats)
    assert len(ambient) == CANONICAL_FEATURE_DIM == 48

    path = __import__("pathlib").Path(
        "models/BNBUSDT/bnbusdt_balanced_20260524/gaussian_p5_20260524T120449.json"
    )
    import json
    from training.trainer import load_gaussian_model

    _, _, meta = load_gaussian_model(
        "BNBUSDT/bnbusdt_balanced_20260524/gaussian_p5_20260524T120449.json"
    )
    named = extract_model_feature_vector(feats, meta["feature_schema_resolved"])
    assert len(named) == 38
    # Truncating ambient by index is NOT equal to name-anchored extract under v4
    # (MACD split shifts the tail) — this is exactly the FAIL_OPEN we closed.
    truncated = ambient[:38]
    assert truncated != named
