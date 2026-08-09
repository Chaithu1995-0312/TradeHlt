"""crt_phase_observation must not be an identity dependency of other dimensions."""

from __future__ import annotations

from msip.interpretation_config import default_experimental_section, load_msip_shadow_config
from msip.shadow_emitter import ProvenanceContext, build_market_state, observe_crt_state


def _feats():
    return {
        "timestamp": "t",
        "higher_high": 0,
        "lower_low": 1,
        "break_of_structure": 0,
        "liquidity_sweep": 0,
        "sweep_detected": 0,
        "liquidity_distance": 0.5,
        "liquidity_pressure_score": 0.1,
        "volatility_regime": 1,
        "atr": 0.01,
        "volatility_ratio": 1.1,
        "session": 1,
        "hour_of_day": 11,
        "trend_strength": 0.01,
        "trend_bias": 0,
        "ema_fast": 5.0,
        "ema_slow": 5.1,
        "body_ratio": 0.6,
        "body_size": 1.0,
        "wick_size": 1.2,
    }


def test_vector_complete_without_crt_observation():
    cfg = load_msip_shadow_config({"msip_shadow": default_experimental_section()})
    prov = ProvenanceContext(config_id=cfg.config_id, config_sha256=cfg.config_sha256)
    vec = build_market_state(_feats(), cfg, prov, crt_obs=None)
    # other dimensions populated independently of CRT
    assert vec.dimensions["structure_state"]["higher_high"] == 0
    assert vec.dimensions["crt_phase_observation"]["observed"] is False
    assert vec.status == "COMPLETE"


def test_crt_state_change_does_not_change_what_fields():
    cfg = load_msip_shadow_config({"msip_shadow": default_experimental_section()})
    prov = ProvenanceContext(config_id=cfg.config_id, config_sha256=cfg.config_sha256)
    v1 = build_market_state(
        _feats(), cfg, prov, crt_obs=observe_crt_state({"crt_state": "RANGE", "observed": True})
    )
    v2 = build_market_state(
        _feats(), cfg, prov, crt_obs=observe_crt_state({"crt_state": "SWEEP", "observed": True})
    )
    for dim in (
        "structure_state",
        "liquidity_state",
        "volatility_state",
        "session_state",
        "trend_state",
        "candle_quality_state",
    ):
        assert v1.dimensions[dim] == v2.dimensions[dim]
    assert v1.dimensions["crt_phase_observation"]["crt_state"] != v2.dimensions[
        "crt_phase_observation"
    ]["crt_state"]
