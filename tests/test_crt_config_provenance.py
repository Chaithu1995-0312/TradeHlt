"""P1 observe floors for CRTConfig construction provenance (F-057 class)."""
from __future__ import annotations
from tests.helpers.crt_config import crt_config_for_test, crt_test_fields

import dataclasses
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
    cfg = ConfigBuilder.build("XAUUSD", overrides=crt_test_fields())
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
    base = ConfigBuilder.build("XAUUSD", overrides=crt_test_fields())
    out = ConfigBuilder.from_existing("XAUUSD", base, extra_overrides={"body_ratio_min": 0.55})
    prov = get_provenance(out)
    assert prov.mode == ConstructionMode.EXPLICIT
    assert out.body_ratio_min == 0.55


def test_fingerprint_diverges_router_vs_prod_xauusd():
    """F-057 visibility: bare builder ≠ production merge on XAUUSD."""
    ver = get_active_version()
    router = ConfigBuilder.build("XAUUSD", overrides=crt_test_fields())
    prod = load_prod_config_from_registry(ver, "XAUUSD")
    assert fingerprint(router) != fingerprint(prod)
    # EPIC-84: the schema surface is field names + types (no values exist without a config).
    schema = schema_fingerprint()
    assert len(schema) == len(dataclasses.fields(type(prod)))
    assert all(isinstance(n, str) and isinstance(t, str) for n, t in schema)


def test_compare_surfaces_structure():
    report = compare_surfaces("XAUUSD")
    # EPIC-84: the class profile is reported as declared values vs production (no router base).
    assert report["router_equals_prod"] is False
    assert report["production_merged"]["mode"] == ConstructionMode.PRODUCTION_MERGED.value
    assert report["router_profile"]["class"] == "FOREX"
    assert report["router_profile"]["differs_from_prod"]
    assert report["schema"]["n_fields"] == len(report["schema"]["fields"])
    assert report["prod_declares_schema_fields"] is True


def test_require_mode_non_strict_warns_only():
    cfg = ConfigBuilder.build("XAUUSD", overrides=crt_test_fields())
    mode = require_mode(
        cfg,
        {ConstructionMode.PRODUCTION_MERGED},
        context="test_non_strict",
        fail_closed=False,
    )
    assert mode == ConstructionMode.ROUTER_BASE


def test_require_mode_strict_raises(monkeypatch):
    # The environment no longer influences strictness (EPIC-84): the env var is ignored.
    monkeypatch.delenv("CRT_CONFIG_STRICT", raising=False)
    cfg = ConfigBuilder.build("XAUUSD", overrides=crt_test_fields())
    with pytest.raises(RuntimeError, match="F-057"):
        require_mode(
            cfg,
            {ConstructionMode.PRODUCTION_MERGED},
            context="test_strict",
            fail_closed=True,
        )


def test_require_mode_fail_closed_is_required():
    cfg = ConfigBuilder.build("XAUUSD", overrides=crt_test_fields())
    with pytest.raises(TypeError):
        require_mode(cfg, {ConstructionMode.PRODUCTION_MERGED}, context="x")  # type: ignore[call-arg]


def test_assert_product_rejects_router_base():
    from config_layer.crt_config_provenance import assert_product_crt_config

    cfg = ConfigBuilder.build("XAUUSD", overrides=crt_test_fields())
    with pytest.raises(RuntimeError, match="ROUTER_BASE"):
        assert_product_crt_config(cfg, context="unit", allow_router_base=False)


def test_assert_product_allows_router_with_escape():
    from config_layer.crt_config_provenance import assert_product_crt_config

    cfg = ConfigBuilder.build("XAUUSD", overrides=crt_test_fields())
    mode = assert_product_crt_config(cfg, context="unit", allow_router_base=True)
    assert mode == ConstructionMode.ROUTER_BASE


def test_assert_product_allows_production_merged():
    from config_layer.crt_config_provenance import assert_product_crt_config

    cfg = load_prod_config_from_registry(get_active_version(), "XAUUSD")
    mode = assert_product_crt_config(cfg, context="unit", allow_router_base=False)
    assert mode == ConstructionMode.PRODUCTION_MERGED


def test_mark_explicit_makes_product_admissible():
    from config_layer.crt_config_provenance import assert_product_crt_config, mark_explicit

    cfg = mark_explicit(crt_config_for_test(body_ratio_min=0.55), instrument="TEST")
    mode = assert_product_crt_config(cfg, context="unit", allow_router_base=False)
    assert mode == ConstructionMode.EXPLICIT
    assert cfg.body_ratio_min == 0.55
