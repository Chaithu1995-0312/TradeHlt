"""
dot_graph_context.py — flow resolution + architectural graph context for Context Reports.

Given the code that executed in a run (the `code_context` produced by `code_context_extractor`),
this resolves which *flow* the run belongs to and loads that flow's small dependency-graph slice
(`flow_graphs/<flow>.dot`, derived from the hand-authored `flow_context/<flow>.json` manifest).
When no flow matches, it falls back to a bounded 1-hop neighbourhood of the executed modules taken
from the global `graph.dot`.

IMPORTANT — edges are ARCHITECTURAL, not runtime. `graph.dot` is an *import* graph: an edge
``A -> B`` means "A depends_on / imports B", never "A calls B" or "A executes before B". The output
keys are therefore ``depends_on`` (outgoing imports) and ``imported_by`` (incoming / upstream
consumers — the impact radius), never caller/callee.

No `src.*` imports — pure stdlib, stateless, operates on raw strings/paths from server routes (same
contract as `code_context_extractor.py`). Fail-open: any missing artifact degrades to
``{"available": False}`` so the Context report still works without the flow layer.
"""
from __future__ import annotations

import ast
import json
import re
import textwrap
from pathlib import Path
from typing import Any

# Edge line in a Graphviz .dot:  "A" -> "B";
_EDGE_RE = re.compile(r'"([^"]+)"\s*->\s*"([^"]+)"')

# Bounds for the global-neighbourhood fallback (the flow slice is already small by construction).
_MAX_GRAPH_NODES = 6     # touched modules expanded in the fallback
_MAX_NEIGHBORS = 12      # per direction, per node


# ── module-name mapping ───────────────────────────────────────────────────────
def _file_to_module(file_path: str, repo_root: Path) -> str | None:
    """
    Map an executed source file to its `graph.dot` node name.

    `…/src/control_plane/foo.py` -> `control_plane.foo`;  `…/src/core/__init__.py` -> `core`.
    Files outside `src/` (e.g. a `scripts/` entry point) have no graph node -> None.
    """
    parts = Path(file_path).as_posix().split("/")
    if "src" not in parts:
        return None
    idx = len(parts) - 1 - parts[::-1].index("src")   # last 'src' segment
    rel = parts[idx + 1:]
    if not rel:
        return None
    rel = list(rel)
    rel[-1] = rel[-1][:-3] if rel[-1].endswith(".py") else rel[-1]
    if rel and rel[-1] == "__init__":
        rel = rel[:-1]
    return ".".join(rel) if rel else None


def _executed_modules(code_context: list[dict[str, Any]], repo_root: Path) -> list[str]:
    seen: list[str] = []
    for entry in code_context or []:
        mod = _file_to_module(entry.get("file", ""), repo_root)
        if mod and mod not in seen:
            seen.append(mod)
    return seen


# ── .dot parsing ──────────────────────────────────────────────────────────────
def _parse_edges(dot_text: str) -> list[tuple[str, str]]:
    """Return architectural import edges (src depends_on dst) from a .dot file's text."""
    return [(m.group(1), m.group(2)) for m in _EDGE_RE.finditer(dot_text)]


def _neighbors(module: str, edges: list[tuple[str, str]]) -> dict[str, list[str]]:
    """depends_on = outgoing imports; imported_by = incoming (upstream consumers / impact radius)."""
    depends_on = sorted({dst for src, dst in edges if src == module})
    imported_by = sorted({src for src, dst in edges if dst == module})
    return {
        "module": module,
        "depends_on": depends_on[:_MAX_NEIGHBORS],
        "imported_by": imported_by[:_MAX_NEIGHBORS],
    }


