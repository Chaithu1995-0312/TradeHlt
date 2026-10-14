from __future__ import annotations

import ast
import hashlib
import json
import os
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _literal_docstring(node: ast.AST) -> str | None:
    try:
        value = ast.get_docstring(node, clean=True)
        return value.strip() if value else None
    except Exception:
        return None


def inspect_python_file(path: Path, root: Path) -> dict[str, Any]:
    rel = path.resolve().relative_to(root.resolve()).as_posix()
    raw = path.read_bytes()
    item: dict[str, Any] = {
        "path": rel,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
        "parse_status": "OK",
        "module_docstring": None,
        "imports": [],
        "definitions": [],
        "likely_reads": [],
        "likely_writes": [],
        "intent_candidate": None,
        "intent_confidence": "LOW",
        "execution_verified": False,
    }
    try:
        tree = ast.parse(raw.decode("utf-8"), filename=rel)
    except (SyntaxError, UnicodeDecodeError) as exc:
        item.update(parse_status="ERROR", parse_error=str(exc))
        return item

    item["module_docstring"] = _literal_docstring(tree)
    imports: set[str] = set()
    definitions: list[dict[str, Any]] = []
    reads: set[str] = set()
    writes: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add("." * (node.level or 0) + (node.module or ""))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definitions.append({"name": node.name, "kind": type(node).__name__, "line": node.lineno,
                                "docstring": _literal_docstring(node)})
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            if name in {"read_csv", "read_parquet", "read_json", "read_text", "open", "load", "read_excel"}:
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    reads.add(node.args[0].value)
            if name in {"to_csv", "to_parquet", "to_json", "to_excel", "write_text", "dump", "savefig"}:
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    writes.add(node.args[0].value)
                for kw in node.keywords:
                    if kw.arg in {"path_or_buf", "fname", "file"} and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        writes.add(kw.value.value)

    item["imports"] = sorted(imports)
    item["definitions"] = sorted(definitions, key=lambda d: (d["line"], d["name"]))
    item["likely_reads"] = sorted(reads)
    item["likely_writes"] = sorted(writes)
    declared = item["module_docstring"] or next((d["docstring"] for d in definitions if d["docstring"]), None)
    if declared:
        item["intent_candidate"] = declared.splitlines()[0][:300]
        item["intent_confidence"] = "MEDIUM" if item["module_docstring"] else "LOW"
    else:
        item["intent_candidate"] = _candidate_from_path(rel)
    return item


def _candidate_from_path(rel: str) -> str:
    stem = Path(rel).stem.replace("_", " ").replace("-", " ")
    return f"Unverified intent candidate inferred from filename: {stem}"


def inventory(root: str | Path, include_dirs: tuple[str, ...] = ("scripts/analysis", "scripts/research")) -> dict[str, Any]:
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError(f"Repository root is not a directory: {root}")
    files: list[Path] = []
    for include in include_dirs:
        base = root / include
        if base.exists():
            files.extend(p for p in base.rglob("*.py") if p.is_file() and not any(part in {"__pycache__", ".venv", "venv"} for part in p.parts))
    unique = sorted(set(files))
    scripts = [inspect_python_file(p, root) for p in unique]
    return {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository_root": str(root),
        "scan_roots": list(include_dirs),
        "script_count": len(scripts),
        "counts": {
            "parse_ok": sum(s["parse_status"] == "OK" for s in scripts),
            "parse_error": sum(s["parse_status"] != "OK" for s in scripts),
            "module_docstring_present": sum(bool(s["module_docstring"]) for s in scripts),
            "execution_verified": 0,
        },
        "scripts": scripts,
        "limitations": [
            "Static AST inspection only; scripts were not executed.",
            "Read/write path detection is heuristic and only captures literal paths.",
            "Intent candidates are not approved script contracts.",
        ],
    }


