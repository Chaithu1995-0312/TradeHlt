"""python -m research.evidence --out results/research/parquet_evidence_layer"""
from __future__ import annotations

import argparse
from pathlib import Path

from research.evidence.driver import DEFAULT_OUT, DriverConfig, run, write_report


def main() -> int:
    p = argparse.ArgumentParser(
        description="Query the XAUUSD parquet projections as an evidence layer (not a dataset)."
    )
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--question", default=None, help="Optional research question to route.")
    p.add_argument(
        "--atlas",
        choices=("leakage", "state_value", "asymmetry"),
        default=None,
        help="Run one atlas only.",
    )
    p.add_argument("--max-rows", type=int, default=None, help="Debug cap; omit for the full corpus.")
    args = p.parse_args()
    cfg = DriverConfig(
        out_dir=Path(args.out),
        question=args.question,
        atlas=args.atlas,
        max_rows=args.max_rows,
    )
    report = run(cfg)
    path = write_report(report, cfg.out_dir)
    print(
        f"records={report['n_records']} loaded={report['loaded_n']} "
        f"route={report['route']} wrote={path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
