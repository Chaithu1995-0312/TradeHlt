# -*- coding: utf-8 -*-
"""Thin CLI: Program 12 Slice 2 H1/H4 ladder on the sealed one-month parent.

Echoes path, n, first, last, and sha256 before any runner. Projects H1 and H4
with research.resample, writes ladder_bars.csv, and declares that file's clock.
Does not admit the parent. Does not run D1. Does not edit configs/production.

Usage:
    python scripts/research/timeframe_ladder.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from data_ingestion.clock_registry import TZ_MT5_SERVER_NY_DST, declare_in_process  # noqa: E402
from research.resample import write_csv  # noqa: E402
from research.timeframe_ladder.parity import DECLARED_PARENT_PATH, load_ohlcv_csv, project  # noqa: E402
from research.timeframe_ladder.run import (  # noqa: E402
    PROJECTED_CSV_NAME,
    ParentWindowError,
    assert_declared_parent,
    execute_timeframe,
    format_funnel_line,
    parent_file_identity,
    render_funnel_markdown,
)
from utils.console_safe import safe_print  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    del argv  # the sealed parent is the only corpus this command runs
    parent_path = _ROOT / DECLARED_PARENT_PATH
    if not parent_path.is_file():
        safe_print(f"PARENT_MISSING path={DECLARED_PARENT_PATH}")
        return 2
    identity = parent_file_identity(parent_path)
    safe_print(
        f"parent path={identity['path']} n={identity['n']} "
        f"first={identity['first']} last={identity['last']} sha256={identity['sha256']}"
    )
    try:
        assert_declared_parent(identity)
    except ParentWindowError as exc:
        safe_print(str(exc))
        return 2

    parent = load_ohlcv_csv(parent_path)
    reports = []
    for timeframe in ("H1", "H4"):
        projected = project(parent, timeframe)
        out = _ROOT / "results" / "program12_slice2" / timeframe
        csv_path = out / PROJECTED_CSV_NAME
        write_csv(projected, csv_path)
        declare_in_process(
            csv_path,
            TZ_MT5_SERVER_NY_DST,
            reason="Program 12 Slice 2 projected ladder bars from the sealed one-month parent",
        )
        safe_print(f"{timeframe} projected_n={len(projected)} csv={PROJECTED_CSV_NAME}")
        report = execute_timeframe(
            timeframe, projected, csv_path, out, parent=identity,
        )
        reports.append(report)
        safe_print(format_funnel_line(report))

    payload = {"parent": identity, "timeframes": reports}
    results_dir = _ROOT / "results" / "program12_slice2"
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "funnel.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    md = render_funnel_markdown(payload)
    (_ROOT / "docs" / "research" / "program12-slice2-funnel.md").write_text(md, encoding="utf-8")
    failed = [r for r in reports if r.get("status") != "OK"]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
