"""Workflow-DAG completeness guard (M7).

The Workflow-tab Mermaid is hand-drawn, so it can silently drift from the codebase's canonical
pipeline (`registry.WORKFLOW_STAGE_ORDER`). It once eliminated the entire "Replay & Backtest" stage.
This test makes that class of regression a failure: every pipeline stage that has commands mapped to
it must be represented by at least one command node in the DAG's `NODE_TO_CMD`.
"""
from __future__ import annotations

import re
from pathlib import Path

from src.control_plane.registry import (
    WORKFLOW_STAGE_ORDER, _WORKFLOW_STAGE_BY_COMMAND, core_command_specs,
)

_PANEL = Path(__file__).resolve().parents[1] / "ui_kits" / "control_plane" / "WorkflowPanel.jsx"


def _dag_command_ids() -> set[str]:
    """Command ids referenced as Mermaid node→command values in WorkflowPanel.jsx."""
    text = _PANEL.read_text(encoding="utf-8")
    all_ids = {s.id for s in core_command_specs()}
    quoted = set(re.findall(r'"([a-z_]+\.[a-z_0-9.]+)"', text))
    return quoted & all_ids


def _stages_with_commands() -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for cmd, stage in _WORKFLOW_STAGE_BY_COMMAND.items():
        out.setdefault(stage, set()).add(cmd)
    return out


def test_every_pipeline_stage_is_represented_in_the_dag():
    dag = _dag_command_ids()
    by_stage = _stages_with_commands()
    missing = [stage for stage in WORKFLOW_STAGE_ORDER
               if by_stage.get(stage) and not (by_stage[stage] & dag)]
    assert not missing, (
        f"Workflow DAG silently eliminates pipeline stage(s): {missing} — no command from each "
        f"appears in WorkflowPanel.jsx NODE_TO_CMD. (registry.WORKFLOW_STAGE_ORDER is the authority.)"
    )


def test_replay_and_backtest_stage_present():
    # The exact regression that prompted this guard: Replay & Backtest had been dropped entirely.
    assert "backtest.v2" in _dag_command_ids(), \
        "the Replay & Backtest stage (backtest.v2) is missing from the Workflow DAG"
