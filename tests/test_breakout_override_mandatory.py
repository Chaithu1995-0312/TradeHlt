"""EPIC-84 O1: crt_engine.breakout_disp_threshold_overrides is mandatory; the loader resolves it
into CRTConfig so the CRT engine and the ExecutionPlanner use the identical per-symbol value."""
import json
from pathlib import Path

import pytest

from config_layer.execution_planner import planner_config_from_production
from config_layer.production_config import load_prod_config_from_registry
from config_layer.strict_config import ConfigKeyMissingError

REPO = Path(__file__).resolve().parents[1]
PROD = REPO / "configs" / "production"
ACTIVE = (PROD / "ACTIVE_VERSION").read_text(encoding="utf-8").strip()


def _active() -> dict:
    return json.loads((PROD / f"{ACTIVE}.json").read_text(encoding="utf-8"))


def _load(tmp_path: Path, data: dict, instrument: str):
    reg = tmp_path / "reg"
    reg.mkdir(exist_ok=True)
    (reg / f"{ACTIVE}.json").write_text(json.dumps(data), encoding="utf-8")
    return load_prod_config_from_registry(ACTIVE, instrument, registry_dir=str(reg),
                                          verify_hash=False)


def test_active_declares_the_map():
    assert _active()["crt_engine"]["breakout_disp_threshold_overrides"] == {}


def test_missing_map_fails_closed(tmp_path):
    data = _active()
    data["crt_engine"].pop("breakout_disp_threshold_overrides")
    with pytest.raises(ConfigKeyMissingError) as ei:
        _load(tmp_path, data, "XAUUSD")
    assert "breakout_disp_threshold_overrides" in ei.value.missing
    with pytest.raises(ConfigKeyMissingError):
        planner_config_from_production(data, "XAUUSD")


def test_symbol_override_reaches_engine_and_planner_identically(tmp_path):
    data = _active()
    data["crt_engine"]["breakout_disp_threshold_overrides"] = {"xauusd": 1.3}
    cfg_x = _load(tmp_path, data, "XAUUSD")
    assert cfg_x.breakout_disp_threshold == 1.3                      # CRT engine value
    assert planner_config_from_production(data, "XAUUSD")["breakout_disp_threshold"] == 1.3
    cfg_e = _load(tmp_path, data, "EURUSD")                           # not overridden
    glob = float(data["crt_engine"]["breakout_disp_threshold"])
    assert cfg_e.breakout_disp_threshold == glob
    assert planner_config_from_production(data, "EURUSD")["breakout_disp_threshold"] == glob


def test_params_global_wins_for_both(tmp_path):
    data = _active()
    data["params"]["breakout_disp_threshold"] = 1.7
    assert _load(tmp_path, data, "XAUUSD").breakout_disp_threshold == 1.7
    assert planner_config_from_production(data, "XAUUSD")["breakout_disp_threshold"] == 1.7


def test_conflicting_instrument_override_fails_closed(tmp_path):
    data = _active()
    data["crt_engine"]["breakout_disp_threshold_overrides"] = {"XAUUSD": 1.3}
    data["crt_engine"]["instrument_overrides"] = {"XAUUSD": {"breakout_disp_threshold": 1.4}}
    with pytest.raises(ValueError, match="declare it in one place|Declare it in one place"):
        _load(tmp_path, data, "XAUUSD")


def test_non_mapping_rejected(tmp_path):
    data = _active()
    data["crt_engine"]["breakout_disp_threshold_overrides"] = [1.3]
    with pytest.raises(TypeError):
        _load(tmp_path, data, "XAUUSD")
