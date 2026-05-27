"""
code_context_extractor.py — AST-based code extraction for Context Reports.

Extracts the specific Python functions/classes that were likely executed in a run,
using two signals:
  1. The main script path from command_line (all top-level symbols)
  2. File paths referenced in stdout/stderr tracebacks (only the hit functions)

No src.* imports — pure stdlib, operates on raw strings/paths from server routes.
"""
from __future__ import annotations

import ast
import re
import textwrap
from pathlib import Path
from typing import Any

# Regex to extract "File <path>, line <n>" from Python tracebacks
_TB_RE = re.compile(r'File ["\']([^"\']+\.py)["\'],\s*line\s*(\d+)')

# Cap total symbols sent to the LLM to keep token budget bounded
_MAX_SYMBOLS = 8
# Max characters per code block (avoids sending a 1 000-line function verbatim)
_MAX_CODE_CHARS = 3_000


def _find_script_path(command_line: list[str], repo_root: Path) -> Path | None:
    """
    Locate the main Python script from a command_line list.
    Handles:  ['python', 'scripts/foo.py', ...]
              ['python', '-m', 'scripts.foo', ...]
              ['coverage', 'run', ..., 'scripts/foo.py', ...]
    Returns an absolute Path if the file exists, else None.
    """
    for i, tok in enumerate(command_line):
        if tok in ("-m", "--module"):
            # next token is a dotted module name → convert to path
            if i + 1 < len(command_line):
                mod = command_line[i + 1].replace(".", "/")
                for candidate in (
                    repo_root / (mod + ".py"),
                    repo_root / "src" / (mod + ".py"),
                    repo_root / "scripts" / (mod + ".py"),
                ):
                    if candidate.exists():
                        return candidate
        if tok.endswith(".py"):
            p = Path(tok)
            if not p.is_absolute():
                p = repo_root / p
            if p.exists():
                return p
    return None


def _ast_symbols(source: str, path: Path) -> list[dict[str, Any]]:
    """
    Parse source into an AST and return all top-level function/class definitions
    as dicts with keys: file, symbol, kind, start_line, end_line, code.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    lines = source.splitlines(keepends=True)
    results = []
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        start = node.lineno - 1          # 0-based
        end   = getattr(node, "end_lineno", start + 1)
        block = "".join(lines[start:end])
        block = textwrap.dedent(block)
        if len(block) > _MAX_CODE_CHARS:
            block = block[:_MAX_CODE_CHARS] + "\n# ... (truncated)"
        results.append({
            "file":       str(path),
            "symbol":     node.name,
            "kind":       "class" if isinstance(node, ast.ClassDef) else "function",
            "start_line": node.lineno,
            "end_line":   end,
            "code":       block,
        })
    return results


def _symbols_hitting_line(symbols: list[dict], lineno: int) -> list[dict]:
    """Return symbols whose line range contains lineno."""
    return [s for s in symbols if s["start_line"] <= lineno <= s["end_line"]]


def extract_code_context(
    command_line: list[str],
    stdout: str,
    stderr: str,
    repo_root: Path,
) -> list[dict[str, Any]]:
    """
    Public API.  Returns up to _MAX_SYMBOLS code blocks most relevant to this run.

    Priority order:
      1. Functions/classes in traceback-referenced files at the exact hit line (highest signal)
      2. All top-level symbols from the main script
      3. Functions in traceback files not directly hit by a line reference

    Each dict: {file, symbol, kind, start_line, end_line, code, source}
      source: "traceback" | "main_script"
    """
    seen: dict[str, dict] = {}   # (file, symbol) → entry

    # ── Phase 1: parse traceback file references ──────────────────────────────
    combined = (stdout or "") + "\n" + (stderr or "")
    tb_hits: dict[str, set[int]] = {}   # path_str → set of line numbers
    for m in _TB_RE.finditer(combined):
        raw_path, lineno_str = m.group(1), m.group(2)
        p = Path(raw_path)
        if not p.is_absolute():
            p = repo_root / p
        key = str(p)
        tb_hits.setdefault(key, set()).add(int(lineno_str))

    # Extract hit symbols from traceback files
    for path_str, linenos in tb_hits.items():
        p = Path(path_str)
        if not p.exists():
            continue
        try:
            source = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        symbols = _ast_symbols(source, p)
        for ln in linenos:
            for sym in _symbols_hitting_line(symbols, ln):
                key = (sym["file"], sym["symbol"])
                if key not in seen:
                    seen[key] = {**sym, "source": "traceback"}

    # ── Phase 2: main script — all top-level symbols ──────────────────────────
    main_script = _find_script_path(command_line, repo_root)
    if main_script:
        try:
            source = main_script.read_text(encoding="utf-8", errors="replace")
            for sym in _ast_symbols(source, main_script):
                key = (sym["file"], sym["symbol"])
                if key not in seen:
                    seen[key] = {**sym, "source": "main_script"}
        except OSError:
            pass

    # ── Phase 3: remaining traceback symbols not already captured ─────────────
    for path_str in tb_hits:
        p = Path(path_str)
        if not p.exists():
            continue
        try:
            source = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for sym in _ast_symbols(source, p):
            key = (sym["file"], sym["symbol"])
            if key not in seen:
                seen[key] = {**sym, "source": "traceback_file"}

    if not seen:
        return []

    # ── Sort: traceback hits first, then by code size (descending) ────────────
    priority = {"traceback": 0, "main_script": 1, "traceback_file": 2}
    ordered = sorted(
        seen.values(),
        key=lambda s: (priority.get(s["source"], 9), -(s["end_line"] - s["start_line"])),
    )
    return ordered[:_MAX_SYMBOLS]
