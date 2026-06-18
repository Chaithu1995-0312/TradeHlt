"""Unit floor for dot_graph_context — flow resolution + architectural graph context.

Covers the public contract used by the Context route: file→node mapping, flow resolution,
the flow-slice vs global-neighbourhood branches, fail-open behaviour, and the architectural
vocabulary (depends_on / imported_by — never caller/callee).
"""
from __future__ import annotations

from pathlib import Path

from src.control_plane.dot_graph_context import (
    _file_to_module,
    extract_graph_context,
    resolve_flow,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]


# ── file → module ─────────────────────────────────────────────────────────────
def test_file_to_module_basic():
    assert _file_to_module("src/control_plane/server.py", _REPO_ROOT) == "control_plane.server"
    assert _file_to_module(r"D:\x\src\core\engine_runner.py", _REPO_ROOT) == "core.engine_runner"


def test_file_to_module_package_init():
    assert _file_to_module("src/core/__init__.py", _REPO_ROOT) == "core"


def test_file_to_module_non_src_returns_none():
    assert _file_to_module("scripts/analysis/gen_pyan.py", _REPO_ROOT) is None
    assert _file_to_module("README.md", _REPO_ROOT) is None


# ── flow resolution ───────────────────────────────────────────────────────────
def test_resolve_flow_picks_runtime():
    cc = [{"file": "src/core/engine_runner.py"}, {"file": "src/runtime/backtest_v2.py"}]
    flow = resolve_flow(cc, _REPO_ROOT)
    assert flow is not None and flow["flow"] == "runtime"


def test_resolve_flow_none_for_unmapped():
    assert resolve_flow([{"file": "scripts/x.py"}], _REPO_ROOT) is None
    assert resolve_flow([], _REPO_ROOT) is None


# ── graph context ─────────────────────────────────────────────────────────────
def test_flow_slice_branch_and_vocabulary():
    cc = [{"file": "src/control_plane/server.py"}, {"file": "src/control_plane/jobs.py"}]
    ctx = extract_graph_context(cc, _REPO_ROOT)
    assert ctx["available"] is True
    assert ctx["source"] == "flow_slice"
    assert ctx["flow"] == "control_plane"
    assert ctx["edge_count"] > 0
    # architectural vocabulary only — never caller/callee
    node = ctx["nodes"][0]
    assert set(node) == {"module", "depends_on", "imported_by"}


def test_unavailable_when_no_modules():
    ctx = extract_graph_context([{"file": "scripts/only.py"}], _REPO_ROOT)
    assert ctx == {"available": False}


def test_fail_open_missing_repo(tmp_path):
    # No flow_context/, flow_graphs/, or graph.dot under tmp_path → degrade, never raise.
    cc = [{"file": "src/core/engine_runner.py"}]
    ctx = extract_graph_context(cc, tmp_path)
    assert ctx == {"available": False}
