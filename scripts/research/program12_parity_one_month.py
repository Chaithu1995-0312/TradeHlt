# -*- coding: utf-8 -*-
"""Thin CLI: Program 12 one-month XAUUSD projector parity (F-080 method).

Logic lives in ``src/research/timeframe_ladder/parity.py``. This script loads
paths, prints n/first/last, writes JSON. It does not fetch, does not admit a
corpus, and does not run the ladder.

Usage:
    python scripts/research/program12_parity_one_month.py --parent data/XAUUSD_M15.csv
    python scripts/research/program12_parity_one_month.py --parent data/XAUUSD_M15.csv \\
        --native-h4 data/mt5/XAUUSD_H4_20260707_20260806.csv \\
        --native-h1 data/mt5/XAUUSD_H1_20260707_20260806.csv \\
        --out results/research/program12/parity_one_month.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from research.timeframe_ladder.parity import (  # noqa: E402
    DECLARED_PARENT_PATH,
    compare_projected_vs_native,
    load_ohlcv_csv,
    parent_window_report,
    project,
)
from utils.console_safe import safe_print  # noqa: E402


def _echo(label: str, candles) -> dict:
    report = parent_window_report(candles) if candles else {
        "n": 0, "first": None, "last": None,
        "declared_n": None, "declared_first": None, "declared_last": None,
        "matches_declared_window": False,
    }
    safe_print(
        f"{label}: path-echo n={report['n']} first={report['first']} last={report['last']}"
    )
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Program 12 one-month projector parity")
    ap.add_argument("--parent", default=DECLARED_PARENT_PATH, help="M15 parent CSV (explicit path)")
    ap.add_argument("--native-h4", default=None, help="Native H4 CSV for the same dates")
    ap.add_argument("--native-h1", default=None, help="Native H1 CSV for the same dates")
    ap.add_argument(
        "--out",
        default=str(_ROOT / "results" / "research" / "program12" / "parity_one_month.json"),
        help="JSON report path",
    )
    args = ap.parse_args(argv)

    parent_path = Path(args.parent)
    safe_print(f"parent path={parent_path.resolve()}")
    parent = load_ohlcv_csv(parent_path)
    parent_report = _echo("parent", parent)
    if not parent_report["matches_declared_window"]:
        safe_print(
            "WARN: parent does not match the declared one-month window "
            f"(n={parent_report['declared_n']} "
            f"{parent_report['declared_first']} -> {parent_report['declared_last']})"
        )

    body = {
        "kind": "program12_one_month_parity",
        "parent_path": str(parent_path),
        "parent": parent_report,
        "projected": {},
        "compare": {},
    }
    for rule in ("H1", "H4"):
        proj = project(parent, rule)
        body["projected"][rule] = {
            "n": len(proj),
            "first": proj[0].timestamp.isoformat(sep=" ") if proj else None,
            "last": proj[-1].timestamp.isoformat(sep=" ") if proj else None,
        }
        safe_print(
            f"projected {rule}: n={len(proj)} first={body['projected'][rule]['first']} "
            f"last={body['projected'][rule]['last']}"
        )

    native_map = {"H1": args.native_h1, "H4": args.native_h4}
    missing_native = [r for r, p in native_map.items() if not p]
    for rule, npath in native_map.items():
        if not npath:
            continue
        np = Path(npath)
        safe_print(f"native {rule} path={np.resolve()}")
        native = load_ohlcv_csv(np)
        _echo(f"native {rule}", native)
        proj = project(parent, rule)
        body["compare"][rule] = compare_projected_vs_native(proj, native, rule=rule)
        safe_print(f"compare {rule}: status={body['compare'][rule]['status']}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    safe_print(f"wrote {out}")

    if missing_native:
        safe_print(
            "NEED_NATIVE: no native file for " + ",".join(missing_native)
            + " — projector ran; compare skipped for those rules."
        )
        return 2
    statuses = [body["compare"][r]["status"] for r in ("H1", "H4") if r in body["compare"]]
    if any(s == "FAIL" for s in statuses):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
