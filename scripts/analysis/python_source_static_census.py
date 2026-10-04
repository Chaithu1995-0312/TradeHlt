# save as: scripts/analysis/python_source_static_census.py

from __future__ import annotations

import ast
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SOURCE_ROOTS = [
    ROOT / "src",
    ROOT / "scripts",
]

TEST_ROOTS = [
    ROOT / "tests",
    ROOT / "test",
]

EXCLUDED_PARTS = {
    ".git",
    ".claude",
    "archive",
    "venv",
    ".venv",
    "node_modules",
    "dist",
    "build",
    "target",
    "__pycache__",
}

OUTPUT_JSONL = ROOT / "python_source_static_census.jsonl"
OUTPUT_CSV = ROOT / "python_source_static_census.csv"
SUMMARY_JSON = ROOT / "python_source_static_census_summary.json"


CONFIG_PATTERNS = (
    re.compile(r"\b(?:config|cfg|settings|params|parameters)\s*\["),
    re.compile(r"\b(?:config|cfg|settings|params|parameters)\.get\s*\("),
    re.compile(r"\bget_prod_config\s*\("),
    re.compile(r"\bget_prod_section\s*\("),
    re.compile(r"\bConfigBuilder\.build\s*\("),
    re.compile(r"\bos\.environ\b"),
    re.compile(r"\bos\.getenv\s*\("),
)

FILE_IO_PATTERNS = (
    re.compile(r"\bopen\s*\("),
    re.compile(r"\bPath\s*\([^)]*\)\.(?:read_text|write_text|read_bytes|write_bytes|open)\s*\("),
    re.compile(r"\b(?:read_csv|to_csv|read_json|to_json|read_parquet|to_parquet|read_pickle|to_pickle)\s*\("),
)

NETWORK_PATTERNS = (
    re.compile(r"\brequests\.(?:get|post|put|patch|delete|request)\s*\("),
    re.compile(r"\bhttpx\.(?:get|post|put|patch|delete|request|Client|AsyncClient)\b"),
    re.compile(r"\baiohttp\.(?:ClientSession|request)\b"),
    re.compile(r"\burllib\.request\b"),
    re.compile(r"\bsocket\.(?:socket|create_connection)\b"),
)

SUBPROCESS_PATTERNS = (
    re.compile(r"\bsubprocess\.(?:run|Popen|call|check_call|check_output)\s*\("),
    re.compile(r"\bos\.system\s*\("),
    re.compile(r"\bos\.popen\s*\("),
)


def canonical_python_files() -> list[Path]:
    files = []

    for source_root in SOURCE_ROOTS:
        if not source_root.exists():
            continue

        for path in source_root.rglob("*.py"):
            if any(part in EXCLUDED_PARTS for part in path.parts):
                continue
            files.append(path.resolve())

    return sorted(set(files))


def test_python_files() -> list[Path]:
    files = []

    for test_root in TEST_ROOTS:
        if not test_root.exists():
            continue

        for path in test_root.rglob("*.py"):
            if any(part in EXCLUDED_PARTS for part in path.parts):
                continue
            files.append(path.resolve())

    return sorted(set(files))


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def code_loc(text: str) -> int:
    """
    Approximate source LOC:
    count non-empty, non-comment physical lines.

    Important:
    This is NOT authoritative cloc LOC.
    cloc reconciliation is performed separately.
    """
    count = 0

    for line in text.splitlines():
        stripped = line.strip()

        if not stripped:
            continue

        if stripped.startswith("#"):
            continue

        count += 1

    return count


def module_name(path: Path) -> str:
    relative = path.relative_to(ROOT).with_suffix("")
    return ".".join(relative.parts)


def imported_module_names(tree: ast.AST) -> list[str]:
    imports = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)

        elif isinstance(node, ast.ImportFrom):
            prefix = "." * node.level
            module = node.module or ""
            imports.add(prefix + module)

    return sorted(imports)


def internal_import_names(imports: list[str]) -> list[str]:
    internal = []

    for name in imports:
        normalized = name.lstrip(".")

        if (
            normalized == "src"
            or normalized.startswith("src.")
            or normalized == "scripts"
            or normalized.startswith("scripts.")
            or normalized == "config_layer"
            or normalized.startswith("config_layer.")
            or normalized == "core"
            or normalized.startswith("core.")
            or normalized == "engines"
            or normalized.startswith("engines.")
            or normalized == "features"
            or normalized.startswith("features.")
            or normalized == "runtime"
            or normalized.startswith("runtime.")
        ):
            internal.append(name)

    return sorted(set(internal))


def top_level_execution(tree: ast.Module) -> bool:
    """
    Detect executable module-level statements.

    Imports, definitions, assignments, and docstrings do not count.
    __main__ guards count separately as entry-point markers.
    """

    passive_nodes = (
        ast.Import,
        ast.ImportFrom,
        ast.FunctionDef,
        ast.AsyncFunctionDef,
        ast.ClassDef,
        ast.Assign,
        ast.AnnAssign,
    )

    for node in tree.body:
        if isinstance(node, passive_nodes):
            continue

        if isinstance(node, ast.Expr):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                continue

        if is_main_guard(node):
            continue

        return True

    return False


def is_main_guard(node: ast.AST) -> bool:
    if not isinstance(node, ast.If):
        return False

    test = node.test

    return (
        isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Name)
        and test.left.id == "__name__"
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.Eq)
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value == "__main__"
    )


def entry_point_markers(tree: ast.Module) -> list[str]:
    markers = set()

    for node in tree.body:
        if is_main_guard(node):
            markers.add("__main__")

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in {"main", "cli", "run", "serve", "worker"}:
                markers.add(f"function:{node.name}")

    return sorted(markers)


