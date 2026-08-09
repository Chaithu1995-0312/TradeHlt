"""semantic_objects — the GENERATED Object layer of the Semantic OS.

Every Python file in the repository becomes one Object record. **Nothing here is hand-authored.**
Purpose, dependencies, consumers, config keys, tests, ownership, and entry points are all computed
by joining artifacts that already exist, and every emitted field carries an explicit evidence
class so a reader can tell a proven edge from a name-match.

  PROVEN          derived from the artifact that owns the fact (AST, an exact-path registry join)
  HEURISTIC       a curated classification, or a name-based match that could be wrong
  TEXT_REFERENCE  a textual hit — evidence that a string appears, nothing more

The universe is **disk enumeration**, never an artifact's row count. Artifacts are *enrichments*.
This matters: the encyclopedia's 813 rows are stale against 844 code files on disk, and
``module_attribution`` covers 463 of 472 ``src/`` modules. Taking any of them as the denominator
would silently under-report. ``coverage_report()`` publishes each gap instead of hiding it.

Import edges come from a fresh ``ast`` walk (``ast_import_census``), NOT from ``graph.dot``.
``graph.dot`` is ``src/``-scoped AND independently stale (measured 2026-08-08: 347 nodes vs 472
files), so it is kept only as a corroborating cross-check in ``graph_dot_agreement``.

What is deliberately NOT computed — these stay ``None``, never guessed:
  * call-level edges (everything here is module-import level);
  * behavioural test coverage (no coverage data exists in the repo — textual hits are NOT coverage);
  * "runs in production" (``relevance`` / ``reachability_declared`` / import-reachability are three
    different claims and are kept as three separate fields, never collapsed into one ``is_live``);
  * ``owner_surface`` where the attribution registry says ``UNATTRIBUTED`` (it says that for all
    463 of its rows today — the honest answer is the sentinel, not a guess).
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable, Optional

_ROOT = Path(__file__).resolve().parents[2]
_GOV = _ROOT / "docs" / "governance"
_ARCH = _ROOT / "docs" / "architecture"

_ENCYCLOPEDIA = _ROOT / "docs" / "book" / "encyclopedia" / "encyclopedia_rows.jsonl"
_MODULE_STUBS = _GOV / "module_attribution_stubs.jsonl"
_SCRIPT_REGISTRY = _ROOT / "data" / "script_registry.jsonl"
_SCRIPT_STUBS = _GOV / "script_registry_stubs.jsonl"
_CONFIG_GRAPH = _ARCH / "config-consumer-graph.generated.json"
_CITATION_MAP = _ARCH / "citation-map.generated.md"
_FINDINGS_JSONL = _ROOT / "data" / "findings.jsonl"
_FINDINGS_DOC = _ROOT / "docs" / "current-findings.md"
_FRAMEWORK_JSONL = _ROOT / "data" / "framework_registry.jsonl"

#: Import roots, in resolution priority order. Mirrors pyproject's
#: ``pythonpath = ["src", "scripts", "."]`` so a dotted name resolves the way pytest resolves it.
_IMPORT_ROOTS: tuple[tuple[str, str], ...] = (
    ("src", "src/"),
    ("scripts", "scripts/"),
    (".", ""),
)

_UNIVERSE_TREES = {
    "code": ("src", "scripts"),
    "all": ("src", "scripts", "tests"),
}

#: Every emitted field must appear here — ``test_semantic_os_objects`` asserts exhaustiveness, so
#: a new field cannot ship without an explicit, reviewed evidence class.
FIELD_EVIDENCE_CLASS: dict[str, str] = {
    # identity — read straight off disk
    "id": "PROVEN",
    "path": "PROVEN",
    "kind": "PROVEN",
    "bytes": "PROVEN",
    "sha256": "PROVEN",
    "package": "PROVEN",
    "classes": "PROVEN",
    "functions": "PROVEN",
    "has_main": "PROVEN",
    "parse_error": "PROVEN",
    # purpose — curated prose, or a docstring; never synthesised
    "purpose": "TEXT_REFERENCE",
    "purpose_source": "PROVEN",
    "relevance": "HEURISTIC",
    "phase": "HEURISTIC",
    "group": "HEURISTIC",
    "book_status": "HEURISTIC",
    "source_doc": "PROVEN",
    "encyclopedia_id": "PROVEN",
    # dependencies — fresh AST, so the import statement provably exists
    "imports": "PROVEN",
    "imported_by": "PROVEN",
    "unresolved_imports": "PROVEN",
    "dynamic_import_risk": "TEXT_REFERENCE",
    "graph_dot_agreement": "PROVEN",
    # ownership
    "owner_boundary": "PROVEN",
    "owner_surface": "PROVEN",
    "regime": "HEURISTIC",
    "reachability_declared": "HEURISTIC",
    "concepts": "PROVEN",
    "journey_steps": "PROVEN",
    # config
    "config_keys": "PROVEN",
    "config_keys_heuristic": "HEURISTIC",
    # tests — two separate fields; a textual hit is NOT coverage
    "tests_importing": "PROVEN",
    "test_text_references": "TEXT_REFERENCE",
    # docs + evidence
    "doc_citations": "HEURISTIC",
    "findings_evidence": "PROVEN",
    "framework_evidence": "PROVEN",
    # registry joins
    "script_registry": "PROVEN",
    "entry_points": "PROVEN",
    "present_in": "PROVEN",
    # semantic identity — the rename-stable name layer (Semantic File Identity Layer)
    "semantic_id": "HEURISTIC",
    "semantic_name": "HEURISTIC",
    "filename_semantic_status": "HEURISTIC",
    "identity_tier": "PROVEN",
    "identity_provenance": "PROVEN",
}


# ── io helpers ──────────────────────────────────────────────────────────────────────────────

def _read_jsonl(path: Path) -> list[dict]:
    out: list[dict] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:  # noqa: BLE001
                    continue
    except Exception:  # noqa: BLE001
        return []
    return out


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def _posix(path: Path, root: Path = _ROOT) -> str:
    return path.relative_to(root).as_posix()


# ── universe ────────────────────────────────────────────────────────────────────────────────

def discover_universe(universe: str = "code", root: Path = _ROOT) -> list[str]:
    """Every Python file in scope, from DISK — the denominator, never an artifact's row count."""
    if universe not in _UNIVERSE_TREES:
        raise ValueError(f"unknown universe {universe!r}; expected one of {sorted(_UNIVERSE_TREES)}")
    found: set[str] = set()
    for tree in _UNIVERSE_TREES[universe]:
        base = root / tree
        if base.is_dir():
            found |= {_posix(p, root) for p in base.rglob("*.py")}
    found |= {_posix(p, root) for p in root.glob("*.py")}  # repo-root scripts
    return sorted(found)


