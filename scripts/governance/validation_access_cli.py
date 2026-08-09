#!/usr/bin/env python3
"""validation_access_cli.py — VA-XAUUSD-M15 dual-surface validation access.

Surface A: human CLI ladder (stdout + ladder_cli.md)
Surface B: LLM evidence pack under results/validation_access/xauusd_m15/<run_id>/

Sequence (gating): S → I → F → E

Design freeze: docs/governance/VALIDATION_ACCESS_VA_XAUUSD_M15.md
Authority: access/packaging only — no promotion.

Usage:
  PYTHONPATH=src python scripts/governance/validation_access_cli.py
  PYTHONPATH=src python scripts/governance/validation_access_cli.py --live-story
  PYTHONPATH=src python scripts/governance/validation_access_cli.py --live-impl
  PYTHONPATH=src python scripts/governance/validation_access_cli.py --no-pack
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from validation_access.ladder import run_ladder  # noqa: E402
from validation_access.surfaces import format_cli_report, write_evidence_pack  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="VA-XAUUSD-M15 validation access — dual surface S→I→F→E"
    )
    ap.add_argument(
        "--live-story",
        action="store_true",
        help="Re-run live six-layer story binding (slower) instead of INDEX.json",
    )
    ap.add_argument(
        "--live-impl",
        action="store_true",
        help="Re-run full XAUUSD implementation harness (slow); default uses freeze artifact",
    )
    ap.add_argument(
        "--no-pack",
        action="store_true",
        help="Surface A only — do not write Surface B evidence pack",
    )
    ap.add_argument(
        "--root",
        type=Path,
        default=_ROOT,
        help="Repository root (default: auto)",
    )
    args = ap.parse_args(argv)

    result = run_ladder(
        args.root,
        live_story=bool(args.live_story),
        live_impl=bool(args.live_impl),
    )

    # Surface A
    report = format_cli_report(result)
    print(report)

    pack_dir = None
    if not args.no_pack:
        pack_dir = write_evidence_pack(result, args.root)
        print(f"[Surface B] evidence pack → {pack_dir}")
        print(f"[Surface A] CLI summary also at {pack_dir / 'ladder_cli.md'}")

    # Exit codes: 0 if ladder completed without FAIL/ERROR/BLOCKED hard stop
    # E=OPEN is success for access layer
    hard = result.overall_status.startswith("BLOCKED") or any(
        result.overall_status.endswith(x) for x in ("_FAIL", "_ERROR")
    ) or result.overall_status in ("FAIL", "ERROR")
    # also check rung hard fails
    for code in ("S", "I", "F", "E"):
        st = result.rungs[code].status
        if st in ("FAIL", "ERROR") or st.startswith("BLOCKED"):
            # E OPEN is fine; F PARTIAL is fine for access exit 0 if overall ladder_complete*
            if code == "E" and st == "OPEN":
                continue
            if code == "F" and st == "PARTIAL":
                continue
            if st.startswith("BLOCKED") or st in ("FAIL", "ERROR"):
                hard = True
                break
    # Prefer overall_status semantics
    if result.overall_status.startswith("LADDER_COMPLETE"):
        hard = False
    if result.overall_status == "PASS":
        hard = False
    return 1 if hard else 0


if __name__ == "__main__":
    raise SystemExit(main())
