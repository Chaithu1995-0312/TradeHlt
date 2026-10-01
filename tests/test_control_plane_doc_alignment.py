from __future__ import annotations

from pathlib import Path

from src.control_plane.registry import core_command_specs


def test_agents_path_alignment() -> None:
    # AGENTS.md is a pointer to CLAUDE.md (it deliberately holds no doctrine); the stale paths
    # must appear in neither, and the current ones live in CLAUDE.md.
    agents = Path("AGENTS.md").read_text(encoding="utf-8")
    manual = Path("CLAUDE.md").read_text(encoding="utf-8")
    assert "CLAUDE.md" in agents
    for content in (agents, manual):
        assert "production_configs/{version}.json" not in content
        assert "python runtime/baseline_capture.py" not in content
    assert "configs/production/" in manual
    assert "python src/runtime/baseline_capture.py" in manual


def test_cli_matrix_contains_all_core_command_ids() -> None:
    cli_matrix = Path("docs/reference/cli-matrix.md").read_text(encoding="utf-8")
    assert "Suggested Next" in cli_matrix
    for spec in core_command_specs():
        assert f"`{spec.id}`" in cli_matrix
