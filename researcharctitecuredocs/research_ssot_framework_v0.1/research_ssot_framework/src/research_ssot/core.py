from __future__ import annotations

import ast
import hashlib
import json
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

OPERATIONS = {"contract_check", "artifact_resolve", "measurement", "compare", "bridge", "evidence_assembly"}
REUSE_POLICIES = {
    "NEVER_REUSE_FINAL_REPORT_WITHOUT_REVALIDATION",
    "REUSE_ONLY_EXACT_IDENTITY",
    "REUSE_IF_CONTRACT_AND_HASH_MATCH",
    "NEVER_REUSE",
}
NODE_STATUSES = {"PLANNED", "BLOCKED", "BLOCKED_UPSTREAM", "COMPLETED", "REUSED", "FAILED", "SKIPPED"}
EXTERNAL_KINDS = {"contract", "identity", "dataset", "config"}
DEFAULT_SCAN_ROOTS = ("scripts/analysis", "scripts/research", "src/research")
INVENTORY_VOLATILE_KEYS = {"generated_at_utc", "repository_root", "content_sha256"}
EXECUTED_STATUSES = {"COMPLETED", "REUSED", "FAILED", "SKIPPED"}
EVIDENCE_STATUSES = {"COMPLETED", "REUSED"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _canonical_sha256(data: Any) -> str:
    raw = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


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
        "path": rel, "sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw),
        "parse_status": "OK", "module_docstring": None, "imports": [], "definitions": [],
        "likely_reads": [], "likely_writes": [], "intent_candidate": None,
        "intent_confidence": "LOW", "execution_verified": False,
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
            if name == "open" and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                mode = None
                if len(node.args) > 1 and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
                    mode = node.args[1].value
                for kw in node.keywords:
                    if kw.arg == "mode" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        mode = kw.value.value
                if mode and any(flag in mode for flag in "wax+"):
                    writes.add(node.args[0].value)
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


def inventory(root: str | Path, include_dirs: tuple[str, ...] = DEFAULT_SCAN_ROOTS,
              now: datetime | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError(f"Repository root is not a directory: {root}")
    files: list[Path] = []
    ignored = {"__pycache__", ".venv", "venv", ".git"}
    for include in include_dirs:
        base = root / include
        if base.exists():
            files.extend(p for p in base.rglob("*.py") if p.is_file() and not any(part in ignored for part in p.parts))
    unique = sorted(set(files))
    scripts = [inspect_python_file(p, root) for p in unique]
    result = {
        "schema_version": "1.1", "generated_at_utc": (now or datetime.now(timezone.utc)).isoformat(),
        "repository_root": str(root), "scan_roots": list(include_dirs), "script_count": len(scripts),
        "counts": {"parse_ok": sum(s["parse_status"] == "OK" for s in scripts),
                   "parse_error": sum(s["parse_status"] != "OK" for s in scripts),
                   "module_docstring_present": sum(bool(s["module_docstring"]) for s in scripts),
                   "execution_verified": 0},
        "scripts": scripts,
        "limitations": ["Static AST inspection only; scripts were not executed.",
                        "Read/write path detection is heuristic and only captures literal paths.",
                        "Intent candidates are not approved script contracts."],
    }
    # Generation time and the machine-local absolute root are excluded from the stable identity,
    # so the same tree yields the same content_sha256 across runs and across clones.
    result["content_sha256"] = _canonical_sha256({k: v for k, v in result.items() if k not in INVENTORY_VOLATILE_KEYS})
    return result


def load_manifest(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != "1.1":
        raise ValueError("Unsupported manifest schema_version; expected 1.1")
    if not isinstance(data.get("nodes"), list) or not isinstance(data.get("intents"), dict):
        raise ValueError("Manifest requires 'nodes' array and 'intents' object")
    if not isinstance(data.get("external_inputs", []), list):
        raise ValueError("Manifest 'external_inputs' must be an array")
    return data


def _output_name(output: Any) -> str:
    return output if isinstance(output, str) else output.get("name", "")


def _output_producer_spec(node: dict[str, Any], output: Any) -> Any:
    if isinstance(output, dict) and "state_producer" in output:
        return output["state_producer"]
    return node.get("state_producer", "inherit")


def _node_outputs(manifest: dict[str, Any]) -> dict[str, tuple[str, Any]]:
    result: dict[str, tuple[str, Any]] = {}
    for node in manifest.get("nodes", []):
        node_id = node.get("node_id", "<missing>")
        for output in node.get("outputs", []):
            name = _output_name(output)
            if name:
                result[f"{node_id}.{name}"] = (node_id, output)
    return result


def _intent_closure(intent: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> set[str]:
    closure: set[str] = set()
    def collect(node_id: str) -> None:
        if node_id in closure or node_id not in by_id:
            return
        closure.add(node_id)
        for dep in by_id[node_id].get("depends_on", []):
            collect(dep)
    for root in intent.get("root_nodes", []):
        collect(root)
    return closure


def validate_manifest(manifest: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    def add(code: str, message: str, severity: str = "ERROR") -> None:
        issues.append({"severity": severity, "code": code, "message": message})

    external_list = manifest.get("external_inputs", [])
    external: dict[str, dict[str, Any]] = {}
    for entry in external_list:
        if not isinstance(entry, dict) or not entry.get("id"):
            add("EXTERNAL_INPUT_ID_MISSING", "Every external input needs an id")
            continue
        ext_id = entry["id"]
        if ext_id in external:
            add("EXTERNAL_INPUT_DUPLICATE", f"Duplicate external input id: {ext_id}")
        external[ext_id] = entry
        if entry.get("kind") not in EXTERNAL_KINDS:
            add("EXTERNAL_INPUT_KIND_INVALID", f"{ext_id}: kind must be one of {sorted(EXTERNAL_KINDS)}")
        if not isinstance(entry.get("ref"), str) or not entry.get("ref"):
            add("EXTERNAL_INPUT_REF_MISSING", f"{ext_id}: ref must be a non-empty string")

    by_id: dict[str, dict[str, Any]] = {}
    for node in manifest.get("nodes", []):
        node_id = node.get("node_id")
        if not node_id:
            add("NODE_ID_MISSING", "A node has no node_id")
            continue
        if node_id in by_id:
            add("NODE_ID_DUPLICATE", f"Duplicate node_id: {node_id}")
        by_id[node_id] = node
        for field in ("purpose", "operation", "inputs", "outputs", "depends_on", "reuse_policy", "required"):
            if field not in node:
                add("NODE_FIELD_MISSING", f"{node_id}: missing {field}")
        if node.get("operation") not in OPERATIONS:
            add("OPERATION_INVALID", f"{node_id}: unsupported operation {node.get('operation')!r}")
        if node.get("reuse_policy") not in REUSE_POLICIES:
            add("REUSE_POLICY_INVALID", f"{node_id}: unsupported reuse_policy {node.get('reuse_policy')!r}")
        if not isinstance(node.get("required"), bool):
            add("REQUIRED_INVALID", f"{node_id}: required must be boolean")

    output_map = _node_outputs(manifest)
    for node in manifest.get("nodes", []):
        node_id = node.get("node_id", "<missing>")
        for dep in node.get("depends_on", []):
            if dep not in by_id:
                add("DEPENDENCY_MISSING", f"{node_id}: missing dependency {dep}")
        for value in node.get("inputs", []):
            if not isinstance(value, str):
                add("INPUT_REFERENCE_INVALID", f"{node_id}: input references must be strings")
                continue
            if value in external:
                continue
            if value not in output_map:
                add("INPUT_UNRESOLVED", f"{node_id}: input {value!r} is neither an external input nor a node output")
                continue
            producer_node, _ = output_map[value]
            if producer_node == node_id or producer_node not in by_id[node_id].get("depends_on", []):
                # Direct dependencies may themselves depend on the output producer; checked below transitively.
                ancestors: set[str] = set()
                stack = list(by_id[node_id].get("depends_on", []))
                while stack:
                    ancestor = stack.pop()
                    if ancestor in ancestors or ancestor not in by_id:
                        continue
                    ancestors.add(ancestor)
                    stack.extend(by_id[ancestor].get("depends_on", []))
                if producer_node not in ancestors:
                    add("HIDDEN_DEPENDENCY", f"{node_id}: consumes {value} from non-ancestor {producer_node}")

    # Validate producer declarations and config identity references.
    def check_producer(node_id: str, spec: Any) -> None:
        if spec in (None, "none", "inherit"):
            return
        if not isinstance(spec, dict) or not spec.get("kind") or not spec.get("config_ref"):
            add("STATE_PRODUCER_INVALID", f"{node_id}: state_producer must be 'none', 'inherit', or {{kind, config_ref}}")
            return
        config_ref = spec["config_ref"]
        if config_ref not in external or external[config_ref].get("kind") != "config":
            add("STATE_PRODUCER_CONFIG_INVALID", f"{node_id}: config_ref {config_ref!r} must name an external_inputs id of kind config")
    for ext_id, entry in external.items():
        if "state_producer" not in entry:
            continue
        if entry.get("kind") != "dataset":
            add("STATE_PRODUCER_INVALID", f"{ext_id}: only dataset external inputs may declare state_producer")
        elif entry["state_producer"] == "inherit":
            add("STATE_PRODUCER_INVALID", f"{ext_id}: an external input has nothing to inherit from")
        else:
            check_producer(ext_id, entry["state_producer"])
    for node in manifest.get("nodes", []):
        if "state_producer" in node:
            check_producer(node.get("node_id", "<missing>"), node["state_producer"])
        if node.get("operation") == "bridge":
            contract = node.get("bridge_contract")
            if contract not in external or external[contract].get("kind") != "contract":
                add("BRIDGE_CONTRACT_REQUIRED", f"{node.get('node_id')}: bridge requires bridge_contract naming an external input of kind contract")
        for output in node.get("outputs", []):
            if isinstance(output, dict) and "state_producer" in output:
                check_producer(node.get("node_id", "<missing>"), output["state_producer"])

    # DAG cycles.
    graph = {n.get("node_id"): n.get("depends_on", []) for n in manifest.get("nodes", []) if n.get("node_id")}
    visiting: set[str] = set(); visited: set[str] = set()
    def visit(node_id: str) -> None:
        if node_id in visiting:
            add("DEPENDENCY_CYCLE", f"Dependency cycle includes {node_id}")
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

    # Claim-to-evidence references must resolve inside each intent's dependency closure.
    for intent_id, intent in manifest.get("intents", {}).items():
        if not intent.get("root_nodes"):
            add("INTENT_ROOT_MISSING", f"{intent_id}: root_nodes is empty")
        for root in intent.get("root_nodes", []):
            if root not in by_id:
                add("INTENT_ROOT_UNKNOWN", f"{intent_id}: unknown root node {root}")
        claims = intent.get("required_claims", {})
        if not isinstance(claims, dict):
            add("CLAIMS_SCHEMA_INVALID", f"{intent_id}: required_claims must map claim_id to output-reference lists")
            continue
        closure = _intent_closure(intent, by_id)
        for claim_id, refs in claims.items():
            if not isinstance(refs, list) or not refs:
                add("CLAIM_EVIDENCE_EMPTY", f"{intent_id}.{claim_id}: at least one evidence output is required")
                continue
            for ref in refs:
                if not isinstance(ref, str) or ref not in output_map:
                    add("CLAIM_EVIDENCE_UNKNOWN", f"{intent_id}.{claim_id}: unknown evidence output {ref!r}")
                elif output_map[ref][0] not in closure:
                    add("CLAIM_EVIDENCE_UNKNOWN", f"{intent_id}.{claim_id}: {ref!r} is outside the intent closure")

    # Producer pooling validation is intent-scoped to avoid unrelated graph branches affecting each other.
    for intent_id, intent in manifest.get("intents", {}).items():
        closure = _intent_closure(intent, by_id)
        producer_sets: dict[str, set[str]] = {}
        # Comparison taint: any output descended from a compare output stays diagnostic until a
        # bridge explicitly re-establishes a population.
        comparison_outputs: set[str] = set()
        for node_id in _topological_ids(by_id, closure):
            node = by_id[node_id]
            op = node.get("operation")
            input_producers: set[str] = set()
            input_comparison = False
            for ref in node.get("inputs", []):
                if ref in external:
                    input_producers.update(_external_producers(ref, external))
                    continue
                if ref in comparison_outputs:
                    input_comparison = True
                if ref in producer_sets:
                    input_producers.update(producer_sets[ref])
            stateful_inputs = bool(input_producers) or input_comparison
            if input_comparison and op == "measurement":
                add("COMPARISON_REUSED_AS_POPULATION", f"{node_id}: comparison output cannot be measured as a state population")
            if len(input_producers) >= 2:
                if op == "compare":
                    pass
                elif op == "bridge":
                    contract = node.get("bridge_contract")
                    if contract not in external or external[contract].get("kind") != "contract":
                        add("BRIDGE_CONTRACT_REQUIRED", f"{node_id}: bridge requires bridge_contract naming an external input of kind contract")
                else:
                    add("PRODUCER_POOLING", f"{node_id}: combines distinct state producers {sorted(input_producers)} without compare/bridge")
            node_spec = node.get("state_producer", "inherit")
            if op == "artifact_resolve" and node_spec == "inherit":
                add("STATE_PRODUCER_UNDECLARED", f"{node_id}: artifact_resolve must declare state_producer ('none' or {{kind, config_ref}})")
            own = _producer_from_spec(node_spec, external)
            output_producer_union: set[str] = set()
            if own is not None:
                output_producer_union.add(own)
            elif node_spec == "inherit":
                output_producer_union.update(input_producers)
            if op == "bridge" and len(input_producers) >= 2:
                output_producer_union = {f"pooled@bridge:{node_id}:{node.get('bridge_contract')}"}
            if op == "compare" and len(input_producers) >= 2:
                output_producer_union = {f"comparison@{node_id}"}
            state_output_producers: set[str] = set()
            for output in node.get("outputs", []):
                name = _output_name(output)
                ref = f"{node_id}.{name}"
                spec = _output_producer_spec(node, output)
                explicit = _producer_from_spec(spec, external)
                if spec == "none" and stateful_inputs:
                    add("PRODUCER_DROPPED", f"{node_id}.{name}: output of a node with state inputs cannot declare state_producer 'none'")
                if explicit is not None and input_producers and op != "bridge" and explicit not in input_producers:
                    add("PRODUCER_RELABELED", f"{node_id}.{name}: declares {explicit} but its inputs carry {sorted(input_producers)}")
                if spec == "inherit" and not stateful_inputs and op != "artifact_resolve":
                    add("STATE_PRODUCER_UNDECLARED", f"{node_id}.{name}: no state inputs to inherit from; declare state_producer explicitly")
                if spec == "none":
                    producer_sets[ref] = set()
                elif explicit is not None:
                    producer_sets[ref] = {explicit}
                    state_output_producers.add(explicit)
                else:
                    producer_sets[ref] = set(output_producer_union)
                    state_output_producers.update(output_producer_union)
                if (op == "compare" and len(input_producers) >= 2) or (input_comparison and op != "bridge"):
                    comparison_outputs.add(ref)
            if len(state_output_producers) > 1:
                add("MULTIPLE_PRODUCERS_EMITTED", f"{node_id}: emits state outputs for multiple producers {sorted(state_output_producers)}", "WARNING")
    # Deduplicate repeated diagnostics from output/producer traversal.
    seen: set[tuple[str, str, str]] = set()
    unique_issues = []
    for issue in issues:
        key = (issue["severity"], issue["code"], issue["message"])
        if key not in seen:
            seen.add(key); unique_issues.append(issue)
    return unique_issues


def _producer_from_spec(spec: Any, external: dict[str, dict[str, Any]]) -> str | None:
    if spec in (None, "none", "inherit") or not isinstance(spec, dict):
        return None
    config_ref = spec.get("config_ref")
    # Identity is intentionally kind + config reference, not just producer kind.
    return f"{spec.get('kind')}@{config_ref}" if config_ref in external else None


def _external_producers(ext_id: str, external: dict[str, dict[str, Any]]) -> set[str]:
    """Producer identities carried by an external input.

    Only dataset externals can carry state. An undeclared dataset is an unknown producer with its own
    identity, so it can never silently pool with a tagged producer or with another unknown dataset.
    """
    entry = external[ext_id]
    if entry.get("kind") != "dataset":
        return set()
    spec = entry.get("state_producer")
    if spec is None:
        return {f"unknown@{ext_id}"}
    if spec == "none":
        return set()
    producer = _producer_from_spec(spec, external)
    return {producer} if producer else {f"unknown@{ext_id}"}


def _producer_config_refs(node: dict[str, Any], external: dict[str, dict[str, Any]]) -> list[str]:
    """Every config external a node's producer identity depends on (own, per-output, dataset inputs)."""
    specs = [node.get("state_producer")]
    specs += [o.get("state_producer") for o in node.get("outputs", []) if isinstance(o, dict)]
    specs += [external[r].get("state_producer") for r in node.get("inputs", []) if r in external]
    return [s["config_ref"] for s in specs if isinstance(s, dict) and s.get("config_ref") in external]


def _topological_ids(by_id: dict[str, dict[str, Any]], closure: set[str]) -> list[str]:
    indegree = {n: 0 for n in closure}
    children: dict[str, list[str]] = defaultdict(list)
    for node_id in closure:
        for dep in by_id[node_id].get("depends_on", []):
            if dep in closure:
                indegree[node_id] += 1
                children[dep].append(node_id)
    queue = deque(sorted(n for n, degree in indegree.items() if degree == 0))
    result = []
    while queue:
        current = queue.popleft(); result.append(current)
        for child in sorted(children[current]):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    return result


def _external_lookup(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {x["id"]: x for x in manifest.get("external_inputs", []) if isinstance(x, dict) and x.get("id")}


def build_plan(manifest: dict[str, Any], intent_id: str) -> dict[str, Any]:
    issues = validate_manifest(manifest)
    errors = [i for i in issues if i["severity"] == "ERROR"]
    if errors:
        raise ValueError("Manifest validation failed: " + "; ".join(i["message"] for i in errors))
    if intent_id not in manifest["intents"]:
        raise ValueError(f"Unknown intent_id: {intent_id}")
    nodes = {n["node_id"]: n for n in manifest["nodes"]}
    intent = manifest["intents"][intent_id]
    closure = _intent_closure(intent, nodes)
    ordered = _topological_ids(nodes, closure)
    external = _external_lookup(manifest)
    outputs = _node_outputs(manifest)
    statuses: dict[str, str] = {}
    reasons: dict[str, list[str]] = {}
    for node_id in ordered:
        node = nodes[node_id]
        upstream_bad = [dep for dep in node.get("depends_on", []) if dep in statuses and statuses[dep] in {"BLOCKED", "BLOCKED_UPSTREAM", "FAILED", "SKIPPED"}]
        if upstream_bad:
            statuses[node_id] = "BLOCKED_UPSTREAM"
            reasons[node_id] = [f"Upstream dependency not available: {dep} ({statuses[dep]})" for dep in upstream_bad]
            continue
        unresolved = [ref for ref in node.get("inputs", []) if ref in external and external[ref].get("ref") == "UNRESOLVED"]
        if node.get("operation") == "bridge" and node.get("bridge_contract") in external and external[node["bridge_contract"]].get("ref") == "UNRESOLVED":
            unresolved.append(node["bridge_contract"])
        # Producer identity is kind + config; an unresolved config leaves the identity unknown.
        for config_ref in _producer_config_refs(node, external):
            if external[config_ref].get("ref") == "UNRESOLVED" and config_ref not in unresolved:
                unresolved.append(config_ref)
        if unresolved:
            statuses[node_id] = "BLOCKED"
            reasons[node_id] = [f"External input unresolved: {ref}" for ref in unresolved]
            continue
        statuses[node_id] = "PLANNED"
        reasons[node_id] = []

    planned_nodes = []
    for node_id in ordered:
        node = dict(nodes[node_id])
        node["status"] = statuses[node_id]
        node["blocked_reasons"] = reasons.get(node_id, [])
        planned_nodes.append(node)
    plan = {
        "schema_version": "1.1", "intent_id": intent_id, "intent": intent,
        "execution_policy": "NO_ARBITRARY_SCRIPT_EXECUTION", "ordered_nodes": planned_nodes,
        "root_nodes": intent["root_nodes"], "validation_issues": issues,
        "external_inputs": manifest.get("external_inputs", []), "node_results": {},
    }
    plan["claims"] = _claim_statuses(intent, plan["ordered_nodes"], {})
    plan["plan_status"] = _derive_report_status(plan["ordered_nodes"], plan["claims"])
    return plan


def _claim_statuses(intent: dict[str, Any], nodes: list[dict[str, Any]], results: dict[str, Any]) -> list[dict[str, Any]]:
    by_id = {n["node_id"]: n for n in nodes}
    outputs = {f"{n['node_id']}.{_output_name(o)}": n for n in nodes for o in n.get("outputs", [])}
    claims = []
    for claim_id, refs in intent.get("required_claims", {}).items():
        supporting = []
        unsupported = []
        for ref in refs:
            node = outputs.get(ref)
            status = results.get(node["node_id"], {}).get("status", node.get("status", "PLANNED")) if node else "UNKNOWN"
            (supporting if status in {"COMPLETED", "REUSED"} else unsupported).append({"output": ref, "status": status})
        claims.append({"claim_id": claim_id, "status": "SUPPORTED" if not unsupported and supporting else "UNSUPPORTED",
                       "evidence": supporting, "missing_or_unverified": unsupported})
    return claims


def _derive_report_status(nodes: list[dict[str, Any]], claims: list[dict[str, Any]]) -> str:
    """Single derivation used by both plan and apply. Precedence:
    BLOCKED > INCOMPLETE > PARTIAL > COMPLETE / PLANNED_NOT_EXECUTED."""
    statuses = [n.get("status", "PLANNED") for n in nodes]
    if any(s in {"BLOCKED", "BLOCKED_UPSTREAM"} for s in statuses):
        return "BLOCKED"
    if any(n.get("status") in {"FAILED", "SKIPPED"} and n.get("required", True) for n in nodes):
        return "INCOMPLETE"
    planned = sum(s == "PLANNED" for s in statuses)
    executed = sum(s in EXECUTED_STATUSES for s in statuses)
    if planned == 0 and executed:
        # Everything that could run has a result; an unsupported claim means evidence is missing.
        return "COMPLETE" if all(c["status"] == "SUPPORTED" for c in claims) else "INCOMPLETE"
    if executed:
        return "PARTIAL"
    return "PLANNED_NOT_EXECUTED"


def _validate_evidence(node_id: str, result: dict[str, Any], base_dir: Path) -> list[dict[str, str]]:
    """COMPLETED/REUSED must carry re-verifiable artifacts; a stated hash is re-computed, not trusted."""
    artifacts = result.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError(f"{node_id}: {result.get('status')} requires a non-empty 'artifacts' list of {{path, sha256}}")
    run_identity_ref = result.get("run_identity_ref")
    if not isinstance(run_identity_ref, str) or not run_identity_ref:
        raise ValueError(f"{node_id}: {result.get('status')} requires a non-empty 'run_identity_ref'")
    if result.get("status") == "REUSED" and not (isinstance(result.get("reused_identity"), str) and result["reused_identity"]):
        raise ValueError(f"{node_id}: REUSED requires 'reused_identity' naming the matched prior run identity")
    verified = []
    for artifact in artifacts:
        if not isinstance(artifact, dict) or not artifact.get("path") or not artifact.get("sha256"):
            raise ValueError(f"{node_id}: every artifact needs 'path' and 'sha256'")
        path = Path(artifact["path"])
        target = path if path.is_absolute() else base_dir / path
        if not target.is_file():
            raise ValueError(f"{node_id}: evidence artifact not found: {artifact['path']}")
        actual = sha256_file(target)
        if actual != str(artifact["sha256"]).lower():
            raise ValueError(f"{node_id}: evidence artifact hash mismatch for {artifact['path']} (stated {artifact['sha256']}, actual {actual})")
        verified.append({"path": artifact["path"], "sha256": actual})
    return verified


def apply_execution_results(plan: dict[str, Any], results: dict[str, dict[str, Any]],
                            base_dir: str | Path | None = None) -> dict[str, Any]:
    """Apply externally executed adapter results; this function never executes scripts itself.

    Results map node_id to {status: COMPLETED|REUSED|FAILED|SKIPPED, ...}. COMPLETED/REUSED must carry
    artifacts whose SHA-256 is re-computed here (relative paths resolve against base_dir). A failed
    node keeps FAILED whether or not it is required; only its dependents become SKIPPED.
    """
    copied = json.loads(json.dumps(plan))
    base = Path(base_dir) if base_dir is not None else Path.cwd()
    known = {n["node_id"] for n in copied["ordered_nodes"]}
    unknown = sorted(set(results) - known)
    if unknown:
        raise ValueError(f"Execution results name nodes not in this plan: {unknown}")
    final_results: dict[str, dict[str, Any]] = {}
    for node in copied["ordered_nodes"]:
        node_id = node["node_id"]
        provided = results.get(node_id)
        unavailable = [dep for dep in node.get("depends_on", [])
                       if final_results.get(dep, {}).get("status") in {"FAILED", "SKIPPED", "BLOCKED", "BLOCKED_UPSTREAM"}]
        if node.get("status") in {"BLOCKED", "BLOCKED_UPSTREAM"} or unavailable:
            if provided is not None and provided.get("status") in EVIDENCE_STATUSES:
                raise ValueError(f"{node_id}: result claims {provided.get('status')} but the node cannot have run "
                                 f"({node.get('status') if not unavailable else 'upstream unavailable: ' + ', '.join(unavailable)})")
            if node.get("status") in {"BLOCKED", "BLOCKED_UPSTREAM"}:
                final_status = node["status"]
            else:
                final_status = "SKIPPED"
                node["blocked_reasons"] = [f"Upstream dependency unavailable: {dep}" for dep in unavailable]
            node["execution_result"] = {}
            final_results[node_id] = {"status": final_status}
            node["status"] = final_status
            continue
        if provided is None:
            final_status = node.get("status", "PLANNED")
            entry: dict[str, Any] = {"status": final_status}
        else:
            requested = provided.get("status")
            if requested not in EXECUTED_STATUSES:
                raise ValueError(f"{node_id}: execution result status must be one of {sorted(EXECUTED_STATUSES)}")
            final_status = requested
            entry = {**provided, "status": final_status}
            if requested in EVIDENCE_STATUSES:
                entry["artifacts"] = _validate_evidence(node_id, provided, base)
        node["status"] = final_status
        node["execution_result"] = provided or {}
        final_results[node_id] = entry
    copied["node_results"] = final_results
    copied["claims"] = _claim_statuses(copied["intent"], copied["ordered_nodes"], final_results)
    copied["plan_status"] = _derive_report_status(copied["ordered_nodes"], copied["claims"])
    return copied


def write_json(path: str | Path, data: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def render_report(plan: dict[str, Any], inventory_data: dict[str, Any] | None = None) -> str:
    intent = plan["intent"]
    lines = [f"# Research SSOT Final Report: {plan['intent_id']}", "",
             f"**Status:** `{plan['plan_status']}`  ",
             f"**Execution policy:** `{plan['execution_policy']}`", "",
             "## Intent", "", intent.get("description", "No description declared."), "",
             "## Analysis tree", "", "| Order | Node | Status | Purpose | Operation | Depends on |", "|---:|---|---|---|---|---|"]
    for i, node in enumerate(plan["ordered_nodes"], 1):
        purpose = str(node.get("purpose", "")).replace("|", "\\|")
        lines.append(f"| {i} | `{node['node_id']}` | `{node.get('status', 'PLANNED')}` | {purpose} | `{node.get('operation', '')}` | {', '.join(f'`{d}`' for d in node.get('depends_on', [])) or '—'} |")
    lines += ["", "## Claims and evidence", "", "| Claim | Status | Evidence | Missing / unverified |", "|---|---|---|---|"]
    for claim in plan.get("claims", []):
        evidence = ", ".join(f"`{x['output']}` ({x['status']})" for x in claim.get("evidence", [])) or "—"
        missing = ", ".join(f"`{x['output']}` ({x['status']})" for x in claim.get("missing_or_unverified", [])) or "—"
        lines.append(f"| `{claim['claim_id']}` | **{claim['status']}** | {evidence} | {missing} |")
    lines += ["", "## Blocked reasons", ""]
    blockers = [(n["node_id"], reason) for n in plan["ordered_nodes"] for reason in n.get("blocked_reasons", [])]
    if blockers:
        for node_id, reason in blockers:
            lines.append(f"- `{node_id}`: {reason}")
    else:
        lines.append("None recorded.")
    unresolved = [x for x in plan.get("external_inputs", []) if x.get("ref") == "UNRESOLVED"]
    if unresolved:
        lines += ["", "### Unresolved external inputs", ""]
        lines.extend(f"- `{x['id']}` (kind: `{x['kind']}`)" for x in unresolved)
    lines += ["", "## Required evidence outputs", ""]
    for node in plan["ordered_nodes"]:
        for output in node.get("outputs", []):
            lines.append(f"- `{node['node_id']}` → `{_output_name(output)}`")
    lines += ["", "## Inventory snapshot", ""]
    if inventory_data is None:
        lines.append("No script inventory was attached to this report.")
    else:
        counts = inventory_data.get("counts", {})
        lines += [f"- Scripts scanned: **{inventory_data.get('script_count', 0)}**",
                  f"- AST parse OK: **{counts.get('parse_ok', 0)}**",
                  f"- AST parse errors: **{counts.get('parse_error', 0)}**",
                  f"- Execution-verified scripts: **{counts.get('execution_verified', 0)}**",
                  f"- Inventory content SHA-256: `{inventory_data.get('content_sha256', 'missing')}`"]
    lines += ["", "## Interpretation and limits", "",
              "A claim is SUPPORTED only when every mapped evidence output comes from a COMPLETED or REUSED node. PLANNED, BLOCKED, FAILED, or SKIPPED outputs do not support conclusions. This framework does not execute arbitrary scripts; execution results must come from explicitly registered adapters, and every COMPLETED/REUSED result must carry artifacts whose SHA-256 is re-computed when results are applied. Producer identity is kind + config reference. A compare output is diagnostic and cannot be reused as a state population.", ""]
    return "\n".join(lines)