def count_pattern_hits(text: str, patterns: tuple[re.Pattern, ...]) -> int:
    return sum(len(pattern.findall(text)) for pattern in patterns)


def build_test_reference_index(
    source_files: list[Path],
    tests: list[Path],
) -> dict[str, list[str]]:

    references: dict[str, set[str]] = defaultdict(set)

    source_by_stem: dict[str, list[Path]] = defaultdict(list)
    source_by_module: dict[str, Path] = {}

    for source in source_files:
        source_by_stem[source.stem].append(source)
        source_by_module[module_name(source)] = source

    for test in tests:
        try:
            text = test.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(text, filename=str(test))
        except SyntaxError:
            continue

        imports = imported_module_names(tree)

        for imported in imports:
            normalized = imported.lstrip(".")

            for source_module, source_path in source_by_module.items():
                if (
                    normalized == source_module
                    or normalized.endswith("." + source_module)
                    or source_module.endswith("." + normalized)
                ):
                    references[rel(source_path)].add(rel(test))

        tokens = set(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", text))

        for token in tokens:
            for source_path in source_by_stem.get(token, []):
                references[rel(source_path)].add(rel(test))

    return {
        source: sorted(test_paths)
        for source, test_paths in references.items()
    }


def analyze_file(
    path: Path,
    test_reference_index: dict[str, list[str]],
) -> dict:

    relative_path = rel(path)

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(text, filename=str(path))
        parse_status = "OK"
        syntax_error = None

    except SyntaxError as exc:
        text = path.read_text(encoding="utf-8", errors="replace")
        tree = None
        parse_status = "SYNTAX_ERROR"
        syntax_error = f"{exc.msg} line={exc.lineno}"

    if tree is None:
        return {
            "path": relative_path,
            "loc_approx": code_loc(text),
            "classes": None,
            "functions": None,
            "async_functions": None,
            "imports": [],
            "internal_imports": [],
            "entry_point_markers": [],
            "config_reads": count_pattern_hits(text, CONFIG_PATTERNS),
            "file_io_hits": count_pattern_hits(text, FILE_IO_PATTERNS),
            "subprocess_usage": count_pattern_hits(text, SUBPROCESS_PATTERNS),
            "network_usage": count_pattern_hits(text, NETWORK_PATTERNS),
            "top_level_execution": None,
            "test_references": test_reference_index.get(relative_path, []),
            "test_reference_count": len(test_reference_index.get(relative_path, [])),
            "parse_status": parse_status,
            "syntax_error": syntax_error,
        }

    classes = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
    ]

    functions = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    ]

    async_functions = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef)
    ]

    imports = imported_module_names(tree)

    test_references = test_reference_index.get(relative_path, [])

    return {
        "path": relative_path,
        "loc_approx": code_loc(text),
        "classes": sorted(classes),
        "class_count": len(classes),
        "functions": sorted(functions),
        "function_count": len(functions),
        "async_functions": sorted(async_functions),
        "async_function_count": len(async_functions),
        "imports": imports,
        "import_count": len(imports),
        "internal_imports": internal_import_names(imports),
        "internal_import_count": len(internal_import_names(imports)),
        "entry_point_markers": entry_point_markers(tree),
        "config_reads": count_pattern_hits(text, CONFIG_PATTERNS),
        "file_io_hits": count_pattern_hits(text, FILE_IO_PATTERNS),
        "subprocess_usage": count_pattern_hits(text, SUBPROCESS_PATTERNS),
        "network_usage": count_pattern_hits(text, NETWORK_PATTERNS),
        "top_level_execution": top_level_execution(tree),
        "test_references": test_references,
        "test_reference_count": len(test_references),
        "parse_status": parse_status,
        "syntax_error": syntax_error,
    }


def main() -> None:
    source_files = canonical_python_files()
    tests = test_python_files()

    test_reference_index = build_test_reference_index(source_files, tests)

    records = [
        analyze_file(path, test_reference_index)
        for path in source_files
    ]

    with OUTPUT_JSONL.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    csv_fields = [
        "path",
        "loc_approx",
        "class_count",
        "function_count",
        "async_function_count",
        "import_count",
        "internal_import_count",
        "entry_point_markers",
        "config_reads",
        "file_io_hits",
        "subprocess_usage",
        "network_usage",
        "top_level_execution",
        "test_reference_count",
        "parse_status",
        "syntax_error",
    ]

    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=csv_fields)
        writer.writeheader()

        for record in records:
            row = {
                field: record.get(field)
                for field in csv_fields
            }

            row["entry_point_markers"] = json.dumps(
                row["entry_point_markers"]
            )

            writer.writerow(row)

    summary = {
        "schema": "python_source_static_census.v1",
        "source_roots": [rel(root) for root in SOURCE_ROOTS],
        "source_file_count": len(source_files),
        "test_file_count": len(tests),
        "parse_ok": sum(r["parse_status"] == "OK" for r in records),
        "parse_errors": sum(r["parse_status"] != "OK" for r in records),
        "files_with_test_references": sum(
            r["test_reference_count"] > 0
            for r in records
        ),
        "files_with_entry_point_markers": sum(
            bool(r["entry_point_markers"])
            for r in records
        ),
        "files_with_top_level_execution": sum(
            r["top_level_execution"] is True
            for r in records
        ),
        "files_with_config_reads": sum(
            r["config_reads"] > 0
            for r in records
        ),
        "files_with_file_io": sum(
            r["file_io_hits"] > 0
            for r in records
        ),
        "files_with_subprocess_usage": sum(
            r["subprocess_usage"] > 0
            for r in records
        ),
        "files_with_network_usage": sum(
            r["network_usage"] > 0
            for r in records
        ),
    }

    SUMMARY_JSON.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()