def _kind_for(rel_path: str) -> str:
    if rel_path.startswith("src/"):
        return "module"
    if rel_path.startswith("tests/"):
        return "test"
    if rel_path.startswith("scripts/"):
        return "script"
    return "root_script"


def _package_for(rel_path: str) -> Optional[str]:
    """Dotted package, with ``src/`` stripped so it joins against ``graph.dot`` node names."""
    trimmed = rel_path[:-len(".py")] if rel_path.endswith(".py") else rel_path
    if trimmed.endswith("/__init__"):
        trimmed = trimmed[: -len("/__init__")]
    if trimmed.startswith("src/"):
        trimmed = trimmed[len("src/"):]
    if "/" not in trimmed:
        return None
    return trimmed.rsplit("/", 1)[0].replace("/", ".")


# ── AST: source facts + import census ───────────────────────────────────────────────────────

def _dotted_candidates(rel_path: str) -> list[str]:
    """Every dotted name this file answers to, given the configured import roots."""
    if not rel_path.endswith(".py"):
        return []
    trimmed = rel_path[: -len(".py")]
    if trimmed.endswith("/__init__"):
        trimmed = trimmed[: -len("/__init__")]
    out: list[str] = []
    for _label, prefix in _IMPORT_ROOTS:
        if prefix and not trimmed.startswith(prefix):
            continue
        stripped = trimmed[len(prefix):] if prefix else trimmed
        if stripped:
            out.append(stripped.replace("/", "."))
    return out