def load_manifest(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != "1.0":
        raise ValueError("Unsupported manifest schema_version; expected 1.0")
    if not isinstance(data.get("nodes"), list) or not isinstance(data.get("intents"), dict):
        raise ValueError("Manifest requires 'nodes' array and 'intents' object")
    return data


def validate_manifest(manifest: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for node in manifest["nodes"]:
        node_id = node.get("node_id")
        if not node_id:
            issues.append({"severity": "ERROR", "code": "NODE_ID_MISSING", "message": "A node has no node_id"})
            continue
        if node_id in by_id:
            issues.append({"severity": "ERROR", "code": "NODE_ID_DUPLICATE", "message": f"Duplicate node_id: {node_id}"})
        by_id[node_id] = node
        for field in ("purpose", "operation", "inputs", "outputs", "depends_on"):
            if field not in node:
                issues.append({"severity": "ERROR", "code": "NODE_FIELD_MISSING", "message": f"{node_id}: missing {field}"})
    for node in manifest["nodes"]:
        for dep in node.get("depends_on", []):
            if dep not in by_id:
                issues.append({"severity": "ERROR", "code": "DEPENDENCY_MISSING", "message": f"{node.get('node_id')}: missing dependency {dep}"})
    for intent_id, intent in manifest["intents"].items():
        if not intent.get("root_nodes"):
            issues.append({"severity": "ERROR", "code": "INTENT_ROOT_MISSING", "message": f"{intent_id}: root_nodes is empty"})
        for root in intent.get("root_nodes", []):
            if root not in by_id:
                issues.append({"severity": "ERROR", "code": "INTENT_ROOT_UNKNOWN", "message": f"{intent_id}: unknown root node {root}"})
    # Cycle check across all nodes.
    graph = {n.get("node_id"): n.get("depends_on", []) for n in manifest["nodes"] if n.get("node_id")}
    visiting: set[str] = set(); visited: set[str] = set()
    def visit(node_id: str) -> None:
        if node_id in visiting:
            issues.append({"severity": "ERROR", "code": "DEPENDENCY_CYCLE", "message": f"Dependency cycle includes {node_id}"})
            return
        if node_id in visited:
            return
        visiting.add(node_id)
        for dep in graph.get(node_id, []):
            if dep in graph:
                visit(dep)
        visiting.remove(node_id); visited.add(node_id)
    for node_id in graph:
        visit(node_id)
    return issues


def build_plan(manifest: dict[str, Any], intent_id: str) -> dict[str, Any]:
    issues = validate_manifest(manifest)
    errors = [i for i in issues if i["severity"] == "ERROR"]
    if errors:
        raise ValueError("Manifest validation failed: " + "; ".join(i["message"] for i in errors))
    if intent_id not in manifest["intents"]:
        raise ValueError(f"Unknown intent_id: {intent_id}")
    nodes = {n["node_id"]: n for n in manifest["nodes"]}
    intent = manifest["intents"][intent_id]
    required: set[str] = set()
    def collect(node_id: str) -> None:
        if node_id in required:
            return
        required.add(node_id)
        for dep in nodes[node_id].get("depends_on", []):
            collect(dep)
    for root in intent["root_nodes"]:
        collect(root)
    indegree = {node_id: 0 for node_id in required}
    children: dict[str, list[str]] = defaultdict(list)
    for node_id in required:
        for dep in nodes[node_id].get("depends_on", []):
            if dep in required:
                indegree[node_id] += 1
                children[dep].append(node_id)
    queue = deque(sorted(n for n, degree in indegree.items() if degree == 0))
    ordered: list[str] = []
    while queue:
        current = queue.popleft(); ordered.append(current)
        for child in sorted(children[current]):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if len(ordered) != len(required):
        raise ValueError("Dependency graph contains a cycle")
    return {
        "schema_version": "1.0",
        "intent_id": intent_id,
        "intent": intent,
        "plan_status": "PLANNED_NOT_EXECUTED",
        "execution_policy": "NO_ARBITRARY_SCRIPT_EXECUTION",
        "ordered_nodes": [nodes[n] for n in ordered],
        "root_nodes": intent["root_nodes"],
        "validation_issues": issues,
    }


def write_json(path: str | Path, data: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def render_report(plan: dict[str, Any], inventory_data: dict[str, Any] | None = None) -> str:
    intent = plan["intent"]
    lines = [f"# Research SSOT Final Plan: {plan['intent_id']}", "",
             f"**Status:** `{plan['plan_status']}`  ",
             f"**Execution policy:** `{plan['execution_policy']}`", "",
             "## Intent", "", intent.get("description", "No description declared."), "",
             "## Planned analysis tree", "", "| Order | Node | Purpose | Operation | Depends on |", "|---:|---|---|---|---|"]
    for i, node in enumerate(plan["ordered_nodes"], 1):
        lines.append(f"| {i} | `{node['node_id']}` | {node['purpose']} | `{node['operation']}` | {', '.join(f'`{d}`' for d in node.get('depends_on', [])) or '—'} |")
    lines += ["", "## Required evidence outputs", ""]
    for node in plan["ordered_nodes"]:
        for output in node.get("outputs", []):
            lines.append(f"- `{node['node_id']}` → `{output}`")
    lines += ["", "## Inventory snapshot", ""]
    if inventory_data is None:
        lines.append("No script inventory was attached to this report.")
    else:
        counts = inventory_data.get("counts", {})
        lines += [f"- Scripts scanned: **{inventory_data.get('script_count', 0)}**",
                  f"- AST parse OK: **{counts.get('parse_ok', 0)}**",
                  f"- AST parse errors: **{counts.get('parse_error', 0)}**",
                  f"- Execution-verified scripts: **{counts.get('execution_verified', 0)}**"]
    lines += ["", "## Interpretation and limits", "",
              "This output is a deterministic plan, not a research finding. No script was executed by this MVP. Intent inferred from names/docstrings is not verified runtime behavior. Evidence validity, dataset compatibility, and metric contracts must be checked before any finding is admitted.", ""]
    return "\n".join(lines)
