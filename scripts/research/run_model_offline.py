#!/usr/bin/env python3
"""Trigger one model on historical OHLCV (OBSERVATION_ONLY).

Authority: research only. PRODUCTION_BEHAVIOR_CHANGED=false.
No silent defaults: required CLI flags have no inventing defaults.

Examples
--------
  python scripts/research/run_model_offline.py --list

  python scripts/research/run_model_offline.py \\
    --model rr \\
    --csv data/BNBUSDT_M15.csv \\
    --instrument BNBUSDT \\
    --out-dir results/model_runners \\
    --limit 200
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run_model_offline",
        description=(
            "Run one production model on historical OHLCV. "
            "Research/observation only — no promote authority."
        ),
    )
    p.add_argument(
        "--list",
        action="store_true",
        help="List Phase-1 model ids and exit",
    )
    p.add_argument(
        "--model",
        help="Model id (see --list)",
    )
    p.add_argument(
        "--csv",
        help="Path to historical OHLCV CSV",
    )
    p.add_argument(
        "--instrument",
        help="Instrument id (required for scoring runs)",
    )
    p.add_argument(
        "--out-dir",
        help="Output root directory (required for scoring runs)",
    )
    p.add_argument(
        "--config-path",
        default=None,
        help=(
            "Explicit production JSON path. If omitted, uses "
            "configs/production/ACTIVE_VERSION only (one resolution path)."
        ),
    )
    p.add_argument(
        "--start",
        default=None,
        help="Inclusive window start (ISO). Omit for full post-warmup series.",
    )
    p.add_argument(
        "--end",
        default=None,
        help="Inclusive window end (ISO). Omit for full post-warmup series.",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max bars after window filter (omit for no cap)",
    )
    p.add_argument(
        "--format",
        dest="formats",
        default=None,
        help=(
            "Comma-separated: jsonl,csv,manifest,summary. "
            "Omit for fixed contract set (jsonl,manifest,summary)."
        ),
    )
    p.add_argument(
        "--artifact",
        default=None,
        help="Required for tradenet / rr_trained / envelope when runnable",
    )
    p.add_argument(
        "--emit",
        default=None,
        choices=("events", "all"),
        help="Required for crt_state_machine: events|all",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    from research.model_runners.contracts import list_models
    from research.model_runners.runner import RunRequest, run_model

    if args.list:
        print("Model catalog (OBSERVATION_ONLY):")
        for m in list_models():
            flag = "RUN" if m.runnable else "BLOCK"
            print(
                f"  [{flag}] {m.model_id:18} spine={m.spine_active} "
                f"status={m.audit_status}"
            )
            print(f"         {m.description}")
            print(f"         entry={m.entry_point}")
        return 0

    missing = [
        name
        for name, val in (
            ("--model", args.model),
            ("--csv", args.csv),
            ("--instrument", args.instrument),
            ("--out-dir", args.out_dir),
        )
        if not val
    ]
    if missing:
        parser.error(
            "scoring run requires "
            + ", ".join(missing)
            + " (or pass --list)"
        )

    req = RunRequest(
        model_id=args.model,
        csv_path=Path(args.csv),
        instrument=args.instrument,
        out_dir=Path(args.out_dir),
        repo_root=ROOT,
        config_path=Path(args.config_path) if args.config_path else None,
        start=args.start,
        end=args.end,
        limit=args.limit,
        formats=args.formats,
        artifact=Path(args.artifact) if args.artifact else None,
        emit=args.emit,
    )
    try:
        result = run_model(req)
    except (FileNotFoundError, KeyError, ValueError, RuntimeError, TypeError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    print(f"model={args.model} instrument={args.instrument}")
    print(f"run_id={result.run_id}")
    print(f"run_dir={result.run_dir}")
    print(f"n_ok={result.n_ok} n_error={result.n_error}")
    print(f"manifest={result.manifest_path}")
    print("authority=research_only PRODUCTION_BEHAVIOR_CHANGED=false")
    return 0 if result.n_error == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
