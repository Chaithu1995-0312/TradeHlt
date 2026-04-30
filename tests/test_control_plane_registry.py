from __future__ import annotations

import sys
from pathlib import Path

from src.control_plane.registry import REPO_ROOT, command_map, render_command, workflow_stage_order


def test_registry_contains_core_commands() -> None:
    specs = command_map()
    expected = {
        "data.prepare_data",
        "tuning.auto_tuner_multi",
        "validation.config_validator",
        "promotion.manager",
        "governance.orchestrator",
        "replay.unified",
        "backtest.v2",
        "backtest.bitnet",
        "baseline.capture",
        "live.inout_runner",
    }
    assert expected.issubset(specs.keys())


def test_tutorial_mapping_and_stage_order() -> None:
    specs = command_map()
    stages = set(workflow_stage_order())
    assert stages
    for spec in specs.values():
        assert spec.workflow_stage in stages
        for next_id in spec.recommended_next_command_ids:
            assert next_id in specs


def test_render_command_module_mode() -> None:
    spec = command_map()["live.inout_runner"]
    cmd = render_command(spec, {"cycles": 10})
    assert cmd[:3] == [sys.executable, "-m", "inout.runner"]
    assert "--cycles" in cmd
    assert "10" in cmd


def test_render_command_subcommand_scoping_validator() -> None:
    spec = command_map()["validation.config_validator"]
    cmd = render_command(spec, {"subcommand": "validate-prod"})
    joined = " ".join(cmd)
    assert "validate-prod" in joined
    assert "--config-id" not in joined
    assert "--params" not in joined


def test_render_command_subcommand_scoping_promotion_list() -> None:
    spec = command_map()["promotion.manager"]
    cmd = render_command(spec, {"subcommand": "list"})
    joined = " ".join(cmd)
    assert " list" in f" {' '.join(cmd)}"
    assert "--data-dir" not in joined
    assert "--notes" not in joined


def test_render_command_exact_backtest_v2_minimal() -> None:
    spec = command_map()["backtest.v2"]
    cmd = render_command(spec, {"csv": "data/EURUSD_M15.csv"})
    expected_prefix = [sys.executable, str((REPO_ROOT / "src/runtime/backtest_v2.py").resolve())]
    assert cmd[:2] == expected_prefix
    assert "--csv" in cmd
    assert "data/EURUSD_M15.csv" in cmd
    assert "--instrument" in cmd and "AUTO" in cmd
