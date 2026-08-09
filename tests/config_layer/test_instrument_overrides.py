"""Tests for the governed per-instrument CRT override resolver (Phase 3).

Covers resolve_instrument_overrides + its end-to-end effect through
load_prod_config_from_registry (per-instrument wins over params, never overwritten).
"""

import json

import pytest

from config_layer.production_config import (
    load_prod_config_from_registry,
    resolve_instrument_overrides,
)


# ── resolver unit behavior ───────────────────────────────────────

def _cfg(overrides):
    return {"instrument_overrides": overrides}


def test_resolver_hit_case_insensitive_and_coerced():
    ce = _cfg({"bnbusdt": {"weak_link_weight": 0.0, "conf_weights": [0.54, 0.0, 0.23, 0.23]}})
    out = resolve_instrument_overrides(ce, "BNBUSDT")
    assert out["weak_link_weight"] == 0.0
    assert out["conf_weights"] == (0.54, 0.0, 0.23, 0.23)  # list coerced to tuple


def test_resolver_miss_returns_empty():
    ce = _cfg({"BNBUSDT": {"weak_link_weight": 0.0}})
    assert resolve_instrument_overrides(ce, "EURUSD") == {}


def test_resolver_no_block_returns_empty():
    assert resolve_instrument_overrides({}, "BNBUSDT") == {}
    assert resolve_instrument_overrides(None, "BNBUSDT") == {}
    assert resolve_instrument_overrides({"instrument_overrides": {}}, "BNBUSDT") == {}


def test_resolver_unknown_key_raises():
    ce = _cfg({"BNBUSDT": {"not_a_real_field": 1.0}})
    with pytest.raises(ValueError):
        resolve_instrument_overrides(ce, "BNBUSDT")


# ── end-to-end through the registry loader ───────────────────────

@pytest.fixture
def temp_registry(tmp_path):
    """Minimal but hash-valid-free registry: load with verify_hash=False."""
    def _build(instrument_overrides):
        data = {
            "params": {"score_threshold": 0.45, "body_ratio_min": 0.70},
            "crt_engine": {
                "ema_fast": 2, "ema_slow": 5,
                "conf_weights": [0.35, 0.35, 0.15, 0.15],
                "weak_link_weight": 0.30,
            },
        }
        if instrument_overrides is not None:
            data["crt_engine"]["instrument_overrides"] = instrument_overrides
        p = tmp_path / "v_test.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        return p
    return _build


def test_end_to_end_override_wins_over_params(temp_registry, monkeypatch):
    import config_layer.production_config as pc
    reg = temp_registry({"BNBUSDT": {"weak_link_weight": 0.0,
                                     "conf_weights": [0.538462, 0.0, 0.230769, 0.230769]}})
    monkeypatch.setattr(pc, "_get_registry_path", lambda *a, **k: reg)

    bnb = load_prod_config_from_registry("v_test", "BNBUSDT", verify_hash=False)
    eur = load_prod_config_from_registry("v_test", "EURUSD", verify_hash=False)

    # per-instrument override applied for BNBUSDT
    assert bnb.weak_link_weight == 0.0
    assert bnb.conf_weights[1] == 0.0
    # EURUSD untouched — keeps the global crt_engine values
    assert eur.weak_link_weight == 0.30
    assert eur.conf_weights == (0.35, 0.35, 0.15, 0.15)
    # everything else identical between the two (only the 2 override keys differ)
    assert bnb.score_threshold == eur.score_threshold
    assert bnb.ema_fast == eur.ema_fast


def test_end_to_end_no_overrides_block_is_inert(temp_registry, monkeypatch):
    import config_layer.production_config as pc
    reg = temp_registry(None)
    monkeypatch.setattr(pc, "_get_registry_path", lambda *a, **k: reg)
    cfg = load_prod_config_from_registry("v_test", "BNBUSDT", verify_hash=False)
    assert cfg.weak_link_weight == 0.30
    assert cfg.conf_weights == (0.35, 0.35, 0.15, 0.15)
