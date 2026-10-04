"""verify_archive_manifests.py — prove every file under archive/ is tracked and nothing was deleted.

Thin CLI over `src/governance/archive_manifest.py` (all logic lives there). Floor:
`tests/governance/test_archive_manifests.py`.

Usage
    python scripts/maintenance/verify_archive_manifests.py            # verify; exit 1 on violations
    python scripts/maintenance/verify_archive_manifests.py --json     # machine-readable report
    python scripts/maintenance/verify_archive_manifests.py backfill   # dry-run: rows that WOULD be added
    python scripts/maintenance/verify_archive_manifests.py backfill --apply
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from governance import archive_manifest as am  # noqa: E402


def _verify(args: argparse.Namespace) -> int:
    rep = am.verify(ROOT)
    if args.json:
        print(json.dumps(rep.as_dict(), indent=2))
    else:
        print(f"manifests={rep.manifests} rows={rep.rows} archive_files={rep.archive_files} "
              f"violations={len(rep.violations)} warnings={len(rep.warnings)}")
        for v in rep.violations:
            print(f"  VIOLATION {v}")
        for w in rep.warnings:
            print(f"  warning   {w}")
    return 0 if rep.ok else 1


def _backfill(args: argparse.Namespace) -> int:
    plan = am.backfill_rows(ROOT)
    total = sum(len(v) for v in plan.values())
    for target, rows in sorted(plan.items()):
        print(f"{target.relative_to(ROOT).as_posix()}: {len(rows)} row(s)")
        for r in rows:
            print(f"  {r['action']:22s} {r['archive_path']}  <- {r['original_path'] or '?'}")
        if args.apply:
            am.append_rows(target, rows)
    print(f"{'appended' if args.apply else 'would append'} {total} row(s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="verify_archive_manifests", description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="emit the verify report as JSON")
    sub = ap.add_subparsers(dest="cmd")
    bf = sub.add_parser("backfill", help="account for archived files that have no manifest row")
    bf.add_argument("--apply", action="store_true", help="append the rows (default: dry run)")
    args = ap.parse_args(argv)
    return _backfill(args) if args.cmd == "backfill" else _verify(args)


if __name__ == "__main__":
    raise SystemExit(main())
