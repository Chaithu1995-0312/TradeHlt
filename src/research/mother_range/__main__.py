"""python -m research.mother_range --out results/mother_range/mc_mrange_xauusd_m15_v1"""
from __future__ import annotations

import argparse
from pathlib import Path

from research.mother_range.driver import CORPUS, run, write_report


def main() -> int:
    p = argparse.ArgumentParser(description="MC-MRANGE-XAUUSD-M15-V1 single-pass holdout")
    p.add_argument("--corpus", default=str(CORPUS))
    p.add_argument("--out", default="results/mother_range/mc_mrange_xauusd_m15_v1")
    args = p.parse_args()
    report = run(Path(args.corpus))
    write_report(report, Path(args.out))
    print(f"verdict={report['verdict']} holdout_n={report['holdout']['n']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