# ── flow resolution ───────────────────────────────────────────────────────────
def _load_manifests(repo_root: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in sorted((repo_root / "flow_context").glob("*.json")):
        try:
            out.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return out


def resolve_flow(code_context: list[dict[str, Any]], repo_root: Path) -> dict[str, Any] | None:
    """
    Pick the flow whose membership best matches the executed modules.

    Score = module-set overlap, +2 if the flow entrypoint is among the executed modules,
    +0.5 per manifest keyword found inside an executed module name (tiebreaker). A flow qualifies
    on module overlap OR an entrypoint match; None only if neither a member nor the entrypoint ran.
    """
    executed = _executed_modules(code_context, repo_root)
    if not executed:
        return None
    exec_set = set(executed)
    best: dict[str, Any] | None = None
    best_score = 0.0
    for man in _load_manifests(repo_root):
        modules = set(man.get("modules", []))
        # A flow matches if any of its modules ran OR its entrypoint ran. The entrypoint is
        # definitionally part of the flow but is usually NOT listed in `modules` (it is the harness
        # that runs the spine, e.g. runtime.backtest_v2) — so its bonus must be counted BEFORE the
        # skip, otherwise a clean entrypoint-only run (the common case) resolves to no flow.
        score = float(len(exec_set & modules))
        if man.get("entrypoint") in exec_set:
            score += 2.0
        if score == 0.0:
            continue                      # neither a member nor the entrypoint ran → not this flow
        kws = man.get("keywords", [])
        score += 0.5 * sum(1 for kw in kws if any(kw in m for m in executed))
        if score > best_score:
            best_score, best = score, man
    return best


# ── public API ────────────────────────────────────────────────────────────────
def extract_graph_context(code_context: list[dict[str, Any]], repo_root: Path) -> dict[str, Any]:
    """
    Architectural graph context for the executed code.

    Returns one of:
      flow matched   -> {"available": True, "source": "flow_slice", "flow", "title", "doc",
                         "touched_modules", "edges", "nodes", "edge_count"}
      no flow match  -> {"available": True, "source": "global_neighborhood",
                         "touched_modules", "edges", "nodes", "edge_count"}
      nothing usable -> {"available": False}
    Edges are architectural (``[src, dst]`` = src depends_on dst). Fail-open throughout.
    """
    executed = _executed_modules(code_context, repo_root)
    if not executed:
        return {"available": False}

    flow = resolve_flow(code_context, repo_root)

    # ── flow slice (preferred) ────────────────────────────────────────────────
    if flow is not None:
        slice_path = repo_root / "flow_graphs" / f"{flow['flow']}.dot"
        try:
            edges = _parse_edges(slice_path.read_text(encoding="utf-8"))
        except OSError:
            edges = []
        if edges:
            members = list(flow.get("modules", []))
            touched = [m for m in executed if m in set(members)] or members
            return {
                "available": True,
                "source": "flow_slice",
                "flow": flow["flow"],
                "title": flow.get("title", flow["flow"]),
                "doc": flow.get("doc", ""),
                "touched_modules": touched,
                "edges": [[s, d] for s, d in edges],
                "nodes": [_neighbors(m, edges) for m in touched],
                "edge_count": len(edges),
            }

    # ── global-neighbourhood fallback ─────────────────────────────────────────
    try:
        global_edges = _parse_edges((repo_root / "graph.dot").read_text(encoding="utf-8"))
    except OSError:
        return {"available": False}
    if not global_edges:
        return {"available": False}

    touched = executed[:_MAX_GRAPH_NODES]
    touched_set = set(touched)
    nbr_edges: set[tuple[str, str]] = set()
    for src, dst in global_edges:
        if src in touched_set or dst in touched_set:
            nbr_edges.add((src, dst))
    return {
        "available": True,
        "source": "global_neighborhood",
        "touched_modules": touched,
        "edges": sorted([s, d] for s, d in nbr_edges),
        "nodes": [_neighbors(m, list(nbr_edges)) for m in touched],
        "edge_count": len(nbr_edges),
    }


# ── workflow-node → flow (M5) ──────────────────────────────────────────────────
# Caps for the flow-level code context (when there is no run to extract from).
_MAX_FLOW_MODULES = 6        # modules expanded into code context
_MAX_SYMS_PER_MODULE = 2     # top-level defs taken per module
_MAX_SYM_CHARS = 1_200       # per code block


def resolve_flow_for_command(command_id: str, repo_root: Path,
                             script: str | None = None) -> dict[str, Any] | None:
    """
    Map a Workflow-DAG node (a command id) to its flow manifest.

    Primary: the manifest whose curated ``command_ids`` contains the id (SSOT).
    Fallback: the command's ``script`` mapped via `_file_to_module` to a flow's member module.
    Returns the manifest or None (unmapped → caller falls open to run-only). Fail-open.
    """
    if not command_id:
        return None
    manifests = _load_manifests(repo_root)
    for man in manifests:
        if command_id in (man.get("command_ids") or []):
            return man
    if script:
        mod = _file_to_module(script, repo_root)
        if mod:
            for man in manifests:
                if mod in set(man.get("modules", [])):
                    return man
    return None


def _module_to_path(module: str, repo_root: Path) -> Path | None:
    parts = module.split(".")
    p = repo_root.joinpath("src", *parts).with_suffix(".py")
    if p.exists():
        return p
    pkg = repo_root.joinpath("src", *parts, "__init__.py")
    return pkg if pkg.exists() else None


def _top_level_symbols(path: Path) -> list[dict[str, Any]]:
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source)
    except (OSError, SyntaxError):
        return []
    lines = source.splitlines(keepends=True)
    out: list[dict[str, Any]] = []
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        start = node.lineno - 1
        end = getattr(node, "end_lineno", start + 1)
        block = textwrap.dedent("".join(lines[start:end]))[:_MAX_SYM_CHARS]
        out.append({
            "file": str(path), "symbol": node.name,
            "kind": "class" if isinstance(node, ast.ClassDef) else "function",
            "start_line": node.lineno, "end_line": end, "code": block,
            "source": "flow_module",
        })
    return out


