"""Thin CLI for the module attribution census (core lives in src/governance/module_census.py).

    python scripts/analysis/module_census.py
    python scripts/analysis/module_census.py --write-stubs docs/governance/module_attribution_stubs.jsonl
    python scripts/analysis/module_census.py --coverage
    python scripts/analysis/module_census.py --json reports/module_census.LATEST.json

Reports coverage of ``src/**/*.py`` against the attribution ledger. Observe-only unless
``--write-stubs`` is passed. Coverage exit code is non-zero only under ``--enforce``.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from governance.module_attribution import (  # noqa: E402
    DEFAULT_STUBS_PATH,
    ModuleAttributionRegistry,
)
from governance.module_census import (  # noqa: E402
    DEFAULT_STUB_TS,
    census_report,
    discover_modules,
    write_stubs,
)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Module attribution census (observe + write-stubs + coverage)"
    )
    ap.add_argument("--repo-root", default=str(_ROOT), help="Repository root")
    ap.add_argument("--write-stubs", metavar="PATH", help="Merge path-stable stubs JSONL")
    ap.add_argument("--json", metavar="PATH", help="Write census summary JSON")
    ap.add_argument(
        "--coverage",
        action="store_true",
        help="Report ledger coverage vs disk (enumeration + attribution)",
    )
    ap.add_argument(
        "--registry",
        metavar="PATH",
        help="Attribution ledger to check coverage against (default: the stubs file)",
    )
    ap.add_argument(
        "--enforce",
        action="store_true",
        help="Exit non-zero if any module is unattributed (Phase 4 ratchet; warn-only otherwise)",
    )
    ap.add_argument(
        "--timestamp",
        default=DEFAULT_STUB_TS,
        help="Pinned timestamp for NEW stub rows only",
    )
    args = ap.parse_args(argv)

    root = Path(args.repo_root).resolve()
    discovered = discover_modules(root)
    report = census_report(discovered)
    print(json.dumps(report, indent=2))

    if args.write_stubs:
        stubs = write_stubs(Path(args.write_stubs), discovered, timestamp=args.timestamp)
        print(f"Wrote {len(stubs)} stub records → {args.write_stubs}", file=sys.stderr)

    rc = 0
    if args.coverage:
        reg_path = Path(args.registry) if args.registry else DEFAULT_STUBS_PATH
        registry = ModuleAttributionRegistry(reg_path)
        cov = registry.coverage_against_disk({f.path for f in discovered})
        print(json.dumps({"coverage": cov, "registry": str(reg_path)}, indent=2))
        if not cov["enumeration_ok"]:
            print(
                f"ENUMERATION DRIFT: {len(cov['unregistered'])} unregistered, "
                f"{len(cov['missing_on_disk'])} missing on disk",
                file=sys.stderr,
            )
            rc = 1
        if not cov["attribution_ok"]:
            level = "FAIL" if args.enforce else "WARN"
            print(
                f"{level}: {len(cov['unattributed'])} module(s) unattributed "
                f"({cov['attribution_pct']}% attributed)",
                file=sys.stderr,
            )
            if args.enforce:
                rc = 1

    if args.json:
        outp = Path(args.json)
        outp.parent.mkdir(parents=True, exist_ok=True)
        payload = {**report, "modules": [asdict(f) for f in discovered]}
        outp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Wrote census JSON → {args.json}", file=sys.stderr)

    return rc


if __name__ == "__main__":
    raise SystemExit(main())
