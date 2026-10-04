"""python -m research.sujan_crt --out docs/research-readiness/sujan_crt/mc_sujan_xauusd_m15_v1"""
from __future__ import annotations

import argparse
from pathlib import Path

from research.sujan_crt.driver import CORPUS, run, write_report


def main() -> int:
    p = argparse.ArgumentParser(description="MC-SUJAN-XAUUSD-M15-V1 SEM-031 funnel measurement")
    p.add_argument("--corpus", default=str(CORPUS))
    p.add_argument("--out", default="docs/research-readiness/sujan_crt/mc_sujan_xauusd_m15_v1")
    args = p.parse_args()
    report = run(Path(args.corpus))
    write_report(report, Path(args.out))
    print(
        f"verdict={report['verdict']} holdout_n={report['holdout']['n']} "
        f"detected={report['detected_funnel']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
