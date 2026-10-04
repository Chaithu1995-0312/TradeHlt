"""
gen_flow_graphs.py
==================
Flow-scoped dependency-graph slices for the Tradelatest `src/` tree.

WHY: the global `graph.dot` (module-level import graph from `gen_code_map.py`) is accurate but
undifferentiated — feeding all ~515 edges to an LLM is wasteful and unfocused. A *flow* is a
hand-curated subset of modules (the only human-authored artifact: `flow_context/<flow>.json`).
This tool DERIVES, per flow, a small induced subgraph (`flow_graphs/<flow>.dot`, ~20–60 edges)
covering the flow's modules plus their 1-hop dependency boundary — the perfect bounded context
for the Context-button architecture report and for per-flow multi-LLM handoff.

Single derivation source: edges come from `gen_code_map.build_graph()` (AST-derived), never
hand-drawn. The flow manifest only decides *membership*; the generator validates every listed
module against the real graph (drift caught at build time) and slices the edges.

Stdlib only (reuses `gen_code_map`, itself `ast` + `pathlib`). Deterministic: every collection is
sorted before emit, so reruns are byte-identical (diff-friendly, test-friendly).

Usage:
  python scripts/analysis/gen_flow_graphs.py            # write flow_graphs/<flow>.dot for every manifest
  python scripts/analysis/gen_flow_graphs.py --flow runtime   # print one slice to stdout, write nothing

Determinism note: import the AST graph fresh each run via `build_graph()`, so a `gen_code_map`
regeneration and a `gen_flow_graphs` run always agree on node identity.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Repo root = two levels up from scripts/analysis/gen_flow_graphs.py
_REPO_ROOT = Path(__file__).resolve().parents[2]
_FLOW_CONTEXT = _REPO_ROOT / "flow_context"
_FLOW_GRAPHS = _REPO_ROOT / "flow_graphs"

# gen_code_map lives in this same directory — make it importable regardless of cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_code_map import build_graph  # noqa: E402  (sibling script, single AST derivation source)

_REQUIRED_KEYS = ("flow", "title", "doc", "entrypoint", "modules", "keywords")


def load_manifest(path: Path) -> dict:
    """Load + shallow-validate a flow manifest (shape only; module-existence is checked at slice time)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    missing = [k for k in _REQUIRED_KEYS if k not in data]
    if missing:
        raise ValueError(f"{path.name}: manifest missing required key(s): {missing}")
    if not isinstance(data["modules"], list) or not data["modules"]:
        raise ValueError(f"{path.name}: 'modules' must be a non-empty list")
    return data


def iter_manifests() -> list[Path]:
    return sorted(_FLOW_CONTEXT.glob("*.json"))


def slice_flow(manifest: dict, module_set: set[str], edges: dict[str, list[str]]) -> dict:
    """
    Return the flow's induced subgraph + 1-hop dependency boundary.

    members          : the manifest's modules (validated to exist as graph nodes).
    boundary         : nodes outside `members` directly connected by an import edge.
    member_edges     : (src, dst) both in members.
    boundary_edges   : (src, dst) with exactly one endpoint in members.
    Edges are *architectural* import relationships (src depends_on dst), not runtime order.
    """
    members = set(manifest["modules"])
    unknown = sorted(m for m in members if m not in module_set)
    if unknown:
        raise ValueError(
            f"flow '{manifest['flow']}': module(s) not in graph.dot node set (drift): {unknown}. "
            f"Fix flow_context/{manifest['flow']}.json or regenerate graph.dot via gen_code_map.py."
        )

    member_edges: set[tuple[str, str]] = set()
    boundary_edges: set[tuple[str, str]] = set()
    boundary: set[str] = set()
    for src in sorted(edges):
        for dst in edges[src]:
            s_in, d_in = src in members, dst in members
            if s_in and d_in:
                member_edges.add((src, dst))
            elif s_in and not d_in:          # member depends_on an outside module (downstream boundary)
                boundary_edges.add((src, dst))
                boundary.add(dst)
            elif d_in and not s_in:          # outside module depends_on a member (upstream boundary)
                boundary_edges.add((src, dst))
                boundary.add(src)

    return {
        "flow": manifest["flow"],
        "title": manifest["title"],
        "members": sorted(members),
        "boundary": sorted(boundary),
        "member_edges": sorted(member_edges),
        "boundary_edges": sorted(boundary_edges),
    }


def emit_dot(sl: dict) -> str:
    """Render a flow slice to Graphviz. Members clustered; boundary nodes dashed/greyed."""
    flow = sl["flow"]
    lines = [
        f"digraph flow_{flow} {{",
        "    rankdir=LR;",
        "    node [shape=box, fontsize=10];",
        "",
        f'    subgraph "cluster_{flow}" {{',
        f'        label="{flow} — {sl["title"]}"; style="rounded";',
    ]
    for m in sl["members"]:
        lines.append(f'        "{m}";')
    lines.append("    }")
    lines.append("")
    if sl["boundary"]:
        lines.append("    // 1-hop dependency boundary (not flow members)")
        for b in sl["boundary"]:
            lines.append(f'    "{b}" [style="dashed", fontcolor="#888888"];')
        lines.append("")
    lines.append("    // member -> member (intra-flow dependencies)")
    for src, dst in sl["member_edges"]:
        lines.append(f'    "{src}" -> "{dst}";')
    if sl["boundary_edges"]:
        lines.append("")
        lines.append("    // boundary dependencies (one endpoint outside the flow)")
        for src, dst in sl["boundary_edges"]:
            lines.append(f'    "{src}" -> "{dst}";')
    lines.append("}")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="Flow-scoped dependency-graph slice generator.")
    ap.add_argument("--flow", help="Print one flow's slice to stdout and exit (writes nothing).")
    args = ap.parse_args()

    _modules, module_set, _top, edges = build_graph()

    if args.flow:
        path = _FLOW_CONTEXT / f"{args.flow}.json"
        if not path.exists():
            ap.error(f"no manifest: flow_context/{args.flow}.json")
        sys.stdout.write(emit_dot(slice_flow(load_manifest(path), module_set, edges)))
        return

    _FLOW_GRAPHS.mkdir(parents=True, exist_ok=True)
    total = 0
    for mpath in iter_manifests():
        sl = slice_flow(load_manifest(mpath), module_set, edges)
        out = _FLOW_GRAPHS / f"{sl['flow']}.dot"
        out.write_text(emit_dot(sl), encoding="utf-8")
        n_edges = len(sl["member_edges"]) + len(sl["boundary_edges"])
        total += 1
        print(f"{sl['flow']:<14} {len(sl['members'])} members, "
              f"{len(sl['boundary'])} boundary, {n_edges} edges -> "
              f"{out.relative_to(_REPO_ROOT)}")
    print(f"wrote {total} flow graph(s) to {_FLOW_GRAPHS.relative_to(_REPO_ROOT)}")


if __name__ == "__main__":
    main()
