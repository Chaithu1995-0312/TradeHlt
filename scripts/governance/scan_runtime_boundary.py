#!/usr/bin/env python3
"""
scan_runtime_boundary.py — enforce the kernel <-> research import direction,
PLUS the narrower research -> promotion/validation authority boundary.

Two independent checks, both AST-based:

1. Kernel <-> research DIRECTION (original scope — Research Runtime Step 0):
   The repository is one execution KERNEL with two authority contexts. Research may
   import the kernel as a proven primitive (``CandleLoader``, ``CRTEngine``,
   ``FeaturePipeline``); the kernel must NEVER import research.

       research / interpreters  --imports-->  kernel        ALLOWED
       kernel                   --imports-->  research      FORBIDDEN

   Why this direction matters (not style): research measures the system that trades. A
   kernel->research edge means production behavior can change when a research module
   changes — the coupling this boundary exists to prevent. See CLAUDE.md §6.5 (Authority
   Ladder) and F-037 / F-058 for what drift costs.

2. Research -> promotion/validation AUTHORITY (added 2026-07-29, see
   ``src/research/__init__.py``): research may freely import kernel *engines* to
   observe/score with them — ``research.model_runners.adapters`` deliberately does
   this so research measures what production actually runs, not a reimplementation
   that could silently diverge (the F-037 failure mode). What research must NEVER
   acquire is the power to PROMOTE or VALIDATE-FOR-PROMOTION:

       research / interpreters  --imports-->  governance.promotion_manager   FORBIDDEN
       research / interpreters  --imports-->  config_layer.config_validator  FORBIDDEN

   This check replaces a docstring-only rule that drifted silently out of sync with
   the code — a rule not mechanically enforced is not a rule, just a memory.

``src/interpreters/`` is classified RESEARCH-side: it is consumed only by
``src/research/hypotheses/weekly_sweep_reversal.py``, ``scripts/research/`` and
``tests/interpreters/`` — no kernel package imports it.

Scope: ``src/`` only. ``scripts/`` and ``tests/`` legitimately import both sides.

Detection is AST-based, not textual: a docstring mentioning "from research → production
registry" (``src/governance/promotion_manager.py:7``) is prose, not an import, and must
not trip the gate. Function-local imports ARE caught (``ast.walk`` visits them).

Exit codes:
  0 — clean (no kernel→research imports AND no research→authority imports)
  1 — one or more violations in either direction
  2 — usage / I/O error

CLI:
  python scripts/governance/scan_runtime_boundary.py
  python scripts/governance/scan_runtime_boundary.py --json
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Iterable

_REPO = Path(__file__).resolve().parents[2]

# Top-level packages under src/ that constitute the RESEARCH side of the boundary.
RESEARCH_PACKAGES: frozenset[str] = frozenset({"research", "interpreters"})

# Modules research/interpreters must NEVER import: the power to promote or to
# validate-for-promotion. Observing/scoring via live engines (core.*) is a
# DIFFERENT, permitted coupling — see module docstring §2.
FORBIDDEN_AUTHORITY_MODULES: frozenset[str] = frozenset({
    "governance.promotion_manager",
    "config_layer.config_validator",
})


def _norm_path(p: str | Path) -> str:
    return str(p).replace("\\", "/").lstrip("./")


def top_level_package(module: str) -> str:
    """'research.contracts' -> 'research'; '' -> ''."""
    return (module or "").split(".", 1)[0]


def side_of_file(rel: str) -> str:
    """Classify a repo-relative src/ path as 'research' or 'kernel'."""
    parts = _norm_path(rel).split("/")
    if len(parts) >= 2 and parts[0] == "src":
        return "research" if parts[1] in RESEARCH_PACKAGES else "kernel"
    return "kernel"


def is_research_module(module: str) -> bool:
    return top_level_package(module) in RESEARCH_PACKAGES


def _resolved_module(node: ast.ImportFrom, rel: str) -> str:
    """Resolve `from .x import y` against the file's package; absolute passes through."""
    if not node.level:
        return node.module or ""
    parts = _norm_path(rel).split("/")
    pkg = parts[1:-1] if parts[:1] == ["src"] else parts[:-1]
    base = pkg[: len(pkg) - (node.level - 1)] if node.level > 1 else pkg
    return ".".join([*base, *( [node.module] if node.module else [] )])


