"""
P1 2026-07-22 — BitNet registry governance (Exists ≠ Selected ≠ Enabled).

Catalog: models/bitnet/bitnet_registry.json
  * dual-schema fork documented (legacy_6 vs export_35)
  * no active selection while use_bitnet=false
  * enable without selection → fail-closed
  * composition_default → model.json for bitnet_score
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "models" / "bitnet" / "bitnet_registry.json"


def test_registry_file_is_catalogued_not_empty():
    assert REGISTRY.is_file()
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert data.get("_governance"), "governance block required"
    gov = data["_governance"]
    assert gov.get("composition_default_version")
    assert gov.get("require_selection_when_enabled") is True
    entries = {
        k: v for k, v in data.items()
        if isinstance(v, dict) and not k.startswith("_") and "model_file" in v
    }
    assert len(entries) >= 2
    assert all(v.get("active") is False for v in entries.values()), (
        "no entry may be active while use_bitnet is false on the active config"
    )


def test_dual_schema_fork_is_explicit():
    from bitnet.bitnet_registry import BitNetRegistry

    reg = BitNetRegistry(REGISTRY).load()
    report = reg.dual_schema_report()
    assert report["fork_present"] is True
    assert 6 in report["distinct_feature_schema_dims"]
    assert 35 in report["distinct_feature_schema_dims"]
    assert report["selected"] is None
    assert report["composition_default"] == "legacy_6_root_model_json"


def test_composition_default_resolves_to_legacy_model_json():
    from bitnet.bitnet_registry import resolve_composition_model_path
    from bitnet.composition import reset_default_composition, get_default_composition

    path = resolve_composition_model_path()
    assert path.replace("\\", "/") in {"model.json", str((ROOT / "model.json").resolve())}
    # normalize: registry stores model.json
    assert Path(path).name == "model.json" or path.endswith("model.json")

    reset_default_composition()
    comp = get_default_composition()
    # predict should work on 6-key dict
    score = float(comp.predict({
        "body_ratio": 0.7,
        "retest_depth": 0.3,
        "disp_strength": 0.5,
        "atr": 0.01,
        "candles_since_retest": 2.0,
        "double_sweep": 0.0,
    }).confidence)
    assert 0.0 <= score <= 1.0
    reset_default_composition()


def test_assert_serve_allowed_noop_when_disabled():
    from bitnet.bitnet_registry import assert_serve_allowed
    assert_serve_allowed(use_bitnet=False)  # must not raise


def test_assert_serve_allowed_fails_closed_when_enabled_without_selection():
    from bitnet.bitnet_registry import BitNetRegistryError, assert_serve_allowed

    with pytest.raises(BitNetRegistryError, match="no active selection"):
        assert_serve_allowed(use_bitnet=True)


def test_enable_with_selection_passes_serve_contract(tmp_path: Path):
    """When exactly one entry is active and artifact exists, enable is allowed."""
    from bitnet.bitnet_registry import BitNetRegistry, BitNetRegistryError

    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    data["legacy_6_root_model_json"]["active"] = True
    path = tmp_path / "bitnet_registry.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    reg = BitNetRegistry(path).load()
    assert reg.selected_version() == "legacy_6_root_model_json"
    reg.assert_serve_allowed(use_bitnet=True)  # no raise

    # Multiple actives fail at load
    data["export_v5_35_results"]["active"] = True
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(BitNetRegistryError, match="multiple active"):
        BitNetRegistry(path).load()


def test_model_resolver_bitnet_still_null_selection():
    from config_layer.model_resolver import resolve_model

    r = resolve_model("bitnet", require_identity_parity=True)
    assert r.version is None
    assert r.artifact_path is None
    assert r.identity_parity is True
    assert r.spine_wired is False


def test_active_config_use_bitnet_false():
    from config_layer.production_config import get_prod_section
    assert get_prod_section("crt_engine").get("use_bitnet") is False


def test_how_path_and_composition_default_are_different_schemas():
    """Documents the dual-schema fork: HOW pin ≠ composition serve artifact."""
    from config_layer.production_config import get_prod_section
    from bitnet.bitnet_registry import BitNetRegistry

    how = str(get_prod_section("engine_runner").get("model_path", "")).replace("\\", "/")
    reg = BitNetRegistry(REGISTRY).load()
    comp = reg.resolve_composition_model_path().replace("\\", "/")
    assert "model_export_format" in how or how.endswith("model_export_format.json")
    assert Path(comp).name == "model.json" or comp.endswith("model.json")
    how_entry = reg.get("export_v5_35_results")
    comp_entry = reg.composition_default_entry()
    assert how_entry and comp_entry
    assert how_entry.feature_schema_dim != comp_entry.feature_schema_dim
