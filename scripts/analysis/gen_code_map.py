"""
gen_code_map.py
===============
Module-level import-dependency graph for the Tradelatest `src/` tree.

WHY (LLM context economy): the legacy pyan call-graph (`pyan_call_flow.dot`) explodes to
tens of thousands of function-level edges — unusable as an LLM navigation aid. This tool
emits a *module-level import graph* instead: small enough to load, accurate enough to trust,
and regenerable so it never drifts.

Stdlib only (`ast` + `pathlib`) — no third-party dependency, no pyan, deterministic output.

Outputs (written to the repo root / docs):
  - graph.dot                              full module graph, one Graphviz cluster per package
  - docs/architecture/code-map.generated.md  L0 package flowchart + one per-package Mermaid slice

Usage:
  python scripts/analysis/gen_code_map.py            # write both artifacts
  python scripts/analysis/gen_code_map.py --package core   # print the `core` slice to stdout

Determinism: every collection is sorted before emit, so two runs on the same tree produce
byte-identical files (diff-friendly; safe to commit).
"""
from __future__ import annotations

import argparse
import ast
from pathlib import Path

# Repo root = two levels up from scripts/analysis/gen_code_map.py
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"
_DOT_OUT = _REPO_ROOT / "graph.dot"
_MERMAID_OUT = _REPO_ROOT / "docs" / "architecture" / "code-map.generated.md"
_ROLES_OUT = _REPO_ROOT / "docs" / "architecture" / "module-roles.generated.md"

# Directory parts that are never part of the importable module tree.
_SKIP_PARTS = {"__pycache__", "logs", "archive"}


def _iter_module_files():
    """Yield (dotted_module, package_context_parts, path) for every importable src/*.py.

    `__init__.py` maps to its package dotted name; relative imports resolve against
    `package_context_parts`.
    """
    for path in sorted(_SRC.rglob("*.py")):
        rel = path.relative_to(_SRC)
        parts = rel.with_suffix("").parts
        if any(p in _SKIP_PARTS for p in parts) or any(p.endswith(".egg-info") for p in parts):
            continue
        if parts[-1] == "__init__":
            mod_parts = parts[:-1]
            if not mod_parts:           # src/__init__.py — skip
                continue
            context = mod_parts          # relative imports in a package resolve against itself
        else:
            mod_parts = parts
            context = parts[:-1]         # ...against the containing package
        yield ".".join(mod_parts), list(context), path


def _collect():
    modules: dict[str, list[str]] = {}   # dotted module -> package-context parts
    for dotted, context, _path in _iter_module_files():
        modules[dotted] = context
    module_set = set(modules)
    top_packages = {m.split(".")[0] for m in module_set}
    return modules, module_set, top_packages


def _resolve(dotted: str, module_set: set[str], top_packages: set[str]) -> str | None:
    """Map an imported dotted name to a real module node, else None (external)."""
    if not dotted:
        return None
    if dotted == "src":
        return None
    if dotted.startswith("src."):
        dotted = dotted[4:]              # `src` is the source root, not a package — normalise
                                         # `src.control_plane.x` to the src-relative node `control_plane.x`
    if dotted.split(".")[0] not in top_packages:
        return None                      # stdlib / third-party
    if dotted in module_set:
        return dotted
    parts = dotted.split(".")
    for i in range(len(parts) - 1, 0, -1):   # longest known prefix
        pref = ".".join(parts[:i])
        if pref in module_set:
            return pref
    return parts[0]                      # package node (no __init__ file)


