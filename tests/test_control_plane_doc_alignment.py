from __future__ import annotations

from pathlib import Path

from src.control_plane.registry import core_command_specs


def test_agents_path_alignment() -> None:
    content = Path("AGENTS.md").read_text(encoding="utf-8")
    assert "production_configs/{version}.json" not in content
    assert "python runtime/baseline_capture.py" not in content
    assert "configs/production/{version}.json" in content
    assert "python src/runtime/baseline_capture.py" in content


def test_cli_matrix_contains_all_core_command_ids() -> None:
    cli_matrix = Path("docs/reference/cli-matrix.md").read_text(encoding="utf-8")
    assert "Suggested Next" in cli_matrix
    for spec in core_command_specs():
        assert f"`{spec.id}`" in cli_matrix
