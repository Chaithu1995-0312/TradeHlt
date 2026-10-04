"""h6_silent_except_census.py — H6: census every silent `except Exception` inside the per-bar
backtest loop, and classify which ones truly swallow the error.

Plan reference: pure-conversation-share-only-rosy-parnas.md §4 H6.

WHAT "SILENT" MEANS HERE
--------------------------
A handler is classified SILENT_SWALLOW if its body contains no `raise` (bare or re-raise) AND no
call whose name suggests it records the failure somewhere a human or a metric would see it (no
`log`/`logger`/`warning`/`error`/`critical`/emit/append to an audit/trace object). `pass`-only and
`self.log.debug(...)`-only bodies both count — DEBUG is silent in practice on a default logging
configuration (this is exactly H2's finding, generalized: H2 is ONE instance of this class, not
the only one).

METHOD
------
Static AST walk of `runtime/backtest_v2.py`, scoped to `BacktestRunner.run` (the per-bar loop
method) only — module-level `except` blocks (import guards, optional-dependency handling) are a
different, well-established and intentional pattern (CLAUDE.md's "optional-import" error mode) and
are excluded by construction, not silently conflated with the in-loop ones this hypothesis is
about. For each `except Exception[ as name]:` node, records: line number, whether the body is a
silent swallow, the exception variable name (if any, so a reviewer can grep whether it is used),
and the first statement's source text (context, not the full body — this is a census, not a diff).

KILL RULE
---------
Every `except Exception` inside the loop either re-raises or logs at INFO+ (hypothesis falsified —
"silent" was overclaimed; report the corrected count, do not adjust the classifier to manufacture
a hit).
"""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC = REPO_ROOT / "src"

_LOUD_CALL_HINTS = ("log", "logger", "warning", "error", "critical", "exception", "emit", "append", "record")


def _is_loud_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    name = ""
    if isinstance(func, ast.Attribute):
        name = func.attr.lower()
    elif isinstance(func, ast.Name):
        name = func.id.lower()
    return any(hint in name for hint in _LOUD_CALL_HINTS)


def _body_reraises(body: list) -> bool:
    for stmt in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(stmt, ast.Raise):
            return True
    return False


def _body_is_loud(body: list) -> bool:
    for stmt in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(stmt, ast.Call) and _is_loud_call(stmt):
            return True
    return False


def _first_stmt_text(body: list, src_lines: list) -> str:
    if not body:
        return ""
    first = body[0]
    line = src_lines[first.lineno - 1].strip() if 0 < first.lineno <= len(src_lines) else ""
    return line[:120]


def main() -> int:
    target = SRC / "runtime" / "backtest_v2.py"
    src_text = target.read_text(encoding="utf-8")
    src_lines = src_text.splitlines()
    tree = ast.parse(src_text, filename=str(target))

    # Find BacktestRunner.run — the per-bar loop lives entirely inside this one method.
    run_method = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "BacktestRunner":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "run":
                    run_method = item
                    break
    if run_method is None:
        print("H6: ABORT — could not locate BacktestRunner.run via AST", file=sys.stderr)
        return 2

    findings = []
    for node in ast.walk(run_method):
        if not isinstance(node, ast.ExceptHandler):
            continue
        is_broad = (
            node.type is None
            or (isinstance(node.type, ast.Name) and node.type.id == "Exception")
        )
        if not is_broad:
            continue
        reraises = _body_reraises(node.body)
        loud = _body_is_loud(node.body)
        silent = not reraises and not loud
        findings.append({
            "line": node.lineno,
            "exception_var": node.name,
            "reraises": reraises,
            "logs_or_records": loud,
            "classification": "SILENT_SWALLOW" if silent else ("RERAISES" if reraises else "LOGGED"),
            "first_statement": _first_stmt_text(node.body, src_lines),
        })

    findings.sort(key=lambda f: f["line"])
    silent_count = sum(1 for f in findings if f["classification"] == "SILENT_SWALLOW")

    verdict = {
        "hypothesis": "H6",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "file": "src/runtime/backtest_v2.py",
        "scope": "BacktestRunner.run (per-bar loop method only)",
        "total_broad_except_blocks": len(findings),
        "silent_swallow_count": silent_count,
        "findings": findings,
        "result": "CONFIRMED_SILENT_EXCEPT_BLOCKS_EXIST" if silent_count else "FALSIFIED_ALL_EXCEPT_BLOCKS_ARE_LOUD_OR_RERAISE",
    }

    out_path = REPO_ROOT / "results" / f"h6_silent_except_census_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(verdict, indent=2), encoding="utf-8")

    print(f"H6 result: {verdict['result']}")
    print(f"  broad except blocks in BacktestRunner.run: {len(findings)} (silent: {silent_count})")
    for f in findings:
        print(f"    L{f['line']:>5} [{f['classification']:>14}] as {f['exception_var']!r}: {f['first_statement']}")
    print(f"  -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
