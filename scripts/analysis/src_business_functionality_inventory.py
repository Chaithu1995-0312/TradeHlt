#!/usr/bin/env python3
"""Inventory business functionality of every src/**/*.py file.

Columns: File Name | Summary of functionality | Referred files
Output: results/analysis/src_business_functionality.xlsx
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    print("pandas required", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
OUT = ROOT / "results" / "analysis" / "src_business_functionality.xlsx"

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
        if re.fullmatch(r"[=#\-─_~*]{4,}", s):
            continue
        if re.fullmatch(r"[\w./\\-]+\.py\s*[=#\-─_~*]*", s, flags=re.I):
            continue
        if re.fullmatch(r"[=#\-─_~*]{2,}\s*[\w./\\-]+\.py\s*[=#\-─_~*]{2,}", s, flags=re.I):
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
    # file package: parent of file relative to src, then go up (level-1)
    try:
        rel = file_path.relative_to(SRC)
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
    tops = {
        p.name
        for p in SRC.iterdir()
        if p.is_dir() and not p.name.startswith("__") and p.name != "tradelatest.egg-info"
    }
    tops.add("src")
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
    py = SRC.joinpath(*parts).with_suffix(".py")
    init = SRC.joinpath(*parts) / "__init__.py"
    if py.is_file():
        return py.relative_to(ROOT).as_posix()
    if init.is_file():
        return init.relative_to(ROOT).as_posix()
    # package prefix only
    return "src/" + "/".join(parts)


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
    rel = path.relative_to(ROOT).as_posix()
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
        "Referred files": "; ".join(referred_display) if referred_display else "(none / stdlib-only)",
    }


def main() -> int:
    files = sorted(SRC.rglob("*.py"))
    # skip __pycache__
    files = [f for f in files if "__pycache__" not in f.parts]
    rows = [analyze_file(f) for f in files]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows, columns=["File Name", "Summary of functionality", "Referred files"])
    with pd.ExcelWriter(OUT, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="src_py_inventory")
        ws = writer.sheets["src_py_inventory"]
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        widths = {"A": 55, "B": 90, "C": 80}
        for col, w in widths.items():
            ws.column_dimensions[col].width = w
        # wrap text for summary + refs
        from openpyxl.styles import Alignment

        for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=3):
            for cell in row:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
    print(f"Wrote {len(df)} rows -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
