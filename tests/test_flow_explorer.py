"""Offline floor for the Flow/Module Explorer (M6) — list + flow/module detail assembly.

Exercises the dot_graph_context helpers the /flows and /flows/<flow>/context routes are built on,
without the HTTP layer: flow list, module code, module role, module I/O (depends_on/imported_by).
"""
from __future__ import annotations

from pathlib import Path

from src.control_plane.dot_graph_context import (
    list_flows, get_flow, build_module_code_context, module_role, module_neighbors,
    build_flow_code_context,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_list_flows_has_ordered_modules_and_io():
    flows = list_flows(_REPO_ROOT)
    names = {f["flow"] for f in flows}
    assert {"runtime", "governance", "training", "agent", "control_plane", "research"} <= names
    runtime = next(f for f in flows if f["flow"] == "runtime")
    # modules preserve start→end order (feature pipeline first, collector last)
    assert runtime["modules"][0] == "features.feature_pipeline"
    assert runtime["modules"][-1] == "core.collector"
    assert runtime["inputs"] and runtime["outputs"]   # I/O contract present


def test_get_flow_and_flow_code():
    man = get_flow("governance", _REPO_ROOT)
    assert man is not None and man["flow"] == "governance"
    assert build_flow_code_context(man, _REPO_ROOT)   # synthesized code from members
    assert get_flow("nope", _REPO_ROOT) is None


def test_module_detail_code_role_and_io():
    code = build_module_code_context("core.decision_engine", _REPO_ROOT)
    assert code and code[0]["source"] == "flow_module"
    assert module_role("core.decision_engine", _REPO_ROOT)            # docstring line 1
    io = module_neighbors("core.decision_engine", _REPO_ROOT)
    assert "core.engine_runner" in io["imported_by"]                  # impact radius (deterministic)
    assert isinstance(io["depends_on"], list)


def test_module_helpers_fail_open():
    assert build_module_code_context("does.not.exist", _REPO_ROOT) == []
    assert module_role("does.not.exist", _REPO_ROOT) is None
    assert module_neighbors("does.not.exist", _REPO_ROOT) == {
        "module": "does.not.exist", "depends_on": [], "imported_by": []
    }
