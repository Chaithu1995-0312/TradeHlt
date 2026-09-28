"""EPIC-84 F3: the production CRT loader fails closed on ANY missing key.

User rule 2026-09-28: no defaults, no fallbacks. Before this, deleting e.g. sl_atr_buffer from
the active registry loaded silently with the CRTConfig code value 0.2 (DC-CONFIG-MISSING-KEY-
REJECT-01 section 2 proof). Now every CRTConfig field removed one at a time must raise
ConfigKeyMissingError naming it.
"""
import dataclasses
import json
import shutil
from pathlib import Path

import pytest

from config_layer.production_config import load_prod_config_from_registry
from config_layer.state_identity import CRTConfig
from config_layer.strict_config import ConfigKeyMissingError

REPO = Path(__file__).resolve().parents[1]
PROD = REPO / "configs" / "production"
ACTIVE = (PROD / "ACTIVE_VERSION").read_text(encoding="utf-8").strip()
FIELDS = [f.name for f in dataclasses.fields(CRTConfig)]


def _write(tmp_path: Path, version: str, data: dict) -> str:
    reg = tmp_path / "reg"
    reg.mkdir(exist_ok=True)
    (reg / f"{version}.json").write_text(json.dumps(data), encoding="utf-8")
    return str(reg)


def _active() -> dict:
    return json.loads((PROD / f"{ACTIVE}.json").read_text(encoding="utf-8"))


def test_active_config_loads_complete():
    cfg = load_prod_config_from_registry(ACTIVE, "XAUUSD")
    assert isinstance(cfg, CRTConfig)


def test_the_original_sl_atr_buffer_proof_now_raises(tmp_path):
    data = _active()
    data["params"].pop("sl_atr_buffer", None)
    data["crt_engine"].pop("sl_atr_buffer", None)
    reg = _write(tmp_path, ACTIVE, data)
    with pytest.raises(ConfigKeyMissingError) as ei:
        load_prod_config_from_registry(ACTIVE, "XAUUSD", registry_dir=reg, verify_hash=False)
    assert any("sl_atr_buffer" in m for m in ei.value.missing)
    assert ACTIVE in str(ei.value)


@pytest.mark.parametrize("field", FIELDS)
def test_every_crtconfig_field_removed_fails_closed(tmp_path, field):
    data = _active()
    present = False
    for sec in ("params", "crt_engine", "engine_runner"):
        if field in data.get(sec, {}):
            data[sec].pop(field)
            present = True
    if not present:
        pytest.skip(f"{field} is supplied by a derived path, not a declared key")
    reg = _write(tmp_path, ACTIVE, data)
    with pytest.raises(ConfigKeyMissingError) as ei:
        load_prod_config_from_registry(ACTIVE, "XAUUSD", registry_dir=reg, verify_hash=False)
    assert any(m.endswith(":" + field) for m in ei.value.missing), ei.value.missing


@pytest.mark.parametrize("section", ["crt_engine", "engine_runner", "params"])
def test_missing_required_section_fails_closed(tmp_path, section):
    data = _active()
    data.pop(section)
    reg = _write(tmp_path, ACTIVE, data)
    with pytest.raises(ConfigKeyMissingError) as ei:
        load_prod_config_from_registry(ACTIVE, "XAUUSD", registry_dir=reg, verify_hash=False)
    assert section in ei.value.missing


def test_unknown_key_still_rejected(tmp_path):
    data = _active()
    data["crt_engine"]["no_such_crt_field"] = 1
    reg = _write(tmp_path, ACTIVE, data)
    with pytest.raises(ValueError, match="unknown override key"):
        load_prod_config_from_registry(ACTIVE, "XAUUSD", registry_dir=reg, verify_hash=False)


@pytest.mark.parametrize("legacy", ["v1_multi_2026_03", "v2_test", "v3_multi_2026_06"])
def test_incomplete_legacy_configs_refuse_to_load(legacy):
    """User decision D2 (2026-09-28): in-use configs are completed; the rest stay on disk
    untouched and refuse to load."""
    with pytest.raises(ConfigKeyMissingError):
        load_prod_config_from_registry(legacy, "XAUUSD", verify_hash=False)


@pytest.mark.parametrize("version", [
    "v2_htfcrt_2026_08", "v5_htfcrt_sot_dual_k23_2026_09", "v2_htfcrt_k23_shadow_2026_09",
    "v2_dispkill_shadow_2026_08", "v4_crt_sot_2026_08", "v2_multi_2026_04",
    "v2_htfcrt_objgate_shadow_2026_08", "v2_multi_bitnet_shadow_2026_07",
    "v2_multi_dimfix_shadow_2026_07", "v3_unified_market_structure_2026_09",
    "v4_dual_construction_2026_09", "v2_multi_2026_04_v3session_probe",
])
def test_in_use_configs_are_complete(version):
    assert isinstance(load_prod_config_from_registry(version, "XAUUSD"), CRTConfig)
