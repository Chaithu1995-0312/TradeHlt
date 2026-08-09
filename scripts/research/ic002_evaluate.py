# -*- coding: utf-8 -*-
"""Evaluate IC-002 path vs static baseline (H-IC002-001). Research only.

Requires prior: python scripts/research/ic002_build_trajectories.py

Usage:
  python scripts/research/ic002_evaluate.py
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

from research.ic002_entry_evolution.evaluate_separation import evaluate_all  # noqa: E402
from research.ic002_entry_evolution.io_util import DEFAULT_OUT  # noqa: E402
from research.ic002_entry_evolution.schema import N_GRID  # noqa: E402
from utils.console_safe import safe_print  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s | %(message)s")
    p = argparse.ArgumentParser(prog="ic002_evaluate")
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--N", type=int, default=None)
    args = p.parse_args(argv)

    n_grid = (args.N,) if args.N is not None else N_GRID
    report = evaluate_all(out_dir=Path(args.out), n_grid=n_grid)
    safe_print(str(report.get("program_verdict")))
    for k, c in sorted((report.get("cells") or {}).items(), key=lambda x: int(x[0])):
        safe_print(
            f"N={k} verdict={c.get('verdict')} AUC_path_OOS={c.get('AUC_path_OOS')} "
            f"AUC_static_OOS={c.get('AUC_static_OOS')} dAUC={c.get('delta_AUC_OOS')}"
        )
    safe_print(f"-> {Path(args.out) / 'REPORT.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
