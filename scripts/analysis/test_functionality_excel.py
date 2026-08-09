#!/usr/bin/env python3
"""
Build an Excel inventory of tests/**/*.py business functionality.

Columns:
  - File Name
  - Summary of functionality
  - Referred files
  - Test Class
  - Intent of test class  (combined method intents)

Read-only analysis. No nested dependency deep-walk — only direct imports
resolved to project-style paths when possible.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from typing import Iterable

try:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
except ImportError as e:  # pragma: no cover
    raise SystemExit(f"openpyxl required: {e}") from e

REPO = Path(__file__).resolve().parents[2]
TESTS = REPO / "tests"
OUT = REPO / "docs" / "analysis" / "tests_functionality_inventory.xlsx"

# stdlib / third-party prefixes to keep as package names (not project files)
_NON_PROJECT_ROOTS = frozenset(
    {
        "abc",
        "argparse",
        "ast",
        "asyncio",
        "base64",
        "builtins",
        "collections",
        "concurrent",
        "contextlib",
        "copy",
        "csv",
        "dataclasses",
        "datetime",
        "decimal",
        "enum",
        "fnmatch",
        "functools",
        "gc",
        "glob",
        "hashlib",
        "heapq",
        "hmac",
        "html",
        "http",
        "importlib",
        "inspect",
        "io",
        "itertools",
        "json",
        "logging",
        "math",
        "multiprocessing",
        "numbers",
        "operator",
        "os",
        "pathlib",
        "pickle",
        "platform",
        "pprint",
        "queue",
        "random",
        "re",
        "shutil",
        "signal",
        "socket",
        "sqlite3",
        "statistics",
        "string",
        "struct",
        "subprocess",
        "sys",
        "tempfile",
        "textwrap",
        "threading",
        "time",
        "traceback",
        "types",
        "typing",
        "unittest",
        "urllib",
        "uuid",
        "warnings",
        "weakref",
        "xml",
        "zipfile",
        "zlib",
        # common third-party
        "pytest",
        "numpy",
        "np",
        "pandas",
        "pd",
        "sklearn",
        "scipy",
        "torch",
        "yaml",
        "openpyxl",
        "requests",
        "httpx",
        "pydantic",
        "fastapi",
        "flask",
        "django",
        "matplotlib",
        "seaborn",
        "joblib",
        "tqdm",
        "click",
        "rich",
        "dotenv",
        "MetaTrader5",
        "mt5",
    }
)

_PROJECT_ROOTS = ("src", "tests", "scripts", "configs", "models", "multi_llm", "context")


def _humanize_token(name: str) -> str:
    """test_foo_bar / TestFooBar → readable phrase."""
    s = name
    if s.startswith("test_"):
        s = s[5:]
    elif s.startswith("Test"):
        s = s[4:]
    # CamelCase split
    s = re.sub(r"(?<!^)(?=[A-Z])", " ", s)
    s = s.replace("_", " ").strip()
    s = re.sub(r"\s+", " ", s)
    return s.lower() if s else name


def _doc_first_line(node: ast.AST | None) -> str:
    if node is None:
        return ""
    doc = ast.get_docstring(node) or ""
    if not doc:
        return ""
    line = doc.strip().splitlines()[0].strip()
    return re.sub(r"\s+", " ", line)


def _resolve_module_to_file(mod: str, file_path: Path) -> str | None:
    """Map import module string to a project-relative path if it looks local."""
    if not mod:
        return None
    root = mod.split(".", 1)[0]
    if root in _NON_PROJECT_ROOTS:
        return None
    # relative package under tests
    if root in _PROJECT_ROOTS or mod.startswith("."):
        # handle relative
        if mod.startswith("."):
            # count dots
            dots = len(mod) - len(mod.lstrip("."))
            remainder = mod.lstrip(".")
            base = file_path.parent
            for _ in range(dots - 1):
                base = base.parent
            if remainder:
                candidate = base / Path(*remainder.split("."))
            else:
                candidate = base
        else:
            candidate = REPO / Path(*mod.split("."))

        py = candidate.with_suffix(".py")
        init = candidate / "__init__.py"
        if py.is_file():
            return str(py.relative_to(REPO)).replace("\\", "/")
        if init.is_file():
            return str(init.relative_to(REPO)).replace("\\", "/")
        # best-effort path even if missing (still a referred target)
        rel = str(Path(*mod.split(".")).with_suffix(".py")).replace("\\", "/")
        if root in _PROJECT_ROOTS:
            return rel
        return rel

    # bare local import from same package (e.g. conftest helpers)
    sibling = file_path.parent / f"{root}.py"
    if sibling.is_file():
        return str(sibling.relative_to(REPO)).replace("\\", "/")
    # package under tests
    for base in (TESTS, REPO / "src", REPO / "scripts"):
        cand = base / root
        if (cand.with_suffix(".py")).is_file():
            return str(cand.with_suffix(".py").relative_to(REPO)).replace("\\", "/")
        if (cand / "__init__.py").is_file():
            return str((cand / "__init__.py").relative_to(REPO)).replace("\\", "/")
    return None


def extract_imports(tree: ast.AST, file_path: Path) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()

    def add(mod: str | None) -> None:
        if not mod:
            return
        resolved = _resolve_module_to_file(mod, file_path)
        if resolved and resolved not in seen:
            seen.add(resolved)
            refs.append(resolved)
        elif not resolved:
            # keep project-looking dotted names as-is if root is project-ish
            root = mod.lstrip(".").split(".", 1)[0]
            if root in _PROJECT_ROOTS and mod not in seen:
                seen.add(mod)
                refs.append(mod.replace(".", "/") + ".py")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                base = (
                    ("." * node.level + node.module)
                    if node.level
                    else node.module
                )
                add(base)
                # also try package.submodule when `from pkg import submod`
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    add(f"{base}.{alias.name}")
            elif node.level and node.level > 0:
                add("." * node.level)
                for alias in node.names:
                    if alias.name != "*":
                        add("." * node.level + alias.name)
    return sorted(refs)


def method_intent(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    doc = _doc_first_line(fn)
    if doc:
        return doc
    return f"verifies {_humanize_token(fn.name)}"


def class_intent(cls: ast.ClassDef) -> str:
    """Combine all test methods' intents into one class intent."""
    class_doc = _doc_first_line(cls)
    methods: list[str] = []
    for item in cls.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if item.name.startswith("test") or item.name in {
                "setup_method",
                "teardown_method",
                "setup_class",
                "teardown_class",
            }:
                if item.name.startswith("test"):
                    methods.append(method_intent(item))
    if not methods and not class_doc:
        return f"Test suite for {_humanize_token(cls.name)}"
    parts: list[str] = []
    if class_doc:
        parts.append(class_doc)
    if methods:
        # de-dupe while preserving order
        seen: set[str] = set()
        uniq: list[str] = []
        for m in methods:
            key = m.lower()
            if key not in seen:
                seen.add(key)
                uniq.append(m)
        parts.append("Methods cover: " + "; ".join(uniq))
    return " | ".join(parts)


