#!/usr/bin/env python3
"""
scan_model_paths_literals.py — detect unauthorized ``models/`` path string literals.

Architectural boundary (ModelPaths Phase 0+):
  Only ModelPaths (and explicitly approved migration/test surfaces) may embed
  ``models/…`` filesystem strings. Everyone else must import ModelPaths / ModelResolver.

Exit codes:
  0 — clean (no unauthorized hits, or hits ⊆ debt file)
  1 — new unauthorized hits not covered by debt
  2 — usage / I/O error

CLI:
  python scripts/governance/scan_model_paths_literals.py
  python scripts/governance/scan_model_paths_literals.py --json
  python scripts/governance/scan_model_paths_literals.py --write-debt  # regenerate debt (review!)
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable

_REPO = Path(__file__).resolve().parents[2]
_DEFAULT_DEBT = _REPO / "docs" / "governance" / "model_paths_literal_debt.json"

# Modules allowed to contain models/ path literals without debt entries.
_APPROVED_FILES: frozenset[str] = frozenset(
    {
        "src/config_layer/model_paths.py",
        "src/config_layer/model_resolver.py",
        "src/utils/zone_schema_migrator.py",
    }
)


def _norm_path(p: str | Path) -> str:
    return str(p).replace("\\", "/").lstrip("./")


def _norm_literal(s: str) -> str:
    return s.replace("\\", "/")


def debt_literal_token(s: str, *, max_len: int = 160) -> str:
    """Stable short token for debt keys; always retains a ``models/`` window when truncated."""
    n = _norm_literal(s)
    if len(n) <= max_len:
        return n
    i = n.find("models/")
    if i < 0:
        return n[: max_len - 3] + "..."
    # Center a window on the first models/ occurrence so truncated docstrings still match.
    half = max_len // 2
    start = max(0, i - half // 2)
    end = min(len(n), start + max_len - 6)
    start = max(0, end - (max_len - 6))
    chunk = n[start:end]
    prefix = "..." if start else ""
    suffix = "..." if end < len(n) else ""
    return prefix + chunk + suffix


def is_approved_module(rel: str) -> bool:
    """Return True if this file may freely embed models/ path literals."""
    rel = _norm_path(rel)
    if rel in _APPROVED_FILES:
        return True
    if rel.startswith("tests/"):
        return True
    # migration tooling (scripts + names)
    name = Path(rel).name.lower()
    if "migrat" in name or name.startswith("convert_zones"):
        return True
    if rel.startswith("scripts/") and (
        "migrat" in rel.lower() or "convert_zones" in rel.lower()
    ):
        return True
    return False


def is_models_path_literal(value: str) -> bool:
    """True if a string constant embeds a models/ filesystem path fragment."""
    return "models/" in _norm_literal(value)


def iter_string_constants(path: Path) -> Iterable[tuple[int, str]]:
    try:
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=str(path))
    except (OSError, SyntaxError, UnicodeError):
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.lineno, node.value


def scan_roots(roots: Iterable[Path], *, repo: Path = _REPO) -> list[dict]:
    """Return list of {file, line, literal} for unauthorized models/ literals."""
    hits: list[dict] = []
    for root in roots:
        root = (repo / root).resolve() if not root.is_absolute() else root
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            rel = _norm_path(path.relative_to(repo))
            if is_approved_module(rel):
                continue
            for lineno, value in iter_string_constants(path):
                if is_models_path_literal(value):
                    hits.append(
                        {
                            "file": rel,
                            "line": lineno,
                            "literal": debt_literal_token(value),
                        }
                    )
    return hits


def debt_key(file: str, literal: str) -> tuple[str, str]:
    return (_norm_path(file), debt_literal_token(literal))


def load_debt(path: Path = _DEFAULT_DEBT) -> dict:
    if not path.exists():
        return {"version": 1, "debt": []}
    return json.loads(path.read_text(encoding="utf-8"))


def debt_key_set(debt_doc: dict) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for entry in debt_doc.get("debt") or []:
        out.add(debt_key(entry["file"], entry["literal"]))
    return out


def actual_key_counter(hits: list[dict]) -> Counter:
    return Counter(debt_key(h["file"], h["literal"]) for h in hits)


def evaluate(hits: list[dict], debt_doc: dict) -> tuple[list[str], list[str]]:
    """
    Returns (new_violations, stale_debt_messages).

    - new_violations: actual keys not in debt (must FAIL)
    - stale_debt: debt keys with zero actual (advisory — fail to force shrink)
    """
    allowed = debt_key_set(debt_doc)
    actual = actual_key_counter(hits)
    actual_keys = set(actual)
    new = sorted(actual_keys - allowed)
    stale = sorted(allowed - actual_keys)
    new_msgs = [
        f"NEW unauthorized models/ literal: {f} :: {lit!r} (×{actual[(f, lit)]})"
        for f, lit in new
    ]
    stale_msgs = [
        f"STALE debt entry (remove from debt file): {f} :: {lit!r}"
        for f, lit in stale
    ]
    return new_msgs, stale_msgs


def build_debt_doc(hits: list[dict]) -> dict:
    c = Counter(debt_key(h["file"], h["literal"]) for h in hits)
    debt = [
        {
            "file": f,
            "literal": lit,
            "count": n,
        }
        for (f, lit), n in sorted(c.items())
    ]
    return {
        "version": 1,
        "description": (
            "Grandfathered models/ path-literal debt outside ModelPaths. "
            "Ratchet: unauthorized hits must match this set; shrink only (never grow) "
            "without an explicit debt-file edit under review."
        ),
        "scan_roots": ["src"],
        "approved_modules": sorted(_APPROVED_FILES)
        + ["tests/**", "scripts/**/*migrat*", "scripts/**/convert_zones*", "**/zone_schema_migrator.py"],
        "match_rule": "AST string Constant containing models/ (backslash normalized to /)",
        "debt": debt,
        "debt_pair_count": len(debt),
        "debt_occurrence_count": sum(d["count"] for d in debt),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="print machine-readable report")
    ap.add_argument(
        "--write-debt",
        action="store_true",
        help="regenerate docs/governance/model_paths_literal_debt.json from current scan",
    )
    ap.add_argument(
        "--debt",
        type=Path,
        default=_DEFAULT_DEBT,
        help="path to debt JSON",
    )
    ap.add_argument(
        "--allow-stale-debt",
        action="store_true",
        help="do not fail when debt entries are already cleaned up (default: fail to force shrink)",
    )
    args = ap.parse_args(argv)

    hits = scan_roots([_REPO / "src"], repo=_REPO)

    if args.write_debt:
        doc = build_debt_doc(hits)
        args.debt.parent.mkdir(parents=True, exist_ok=True)
        args.debt.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {args.debt} pairs={doc['debt_pair_count']} occ={doc['debt_occurrence_count']}")
        return 0

    debt_doc = load_debt(args.debt)
    new_msgs, stale_msgs = evaluate(hits, debt_doc)

    report = {
        "unauthorized_hits": len(hits),
        "unique_pairs": len(actual_key_counter(hits)),
        "new_violations": new_msgs,
        "stale_debt": stale_msgs,
        "ok": not new_msgs and (args.allow_stale_debt or not stale_msgs),
    }

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(
            f"model_paths literal scan: unauthorized_hits={report['unauthorized_hits']} "
            f"unique_pairs={report['unique_pairs']}"
        )
        for m in new_msgs:
            print("  FAIL", m)
        for m in stale_msgs:
            print("  STALE", m)
        if report["ok"]:
            print("OK — no new unauthorized models/ path literals")
        else:
            print("FAIL — see messages above")

    if new_msgs:
        return 1
    if stale_msgs and not args.allow_stale_debt:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
