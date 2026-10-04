"""AST census of file-writing calls under src/ and scripts/.

P0 of the run/trace coverage spine (STORY-12.3). Read-only. Deterministic.
Prints JSONL to stdout, sorted. Does not write assets itself.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAN_ROOTS = (ROOT / "src", ROOT / "scripts")
WRITE_ATTRS = frozenset({"write_text", "write_bytes", "dump", "to_csv", "to_parquet", "writelines"})


def module_name(path: Path) -> str:
    rel = path.relative_to(ROOT).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[0] == "src":
        parts = parts[1:]
    return ".".join(parts)


def _expr(node: ast.AST | None) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return type(node).__name__


def _open_is_write(call: ast.Call) -> bool:
    mode = None
    if len(call.args) >= 2:
        mode = call.args[1]
    for kw in call.keywords:
        if kw.arg == "mode":
            mode = kw.value
    if mode is None:
        return False
    if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
        return any(flag in mode.value for flag in ("w", "a", "x", "+"))
    return True


class _Scan(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.stack: list[str] = []
        self.rows: list[dict] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node: ast.Call) -> None:
        call = ""
        keep = False
        if isinstance(node.func, ast.Name) and node.func.id == "open":
            call = "open"
            keep = _open_is_write(node)
        elif isinstance(node.func, ast.Attribute) and node.func.attr in WRITE_ATTRS:
            call = node.func.attr
            keep = True
        if keep:
            target = node.args[0] if node.args else None
            writer = self.stack[-1] if self.stack else "<module>"
            self.rows.append(
                {
                    "module": module_name(self.path),
                    "writer_symbol": writer,
                    "call": call,
                    "path_literal_or_expr": _expr(target),
                    "file": str(self.path.relative_to(ROOT)).replace("\\", "/"),
                    "line": node.lineno,
                }
            )
        self.generic_visit(node)


def census() -> list[dict]:
    rows: list[dict] = []
    for root in SCAN_ROOTS:
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeError):
                continue
            scan = _Scan(path)
            scan.visit(tree)
            rows.extend(scan.rows)
    rows.sort(key=lambda r: (r["module"], r["writer_symbol"], r["call"], r["file"], r["line"]))
    return rows


def main() -> int:
    rows = census()
    for row in rows:
        print(json.dumps(row, ensure_ascii=False))
    print(f"# n={len(rows)} writers={len({(r['module'], r['writer_symbol']) for r in rows})}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
