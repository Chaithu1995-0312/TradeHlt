"""Query the Framework Registry (001_FRAMEWORK_REGISTRY.md §M2).

    python scripts/governance/query_registry.py --summary
    python scripts/governance/query_registry.py --type strategy
    python scripts/governance/query_registry.py --level 5
    python scripts/governance/query_registry.py --status orphaned
    python scripts/governance/query_registry.py --tree DOMAIN-001
    python scripts/governance/query_registry.py --finding F-021
    python scripts/governance/query_registry.py --orphaned          # structural orphans
    python scripts/governance/query_registry.py --missing-evidence
    python scripts/governance/query_registry.py --validate          # CI gate (exit 1 on error)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _p in (_ROOT / "src", _ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from governance.framework_registry import FrameworkRegistry  # noqa: E402

REGISTRY = _ROOT / "data" / "framework_registry.jsonl"


def _print_records(records: list[dict]) -> None:
    for r in sorted(records, key=lambda x: x["id"]):
        print(f"  {r['id']:<12} L{r['level']} {r['type']:<14} {r['status']:<9} {r['name']}")
    print(f"  ({len(records)} records)")


def _print_tree(reg: FrameworkRegistry, root_id: str) -> None:
    def walk(node: dict, prefix: str = "") -> None:
        tag = node.get("status", "?")
        missing = " [MISSING]" if node.get("missing") else (" [CYCLE]" if node.get("_cycle") else "")
        print(f"{prefix}{node.get('id')} - {node.get('name', '?')} ({tag}){missing}")
        kids = node.get("children", [])
        for i, k in enumerate(kids):
            walk(k, prefix + ("   " if i == len(kids) - 1 else "   "))

    walk(reg.get_tree(root_id))


def main() -> int:
    ap = argparse.ArgumentParser(description="Query the Framework Registry")
    ap.add_argument("--registry", default=str(REGISTRY))
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--type")
    ap.add_argument("--level", type=int)
    ap.add_argument("--status")
    ap.add_argument("--tree", metavar="ROOT_ID")
    ap.add_argument("--finding", metavar="F-NNN")
    ap.add_argument("--orphaned", action="store_true", help="structural orphans (no parent and no children)")
    ap.add_argument("--missing-evidence", action="store_true")
    ap.add_argument("--validate", action="store_true", help="full validation; exit 1 on any error")
    args = ap.parse_args()

    reg = FrameworkRegistry()
    n = reg.load(args.registry)

    if args.validate:
        errors = reg.validate_all()
        if errors:
            print(f"VALIDATION FAILED ({len(errors)} error(s)):")
            for e in errors:
                print(f"  {e}")
            return 1
        print(f"VALIDATION OK - {n} records, 0 errors")
        return 0

    if args.summary:
        print(json.dumps(reg.summary(), indent=2))
    if args.type:
        print(f"type={args.type}:")
        _print_records(reg.filter(type=args.type))
    if args.level is not None:
        print(f"level={args.level}:")
        _print_records(reg.filter(level=args.level))
    if args.status:
        print(f"status={args.status}:")
        _print_records(reg.filter(status=args.status))
    if args.finding:
        print(f"components touched by {args.finding}:")
        _print_records(reg.find_by_finding(args.finding))
    if args.orphaned:
        print("structural orphans (no parent and no children):")
        _print_records(reg.get_orphaned())
    if args.missing_evidence:
        errs = reg.validate_evidence()
        print(f"evidence problems ({len(errs)}):")
        for e in errs:
            print(f"  {e}")
    if not any([args.summary, args.type, args.level is not None, args.status,
                args.tree, args.finding, args.orphaned, args.missing_evidence]):
        print(json.dumps(reg.summary(), indent=2))
    if args.tree:
        _print_tree(reg, args.tree)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
