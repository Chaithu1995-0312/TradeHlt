"""
Strategy Registry floor (target-strategy-architecture.md §13 item5 / §8 / §14.C).

StrategyPackage is a PROJECTION over already-governed config sections + model
registries — these tests pin the projection's shape and the registry's
save/load/resolve round trip, not any new formula authority.
"""
from __future__ import annotations

import json

import pytest

from strategies.strategy_package import StrategyPackage
from strategies.strategy_registry import StrategyNotFoundError, StrategyRegistry


def test_from_active_config_projects_governed_sections():
    pkg = StrategyPackage.from_active_config("XAUUSD")
    assert pkg.version  # non-empty — the active PROD_VERSION
    assert "body_ratio_min" in pkg.thresholds
    assert pkg.risk["min_rr_ratio"] is not None
    assert pkg.provenance["config_hash"]
    assert pkg.provenance["instrument"] == "XAUUSD"
    assert len(pkg.features_used) > 0


def test_content_hash_is_stable_and_order_independent():
    a = StrategyPackage.from_active_config("XAUUSD")
    b = StrategyPackage.from_active_config("XAUUSD")
    assert a.content_hash() == b.content_hash()


def test_content_hash_changes_with_content():
    a = StrategyPackage.from_active_config("XAUUSD")
    b = StrategyPackage(
        name=a.name, version=a.version, features_used=a.features_used,
        thresholds={**a.thresholds, "body_ratio_min": 0.999},
        model=a.model, risk=a.risk, provenance=a.provenance,
    )
    assert a.content_hash() != b.content_hash()


def test_to_dict_from_dict_round_trip():
    pkg = StrategyPackage.from_active_config("BNBUSDT")
    restored = StrategyPackage.from_dict(json.loads(json.dumps(pkg.to_dict(), default=str)))
    assert restored == pkg


def test_registry_save_load_round_trip(tmp_path):
    reg = StrategyRegistry(strategies_dir=tmp_path)
    pkg = StrategyPackage.from_active_config("XAUUSD", name="test_xau_v1", version="t1")
    path = reg.save(pkg)
    assert path.is_file()
    loaded = reg.load("test_xau_v1", "t1")
    assert loaded == pkg


def test_registry_load_missing_raises():
    reg = StrategyRegistry(strategies_dir="___does_not_exist___")
    with pytest.raises(StrategyNotFoundError):
        reg.load("nope", "v0")


def test_resolve_for_instrument_falls_back_to_live_projection(tmp_path):
    reg = StrategyRegistry(strategies_dir=tmp_path)
    pkg = reg.resolve_for_instrument("XAUUSD")
    assert pkg.provenance["instrument"] == "XAUUSD"


def test_resolve_for_instrument_prefers_saved_package(tmp_path):
    reg = StrategyRegistry(strategies_dir=tmp_path)
    saved = StrategyPackage.from_active_config("XAUUSD", name="active_xauusd", version="pinned_v1")
    reg.save(saved)
    resolved = reg.resolve_for_instrument("XAUUSD")
    assert resolved == saved


def test_list_versions_maps_strategy_to_config():
    reg = StrategyRegistry()
    for row in reg.list_versions():
        assert "name" in row and "config_version" in row and "config_hash" in row
