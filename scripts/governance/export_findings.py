"""Regenerate data/findings.jsonl — the GENERATED derived view of docs/current-findings.md.

Thin CLI wrapper over ``governance.findings_export`` (CLAUDE.md §3.3: no business logic in
scripts). The JSONL is never hand-edited; the markdown doc stays the authoritative store
(§6.2). Deterministic: reruns on an unchanged doc are byte-identical.

Run:    python scripts/governance/export_findings.py
Check:  python scripts/governance/export_findings.py --check   (print to stdout, write nothing)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from governance.findings_export import DEFAULT_OUT, export, parse_findings, render  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doc", default=str(_ROOT / "docs" / "current-findings.md"))
    parser.add_argument("--out", default=str(_ROOT / DEFAULT_OUT))
    parser.add_argument("--check", action="store_true", help="print the export; write nothing")
    args = parser.parse_args()

    if args.check:
        sys.stdout.write(render(parse_findings(Path(args.doc))))
        return 0
    n = export(Path(args.doc), Path(args.out))
    print(f"wrote {n} findings -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
