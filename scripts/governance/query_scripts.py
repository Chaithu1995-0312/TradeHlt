"""Query the Script Registry (SITS).

    python scripts/governance/query_scripts.py --summary
    python scripts/governance/query_scripts.py --category DIAGNOSTIC
    python scripts/governance/query_scripts.py --lifecycle EPHEMERAL
    python scripts/governance/query_scripts.py --path scripts/analysis
    python scripts/governance/query_scripts.py --missing-impl
    python scripts/governance/query_scripts.py --missing-impl --jsonl
    python scripts/governance/query_scripts.py --debt
    python scripts/governance/query_scripts.py --debt --jsonl
    python scripts/governance/query_scripts.py --export-debt-report reports/script_promotion_debt.LATEST.md
    python scripts/governance/query_scripts.py --canonical-gap
    python scripts/governance/query_scripts.py --validate
    python scripts/governance/query_scripts.py --validate --repo-root .
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from governance.script_registry import ScriptRegistry  # noqa: E402

REGISTRY = _ROOT / "data" / "script_registry.jsonl"
DEFAULT_DEBT_REPORT = _ROOT / "reports" / "script_promotion_debt.LATEST.md"


def _print_records(records: list[dict]) -> None:
    for r in sorted(records, key=lambda x: x["id"]):
        print(
            f"  {r['id']:<10} {r.get('category', '?'):<16} "
            f"{r.get('lifecycle', '?'):<10} {r.get('implementation_status', '?'):<20} "
            f"{r.get('path', '')}"
        )
    print(f"  ({len(records)} records)")


def main() -> int:
    ap = argparse.ArgumentParser(description="Query the Script Registry (SITS)")
    ap.add_argument("--registry", default=str(REGISTRY))
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--category")
    ap.add_argument("--lifecycle")
    ap.add_argument("--status", dest="implementation_status", help="implementation_status filter")
    ap.add_argument("--task", metavar="REF")
    ap.add_argument("--path", dest="path_substr", help="substring match on path")
    ap.add_argument("--owner-kind")
    ap.add_argument("--missing-impl", action="store_true")
    ap.add_argument(
        "--debt",
        action="store_true",
        help="promotion_debt (expired TTL without valid plan; calendar now by default)",
    )
    ap.add_argument(
        "--debt-days",
        type=int,
        default=None,
        help="test injection: treat every row as this many days old (overrides calendar)",
    )
    ap.add_argument(
        "--jsonl",
        action="store_true",
        help="with --missing-impl / --debt: emit JSON lines (queue-shaped for missing-impl)",
    )
    ap.add_argument(
        "--export-debt-report",
        metavar="PATH",
        nargs="?",
        const=str(DEFAULT_DEBT_REPORT),
        default=None,
        help=f"write markdown debt report (default {DEFAULT_DEBT_REPORT})",
    )
    ap.add_argument("--validate", action="store_true", help="schema + optional path checks; exit 1 on error")
    ap.add_argument(
        "--canonical-gap",
        action="store_true",
        help="ACTIVE CANONICAL_CLI missing control_plane_id / allowlist (PR-4 parity)",
    )
    ap.add_argument(
        "--repo-root",
        default=None,
        help="with --validate: check non-terminal paths exist under this root",
    )
    ap.add_argument(
        "--canonical-allowlist",
        default=str(_ROOT / "docs" / "governance" / "script_canonical_allowlist.json"),
        help="path to script_canonical_allowlist.json",
    )
    args = ap.parse_args()

    reg = ScriptRegistry()
    reg_path = Path(args.registry)
    if not reg_path.exists():
        n = 0
        reg._records = {}
    else:
        n = reg.load(reg_path)

    if args.canonical_gap:
        from governance.script_registry import (  # noqa: WPS433
            _load_core_command_specs,
            load_canonical_allowlist,
        )

        try:
            command_ids = {s.id for s in _load_core_command_specs()()}
        except Exception as exc:  # noqa: BLE001
            print(f"CANONICAL GAP ERROR: cannot load CommandSpecs: {exc}", file=sys.stderr)
            return 2
        allow = load_canonical_allowlist(args.canonical_allowlist)
        errs = reg.validate_control_plane_parity(command_ids, allow)
        if errs:
            print(f"CANONICAL GAP ({len(errs)}):")
            for e in errs:
                print(f"  {e}")
            return 1
        print(f"CANONICAL GAP OK - 0 gaps ({n} records)")
        return 0

    if args.validate:
        problems: list[str] = []
        for rec in reg.records:
            try:
                ScriptRegistry.validate_record(rec)
            except ValueError as exc:
                problems.append(f"[schema] {exc}")
        if args.repo_root:
            problems.extend(
                str(e) for e in reg.validate_paths(Path(args.repo_root))
            )
        # Phase-4: expired TTL debt fails validate (same rule as CI floor)
        debt = reg.promotion_debt()
        for r in debt:
            problems.append(
                f"[debt] {r.get('id')}: expired ttl_days={r.get('ttl_days')} "
                f"without valid promotion plan ({r.get('path')})"
            )
        if problems:
            print(f"VALIDATION FAILED ({len(problems)} error(s)):")
            for p in problems:
                print(f"  {p}")
            return 1
        print(f"VALIDATION OK - {n} records, 0 errors (debt=0)")
        return 0

    if args.export_debt_report is not None:
        out = Path(args.export_debt_report)
        out.parent.mkdir(parents=True, exist_ok=True)
        text = reg.debt_report_markdown()
        out.write_text(text, encoding="utf-8")
        print(f"Wrote debt report → {out}", file=sys.stderr)
        # also print path for agents
        print(str(out))
        return 0

    if args.missing_impl:
        if args.jsonl:
            for line in reg.missing_impl_queue_lines():
                print(json.dumps(line, ensure_ascii=False, sort_keys=True))
        else:
            rows = reg.missing_impl()
            print("missing-impl (logic_in_script, no valid promotion plan; visibility only):")
            _print_records(rows)
        return 0

    if args.debt:
        if args.debt_days is not None:
            rows = reg.promotion_debt(now_days=args.debt_days)
        else:
            rows = reg.promotion_debt(now=datetime.now(timezone.utc))
        if args.jsonl:
            for r in rows:
                print(json.dumps({
                    "kind": "SITS_TTL_DEBT",
                    "script_id": r.get("id"),
                    "path": r.get("path"),
                    "ttl_days": r.get("ttl_days"),
                    "purpose": r.get("purpose"),
                    "authority": "inventory",
                }, ensure_ascii=False, sort_keys=True))
        else:
            print(f"promotion_debt (now_days={args.debt_days!r}):")
            _print_records(rows)
            if rows:
                return 1  # non-zero so CI wrappers can treat debt as failure
        return 0

    filtered = False
    if any([
        args.category,
        args.lifecycle,
        args.implementation_status,
        args.task,
        args.path_substr,
        args.owner_kind,
    ]):
        filtered = True
        rows = reg.filter(
            category=args.category,
            lifecycle=args.lifecycle,
            implementation_status=args.implementation_status,
            task=args.task,
            path_substr=args.path_substr,
            owner_kind=args.owner_kind,
        )
        _print_records(rows)

    if args.summary or not filtered:
        summary = reg.summary()
        summary["ttl_tracked"] = sum(
            1 for r in reg.records if r.get("ttl_days") is not None
        )
        summary["ttl_debt"] = len(reg.promotion_debt())
        summary["missing_impl"] = len(reg.missing_impl())
        print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
