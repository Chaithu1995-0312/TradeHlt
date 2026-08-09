"""DET-01: two-run equality of shadow payloads."""

from __future__ import annotations

from msip.interpretation_config import default_experimental_section, load_msip_shadow_config
from msip.shadow_emitter import ProvenanceContext, build_market_state, stable_json_bytes


def _feats():
    return {
        "timestamp": "2024-05-22T02:00:00",
        "higher_high": 1,
        "lower_low": 0,
        "break_of_structure": -1,
        "liquidity_sweep": 1,
        "sweep_detected": 0,
        "liquidity_distance": 0.25,
        "liquidity_pressure_score": 0.4,
        "volatility_regime": 0,
        "atr": 0.003,
        "volatility_ratio": 0.9,
        "session": 2,
        "hour_of_day": 15,
        "trend_strength": -0.02,
        "trend_bias": -1,
        "ema_fast": 200.5,
        "ema_slow": 201.0,
        "body_ratio": 0.33,
        "body_size": 0.5,
        "wick_size": 1.5,
    }


def test_two_run_byte_identical():
    cfg = load_msip_shadow_config({"msip_shadow": default_experimental_section()})
    prov = ProvenanceContext(
        config_id=cfg.config_id,
        config_sha256=cfg.config_sha256,
        repository_commit="deadbeef",
        corpus_path="data/mt5/XAUUSD_M15.csv",
        corpus_sha256="abc",
    )
    a = build_market_state(_feats(), cfg, prov, symbol="XAUUSD", timeframe="M15", bar_index=7)
    b = build_market_state(_feats(), cfg, prov, symbol="XAUUSD", timeframe="M15", bar_index=7)
    assert stable_json_bytes(a) == stable_json_bytes(b)
