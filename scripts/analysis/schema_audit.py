"""
schema_audit.py
==============
Quick audit for schema consistency across outputs:
  - trade CSVs (schema_name/version)

Usage:
  py schema_audit.py --root results
  py schema_audit.py --csv results/batch/AUDUSD_M15/AUDUSD_M15_trades.csv
"""

from __future__ import annotations

import argparse
import csv
import os
from typing import Optional

from features.feature_schema import SCHEMA_VERSION


def _read_csv_schema(csv_path: str) -> tuple[Optional[str], Optional[str]]:
    try:
        with open(csv_path, "r", newline="") as f:
            reader = csv.DictReader(f)
            first = next(reader, None)
            if not first:
                return None, None
            return first.get("schema_name"), first.get("schema_version")
    except Exception:
        return None, None


def _audit_csvs(root: str) -> None:
    print(f"\n[CSV] Scanning {root} ...")
    count = 0
    mism = 0
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if not fn.endswith("_trades.csv"):
                continue
            path = os.path.join(dirpath, fn)
            name, ver = _read_csv_schema(path)
            count += 1
            ok = (name == "trade_record" and ver == SCHEMA_VERSION)
            if not ok:
                mism += 1
                print(f"  FAIL {path} schema_name={name} schema_version={ver}")
    if count == 0:
        print("  No trades CSVs found.")
    elif mism == 0:
        print(f"  PASS {count} CSVs (schema_name=trade_record, version={SCHEMA_VERSION})")
    else:
        print(f"  FAIL {mism}/{count} CSVs mismatched")


def main() -> None:
    ap = argparse.ArgumentParser(description="Audit schema consistency across outputs")
    ap.add_argument("--root", help="Root to scan for *_trades.csv")
    ap.add_argument("--csv", help="Single trades CSV to check")
    args = ap.parse_args()

    if args.root:
        _audit_csvs(args.root)
    if args.csv:
        name, ver = _read_csv_schema(args.csv)
        print(f"\n[CSV] {args.csv}")
        print(f"  schema_name={name} schema_version={ver}")
        if name == "trade_record" and ver == SCHEMA_VERSION:
            print("  PASS")
        else:
            print("  FAIL")

    if not any([args.root, args.csv]):
        ap.print_help()


if __name__ == "__main__":
    main()