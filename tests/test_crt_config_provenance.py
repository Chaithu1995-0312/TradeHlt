"""P1 observe floors for CRTConfig construction provenance (F-057 class)."""
from __future__ import annotations

import os

import pytest

from config_layer.config_builder import ConfigBuilder
from config_layer.crt_config_provenance import (
    ConstructionMode,
    clear_registry,
    compare_surfaces,
    fingerprint,
    get_provenance,
    require_mode,
    schema_fingerprint,
)
from config_layer.production_config import get_active_version, load_prod_config_from_registry
from config_layer.state_identity import CRTConfig


@pytest.fixture(autouse=True)
def _clear_prov():
    clear_registry()
    yield
    clear_registry()


def test_builder_stamps_router_base():
    cfg = ConfigBuilder.build("XAUUSD")
    prov = get_provenance(cfg)
    assert prov.mode == ConstructionMode.ROUTER_BASE
    assert prov.instrument == "XAUUSD"


def test_prod_registry_restamps_production_merged():
    ver = get_active_version()
    cfg = load_prod_config_from_registry(ver, "XAUUSD")
    prov = get_provenance(cfg)
    assert prov.mode == ConstructionMode.PRODUCTION_MERGED
    assert prov.version == ver
    assert prov.instrument == "XAUUSD"


def test_from_existing_stamps_explicit():
    base = ConfigBuilder.build("XAUUSD")
    out = ConfigBuilder.from_existing("XAUUSD", base, extra_overrides={"body_ratio_min": 0.55})
    prov = get_provenance(out)
    assert prov.mode == ConstructionMode.EXPLICIT
    assert out.body_ratio_min == 0.55


def test_fingerprint_diverges_router_vs_prod_xauusd():
    """F-057 visibility: bare builder ≠ production merge on XAUUSD."""
    ver = get_active_version()
    router = ConfigBuilder.build("XAUUSD")
    prod = load_prod_config_from_registry(ver, "XAUUSD")
    assert fingerprint(router) != fingerprint(prod)
    assert fingerprint(prod) != schema_fingerprint()


def test_compare_surfaces_structure():
    report = compare_surfaces("XAUUSD")
    assert report["router_equals_prod"] is False
    assert report["production_merged"]["mode"] == ConstructionMode.PRODUCTION_MERGED.value
    assert report["router_base"]["mode"] == ConstructionMode.ROUTER_BASE.value


def test_require_mode_non_strict_warns_only():
    cfg = ConfigBuilder.build("XAUUSD")
    # Should not raise without CRT_CONFIG_STRICT
    os.environ.pop("CRT_CONFIG_STRICT", None)
    mode = require_mode(
        cfg,
        {ConstructionMode.PRODUCTION_MERGED},
        context="test_non_strict",
    )
    assert mode == ConstructionMode.ROUTER_BASE


def test_require_mode_strict_raises(monkeypatch):
    monkeypatch.setenv("CRT_CONFIG_STRICT", "1")
    cfg = ConfigBuilder.build("XAUUSD")
    with pytest.raises(RuntimeError, match="F-057"):
        require_mode(
            cfg,
            {ConstructionMode.PRODUCTION_MERGED},
            context="test_strict",
        )


def test_assert_product_rejects_router_base():
    from config_layer.crt_config_provenance import assert_product_crt_config

    cfg = ConfigBuilder.build("XAUUSD")
    with pytest.raises(RuntimeError, match="ROUTER_BASE"):
        assert_product_crt_config(cfg, context="unit", allow_router_base=False)


def test_assert_product_allows_router_with_escape():
    from config_layer.crt_config_provenance import assert_product_crt_config

    cfg = ConfigBuilder.build("XAUUSD")
    mode = assert_product_crt_config(cfg, context="unit", allow_router_base=True)
    assert mode == ConstructionMode.ROUTER_BASE


def test_assert_product_allows_production_merged():
    from config_layer.crt_config_provenance import assert_product_crt_config

    cfg = load_prod_config_from_registry(get_active_version(), "XAUUSD")
    mode = assert_product_crt_config(cfg, context="unit", allow_router_base=False)
    assert mode == ConstructionMode.PRODUCTION_MERGED


def test_mark_explicit_makes_product_admissible():
    from config_layer.crt_config_provenance import assert_product_crt_config, mark_explicit

    cfg = mark_explicit(CRTConfig(body_ratio_min=0.55), instrument="TEST")
    mode = assert_product_crt_config(cfg, context="unit", allow_router_base=False)
    assert mode == ConstructionMode.EXPLICIT
    assert cfg.body_ratio_min == 0.55
