"""Append an updated registry line for a component (001_FRAMEWORK_REGISTRY.md §M4).

Append-only (CLAUDE.md §6.2 rule 4): never mutates a prior line — writes a NEW line with the
changed field(s) + a fresh `last_validated`. `load()` then resolves the latest per id.

    python scripts/governance/update_registry.py --component RISK-002 --status extant \
        --notes "wired PortfolioAllocator into UltronRiskGate (Epic 2 STORY-2.1)"
"""
from __future__ import annotations

import argparse
import datetime as _dt
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _p in (_ROOT / "src", _ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from governance.framework_registry import STATUS_ENUM, FrameworkRegistry  # noqa: E402

REGISTRY = _ROOT / "data" / "framework_registry.jsonl"


def main() -> int:
    ap = argparse.ArgumentParser(description="Append an updated registry line")
    ap.add_argument("--registry", default=str(REGISTRY))
    ap.add_argument("--component", required=True, help="component id, e.g. RISK-002")
    ap.add_argument("--status", choices=sorted(STATUS_ENUM))
    ap.add_argument("--notes")
    ap.add_argument("--add-finding", action="append", default=[], help="append an F-NNN to findings")
    args = ap.parse_args()

    reg = FrameworkRegistry()
    reg.load(args.registry)
    try:
        current = reg.get(args.component)
    except KeyError:
        print(f"ERROR: no component {args.component!r} in {args.registry}")
        return 1

    updated = dict(current)
    if args.status:
        updated["status"] = args.status
    if args.notes:
        updated["notes"] = args.notes
    if args.add_finding:
        updated["findings"] = sorted(set(updated.get("findings", []) + args.add_finding))
    updated["last_validated"] = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    reg.append(updated)  # validates + appends (append-only)
    errors = reg.validate_all()
    if errors:
        print(f"WARNING: appended, but registry now has {len(errors)} validation error(s):")
        for e in errors:
            print(f"  {e}")
        return 1
    print(f"appended update for {args.component}: status={updated['status']} "
          f"last_validated={updated['last_validated']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