def build_flow_code_context(flow_manifest: dict[str, Any], repo_root: Path) -> list[dict[str, Any]]:
    """
    Synthesize a `code_context` (same shape as `extract_code_context`) from a flow's member modules,
    so the architecture report works for a Workflow node that has **no run** yet. Bounded.
    """
    out: list[dict[str, Any]] = []
    for module in (flow_manifest.get("modules") or [])[:_MAX_FLOW_MODULES]:
        path = _module_to_path(module, repo_root)
        if not path:
            continue
        out.extend(_top_level_symbols(path)[:_MAX_SYMS_PER_MODULE])
    return out


# ── flow/module explorer support (M6) ──────────────────────────────────────────
_FLOW_LIST_KEYS = ("flow", "title", "doc", "service_ids", "modules",
                   "inputs", "outputs", "command_ids")


def list_flows(repo_root: Path) -> list[dict[str, Any]]:
    """All flows (manifest subset) for the explorer list. Modules stay start→end ordered."""
    out: list[dict[str, Any]] = []
    for man in _load_manifests(repo_root):
        out.append({k: man.get(k) for k in _FLOW_LIST_KEYS})
    return sorted(out, key=lambda m: m.get("flow") or "")


def get_flow(flow_name: str, repo_root: Path) -> dict[str, Any] | None:
    for man in _load_manifests(repo_root):
        if man.get("flow") == flow_name:
            return man
    return None


def build_module_code_context(module: str, repo_root: Path) -> list[dict[str, Any]]:
    """code_context (extract_code_context shape) for ONE module's top-level symbols."""
    path = _module_to_path(module, repo_root)
    return _top_level_symbols(path) if path else []


def module_role(module: str, repo_root: Path) -> str | None:
    """First non-empty line of a module's docstring (mirrors gen_code_map._module_role)."""
    path = _module_to_path(module, repo_root)
    if not path:
        return None
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return None
    doc = ast.get_docstring(tree)
    if not doc:
        return None
    for line in doc.splitlines():
        if line.strip():
            return line.strip()
    return None


def module_neighbors(module: str, repo_root: Path) -> dict[str, list[str]]:
    """Module's architectural I/O from the GLOBAL graph: depends_on + imported_by. Fail-open."""
    try:
        edges = _parse_edges((repo_root / "graph.dot").read_text(encoding="utf-8"))
    except OSError:
        return {"module": module, "depends_on": [], "imported_by": []}
    return _neighbors(module, edges)