def _edges_for(path: Path, context: list[str], module_set: set[str],
               top_packages: set[str]) -> set[str]:
    """Return the set of internal module nodes that `path` imports."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
    except Exception:
        return set()
    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                t = _resolve(alias.name, module_set, top_packages)
                if t:
                    targets.add(t)
        elif isinstance(node, ast.ImportFrom):
            if node.level:               # relative import
                base = context[: len(context) - (node.level - 1)]
                base_dotted = ".".join(base + (node.module.split(".") if node.module else []))
            else:
                base_dotted = node.module or ""
            # A `from pkg import name` where pkg.name is itself a module → edge to the submodule.
            hit_submodule = False
            for alias in node.names:
                cand = f"{base_dotted}.{alias.name}" if base_dotted else alias.name
                if cand in module_set:
                    targets.add(cand)
                    hit_submodule = True
            if not hit_submodule:
                t = _resolve(base_dotted, module_set, top_packages)
                if t:
                    targets.add(t)
    return targets


def build_graph():
    modules, module_set, top_packages = _collect()
    # module -> sorted list of imported module nodes (internal, no self-edges)
    edges: dict[str, list[str]] = {}
    for dotted, context in modules.items():
        path = _SRC.joinpath(*dotted.split(".")).with_suffix(".py")
        if not path.exists():            # __init__-backed package node
            path = _SRC.joinpath(*dotted.split(".")) / "__init__.py"
        tgts = _edges_for(path, context, module_set, top_packages) if path.exists() else set()
        edges[dotted] = sorted(t for t in tgts if t != dotted)
    return modules, module_set, top_packages, edges


def _pkg(mod: str) -> str:
    return mod.split(".")[0]


def _mid(mod: str) -> str:
    """Sanitize a dotted module name into a Mermaid-safe node id."""
    return mod.replace(".", "_").replace("-", "_")


# ── Emitters ──────────────────────────────────────────────────────────────────

def emit_dot(modules, edges) -> str:
    pkgs: dict[str, list[str]] = {}
    for m in sorted(modules):
        pkgs.setdefault(_pkg(m), []).append(m)
    lines = ["digraph code_map {", '    rankdir=LR;', '    node [shape=box, fontsize=10];', ""]
    for pkg in sorted(pkgs):
        lines.append(f'    subgraph "cluster_{pkg}" {{')
        lines.append(f'        label="{pkg}"; style="rounded";')
        for m in pkgs[pkg]:
            lines.append(f'        "{m}";')
        lines.append("    }")
    lines.append("")
    for src in sorted(edges):
        for dst in edges[src]:
            lines.append(f'    "{src}" -> "{dst}";')
    lines.append("}")
    return "\n".join(lines) + "\n"


def _l0_mermaid(modules, edges) -> str:
    pkg_edges: set[tuple[str, str]] = set()
    for src in edges:
        for dst in edges[src]:
            a, b = _pkg(src), _pkg(dst)
            if a != b:
                pkg_edges.add((a, b))
    pkgs = sorted({_pkg(m) for m in modules})
    out = ["```mermaid", "flowchart LR"]
    for p in pkgs:
        out.append(f'    {p}["{p}"]')
    for a, b in sorted(pkg_edges):
        out.append(f"    {a} --> {b}")
    out.append("```")
    return "\n".join(out)


def _package_mermaid(pkg: str, modules, edges) -> str:
    own = sorted(m for m in modules if _pkg(m) == pkg)
    out = ["```mermaid", "flowchart LR"]
    seen: set[str] = set()
    for m in own:
        out.append(f'    {_mid(m)}["{m}"]')
        seen.add(m)
    # outgoing edges (what this package depends on); render external targets as plain nodes
    ext: set[str] = set()
    edge_lines: list[str] = []
    for m in own:
        for dst in edges.get(m, []):
            edge_lines.append(f"    {_mid(m)} --> {_mid(dst)}")
            if dst not in seen:
                ext.add(dst)
    for e in sorted(ext):
        out.append(f'    {_mid(e)}["{e}"]')
    out.extend(sorted(edge_lines))
    out.append("```")
    return "\n".join(out)


def emit_mermaid_doc(modules, edges) -> str:
    pkgs = sorted({_pkg(m) for m in modules})
    parts = [
        "# code-map.generated.md",
        "",
        "> **GENERATED — do not edit by hand.** Regenerate with "
        "`python scripts/analysis/gen_code_map.py`. Narrative + how-to-navigate lives in "
        "[`code-map.md`](code-map.md); module roles in "
        "[`codebase-state-map.md`](codebase-state-map.md).",
        "",
        f"`src/` module-level import graph — {len(modules)} modules across "
        f"{len(pkgs)} packages. Each per-package slice shows that package's modules and "
        "everything they import (a loadable unit).",
        "",
        "## L0 — package dependency overview",
        "",
        _l0_mermaid(modules, edges),
        "",
    ]
    for pkg in pkgs:
        parts.append(f"## {pkg}")
        parts.append("")
        parts.append(_package_mermaid(pkg, modules, edges))
        parts.append("")
    return "\n".join(parts) + "\n"


def _module_path(dotted: str) -> Path:
    """Resolve a dotted module name back to its .py file (or the package __init__.py)."""
    p = _SRC.joinpath(*dotted.split(".")).with_suffix(".py")
    if not p.exists():
        p = _SRC.joinpath(*dotted.split(".")) / "__init__.py"
    return p


def _module_role(path: Path) -> str | None:
    """First non-empty line of the module docstring, else None."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
    except Exception:
        return None
    doc = ast.get_docstring(tree)
    if not doc:
        return None
    for line in doc.splitlines():
        if line.strip():
            return line.strip()
    return None


