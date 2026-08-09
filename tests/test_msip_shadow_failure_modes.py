"""Failure handling: missing features, partial provenance, disabled section."""

from __future__ import annotations

import pytest

from msip.interpretation_config import (
    Disabled,
    default_experimental_section,
    load_msip_shadow_config,
)
from msip.shadow_emitter import ProvenanceContext, build_market_state


def test_enabled_missing_config_id_fail_closed():
    section = default_experimental_section()
    del section["config_id"]
    with pytest.raises(KeyError, match="config_id"):
        load_msip_shadow_config({"msip_shadow": section})


def test_enabled_wrong_schema_version_fail_closed():
    section = default_experimental_section()
    section["schema_version_required"] = "9.9.9"
    with pytest.raises(ValueError, match="schema_version"):
        load_msip_shadow_config({"msip_shadow": section})


def test_disabled_when_enabled_false():
    cfg = load_msip_shadow_config({"msip_shadow": {"enabled": False}})
    assert isinstance(cfg, Disabled) or cfg.enabled is False


def test_nan_feature_is_partial_not_invented():
    cfg = load_msip_shadow_config({"msip_shadow": default_experimental_section()})
    prov = ProvenanceContext(config_id=cfg.config_id, config_sha256=cfg.config_sha256)
    feats = {
        "timestamp": "t",
        "higher_high": 0,
        "lower_low": 0,
        "break_of_structure": 0,
        "liquidity_sweep": 0,
        "sweep_detected": 0,
        "liquidity_distance": float("nan"),
        "liquidity_pressure_score": 0.1,
        "volatility_regime": 1,
        "atr": 0.01,
        "volatility_ratio": 1.0,
        "session": 1,
        "hour_of_day": 12,
        "trend_strength": 0.0,
        "trend_bias": 0,
        "ema_fast": 1.0,
        "ema_slow": 1.0,
        "body_ratio": 0.4,
        "body_size": 1.0,
        "wick_size": 2.0,
    }
    vec = build_market_state(feats, cfg, prov)
    assert vec.status == "PARTIAL"
    assert vec.dimensions["liquidity_state"]["liquidity_distance"] is None
