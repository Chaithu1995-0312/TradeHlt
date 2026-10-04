"""SEM-033 Phase-1 CLI. Two modes, deliberately separate.

Detect (the original path) — parents must already exist:

    python -m research.sujan_manipulation detect \
        --corpus data/mt5/XAUUSD_M15.csv --parents confirmed_parents.json

Shortlist candidates under the SEM-034 proxy, for you to confirm:

    python -m research.sujan_manipulation candidates \
        --corpus data/mt5/XAUUSD_M15.csv --top-n 50 --verify-parquet

`candidates` does not detect and `detect` does not select. A candidate is not a parent
until the human bridge confirms it on the rendered page.

Phase 1 is DETECTION ONLY. Both modes print counts; a count is an observation, not a result.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from research.sujan_manipulation.bulk_proxy import FROZEN_TOP_N, PROXY_ID, PROXY_STATUS
from research.sujan_manipulation.driver import (
    CORPUS,
    DEFAULT_CLEAN_LABELS,
    run,
    run_candidates,
    write_candidates,
    write_report,
)


def _detect(args: argparse.Namespace) -> int:
    report = run(
        Path(args.corpus),
        Path(args.parents),
        instrument=args.instrument,
        preflight=not args.no_preflight,
    )
    write_report(report, Path(args.out))
    print(
        f"object={report['object']} parents={report['parents']['n_supplied']} "
        f"alerts={report['n_alerts']} "
        f"bulk_candle_selector={report['bulk_candle_selector']['status']} "
        f"economic_claims_allowed={report['economic_claims_allowed']}"
    )
    return 0


def _candidates(args: argparse.Namespace) -> int:
    report = run_candidates(
        Path(args.corpus),
        top_n=args.top_n,
        instrument=args.instrument,
        preflight=not args.no_preflight,
        verify_parquet=args.verify_parquet,
        parquet_source=Path(args.parquet_source),
    )
    out = Path(args.out)
    write_candidates(report, out)
    counts = " ".join(
        f"{k}={len(v)}" for k, v in sorted(report["candidates"].items())
    )
    print(
        f"proxy={PROXY_ID}({PROXY_STATUS}) top_n={args.top_n} {counts} "
        f"overlap={report['overlap']['count']} "
        f"parquet_cross_check={report['parquet_cross_check']['status']} "
        f"economic_claims_allowed={report['economic_claims_allowed']}"
    )
    print(f"confirm candidates in: {(out / 'candidates.html').as_posix()}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        description="SUJAN_MANIPULATION_RESEARCH_PHASE_1 (SEM-033)"
    )
    sub = p.add_subparsers(dest="mode", required=True)

    d = sub.add_parser("detect", help="detect manipulation against supplied parents")
    d.add_argument("--corpus", default=str(CORPUS))
    d.add_argument(
        "--parents",
        required=True,
        help="externally supplied or bridge-confirmed parent bulk-candle timestamps",
    )
    d.add_argument("--instrument", default=None)
    d.add_argument("--out", default="docs/research-readiness/sujan_manipulation/phase1")
    d.add_argument("--no-preflight", action="store_true")
    d.set_defaults(func=_detect)

    c = sub.add_parser("candidates", help="shortlist bulk-candle candidates (SEM-034 proxy)")
    c.add_argument("--corpus", default=str(CORPUS))
    c.add_argument(
        "--top-n",
        type=int,
        default=FROZEN_TOP_N,
        help=f"candidates per ranking; {FROZEN_TOP_N} is the bridge-frozen value "
        "(drift log Record 6)",
    )
    c.add_argument("--instrument", default=None)
    c.add_argument("--out", default="docs/research-readiness/sujan_manipulation/candidates")
    c.add_argument("--no-preflight", action="store_true")
    c.add_argument(
        "--verify-parquet",
        action="store_true",
        help="cross-check magnitudes against the Parquet projection; needs a venv "
        "interpreter (pyarrow). Fails closed rather than degrading silently.",
    )
    c.add_argument("--parquet-source", default=str(DEFAULT_CLEAN_LABELS))
    c.set_defaults(func=_candidates)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