def build_module_index(paths: Iterable[str]) -> dict[str, str]:
    """dotted name -> repo path. Earlier import roots win, so resolution is deterministic."""
    index: dict[str, str] = {}
    for rel_path in sorted(paths):
        for priority, dotted in enumerate(_dotted_candidates(rel_path)):
            existing = index.get(dotted)
            if existing is None:
                index[dotted] = rel_path
            elif existing != rel_path:
                # first writer wins; ties are resolved by the sorted path order above
                continue
    return index


def _read_source(rel_path: str, root: Path = _ROOT) -> str:
    """Read a .py file the way the interpreter does — ``utf-8-sig`` strips a leading BOM.

    Reading BOM'd files as plain ``utf-8`` leaves a U+FEFF that ``ast.parse`` rejects even though
    CPython runs the file fine, which would report a false syntax error (real case in this repo:
    ``scripts/governance/build_g001_consumer_attribution.py``).
    """
    return (root / rel_path).read_text(encoding="utf-8-sig", errors="replace")


def _parse(rel_path: str, root: Path = _ROOT) -> tuple[Optional[ast.Module], str]:
    try:
        text = _read_source(rel_path, root)
    except Exception as exc:  # noqa: BLE001
        return None, f"unreadable: {exc}"
    try:
        return ast.parse(text), ""
    except SyntaxError as exc:
        return None, f"syntax_error: line {exc.lineno}"


def _imported_names(tree: ast.Module, rel_path: str) -> set[str]:
    """Dotted names this module imports, including ``from X import Y`` -> ``X.Y`` candidates."""
    names: set[str] = set()
    package = _package_for(rel_path) or ""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import — resolve against this file's package
                parts = package.split(".") if package else []
                base = ".".join(parts[: len(parts) - node.level + 1]) if parts else ""
                module = f"{base}.{node.module}" if node.module and base else (node.module or base)
            else:
                module = node.module or ""
            if not module:
                continue
            names.add(module)
            for alias in node.names:
                if alias.name != "*":
                    names.add(f"{module}.{alias.name}")
    return names


def ast_import_census(
    paths: Iterable[str], root: Path = _ROOT
) -> tuple[dict[str, list[str]], dict[str, list[str]], dict[str, list[str]], dict[str, str]]:
    """Fresh import graph over the whole universe.

    Returns ``(imports, imported_by, unresolved, parse_errors)``, all keyed by repo path with
    sorted values. Unlike ``graph.dot`` this covers ``scripts/``, ``tests/``, and repo-root files,
    and it is recomputed from disk on every seed so it can never go stale.
    """
    paths = sorted(paths)
    index = build_module_index(paths)
    imports: dict[str, list[str]] = {}
    unresolved: dict[str, list[str]] = {}
    imported_by: dict[str, set[str]] = {p: set() for p in paths}
    parse_errors: dict[str, str] = {}

    for rel_path in paths:
        tree, err = _parse(rel_path, root)
        if tree is None:
            parse_errors[rel_path] = err
            imports[rel_path] = []
            unresolved[rel_path] = []
            continue
        resolved: set[str] = set()
        external: set[str] = set()
        for name in _imported_names(tree, rel_path):
            target = index.get(name)
            if target is None:
                # `from X import Y` where Y is a symbol, not a module — fall back to X
                head = name.rsplit(".", 1)[0]
                target = index.get(head) if "." in name else None
            if target is not None and target != rel_path:
                resolved.add(target)
            elif target is None and "." not in name:
                external.add(name)
        imports[rel_path] = sorted(resolved)
        unresolved[rel_path] = sorted(external)
        for target in resolved:
            imported_by.setdefault(target, set()).add(rel_path)

    return imports, {k: sorted(v) for k, v in imported_by.items()}, unresolved, parse_errors


