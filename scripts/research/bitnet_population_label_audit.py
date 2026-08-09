"""
bitnet_population_label_audit.py
================================
CLI: class balance after every CONTRACT-C preprocessing stage, multi-dataset.

Read-only. Does NOT modify CONTRACT-C.

Examples
--------
  python scripts/research/bitnet_population_label_audit.py \\
    --csv data/XAUUSD_W2026-02-23-to-2026-05-21.csv \\
    --csv data/XAUUSD_W2026-03-23-to-2026-05-21.csv \\
    --csv data/BNBUSDT_M15.csv --max-files-note
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from bitnet.population_label_audit import (  # noqa: E402
    AuditConfig,
    audit_many,
    write_audit_report,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Population/label balance audit (read-only; no CONTRACT-C change)"
    )
    p.add_argument("--csv", action="append", default=[], help="OHLCV CSV (repeatable)")
    p.add_argument(
        "--xauusd-windows",
        action="store_true",
        help="Include all data/XAUUSD_W*.csv",
    )
    p.add_argument(
        "--label-contract",
        default="BITNET_LABEL_ATR_RACE_BULL_V1",
    )
    p.add_argument("--warmup", type=int, default=60)
    p.add_argument("--retest-min", type=float, default=0.05)
    p.add_argument("--holdout-fraction", type=float, default=0.25)
    p.add_argument("--no-bearish-mirror", action="store_true")
    p.add_argument(
        "--out",
        default=None,
        help="Output JSON path (default results/bitnet/audit/population_label_*.json)",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    paths = list(args.csv)
    if args.xauusd_windows:
        paths.extend(sorted(str(p) for p in Path("data").glob("XAUUSD_W*.csv")))
    # de-dupe preserve order
    seen = set()
    uniq = []
    for pth in paths:
        if pth not in seen:
            seen.add(pth)
            uniq.append(pth)
    if not uniq:
        p.error("Provide --csv and/or --xauusd-windows")

    cfg = AuditConfig(
        label_contract_id=args.label_contract,
        warmup=args.warmup,
        bar_filter_min_retest_depth=args.retest_min,
        holdout_fraction=args.holdout_fraction,
        include_bearish_mirror_diagnostic=not args.no_bearish_mirror,
    )
    report = audit_many(uniq, cfg)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.out or f"results/bitnet/audit/population_label_{ts}.json"
    path = write_audit_report(report, out)

    print(f"protocol: {report['protocol_id']}")
    print(f"label_contract: {report['label_contract_id']}")
    print(f"report: {path}")
    print(f"markdown: {Path(path).with_suffix('.md')}")
    print()
    print("S5 (final labeled) by file:")
    for row in report["cross_dataset_S5_summary"]:
        if row.get("error"):
            print(f"  ERR {row['path']}: {row['error']}")
            continue
        print(
            f"  {Path(row['path']).name}: n={row['n_S5']} "
            f"pos={row['n_pos']} neg={row['n_neg']} "
            f"pos_rate={row['pos_rate']:.4f} "
            f"majority={row['majority_rate']:.4f} "
            f"flags={row['flags']}"
        )
    pooled = report.get("pooled_S5") or {}
    if pooled:
        print(
            f"\nPooled S5: n={pooled.get('n_labeled')} "
            f"pos_rate={pooled.get('pos_rate')} "
            f"majority_rate={pooled.get('majority_rate')}"
        )
    print("\n" + report["authority"])
    print(report["recommendation_hint"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
