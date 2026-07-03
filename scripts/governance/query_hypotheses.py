"""Query the Hypothesis Registry (sibling of query_registry.py).

    python scripts/governance/query_hypotheses.py --summary
    python scripts/governance/query_hypotheses.py --status falsified
    python scripts/governance/query_hypotheses.py --model crt
    python scripts/governance/query_hypotheses.py --finding F-042
    python scripts/governance/query_hypotheses.py --family transition
    python scripts/governance/query_hypotheses.py --validate          # CI gate (exit 1 on error)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from governance.hypothesis_registry import HypothesisRegistry  # noqa: E402

REGISTRY = _ROOT / "data" / "hypothesis_registry.jsonl"


def _print_records(records: list[dict]) -> None:
    for r in sorted(records, key=lambda x: x["id"]):
        fids = ",".join(r.get("findings") or []) or "-"
        print(f"  {r['id']:<7} {r['status']:<10} [{fids}] {r['statement'][:90]}")
    print(f"  ({len(records)} records)")


def main() -> int:
    ap = argparse.ArgumentParser(description="Query the Hypothesis Registry")
    ap.add_argument("--registry", default=str(REGISTRY))
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--status")
    ap.add_argument("--model")
    ap.add_argument("--finding", metavar="F-NNN")
    ap.add_argument("--family")
    ap.add_argument("--validate", action="store_true", help="full validation; exit 1 on any error")
    args = ap.parse_args()

    reg = HypothesisRegistry()
    n = reg.load(args.registry)

    if args.validate:
        problems: list[str] = []
        for rec in reg.records:  # schema re-check of what's on disk (dump/append could be bypassed)
            try:
                HypothesisRegistry.validate_record(rec)
            except ValueError as exc:
                problems.append(f"[schema] {exc}")
        problems.extend(str(e) for e in reg.validate_all())
        if problems:
            print(f"VALIDATION FAILED ({len(problems)} error(s)):")
            for p in problems:
                print(f"  {p}")
            return 1
        print(f"VALIDATION OK - {n} records, 0 errors")
        return 0

    if args.summary:
        print(json.dumps(reg.summary(), indent=2))
    if args.status:
        print(f"status={args.status}:")
        _print_records(reg.filter(status=args.status))
    if args.model:
        print(f"model={args.model}:")
        _print_records(reg.filter(model=args.model))
    if args.finding:
        print(f"hypotheses touching {args.finding}:")
        _print_records(reg.filter(finding=args.finding))
    if args.family:
        print(f"family={args.family}:")
        _print_records(reg.filter(family=args.family))
    if not any([args.summary, args.status, args.model, args.finding, args.family]):
        print(json.dumps(reg.summary(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