def research_imports_in_source(src: str, rel: str) -> list[tuple[int, str]]:
    """Return (lineno, module) for every research-side import in `src`.

    Exposed separately so the boundary detector itself is testable on synthetic
    source — a gate that cannot be shown to fail is not enforcement.
    """
    try:
        tree = ast.parse(src, filename=rel)
    except SyntaxError:
        return []
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if is_research_module(alias.name):
                    found.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            module = _resolved_module(node, rel)
            if is_research_module(module):
                found.append((node.lineno, module))
    return sorted(set(found))


def is_forbidden_authority_module(module: str) -> bool:
    """True if `module` IS, or is a submodule of, a forbidden authority module."""
    if not module:
        return False
    return any(
        module == m or module.startswith(m + ".")
        for m in FORBIDDEN_AUTHORITY_MODULES
    )


def authority_imports_in_source(src: str, rel: str) -> list[tuple[int, str]]:
    """Return (lineno, module) for every promotion/validation-authority import in `src`.

    The counterpart check to research_imports_in_source, run over the RESEARCH
    side instead of the kernel side. Exposed separately for the same reason: a
    gate that cannot be shown to fail on synthetic input is not enforcement.
    """
    try:
        tree = ast.parse(src, filename=rel)
    except SyntaxError:
        return []
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if is_forbidden_authority_module(alias.name):
                    found.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            module = _resolved_module(node, rel)
            if is_forbidden_authority_module(module):
                found.append((node.lineno, module))
    return sorted(set(found))


def scan(repo: Path = _REPO) -> list[dict]:
    """Return [{file, line, imports}] for kernel modules importing research."""
    violations: list[dict] = []
    src_root = repo / "src"
    if not src_root.exists():
        return violations
    for path in sorted(src_root.rglob("*.py")):
        rel = _norm_path(path.relative_to(repo))
        if side_of_file(rel) != "kernel":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for lineno, module in research_imports_in_source(text, rel):
            violations.append({"file": rel, "line": lineno, "imports": module})
    return violations


def scan_authority(repo: Path = _REPO) -> list[dict]:
    """Return [{file, line, imports}] for research-side modules importing the
    promotion/validation authority (governance.promotion_manager /
    config_layer.config_validator)."""
    violations: list[dict] = []
    src_root = repo / "src"
    if not src_root.exists():
        return violations
    for path in sorted(src_root.rglob("*.py")):
        rel = _norm_path(path.relative_to(repo))
        if side_of_file(rel) != "research":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for lineno, module in authority_imports_in_source(text, rel):
            violations.append({"file": rel, "line": lineno, "imports": module})
    return violations


def format_violations(violations: Iterable[dict]) -> list[str]:
    return [
        f"kernel module imports research: {v['file']}:{v['line']} -> {v['imports']}"
        for v in violations
    ]


def format_authority_violations(violations: Iterable[dict]) -> list[str]:
    return [
        f"research module imports promotion/validation authority: "
        f"{v['file']}:{v['line']} -> {v['imports']}"
        for v in violations
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="print machine-readable report")
    args = ap.parse_args(argv)

    violations = scan()
    authority_violations = scan_authority()
    msgs = format_violations(violations)
    authority_msgs = format_authority_violations(authority_violations)
    report = {
        "research_packages": sorted(RESEARCH_PACKAGES),
        "forbidden_authority_modules": sorted(FORBIDDEN_AUTHORITY_MODULES),
        "scan_root": "src",
        "violations": violations,
        "violation_count": len(violations),
        "authority_violations": authority_violations,
        "authority_violation_count": len(authority_violations),
        "ok": not violations and not authority_violations,
    }

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(
            f"runtime boundary scan: research_packages={sorted(RESEARCH_PACKAGES)} "
            f"kernel<-research violations={len(violations)} "
            f"research->authority violations={len(authority_violations)}"
        )
        for m in msgs:
            print("  FAIL", m)
        for m in authority_msgs:
            print("  FAIL", m)
        if report["ok"]:
            print("OK - kernel does not import research; research does not import promotion/validation authority")
        else:
            print("FAIL - see messages above")

    return 1 if (violations or authority_violations) else 0


if __name__ == "__main__":
    sys.exit(main())