def _is_main_guard(node: ast.stmt) -> bool:
    """True for a top-level ``if __name__ == "__main__":`` block (AST, not a text scan)."""
    if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
        return False
    test = node.test
    left_is_name = isinstance(test.left, ast.Name) and test.left.id == "__name__"
    if not left_is_name or not test.comparators:
        return False
    right = test.comparators[0]
    return isinstance(right, ast.Constant) and right.value == "__main__"


def _source_facts(rel_path: str, root: Path = _ROOT) -> dict:
    raw = b""
    try:
        raw = (root / rel_path).read_bytes()
    except Exception:  # noqa: BLE001
        pass
    tree, err = _parse(rel_path, root)
    facts = {
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest() if raw else None,
        "classes": [],
        "functions": [],
        "has_main": False,
        "parse_error": err or None,
        "docstring_line1": None,
        "dynamic_import_risk": False,
    }
    text = raw.decode("utf-8-sig", errors="replace")
    facts["dynamic_import_risk"] = bool(
        re.search(r"\bimportlib\b|\b__import__\s*\(", text)
    )
    if tree is None:
        return facts
    facts["has_main"] = any(_is_main_guard(node) for node in tree.body)
    facts["classes"] = sorted(
        n.name for n in tree.body if isinstance(n, ast.ClassDef)
    )
    facts["functions"] = sorted(
        n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    )
    doc = ast.get_docstring(tree)
    if doc:
        first = doc.strip().splitlines()[0].strip()
        facts["docstring_line1"] = first or None
    return facts


# ── enrichment indexes ──────────────────────────────────────────────────────────────────────

def _encyclopedia_index() -> dict[str, dict]:
    return {
        str(r.get("path", "")).replace("\\", "/"): r
        for r in _read_jsonl(_ENCYCLOPEDIA)
        if r.get("path")
    }


def _module_attribution_index() -> dict[str, dict]:
    return {
        str(r.get("module_path", "")).replace("\\", "/"): r
        for r in _read_jsonl(_MODULE_STUBS)
        if r.get("module_path")
    }


def _script_registry_index() -> dict[str, dict]:
    rows = _read_jsonl(_SCRIPT_REGISTRY) or _read_jsonl(_SCRIPT_STUBS)
    return {str(r.get("path", "")).replace("\\", "/"): r for r in rows if r.get("path")}


def _config_index() -> tuple[dict[str, list[str]], dict[str, str]]:
    """file path -> config keys it consumes, plus each key's reachability verdict."""
    graph = _read_json(_CONFIG_GRAPH) or {}
    verdicts: dict[str, str] = {}
    for node in graph.get("nodes") or []:
        if node.get("type") == "config_key" and node.get("id"):
            verdicts[node["id"][len("cfg:"):]] = str(node.get("verdict") or "UNKNOWN")
    by_file: dict[str, set[str]] = {}
    for edge in graph.get("edges") or []:
        src, dst = str(edge.get("from", "")), str(edge.get("to", ""))
        if not src.startswith("cfg:") or not dst.startswith("file:"):
            continue
        by_file.setdefault(dst[len("file:"):].replace("\\", "/"), set()).add(src[len("cfg:"):])
    return {k: sorted(v) for k, v in by_file.items()}, verdicts


