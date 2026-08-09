# -*- coding: utf-8 -*-
"""Build IC-003B sequence-geometry library (H-IC003B-001). Research only.

Usage:
  python scripts/research/ic003b_build.py              # resume by default
  python scripts/research/ic003b_build.py --resume     # skip completed units on disk
  python scripts/research/ic003b_build.py --fresh      # recompute all arms
  python scripts/research/ic003b_build.py --mark-paused  # write PAUSED checkpoint only
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
for _p in (str(_ROOT), str(_SRC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.ic003b_sequence_geometry.build_all import (  # noqa: E402
    DEFAULT_IC002,
    DEFAULT_OUT,
    build_all,
    write_paused_checkpoint,
)
from utils.console_safe import safe_print  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s | %(message)s")
    p = argparse.ArgumentParser(prog="ic003b_build")
    p.add_argument("--ic002", default=str(DEFAULT_IC002))
    p.add_argument("--out", default=str(DEFAULT_OUT))
    g = p.add_mutually_exclusive_group()
    g.add_argument(
        "--resume",
        action="store_true",
        default=True,
        help="Skip units with valid on-disk checkpoints (default)",
    )
    g.add_argument(
        "--fresh",
        action="store_true",
        help="Ignore checkpoints and recompute all arms",
    )
    p.add_argument(
        "--mark-paused",
        action="store_true",
        help="Only write PAUSED checkpoint/RUN_STATUS from current disk inventory",
    )
    args = p.parse_args(argv)
    out = Path(args.out)

    if args.mark_paused:
        snap = write_paused_checkpoint(out)
        safe_print(str(snap))
        safe_print(f"-> {out / 'checkpoint.json'}")
        safe_print(f"-> {out / 'RUN_STATUS.md'}")
        return 0

    resume = not args.fresh
    report = build_all(ic002_dir=Path(args.ic002), out_dir=out, resume=resume)
    pv = report.get("program_verdict") or {}
    safe_print(str(pv))
    safe_print(f"-> {out / 'REPORT.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
