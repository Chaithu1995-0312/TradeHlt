"""Flow-manifest drift floor — the enforceable contract for the flow-scoped LLM context layer.

Mirrors tests/test_doc_citations.py / tests/test_current_findings.py (read-an-artifact-and-assert).
`flow_context/<flow>.json` is the ONLY hand-authored artifact in the flow layer; everything else
(`flow_graphs/<flow>.dot`) is derived from it ∩ the AST import graph (`gen_code_map.build_graph()`).
This test is what makes "manifest = single source of truth" safe — it fails the moment a manifest
drifts from the code or the committed flow graph goes stale.

For each manifest it asserts:
  (a) shape — required keys present, `flow` matches filename, non-empty `modules`/`keywords`;
  (b) the linked human `doc` exists on disk (Layer-1 reuse, not duplication);
  (c) every `modules` entry — and the `entrypoint` — resolves to a real node in graph.dot;
  (d) `flow_graphs/<flow>.dot` regenerates byte-identically (rerun gen_flow_graphs.py to cure).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_FLOW_CONTEXT = _REPO_ROOT / "flow_context"
_FLOW_GRAPHS = _REPO_ROOT / "flow_graphs"

# gen_flow_graphs / gen_code_map are sibling scripts — make them importable.
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "analysis"))
import gen_flow_graphs as gfg  # noqa: E402
from gen_code_map import build_graph  # noqa: E402

_MANIFESTS = sorted(_FLOW_CONTEXT.glob("*.json"))
_REQUIRED_KEYS = ("flow", "title", "doc", "service_ids", "entrypoint", "modules", "keywords",
                  "command_ids", "inputs", "outputs")


@pytest.fixture(scope="module")
def graph():
    """(module_set, edges) from the live AST import graph — single derivation source."""
    _modules, module_set, _top, edges = build_graph()
    return module_set, edges


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_manifests_present():
    assert _MANIFESTS, "expected at least one flow_context/*.json manifest"


@pytest.mark.parametrize("path", _MANIFESTS, ids=lambda p: p.stem)
def test_manifest_shape(path):
    data = _load(path)
    for key in _REQUIRED_KEYS:
        assert key in data, f"{path.name}: missing required key '{key}'"
    assert data["flow"] == path.stem, f"{path.name}: 'flow' must equal filename stem"
    assert isinstance(data["modules"], list) and data["modules"], f"{path.name}: 'modules' must be non-empty"
    assert isinstance(data["keywords"], list) and data["keywords"], f"{path.name}: 'keywords' must be non-empty"
    cmds = data["command_ids"]
    assert isinstance(cmds, list) and all(isinstance(c, str) for c in cmds), \
        f"{path.name}: 'command_ids' must be a list of strings"
    for io in ("inputs", "outputs"):
        vals = data.get(io, [])
        assert isinstance(vals, list) and all(isinstance(v, str) for v in vals), \
            f"{path.name}: '{io}' must be a list of strings"


@pytest.mark.parametrize("path", _MANIFESTS, ids=lambda p: p.stem)
def test_doc_exists(path):
    data = _load(path)
    doc = _REPO_ROOT / data["doc"]
    assert doc.is_file(), f"{path.name}: linked doc '{data['doc']}' not found (Layer-1 reuse contract)"


@pytest.mark.parametrize("path", _MANIFESTS, ids=lambda p: p.stem)
def test_modules_and_entrypoint_resolve(path, graph):
    module_set, _edges = graph
    data = _load(path)
    missing = sorted(m for m in data["modules"] if m not in module_set)
    assert not missing, (
        f"{path.name}: module(s) absent from graph.dot node set (drift): {missing}. "
        f"Fix the manifest or regenerate graph.dot via gen_code_map.py."
    )
    assert data["entrypoint"] in module_set, (
        f"{path.name}: entrypoint '{data['entrypoint']}' is not a graph.dot node"
    )


@pytest.mark.parametrize("path", _MANIFESTS, ids=lambda p: p.stem)
def test_flow_graph_byte_identical(path, graph):
    module_set, edges = graph
    data = gfg.load_manifest(path)
    expected = gfg.emit_dot(gfg.slice_flow(data, module_set, edges))
    committed = _FLOW_GRAPHS / f"{data['flow']}.dot"
    assert committed.is_file(), f"missing flow_graphs/{data['flow']}.dot — run gen_flow_graphs.py"
    assert committed.read_text(encoding="utf-8") == expected, (
        f"flow_graphs/{data['flow']}.dot is stale — rerun: python scripts/analysis/gen_flow_graphs.py"
    )