def _citation_index() -> dict[str, list[str]]:
    """path-or-basename -> citing docs. HEURISTIC: several rows store a bare basename."""
    out: dict[str, set[str]] = {}
    try:
        text = _CITATION_MAP.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        return {}
    for line in text.splitlines():
        if not line.startswith("| `") or line.startswith("| ---"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        path = cells[1].strip("` ")
        docs = re.findall(r"`([^`]+\.md)`", cells[2])
        if path:
            out.setdefault(path.replace("\\", "/"), set()).update(docs)
    return {k: sorted(v) for k, v in out.items()}


_PATH_IN_PROSE = re.compile(r"\b((?:docs|src|tests|scripts|configs|models)/[\w./\-]+\.\w+)")


def _findings_evidence_index() -> dict[str, list[str]]:
    """repo path -> finding ids citing it as evidence (exact path match only)."""
    out: dict[str, set[str]] = {}
    rows = _read_jsonl(_FINDINGS_JSONL)
    if rows:
        for row in rows:
            fid = row.get("id")
            if not fid or row.get("kind") == "meta":
                continue
            for path in row.get("evidence_paths") or []:
                out.setdefault(str(path).replace("\\", "/"), set()).add(fid)
        if out:
            return {k: sorted(v) for k, v in out.items()}
    # Fallback: the tracked findings doc is the source the export derives from anyway.
    try:
        text = _FINDINGS_DOC.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        return {}
    current = None
    for line in text.splitlines():
        header = re.match(r"^###\s+(F-\d{3})\b", line)
        if header:
            current = header.group(1)
            continue
        if current:
            for path in _PATH_IN_PROSE.findall(line):
                out.setdefault(path, set()).add(current)
    return {k: sorted(v) for k, v in out.items()}


def _framework_evidence_index() -> dict[str, list[str]]:
    out: dict[str, set[str]] = {}
    for row in _read_jsonl(_FRAMEWORK_JSONL):
        cid = row.get("id")
        if not cid:
            continue
        for ev in row.get("evidence") or []:
            path = str((ev or {}).get("path", "")).replace("\\", "/")
            if path:
                out.setdefault(path, set()).add(cid)
    return {k: sorted(v) for k, v in out.items()}


def _test_text_index(paths: Iterable[str], root: Path = _ROOT) -> dict[str, list[str]]:
    """basename -> test files whose TEXT mentions it. Textual evidence only, never coverage."""
    test_files = sorted(p for p in paths if p.startswith("tests/"))
    if not test_files:
        test_files = sorted(_posix(p, root) for p in (root / "tests").rglob("*.py"))
    bodies: list[tuple[str, str]] = []
    for rel in test_files:
        try:
            bodies.append((rel, (root / rel).read_text(encoding="utf-8", errors="replace")))
        except Exception:  # noqa: BLE001
            continue
    out: dict[str, set[str]] = {}
    for rel, text in bodies:
        for token in set(re.findall(r"\b([\w\-]+\.py)\b", text)):
            out.setdefault(token, set()).add(rel)
    return {k: sorted(v) for k, v in out.items()}


# ── build ───────────────────────────────────────────────────────────────────────────────────

def build_objects(
    universe: str = "code",
    generated_at: str = "",
    root: Path = _ROOT,
    registry: Any = None,
) -> list[dict]:
    """Compute the full Object layer. Deterministic: sorted paths, sorted values, no clock reads."""
    paths = discover_universe(universe, root)
    # tests/ are always indexed (for tests_importing) even when outside the emitted universe
    scan_paths = sorted(set(paths) | {_posix(p, root) for p in (root / "tests").rglob("*.py")})

    imports, imported_by, unresolved, parse_errors = ast_import_census(scan_paths, root)
    enc = _encyclopedia_index()
    attribution = _module_attribution_index()
    scripts = _script_registry_index()
    config_by_file, config_verdicts = _config_index()
    citations = _citation_index()
    findings = _findings_evidence_index()
    framework = _framework_evidence_index()
    test_text = _test_text_index(scan_paths, root)

    if registry is None:
        try:
            from governance.semantic_os import SemanticOSRegistry

            registry = SemanticOSRegistry.load()
        except Exception:  # noqa: BLE001
            registry = None

    boundary_of: dict[str, str] = {}
    concepts_of: dict[str, list[str]] = {}
    steps_of: dict[str, list[str]] = {}
    if registry is not None:
        from governance.semantic_os import resolve_members

        for bid, boundary in sorted(registry.boundaries.items()):
            for member in resolve_members(
                boundary.get("members") or [], boundary.get("members_exclude") or [], root
            ):
                boundary_of.setdefault(member, bid)
        by_boundary: dict[str, list[str]] = {}
        for cid, concept in sorted(registry.concepts.items()):
            owner = concept.get("owner_boundary")
            if owner:
                by_boundary.setdefault(owner, []).append(cid)
        step_by_boundary: dict[str, list[str]] = {}
        for _journey, step in registry.steps():
            if step.get("boundary"):
                step_by_boundary.setdefault(step["boundary"], []).append(step["step_id"])
        for path, bid in boundary_of.items():
            concepts_of[path] = sorted(by_boundary.get(bid, []))
            steps_of[path] = sorted(step_by_boundary.get(bid, []))

    try:
        from governance.semantic_os import graph_dot_modules, path_to_dotted

        graph_nodes = graph_dot_modules()
    except Exception:  # noqa: BLE001
        graph_nodes, path_to_dotted = set(), lambda _p: None  # type: ignore[assignment]

    # Semantic File Identity join — computed IN-PROCESS (not read from data/semantic_os/
    # file_identities.jsonl): this function is called directly by test fixtures with no seed
    # guarantee, and the seeder itself calls build_objects, so reading the projection here would
    # create an order dependency between two outputs of the same command.
    identity_of: dict[str, dict] = {}
    if registry is not None:
        from governance.semantic_identity import derive_tier3_identities, resolve_identity_index

        curated_identities = getattr(registry, "file_identities", {}) or {}
        derived_identities = derive_tier3_identities(discover_universe("code", root), curated_identities)
        identity_of = resolve_identity_index(curated_identities, derived_identities)

    objects: list[dict] = []
    for rel_path in paths:
        facts = _source_facts(rel_path, root)
        enc_row = enc.get(rel_path) or {}
        attr_row = attribution.get(rel_path) or {}
        scr_row = scripts.get(rel_path) or {}
        basename = rel_path.rsplit("/", 1)[-1]

        purpose = enc_row.get("purpose") or facts["docstring_line1"]
        purpose_source = (
            "encyclopedia" if enc_row.get("purpose")
            else ("docstring_line1" if facts["docstring_line1"] else None)
        )

        keys = config_by_file.get(rel_path, [])
        proven_keys = [k for k in keys if config_verdicts.get(k) == "READ_AND_USED"]
        heuristic_keys = [k for k in keys if k not in proven_keys]

        dotted = path_to_dotted(rel_path)
        if dotted is None:
            agreement = "NOT_APPLICABLE"  # graph.dot is src/-scoped by construction
        elif dotted in graph_nodes:
            agreement = "PRESENT"
        else:
            agreement = "ABSENT_STALE_GRAPH"

        present_in = sorted(
            label for label, hit in (
                ("encyclopedia", bool(enc_row)),
                ("module_attribution", bool(attr_row)),
                ("script_registry", bool(scr_row)),
            ) if hit
        )

        entry_points = sorted(
            f"{label}:{scr_row[key]}"
            for label, key in (("control_plane", "control_plane_id"), ("agent_tool", "agent_tool_id"))
            if scr_row.get(key)
        )

        identity = identity_of.get(rel_path)

        objects.append({
            "id": f"OBJ:{rel_path}",
            "path": rel_path,
            "kind": _kind_for(rel_path),
            "bytes": facts["bytes"],
            "sha256": facts["sha256"],
            "package": _package_for(rel_path),
            "classes": facts["classes"],
            "functions": facts["functions"],
            "has_main": facts["has_main"],
            "parse_error": parse_errors.get(rel_path) or facts["parse_error"],

            "purpose": purpose,
            "purpose_source": purpose_source,
            "relevance": enc_row.get("relevance"),
            "phase": enc_row.get("phase"),
            "group": enc_row.get("group"),
            "book_status": enc_row.get("book_status"),
            "source_doc": enc_row.get("source_doc"),
            "encyclopedia_id": enc_row.get("id"),

            "imports": imports.get(rel_path, []),
            "imported_by": imported_by.get(rel_path, []),
            "unresolved_imports": unresolved.get(rel_path, []),
            "dynamic_import_risk": facts["dynamic_import_risk"],
            "graph_dot_agreement": agreement,

            "owner_boundary": boundary_of.get(rel_path),
            "owner_surface": attr_row.get("owner_surface"),
            "regime": attr_row.get("regime"),
            "reachability_declared": attr_row.get("reachability"),
            "concepts": concepts_of.get(rel_path, []),
            "journey_steps": steps_of.get(rel_path, []),

            "config_keys": proven_keys,
            "config_keys_heuristic": heuristic_keys,

            "tests_importing": [p for p in imported_by.get(rel_path, []) if p.startswith("tests/")],
            "test_text_references": test_text.get(basename, []),

            "doc_citations": sorted(set(citations.get(rel_path, [])) | set(citations.get(basename, []))),
            "findings_evidence": findings.get(rel_path, []),
            "framework_evidence": framework.get(rel_path, []),

            "script_registry": {k: scr_row[k] for k in sorted(scr_row)} or None,
            "entry_points": entry_points,
            "present_in": present_in,

            "semantic_id": identity["id"] if identity else None,
            "semantic_name": identity["semantic_name"] if identity else None,
            "filename_semantic_status": identity["filename_semantic_status"] if identity else None,
            "identity_tier": identity["tier"] if identity else None,
            "identity_provenance": identity["provenance"] if identity else None,
        })

    return sorted(objects, key=lambda o: o["id"])


def coverage_report(objects: list[dict]) -> dict:
    """Publish every denominator gap rather than adopting an artifact's stale row count."""
    total = len(objects)
    by_kind: dict[str, int] = {}
    for obj in objects:
        by_kind[obj["kind"]] = by_kind.get(obj["kind"], 0) + 1

    missing_enc = sorted(o["path"] for o in objects if "encyclopedia" not in o["present_in"])
    src_objects = [o for o in objects if o["kind"] == "module"]
    missing_attr = sorted(
        o["path"] for o in src_objects if "module_attribution" not in o["present_in"]
    )
    unattributed = sum(1 for o in src_objects if (o.get("owner_surface") or "UNATTRIBUTED") == "UNATTRIBUTED")
    stale_graph = sorted(o["path"] for o in objects if o["graph_dot_agreement"] == "ABSENT_STALE_GRAPH")

    return {
        "total_objects": total,
        "by_kind": dict(sorted(by_kind.items())),
        "encyclopedia": {
            "covered": total - len(missing_enc),
            "missing_count": len(missing_enc),
            "missing_sample": missing_enc[:10],
            "note": "encyclopedia_rows.jsonl is a stale enrichment, never the denominator",
        },
        "module_attribution": {
            "src_modules": len(src_objects),
            "missing_count": len(missing_attr),
            "missing_sample": missing_attr[:10],
            "unattributed_owner_surface": unattributed,
            "note": (
                "owner_surface is UNATTRIBUTED across the whole attribution registry today; "
                "the answerable ownership question is owner_boundary"
            ),
        },
        "graph_dot": {
            "absent_count": len(stale_graph),
            "absent_sample": stale_graph[:10],
            "note": "graph.dot is src/-scoped and stale; import edges come from ast_import_census",
        },
        "boundary_claimed": sum(1 for o in objects if o.get("owner_boundary")),
        "parse_errors": sorted(o["path"] for o in objects if o.get("parse_error")),
        "identity": {
            "curated": sum(1 for o in objects if o.get("identity_provenance") == "CURATED"),
            "tier1": sum(1 for o in objects if o.get("identity_tier") == 1),
            "tier2": sum(1 for o in objects if o.get("identity_tier") == 2),
            "derived": sum(1 for o in objects if o.get("identity_provenance") == "DERIVED"),
            "misleading": sum(1 for o in objects if o.get("filename_semantic_status") == "MISLEADING"),
            "compatibility": sum(1 for o in objects if o.get("filename_semantic_status") == "COMPATIBILITY"),
            "historical": sum(1 for o in objects if o.get("filename_semantic_status") == "HISTORICAL"),
            "split": sum(1 for o in objects if o.get("filename_semantic_status") == "SPLIT"),
            "unknown": sum(1 for o in objects if o.get("filename_semantic_status") == "UNKNOWN"),
            "note": (
                "Tier 3 identities are path-derived with filename_semantic_status UNKNOWN — a "
                "slug, not a reviewed claim. See docs/governance/SEMANTIC_FILE_IDENTITY_REPORT.md"
            ),
        },
    }
