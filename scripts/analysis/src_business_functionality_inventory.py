#!/usr/bin/env python3
"""Inventory business functionality of the repository's non-test Python trees.

Columns: File Name | Summary of functionality | Referred files
Output: results/analysis/src_business_functionality.xlsx — one sheet per tree.

Trees covered (see ``TREES``): ``src/`` (the original scope), ``tools/``,
``exec_telemetry/``, and the repo-root ``*.py`` files. ``scripts/`` has its own
long-standing workbook at the repo root and is emitted here only on request
(``--tree scripts --out <path>``) so its output can be diffed rather than
silently overwritten.

The ``src`` sheet is byte-compatible with the pre-multi-tree version: relative-import
resolution and the project-reference filter are unchanged for that tree.

Usage:
    python scripts/analysis/src_business_functionality_inventory.py
    python scripts/analysis/src_business_functionality_inventory.py --tree tools
    python scripts/analysis/src_business_functionality_inventory.py --tree scripts --out /tmp/s.xlsx
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    print("pandas required", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"

#: Value written to "Referred files" when a module imports nothing project-local.
_NO_REFS = "(none / stdlib-only)"
OUT = ROOT / "results" / "analysis" / "src_business_functionality.xlsx"


@dataclass(frozen=True)
class Tree:
    """One Python tree to inventory, and how to resolve its imports.

    ``extra_tops`` widens the project-reference filter beyond ``src/``'s own
    subpackages. It is deliberately EMPTY for ``src`` so that sheet reproduces the
    original single-tree output exactly.
    """

    key: str
    sheet: str
    root: Path
    recursive: bool = True
    extra_tops: frozenset = field(default_factory=frozenset)
    #: Does the Semantic OS declare file identities for this tree? Sheets where it
    #: does not must NOT be enriched — a blank Semantic ID column would read as
    #: "coverage measured at zero" rather than "coverage not measured".
    has_identities: bool = False
    #: Write ``File Name`` relative to the TREE root rather than the repo root.
    #: Only ``scripts`` uses this, to preserve the convention its long-standing
    #: workbook already ships — the enrichment join reads that column verbatim.
    relative_to_tree: bool = False
    #: Emit the legacy ``Counts`` summary sheet alongside this tree's sheet.
    counts_sheet: bool = False


#: Sibling trees an import may legitimately name. ``multi_llm`` is deliberately absent:
#: the repo-root ``multi_llm/`` holds no Python, while ``src/multi_llm/`` does, so claiming
#: the name here would misroute ``src`` imports away from the package that really backs them.
_TREE_TOPS = frozenset({"src", "scripts", "tools", "tests", "mt5_analytics", "exec_telemetry"})

TREES: dict[str, Tree] = {
    "src": Tree("src", "src_py_inventory", SRC, True, frozenset(), True),
    "tools": Tree("tools", "tools_py_inventory", ROOT / "tools", True, _TREE_TOPS, False),
    "exec_telemetry": Tree(
        "exec_telemetry",
        "exec_telemetry_py_inventory",
        ROOT / "exec_telemetry",
        True,
        _TREE_TOPS,
        False,
    ),
    "root": Tree("root", "root_py_inventory", ROOT, False, _TREE_TOPS, True),
    "scripts": Tree(
        "scripts",
        "Scripts Analysis",
        ROOT / "scripts",
        True,
        _TREE_TOPS,
        True,
        relative_to_tree=True,
        counts_sheet=True,
    ),
}

#: Trees written into the default workbook, in sheet order.
DEFAULT_TREES = ("src", "tools", "exec_telemetry", "root")

#: Set per-tree by :func:`inventory_tree`; the import-resolution helpers read it.
_TREE: Tree = TREES["src"]

# Patterns that look like noise for summary
_SKIP_NAMES = frozenset(
    {
        "main",
        "cli",
        "run",
        "execute",
        "load",
        "save",
        "get",
        "set",
        "to_dict",
        "from_dict",
        "from_prod_config",
        "__init__",
        "__repr__",
        "__str__",
        "__call__",
    }
)


def _first_sentence(text: str, max_len: int = 320) -> str:
    if not text:
        return ""
    # Drop decorative banner lines (====, ----, ────, filename.py headers)
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            if lines:
                break  # blank after content often ends title block
            continue
        if re.fullmatch(r"[=#\-─═━┄┈_~*+]{4,}", s):
            continue
        if re.fullmatch(r"[\w./\\-]+\.py\s*[=#\-─═━┄┈_~*+]*", s, flags=re.I):
            continue
        if re.fullmatch(r"[=#\-─═━┄┈_~*+]{2,}\s*[\w./\\-]+\.py\s*[=#\-─═━┄┈_~*+]{2,}", s, flags=re.I):
            continue
        lines.append(s)
    text = " ".join(lines)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^(#+\s*|\"\"\"|'''|\*)", "", text).strip()
    # Prefer first sentence
    m = re.search(r"^(.+?[.!?])(\s|$)", text)
    if m and len(m.group(1)) >= 20:
        text = m.group(1).strip()
    if len(text) > max_len:
        text = text[: max_len - 1].rstrip() + "…"
    return text


def _import_to_module(node: ast.AST) -> list[str]:
    """Return dotted module paths from an import node."""
    out: list[str] = []
    if isinstance(node, ast.Import):
        for alias in node.names:
            out.append(alias.name)
    elif isinstance(node, ast.ImportFrom):
        if node.module:
            # relative imports: level > 0
            if node.level and node.level > 0:
                out.append("." * node.level + (node.module or ""))
            else:
                out.append(node.module)
        elif node.level and node.level > 0:
            # from . import x
            names = [a.name for a in node.names if a.name != "*"]
            if names:
                out.append("." * node.level + "{" + ", ".join(names) + "}")
            else:
                out.append("." * node.level)
    return out


def _resolve_relative(file_path: Path, raw: str) -> str:
    """Best-effort resolve relative import to package path under src."""
    if not raw.startswith("."):
        return raw
    # count leading dots
    level = 0
    while level < len(raw) and raw[level] == ".":
        level += 1
    rest = raw[level:]
    # file package: parent of file relative to the tree root, then go up (level-1)
    try:
        rel = file_path.relative_to(_TREE.root)
    except ValueError:
        return raw
    parts = list(rel.parts[:-1])  # package dirs
    # level 1 = current package; level 2 = parent, etc.
    up = max(level - 1, 0)
    if up:
        parts = parts[:-up] if up <= len(parts) else []
    if rest.startswith("{"):
        return ("." if not parts else ".".join(parts)) + rest if parts else rest
    if rest:
        parts = parts + rest.split(".")
    return ".".join(parts) if parts else rest or raw


def _project_tops() -> set[str]:
    """Top-level import names treated as project-local.

    Always ``src/``'s own subpackages plus ``src`` itself — that is the whole set for
    the ``src`` tree, which keeps its sheet identical to the original single-tree run.
    Other trees additionally claim the sibling tree names they legitimately import from.
    """
    tops = {
        p.name
        for p in SRC.iterdir()
        if p.is_dir() and not p.name.startswith("__") and p.name != "tradelatest.egg-info"
    }
    tops.add("src")
    tops |= set(_TREE.extra_tops)
    return tops


_PROJECT_TOPS = None


def _is_project_ref(mod: str) -> bool:
    """Keep project-local and relative refs; drop stdlib/third-party."""
    global _PROJECT_TOPS
    if _PROJECT_TOPS is None:
        _PROJECT_TOPS = _project_tops()
    if not mod:
        return False
    if mod.startswith("."):
        return True
    top = mod.split(".")[0].split("{")[0]
    if top in _PROJECT_TOPS:
        return True
    if (SRC / top).exists():
        return True
    return False


def _module_to_file_hint(mod: str) -> str:
    """Map a project module path to a best-effort file path under src/."""
    if not mod or mod.startswith(".") and "{" in mod:
        return mod
    clean = mod.lstrip(".")
    if "{" in clean:
        return mod
    # try src/a/b.py then src/a/b/__init__.py
    parts = clean.split(".")
    if parts and parts[0] == "src":
        parts = parts[1:]
    if not parts:
        return mod
    # A sibling tree (tools.x, scripts.y, mt5_analytics.z) lives under ROOT, not src/.
    base, prefix = (SRC, "src/")
    if parts[0] in _TREE_TOPS and (ROOT / parts[0]).is_dir():
        base, prefix = (ROOT, "")
    py = base.joinpath(*parts).with_suffix(".py")
    init = base.joinpath(*parts) / "__init__.py"
    if py.is_file():
        return py.relative_to(ROOT).as_posix()
    if init.is_file():
        return init.relative_to(ROOT).as_posix()
    # package prefix only
    return prefix + "/".join(parts)


def _summarize(tree: ast.AST, source: str, file_path: Path) -> str:
    doc = ast.get_docstring(tree) if isinstance(tree, ast.Module) else None
    if doc:
        s = _first_sentence(doc)
        if s:
            return s

    # Fallback: first non-shebang/comment/import block comment or module-level string
    classes: list[str] = []
    funcs: list[str] = []
    for node in getattr(tree, "body", []) or []:
        if isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            if node.name not in _SKIP_NAMES:
                funcs.append(node.name)

    name = file_path.stem
    package = file_path.parent.name

    if name == "__init__":
        if classes or funcs:
            bits = []
            if classes:
                bits.append("exports: " + ", ".join(classes[:8]))
            if funcs:
                bits.append("fns: " + ", ".join(funcs[:6]))
            return f"Package init for `{package}` ({'; '.join(bits)})."
        return f"Package init for `{package}` (re-export / package marker)."

    parts: list[str] = []
    if classes:
        parts.append("Defines " + ", ".join(classes[:6]) + ("…" if len(classes) > 6 else ""))
    if funcs:
        parts.append("functions " + ", ".join(funcs[:6]) + ("…" if len(funcs) > 6 else ""))
    if parts:
        return f"{name}: " + "; ".join(parts) + "."

    # Last resort: first meaningful comment
    for line in source.splitlines()[:40]:
        line = line.strip()
        if line.startswith("#") and len(line) > 4 and "coding" not in line.lower():
            return _first_sentence(line.lstrip("# ").strip()) or f"{name}: Python module (no docstring)."
    return f"{name}: Python module (no docstring or public API detected)."


def analyze_file(path: Path) -> dict:
    base = _TREE.root if _TREE.relative_to_tree else ROOT
    rel = path.relative_to(base).as_posix()
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return {
            "File Name": rel,
            "Summary of functionality": f"UNREADABLE: {e}",
            "Referred files": "",
        }

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as e:
        # Still try crude import scrape
        refs = sorted(
            set(
                re.findall(
                    r"^(?:from|import)\s+([\w.]+)",
                    source,
                    flags=re.M,
                )
            )
        )
        return {
            "File Name": rel,
            "Summary of functionality": f"SYNTAX ERROR (line {e.lineno}): {e.msg}",
            "Referred files": "; ".join(refs),
        }

    raw_mods: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            # only top-level-ish: skip imports nested deep? User asked for referred files in imports — all imports.
            raw_mods.extend(_import_to_module(node))

    # Prefer project-local refs; if none, show all non-stdlib-ish
    resolved: list[str] = []
    for m in raw_mods:
        if m.startswith("."):
            resolved.append(_resolve_relative(path, m))
        else:
            resolved.append(m)

    project = [m for m in resolved if _is_project_ref(m)]
    # de-dupe preserve order
    seen: set[str] = set()
    ordered: list[str] = []
    for m in project if project else resolved:
        if m not in seen:
            seen.add(m)
            ordered.append(m)

    # Drop pure stdlib when falling back to all
    if not project:
        stdlibish = {
            "os",
            "sys",
            "re",
            "json",
            "math",
            "time",
            "datetime",
            "pathlib",
            "typing",
            "dataclasses",
            "enum",
            "collections",
            "functools",
            "itertools",
            "logging",
            "argparse",
            "hashlib",
            "copy",
            "abc",
            "contextlib",
            "concurrent",
            "threading",
            "multiprocessing",
            "subprocess",
            "tempfile",
            "shutil",
            "glob",
            "io",
            "csv",
            "statistics",
            "random",
            "string",
            "struct",
            "base64",
            "urllib",
            "http",
            "socket",
            "ssl",
            "email",
            "unittest",
            "pytest",
            "asyncio",
            "inspect",
            "traceback",
            "warnings",
            "importlib",
            "pkgutil",
            "types",
            "operator",
            "numbers",
            "decimal",
            "fractions",
            "heapq",
            "bisect",
            "array",
            "queue",
            "weakref",
            "gc",
            "pickle",
            "sqlite3",
            "zlib",
            "gzip",
            "zipfile",
            "tarfile",
            "configparser",
            "tomllib",
            "pprint",
            "textwrap",
            "difflib",
            "fnmatch",
            "linecache",
            "tokenize",
            "uuid",
            "secrets",
            "hmac",
            "platform",
            "signal",
            "errno",
            "ctypes",
            "dataclasses",
            "annotated_types",
            "__future__",
            "numpy",
            "pandas",
            "torch",
            "sklearn",
            "scipy",
            "yaml",
            "requests",
            "httpx",
            "pydantic",
            "fastapi",
            "flask",
            "django",
            "openai",
            "groq",
            "dotenv",
            "tqdm",
            "joblib",
            "matplotlib",
            "seaborn",
            "PIL",
            "cv2",
            "MetaTrader5",
            "mt5",
        }
        ordered = [
            m
            for m in ordered
            if m.split(".")[0].split("{")[0] not in stdlibish
        ]

    # Present referred modules as file-path hints when resolvable
    referred_display: list[str] = []
    seen_disp: set[str] = set()
    for m in ordered:
        hint = _module_to_file_hint(m) if _is_project_ref(m) else m
        if hint not in seen_disp:
            seen_disp.add(hint)
            referred_display.append(hint)

    summary = _summarize(tree, source, path)
    return {
        "File Name": rel,
        "Summary of functionality": summary,
        "Referred files": "; ".join(referred_display) if referred_display else _NO_REFS,
    }


def _iter_tree_files(tree: Tree) -> list[Path]:
    """Every non-``__pycache__`` ``.py`` in the tree, sorted."""
    it = tree.root.rglob("*.py") if tree.recursive else tree.root.glob("*.py")
    return sorted(f for f in it if "__pycache__" not in f.parts)


def inventory_tree(tree: Tree) -> "pd.DataFrame":
    """Analyze one tree. Sets the module-level ``_TREE`` the import helpers read."""
    global _TREE, _PROJECT_TOPS
    _TREE = tree
    _PROJECT_TOPS = None  # recompute: the project-reference filter is tree-scoped
    rows = [analyze_file(f) for f in _iter_tree_files(tree)]
    return pd.DataFrame(rows, columns=["File Name", "Summary of functionality", "Referred files"])


def _style(ws) -> None:
    from openpyxl.styles import Alignment

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for col, w in {"A": 55, "B": 90, "C": 80}.items():
        ws.column_dimensions[col].width = w
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=3):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")


def _readme_rows(trees: list[Tree], counts: dict[str, int]) -> list[str]:
    lines = [
        "Python business-functionality inventory — one sheet per tree.",
        f"Generated by: scripts/analysis/{Path(__file__).name}",
        "Regenerate: python scripts/analysis/src_business_functionality_inventory.py",
        "Summary of functionality: module docstring first line, else inferred from class/function names.",
        "Referred files: direct imports only, resolved to project-relative paths (stdlib/third-party omitted).",
        "No transitive dependency analysis.",
        "",
        "Sheets:",
    ]
    for t in trees:
        scope = f"{t.root.relative_to(ROOT).as_posix() or '.'}/*.py" + ("" if t.recursive else " (non-recursive)")
        ident = "identities declared" if t.has_identities else "NO Semantic OS identities declared for this tree"
        lines.append(f"  {t.sheet}: {scope} — {counts[t.key]} files — {ident}")
    lines += [
        "",
        "Semantic identity columns are appended by",
        "scripts/governance/enrich_workbooks_with_semantic_identity.py (run it AFTER this script;",
        "regeneration overwrites the sheet and drops those columns).",
        "A sheet marked 'NO Semantic OS identities' is left un-enriched on purpose: a blank",
        "Semantic ID column would read as 'coverage measured at zero', not 'coverage not measured'.",
    ]
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--tree",
        action="append",
        choices=sorted(TREES),
        help=f"tree(s) to inventory; default: {' '.join(DEFAULT_TREES)}",
    )
    ap.add_argument("--out", type=Path, help=f"output workbook (default: {OUT.relative_to(ROOT).as_posix()})")
    args = ap.parse_args(argv)

    keys = args.tree or list(DEFAULT_TREES)
    trees = [TREES[k] for k in keys]
    out = args.out or OUT

    frames = {t.key: inventory_tree(t) for t in trees}
    counts = {k: len(df) for k, df in frames.items()}

    out.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        for t in trees:
            frames[t.key].to_excel(writer, index=False, sheet_name=t.sheet)
            _style(writer.sheets[t.sheet])
        for t in trees:
            if not t.counts_sheet:
                continue
            df = frames[t.key]
            refs = df["Referred files"]
            summ = df["Summary of functionality"]
            pd.DataFrame(
                {
                    "Metric": [
                        f"Total Python files under {t.root.relative_to(ROOT).as_posix()}/",
                        "Files with referred project imports",
                        "Files with empty referred files",
                        "Parse/read errors",
                    ],
                    "Value": [
                        len(df),
                        int((refs != _NO_REFS).sum()),
                        int((refs == _NO_REFS).sum()),
                        int(summ.str.startswith(("SYNTAX ERROR", "UNREADABLE")).sum()),
                    ],
                }
            ).to_excel(writer, index=False, sheet_name="Counts")
            writer.sheets["Counts"].column_dimensions["A"].width = 42

        readme = pd.DataFrame({"README": _readme_rows(trees, counts)})
        readme.to_excel(writer, index=False, sheet_name="README")
        writer.sheets["README"].column_dimensions["A"].width = 110

    total = sum(counts.values())
    detail = ", ".join(f"{t.sheet}={counts[t.key]}" for t in trees)
    print(f"Wrote {total} rows ({detail}) -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