def module_summary(
    tree: ast.Module,
    file_path: Path,
    classes: list[ast.ClassDef],
    free_tests: list[ast.FunctionDef | ast.AsyncFunctionDef],
) -> str:
    doc = _doc_first_line(tree)
    if doc:
        return doc
    # infer from filename
    stem = file_path.stem
    base = _humanize_token(stem if stem.startswith("test_") else f"test_{stem}")
    if classes:
        class_bits = ", ".join(c.name for c in classes[:6])
        more = f" (+{len(classes)-6} more)" if len(classes) > 6 else ""
        return (
            f"Pytest module covering {base}. "
            f"Defines test class(es): {class_bits}{more}."
        )
    if free_tests:
        return (
            f"Pytest module covering {base} via "
            f"{len(free_tests)} module-level test function(s)."
        )
    # helpers / fixtures / conftest / __init__
    if file_path.name == "conftest.py":
        return "Shared pytest fixtures and hooks for this package."
    if file_path.name == "__init__.py":
        return "Package marker / re-exports for the test package."
    if "fixture" in stem or "helper" in stem or "oracle" in stem:
        return f"Test support module: {base}."
    return f"Python test/support module for {base}."


def iter_py_files(root: Path) -> Iterable[Path]:
    for p in sorted(root.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        yield p


def analyze_file(path: Path) -> list[dict[str, str]]:
    rel = str(path.relative_to(REPO)).replace("\\", "/")
    name = path.name
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(src, filename=str(path))
    except SyntaxError as e:
        return [
            {
                "File Name": name,
                "Relative Path": rel,
                "Summary of functionality": f"Could not parse ({e})",
                "Referred files": "",
                "Test Class": "",
                "Intent of test class": "",
            }
        ]

    assert isinstance(tree, ast.Module)
    refs = extract_imports(tree, path)
    refs_str = "; ".join(refs) if refs else "(no project file imports)"

    classes: list[ast.ClassDef] = [
        n for n in tree.body if isinstance(n, ast.ClassDef)
    ]
    free_tests: list[ast.FunctionDef | ast.AsyncFunctionDef] = [
        n
        for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n.name.startswith("test")
    ]
    summary = module_summary(tree, path, classes, free_tests)

    rows: list[dict[str, str]] = []
    test_classes = [
        c
        for c in classes
        if c.name.startswith("Test")
        or any(
            isinstance(i, (ast.FunctionDef, ast.AsyncFunctionDef))
            and i.name.startswith("test")
            for i in c.body
        )
    ]
    # if no explicit Test* classes but has other classes with test methods
    if not test_classes and classes:
        # still report non-test helper classes? only if they have test_* methods
        test_classes = [
            c
            for c in classes
            if any(
                isinstance(i, (ast.FunctionDef, ast.AsyncFunctionDef))
                and i.name.startswith("test")
                for i in c.body
            )
        ]

    for cls in test_classes:
        rows.append(
            {
                "File Name": name,
                "Relative Path": rel,
                "Summary of functionality": summary,
                "Referred files": refs_str,
                "Test Class": cls.name,
                "Intent of test class": class_intent(cls),
            }
        )

    if free_tests:
        intents = [method_intent(f) for f in free_tests]
        seen: set[str] = set()
        uniq: list[str] = []
        for m in intents:
            k = m.lower()
            if k not in seen:
                seen.add(k)
                uniq.append(m)
        rows.append(
            {
                "File Name": name,
                "Relative Path": rel,
                "Summary of functionality": summary,
                "Referred files": refs_str,
                "Test Class": "(module-level tests)",
                "Intent of test class": "Methods cover: " + "; ".join(uniq),
            }
        )

    if not rows:
        # support / conftest / helpers without tests
        helper_classes = [c.name for c in classes]
        extra = (
            f" Classes: {', '.join(helper_classes)}." if helper_classes else ""
        )
        rows.append(
            {
                "File Name": name,
                "Relative Path": rel,
                "Summary of functionality": summary + extra,
                "Referred files": refs_str,
                "Test Class": "(no test class)",
                "Intent of test class": "Support/fixture module — no test methods defined.",
            }
        )
    return rows


def write_excel(rows: list[dict[str, str]], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "Test Functionality"

    headers = [
        "File Name",
        "Relative Path",
        "Summary of functionality",
        "Referred files",
        "Test Class",
        "Intent of test class",
    ]
    header_fill = PatternFill("solid", fgColor="1F4E79")
    header_font = Font(color="FFFFFF", bold=True)
    wrap = Alignment(wrap_text=True, vertical="top")

    for col, h in enumerate(headers, 1):
        cell = ws.cell(1, col, h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(wrap_text=True, vertical="center")

    for r_i, row in enumerate(rows, 2):
        for c_i, h in enumerate(headers, 1):
            cell = ws.cell(r_i, c_i, row.get(h, ""))
            cell.alignment = wrap

    widths = {
        "A": 42,
        "B": 48,
        "C": 55,
        "D": 55,
        "E": 36,
        "F": 70,
    }
    for letter, w in widths.items():
        ws.column_dimensions[letter].width = w

    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(rows)+1}"
    ws.freeze_panes = "A2"
    ws.row_dimensions[1].height = 22

    # second sheet: one row per file (classes collapsed)
    ws2 = wb.create_sheet("By File")
    for col, h in enumerate(
        ["File Name", "Relative Path", "Summary of functionality", "Referred files", "Test Classes", "Intent of test class"],
        1,
    ):
        cell = ws2.cell(1, col, h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(wrap_text=True, vertical="center")

    by_file: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_file.setdefault(row["Relative Path"], []).append(row)

    r = 2
    for rel, group in sorted(by_file.items()):
        first = group[0]
        classes = " | ".join(
            g["Test Class"] for g in group if g["Test Class"]
        )
        intents = " || ".join(
            f"[{g['Test Class']}] {g['Intent of test class']}" for g in group
        )
        values = [
            first["File Name"],
            rel,
            first["Summary of functionality"],
            first["Referred files"],
            classes,
            intents,
        ]
        for c, v in enumerate(values, 1):
            cell = ws2.cell(r, c, v)
            cell.alignment = wrap
        r += 1

    for letter, w in {"A": 42, "B": 48, "C": 55, "D": 55, "E": 40, "F": 80}.items():
        ws2.column_dimensions[letter].width = w
    ws2.auto_filter.ref = f"A1:F{r-1}"
    ws2.freeze_panes = "A2"

    # readme sheet
    ws3 = wb.create_sheet("README")
    notes = [
        "tests/ Python inventory — business functionality (direct imports only)",
        f"Generated from: {TESTS}",
        "Scope: every .py under tests/ (excluding __pycache__)",
        "Summary of functionality: module docstring first line, else inferred from file/class names",
        "Referred files: direct import targets resolved to project-relative paths (stdlib/third-party omitted)",
        "Intent of test class: class docstring + combined intents of all test_* methods (docstring or humanized name)",
        "Sheet 'Test Functionality': one row per test class (or module-level tests / support module)",
        "Sheet 'By File': one row per file with classes collapsed",
        "No nested/transitive dependency analysis — only imports written in each file",
    ]
    for i, line in enumerate(notes, 1):
        ws3.cell(i, 1, line)
    ws3.column_dimensions["A"].width = 120

    wb.save(out)


def main() -> int:
    rows: list[dict[str, str]] = []
    files = list(iter_py_files(TESTS))
    for p in files:
        rows.extend(analyze_file(p))
    write_excel(rows, OUT)
    print(f"files={len(files)} rows={len(rows)} out={OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
