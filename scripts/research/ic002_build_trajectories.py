# -*- coding: utf-8 -*-
"""Build IC-002 trajectories (H-IC002-001). Research only.

Usage:
  python scripts/research/ic002_build_trajectories.py
  python scripts/research/ic002_build_trajectories.py --N 4   # single N smoke
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

from research.ic002_entry_evolution.build_trajectories import build_all  # noqa: E402
from research.ic002_entry_evolution.io_util import DEFAULT_OUT  # noqa: E402
from research.ic002_entry_evolution.schema import N_GRID  # noqa: E402
from utils.console_safe import safe_print  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s | %(message)s")
    p = argparse.ArgumentParser(prog="ic002_build_trajectories")
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--N", type=int, default=None, help="single N smoke; default all prereg N_GRID")
    p.add_argument("--entries", default=None)
    p.add_argument("--ohlcv", default=None)
    args = p.parse_args(argv)

    n_grid = (args.N,) if args.N is not None else N_GRID
    if args.N is not None and args.N not in N_GRID:
        safe_print(f"WARNING: N={args.N} not in prereg N_GRID={N_GRID} (smoke only)")

    manifest = build_all(
        entries_path=Path(args.entries) if args.entries else None,
        ohlcv_path=Path(args.ohlcv) if args.ohlcv else None,
        out_dir=Path(args.out),
        n_grid=n_grid,
    )
    safe_print(json_dumps_brief(manifest))
    safe_print(f"-> {args.out}")
    return 0


def json_dumps_brief(m: dict) -> str:
    import json

    return json.dumps(
        {
            "n_entries_source": m.get("n_entries_source"),
            "ohlcv_sha256": (m.get("ohlcv_sha256") or "")[:16],
            "batches": {
                k: v.get("n_trajectories") for k, v in (m.get("batches") or {}).items()
            },
        },
        indent=2,
    )


if __name__ == "__main__":
    raise SystemExit(main())
