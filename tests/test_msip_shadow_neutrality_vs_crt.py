"""CRT outputs must be identical with shadow co-run on vs off (neutrality)."""

from __future__ import annotations

from copy import deepcopy

from msip.interpretation_config import default_experimental_section, load_msip_shadow_config
from msip.shadow_emitter import ProvenanceContext, build_market_state, observe_crt_state


def test_observe_crt_state_is_pure_and_optional():
    snap = {"crt_state": "RANGE", "bar_index": 3, "observed": True}
    # mutate after observe must not affect prior observation object (frozen)
    obs = observe_crt_state(snap)
    snap["crt_state"] = "SWEEP"
    assert obs.crt_state == "RANGE"
    assert obs.observed is True


def test_build_market_state_does_not_require_crt_for_identity():
    cfg = load_msip_shadow_config({"msip_shadow": default_experimental_section()})
    prov = ProvenanceContext(config_id=cfg.config_id, config_sha256=cfg.config_sha256)
    feats = {
        "timestamp": "t0",
        "higher_high": 0,
        "lower_low": 0,
        "break_of_structure": 0,
        "liquidity_sweep": 0,
        "sweep_detected": 0,
        "liquidity_distance": 0.1,
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
    # Simulate a "CRT path" snapshot that shadow never mutates
    crt_path = {"state": "RANGE", "actions": []}
    before = deepcopy(crt_path)

    vec_off_cfg = load_msip_shadow_config({})  # disabled
    assert build_market_state(feats, vec_off_cfg, prov) is None
    assert crt_path == before

    vec_on = build_market_state(
        feats,
        cfg,
        prov,
        crt_obs=observe_crt_state({"crt_state": crt_path["state"], "observed": True}),
    )
    assert vec_on is not None
    # CRT path untouched
    assert crt_path == before
    # shadow observation is join-only
    assert vec_on.dimensions["crt_phase_observation"]["crt_state"] == "RANGE"


def test_shadow_flags_always_false_on_and_off():
    cfg = load_msip_shadow_config({"msip_shadow": default_experimental_section()})
    prov = ProvenanceContext(config_id=cfg.config_id, config_sha256=cfg.config_sha256)
    feats = {
        "timestamp": "t0",
        "higher_high": 0,
        "lower_low": 0,
        "break_of_structure": 0,
        "liquidity_sweep": 0,
        "sweep_detected": 0,
        "liquidity_distance": 0.1,
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
    assert vec.shadow_flags == {
        "affects_crt": False,
        "affects_execution": False,
        "affects_events": False,
    }
