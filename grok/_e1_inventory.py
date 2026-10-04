#!/usr/bin/env python3
"""Extract Group A module summaries for encyclopedia E1."""
from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(r"D:\Tradelatest")
PACKAGES = [
    "src/core",
    "src/config_layer",
    "src/runtime",
    "src/execution",
    "src/engines",
    "src/live",
    "src/inout",
    "src/control_plane",
]


def first_doc(path: Path) -> str:
    src = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(src)
        d = ast.get_docstring(tree) or ""
    except Exception:
        d = ""
    if d:
        lines = [ln.strip() for ln in d.strip().splitlines() if ln.strip()]
        # drop pure box-drawing lines
        lines = [ln for ln in lines if not set(ln) <= set("═╔╗╚╝║─|- ")]
        return " ".join(lines[:5])[:320]
    return ""


def classes(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        return [n.name for n in tree.body if isinstance(n, ast.ClassDef)][:10]
    except Exception:
        return []


def main() -> None:
    for pkg in PACKAGES:
        root = REPO / pkg
        for f in sorted(root.rglob("*.py")):
            if "__pycache__" in f.parts:
                continue
            rel = f.relative_to(REPO).as_posix()
            summ = first_doc(f)
            cls = classes(f)
            print(f"{rel}\t{f.stat().st_size}\t{','.join(cls)}\t{summ}")


if __name__ == "__main__":
    main()
