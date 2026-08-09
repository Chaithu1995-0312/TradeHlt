"""
CRT config reachability parity — Phase 5 CRT Closure.

Pins docs/governance/crt_config_reachability.json against CRTConfig fields and
the production load path for BNBUSDT.
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from config_layer.state_identity import CRTConfig
from config_layer.market_router import classify_market
from config_layer.production_config import PROD_VERSION, get_full_config_dict, load_prod_config_from_registry

_ROOT = Path(__file__).resolve().parents[1]
_PATH = _ROOT / "docs" / "governance" / "crt_config_reachability.json"


def _load() -> dict:
    assert _PATH.is_file(), f"missing reachability artifact: {_PATH}"
    with open(_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def test_artifact_schema_and_field_coverage():
    d = _load()
    assert d["schema"] == "crt_config_reachability.v1"
    assert d["phase"] == 5
    assert d["phase5_status"] == "PASS"
    code_fields = {f.name for f in dataclasses.fields(CRTConfig)}
    matrix_keys = {r["key"] for r in d["matrix"]}
    assert matrix_keys == code_fields
    assert d["field_count"] == len(code_fields)
    # IC-007 PLAN-001 added retest_min_depth_atr_fraction (was 48).
    assert d["field_count"] >= 49
    assert "retest_min_depth_atr_fraction" in code_fields


def test_no_unexpected_unreachable():
    """Only documented special statuses may be non-REACHABLE / non-CONSUMED_DYNAMIC."""
    d = _load()
    allowed_special = {
        "score_threshold": "LEGACY_ONLY",
        "news_blackout_minutes": "DEAD_LOADED",
    }
    for row in d["matrix"]:
        st = row["consumption_status"]
        if st in ("REACHABLE", "CONSUMED_DYNAMIC"):
            continue
        assert row["key"] in allowed_special, f"unexpected status {st} for {row['key']}"
        assert allowed_special[row["key"]] == st


def test_intent_tp1_multipliers_dynamic():
    d = _load()
    intent_keys = {
        "tp1_atr_multiplier_breakout",
        "tp1_atr_multiplier_pullback",
        "tp1_atr_multiplier_liq_sweep",
        "tp1_atr_multiplier_reversal",
    }
    by_key = {r["key"]: r for r in d["matrix"]}
    for k in intent_keys:
        assert by_key[k]["consumption_status"] == "CONSUMED_DYNAMIC"


def test_bnb_load_matches_prod_profile_keys():
    """Params-section knobs must survive load_prod_config_from_registry for BNBUSDT."""
    full = get_full_config_dict()
    params = full.get("params") or {}
    cfg = load_prod_config_from_registry(PROD_VERSION, "BNBUSDT")
    for k in (
        "body_ratio_min",
        "atr_multiplier_min",
        "retest_depth_max",
        "expansion_atr_min_distance",
        "retest_atr_depth_fraction",
    ):
        assert k in params, f"params missing {k}"
        assert getattr(cfg, k) == params[k]


def test_bnb_market_router_class_remediated():
    """F-057 remediation (2026-07-29): market_router is config-driven and
    BNBUSDT is correctly classified CRYPTO in market_router.symbol_map."""
    assert classify_market("BNBUSDT") == "CRYPTO"
    d = _load()
    assert d["load_chain"]["bnb_market_class_bug"]["classify_market('BNBUSDT')"] == "CRYPTO"
    assert d["load_chain"]["bnb_market_class_bug"]["severity"] == "REMEDIATED"


def test_unknown_instrument_fails_closed():
    """F-057 / target-strategy-architecture.md sec14.A: no silent FOREX
    default for an instrument absent from market_router.symbol_map."""
    import pytest
    from config_layer.market_router import UnknownInstrumentError
    with pytest.raises(UnknownInstrumentError):
        classify_market("NOTAREALSYMBOL")


def test_hardcoded_high_risk_present():
    d = _load()
    by_id = {h["id"]: h for h in d["hardcoded_shadows"]}
    assert "HC-G-WEIGHTS" in by_id
    assert "HC-RETEST-MIN-DEPTH" in by_id
    # PLAN-001 remediated the retest min-depth hardcode into HOW.
    assert by_id["HC-RETEST-MIN-DEPTH"].get("severity") == "REMEDIATED"
