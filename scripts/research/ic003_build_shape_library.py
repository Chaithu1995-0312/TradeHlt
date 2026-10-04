# -*- coding: utf-8 -*-
"""Build IC-003 shape library from IC-002 trajectories (H-IC003-001).

Usage:
  python scripts/research/ic003_build_shape_library.py
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

from research.ic003_shapes.build_library import DEFAULT_IC002, DEFAULT_OUT, build_all  # noqa: E402
from utils.console_safe import safe_print  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s | %(message)s")
    p = argparse.ArgumentParser(prog="ic003_build_shape_library")
    p.add_argument("--ic002", default=str(DEFAULT_IC002))
    p.add_argument("--out", default=str(DEFAULT_OUT))
    args = p.parse_args(argv)

    results = build_all(ic002_dir=Path(args.ic002), out_dir=Path(args.out))
    safe_print(str(results.get("program_verdict")))
    for k, r in sorted((results.get("by_N") or {}).items(), key=lambda x: int(x[0])):
        safe_print(
            f"N={k} role={r.get('role')} k*={r.get('k_star')} verdict={r.get('verdict')} "
            f"sil={r.get('gates', {}).get('G2_silhouette', {}).get('silhouette')}"
        )
    safe_print(f"-> {Path(args.out) / 'REPORT.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
