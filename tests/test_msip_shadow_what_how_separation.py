"""WHAT/HOW separation: labels require config id + continuous twins."""

from __future__ import annotations

import pytest

from msip.interpretation_config import (
    default_experimental_section,
    load_msip_shadow_config,
)
from msip.shadow_emitter import ProvenanceContext, build_market_state


def _features(**over):
    base = {
        "timestamp": "2024-05-22T01:00:00",
        "higher_high": 1,
        "lower_low": 0,
        "break_of_structure": 0,
        "liquidity_sweep": 1,
        "sweep_detected": 1,
        "liquidity_distance": 0.2,
        "liquidity_pressure_score": 0.3,
        "volatility_regime": 2,
        "atr": 0.002,
        "volatility_ratio": 1.2,
        "session": 0,
        "hour_of_day": 8,
        "trend_strength": 0.1,
        "trend_bias": 1,
        "ema_fast": 10.0,
        "ema_slow": 9.0,
        "body_ratio": 0.7,
        "body_size": 1.0,
        "wick_size": 1.5,
    }
    base.update(over)
    return base


def test_how_labels_emit_provenance_and_twins():
    section = default_experimental_section(with_how_labels=True)
    cfg = load_msip_shadow_config({"msip_shadow": section})
    prov = ProvenanceContext(config_id=cfg.config_id, config_sha256=cfg.config_sha256)
    vec = build_market_state(_features(), cfg, prov, symbol="XAUUSD", timeframe="M15")
    assert vec.has_how_labels()
    assert "how_label_provenance" in vec.provenance
    assert vec.provenance["how_label_provenance"]["msip_shadow_config_id"] == cfg.config_id
    assert vec.provenance["how_label_provenance"]["msip_shadow_config_sha256"] == cfg.config_sha256
    assert vec.provenance["continuous_twins_present"] is True
    # continuous WHAT still present
    assert vec.dimensions["liquidity_state"]["liquidity_distance"] is not None
    assert "liquidity_band_label" in vec.dimensions["liquidity_state"]


def test_overrides_cannot_change_source_features():
    section = default_experimental_section()
    section["dimensions"]["liquidity_state"]["instrument_overrides"] = {
        "XAUUSD": {"source_features": ["bogus"]}
    }
    with pytest.raises(ValueError, match="label_bands/enabled"):
        load_msip_shadow_config({"msip_shadow": section})


def test_crt_local_source_features_forbidden():
    section = default_experimental_section()
    section["dimensions"]["volatility_state"]["source_features"] = ["crt_local_atr"]
    with pytest.raises(ValueError, match="FORBIDDEN"):
        load_msip_shadow_config({"msip_shadow": section})


def test_absent_section_is_disabled():
    cfg = load_msip_shadow_config({})
    assert getattr(cfg, "enabled", False) is False
    vec = build_market_state(_features(), cfg, ProvenanceContext("x", "y"))
    assert vec is None
