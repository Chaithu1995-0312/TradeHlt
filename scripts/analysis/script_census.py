"""Thin CLI for SITS script census (PR-6: core lives in src/governance/script_census.py).

    python scripts/analysis/script_census.py
    python scripts/analysis/script_census.py --write-stubs docs/governance/script_registry_stubs.jsonl
    python scripts/analysis/script_census.py --json reports/script_census.LATEST.json
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

from governance.script_census import (  # noqa: E402
    DEFAULT_STUB_TS,
    census_report,
    discover_paths,
    write_stubs,
)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="SITS script census (observe + write-stubs)")
    ap.add_argument("--repo-root", default=str(_ROOT), help="Repository root")
    ap.add_argument(
        "--write-stubs",
        metavar="PATH",
        help="Merge path-stable stubs JSONL",
    )
    ap.add_argument("--json", metavar="PATH", help="Write census summary JSON")
    ap.add_argument(
        "--include-src-cli",
        action="store_true",
        help="Also inventory src/**/*.py with __main__",
    )
    ap.add_argument(
        "--timestamp",
        default=DEFAULT_STUB_TS,
        help="Pinned timestamp for NEW stub rows only",
    )
    args = ap.parse_args(argv)

    root = Path(args.repo_root).resolve()
    discovered = discover_paths(root, include_src_cli=args.include_src_cli)
    report = census_report(discovered)
    print(json.dumps(report, indent=2))

    if args.write_stubs:
        stubs = write_stubs(Path(args.write_stubs), discovered, timestamp=args.timestamp)
        print(f"Wrote {len(stubs)} stub records → {args.write_stubs}", file=sys.stderr)

    if args.json:
        outp = Path(args.json)
        outp.parent.mkdir(parents=True, exist_ok=True)
        payload = {**report, "files": [asdict(f) for f in discovered]}
        outp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Wrote census JSON → {args.json}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
