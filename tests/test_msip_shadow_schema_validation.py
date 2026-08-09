"""MSIP MarketStateVector schema / authority validation."""

from __future__ import annotations

from msip.interpretation_config import (
    default_experimental_section,
    load_msip_shadow_config,
)
from msip.market_state_vector import SCHEMA_VERSION, MarketStateVector, validate_field_authorities
from msip.shadow_emitter import ProvenanceContext, build_market_state


def _features(**over):
    base = {
        "timestamp": "2024-05-22T01:00:00",
        "higher_high": 0,
        "lower_low": 0,
        "break_of_structure": 0,
        "liquidity_sweep": 0,
        "sweep_detected": 0,
        "liquidity_distance": 0.1,
        "liquidity_pressure_score": 0.2,
        "volatility_regime": 1,
        "atr": 0.001,
        "volatility_ratio": 1.0,
        "session": 1,
        "hour_of_day": 10,
        "trend_strength": 0.05,
        "trend_bias": 1,
        "ema_fast": 100.0,
        "ema_slow": 99.0,
        "body_ratio": 0.5,
        "body_size": 1.0,
        "wick_size": 2.0,
    }
    base.update(over)
    return base


def test_schema_version_pin():
    cfg = load_msip_shadow_config({"msip_shadow": default_experimental_section()})
    prov = ProvenanceContext(config_id=cfg.config_id, config_sha256=cfg.config_sha256)
    vec = build_market_state(_features(), cfg, prov, symbol="XAUUSD", timeframe="M15")
    assert vec is not None
    assert vec.schema_version == SCHEMA_VERSION
    d = vec.to_dict()
    assert d["schema_version"] == "1.0.0"
    assert d["shadow_flags"] == {
        "affects_crt": False,
        "affects_execution": False,
        "affects_events": False,
    }


def test_shadow_flags_cannot_be_true():
    vec = MarketStateVector(
        schema_version=SCHEMA_VERSION,
        symbol="X",
        timeframe="M15",
        bar_timestamp="t",
        bar_index=0,
        dimensions={},
        provenance={},
        status="COMPLETE",
        shadow_flags={
            "affects_crt": True,
            "affects_execution": True,
            "affects_events": True,
        },
    )
    # __post_init__ forces false
    assert vec.shadow_flags["affects_crt"] is False
    assert vec.to_dict()["shadow_flags"]["affects_execution"] is False


def test_required_dimensions_present():
    cfg = load_msip_shadow_config({"msip_shadow": default_experimental_section()})
    prov = ProvenanceContext(config_id=cfg.config_id, config_sha256=cfg.config_sha256)
    vec = build_market_state(_features(), cfg, prov)
    assert "structure_state" in vec.dimensions
    assert "liquidity_state" in vec.dimensions
    assert "volatility_state" in vec.dimensions
    assert "session_state" in vec.dimensions
    assert "trend_state" in vec.dimensions
    assert "candle_quality_state" in vec.dimensions
    assert "crt_phase_observation" in vec.dimensions
    unknown = validate_field_authorities(vec.dimensions)
    # only confidence-style extras would warn; none expected
    assert unknown == []


def test_missing_feature_marks_partial():
    cfg = load_msip_shadow_config({"msip_shadow": default_experimental_section()})
    prov = ProvenanceContext(config_id=cfg.config_id, config_sha256=cfg.config_sha256)
    feats = _features()
    del feats["atr"]
    vec = build_market_state(feats, cfg, prov)
    assert vec.status == "PARTIAL"
    assert vec.dimensions["volatility_state"]["atr"] is None