def emit_module_roles(modules) -> tuple[str, int, int]:
    """Per-module role table (docstring line 1). Returns (markdown, documented, total)."""
    pkgs: dict[str, list[str]] = {}
    for m in sorted(modules):
        pkgs.setdefault(_pkg(m), []).append(m)
    total = documented = 0
    body: list[str] = []
    for pkg in sorted(pkgs):
        body += [f"### `src/{pkg}/`", "", "| Module | Role (docstring line 1) |", "| --- | --- |"]
        for m in pkgs[pkg]:
            total += 1
            role = _module_role(_module_path(m))
            if role:
                documented += 1
                cell = role.replace("|", "\\|")
            else:
                cell = "_(no module docstring)_"
            body.append(f"| `{m}` | {cell} |")
        body.append("")
    pct = (100 * documented // total) if total else 0
    head = [
        "# module-roles.generated.md",
        "",
        "> **GENERATED — do not edit by hand.** Regenerate with "
        "`python scripts/analysis/gen_code_map.py`. One role line per `src/` module, taken from the "
        "module docstring's first line. Package-level roles + key modules live in "
        "[`codebase-state-map.md`](codebase-state-map.md) §1; the import graph is "
        "[`code-map.generated.md`](code-map.generated.md).",
        "",
        "_`(no module docstring)` flags a module that should get a one-line docstring — that is the "
        "actionable code gap, not a docs gap._",
        "",
        f"**Coverage: {documented}/{total} modules carry a docstring role ({pct}%).** "
        f"{total - documented} flagged `(no module docstring)`.",
        "",
    ]
    return "\n".join(head + body) + "\n", documented, total


def main() -> None:
    ap = argparse.ArgumentParser(description="Module-level import-graph generator for src/.")
    ap.add_argument("--package", help="Print one package's Mermaid slice to stdout and exit.")
    args = ap.parse_args()

    modules, module_set, top_packages, edges = build_graph()
    n_edges = sum(len(v) for v in edges.values())

    if args.package:
        print(_package_mermaid(args.package, modules, edges))
        return

    _DOT_OUT.write_text(emit_dot(modules, edges), encoding="utf-8")
    _MERMAID_OUT.parent.mkdir(parents=True, exist_ok=True)
    _MERMAID_OUT.write_text(emit_mermaid_doc(modules, edges), encoding="utf-8")
    roles_doc, documented, total = emit_module_roles(modules)
    _ROLES_OUT.write_text(roles_doc, encoding="utf-8")
    print(f"{len(modules)} modules, {n_edges} internal edges, "
          f"{len({_pkg(m) for m in modules})} packages")
    print(f"module roles: {documented}/{total} documented")
    print(f"wrote {_DOT_OUT.relative_to(_REPO_ROOT)}, "
          f"{_MERMAID_OUT.relative_to(_REPO_ROOT)}, {_ROLES_OUT.relative_to(_REPO_ROOT)}")


if __name__ == "__main__":
    main()
