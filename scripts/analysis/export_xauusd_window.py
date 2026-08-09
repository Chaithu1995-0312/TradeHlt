# -*- coding: utf-8 -*-
"""export_xauusd_window.py — export a trailing window of XAUUSD M15 candles to .xlsx.

Reads the ONLY approved XAUUSD load target — the Phase-1 frozen candidate
`data/mt5/XAUUSD_M15.csv` — resolved via guard_xauusd_csv_path, which fail-closes on
path/hash/row/range drift. This is deliberate: the extended root twin
(`data/XAUUSD_M15.csv`, 50,169 rows) is NOT the canonical corpus and must never be the
source of an export.

Output goes to results/ (gitignored), NEVER under data/ — a derived artifact written into
the frozen-corpus tree is the undeclared-substitution defect G-10 warns about
(docs/governance/CORPUS_AUTHORITY.md).

TRUST: the corpus is FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION. The exported sheet
inherits that status — NOT AUTHORITATIVE / VALIDATED / APPROVED / ECONOMICALLY_ADMISSIBLE.
Read-only w.r.t. the corpus: no config, spine, or ACTIVE_VERSION edits.

Usage:
  python scripts/analysis/export_xauusd_window.py                      # trailing 2 months
  python scripts/analysis/export_xauusd_window.py --months 6
  python scripts/analysis/export_xauusd_window.py --output-dir results/XAUUSD/exports
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from data_ingestion.xauusd_phase1_candidate import (  # noqa: E402
    PHASE1_SHA256, PHASE1_STATUS, guard_xauusd_csv_path,
)
from utils.console_safe import safe_print  # noqa: E402

INSTRUMENT = "XAUUSD"
TIMEFRAME = "M15"
DEFAULT_MONTHS = 2
DEFAULT_OUTPUT_DIR = "results/XAUUSD/exports"


def _guarded_csv() -> str:
    """The ONLY approved XAUUSD load — the frozen candidate (NOT the root/glob)."""
    return guard_xauusd_csv_path("data/XAUUSD_M15.csv", INSTRUMENT)


def _out_name(fmt: str, first_ts, last_ts) -> str:
    """Filename for the export. The two formats deliberately use DIFFERENT shapes.

    xlsx (human-readable copy):  XAUUSD_M15_<first>_to_<last>.xlsx
    csv  (machine/backtest):     XAUUSD_W<first>-to-<last>.csv

    The csv name is constrained by two independent consumers and must satisfy both:

    * `is_xauusd_m15_request` (xauusd_phase1_candidate.py:200) rewrites any XAUUSD M15
      request to the frozen corpus. It matches a `XAUUSD_M15` filename prefix AND,
      separately, `instrument="XAUUSD"` + `"M15"` anywhere in the name. A csv named the
      xlsx way would be silently swapped for the full 47,275-row corpus, so the csv name
      carries NO `M15` token. This bypass is deliberate and declared (the file is a
      verified tail slice of the frozen corpus) — see the SF-001 findings entry.
    * `_parse_symbol_tf` (dataset_integrity.py:456) does `stem.rsplit("_", 1)`, so the
      text before the LAST underscore must be exactly `XAUUSD`. CORRECTED 2026-07-18:
      the earlier reason given here ("else the L2 gate misdetects the market class and
      applies the wrong session calendar") was WRONG for gold -- `classify_market`
      (:114) only tests for a crypto quote suffix (USDT/USDC/BUSD), so a garbled XAUUSD
      symbol still resolves to WEEKDAY. The real enforcement is
      `_check_path_consistency` (:516): `instrument.upper() != symbol.upper()` is a HARD
      failure -> REJECT, and backtest_v2 exits 1 on a rejected dataset. (The
      wrong-calendar failure mode is real, but only for CRYPTO symbols, where garbling
      breaks the USDT suffix test.) The unparseable TF token falls back to
      `default_bar_minutes: 15`, which matches the real modal delta, so the
      timeframe-consistency check still passes.

    NOTE the L2 gate ALSO requires the file to live under a canonical data root
    (`roots: ['data']`, :506) -- an export written under `results/` is REJECTED before
    any candle is read. See the `--for-backtest` flag.
    """
    if fmt == "csv":
        return f"{INSTRUMENT}_W{first_ts.date()}-to-{last_ts.date()}.csv"
    return f"{INSTRUMENT}_{TIMEFRAME}_{first_ts.date()}_to_{last_ts.date()}.xlsx"


def export_window(months: int, output_dir: Path, fmt: str = "xlsx") -> list[Path]:
    """Slice the trailing *months* of the frozen candidate and write it out.

    Returns the written paths. The filename carries the ACTUAL first/last dates present
    in the slice, not the requested cutoff — gold has weekend/holiday gaps, so the two
    differ and the data bounds are what a reader needs.
    """
    csv_path = _guarded_csv()
    df = pd.read_csv(csv_path, parse_dates=["timestamp"])

    last_ts = df["timestamp"].max()
    cutoff = last_ts - pd.DateOffset(months=months)
    window = df[df["timestamp"] >= cutoff].reset_index(drop=True)
    if window.empty:
        raise SystemExit(f"empty window: no rows at/after {cutoff} (corpus ends {last_ts})")

    first_ts = window["timestamp"].min()
    out_dir = output_dir if output_dir.is_absolute() else _ROOT / output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for one_fmt in (("xlsx", "csv") if fmt == "both" else (fmt,)):
        out_path = out_dir / _out_name(one_fmt, first_ts, last_ts)
        if one_fmt == "csv":
            window.to_csv(out_path, index=False)
        else:
            window.to_excel(out_path, index=False)
        written.append(out_path)

    safe_print(f"source      : {Path(csv_path).as_posix()}")
    safe_print(f"parent sha  : {PHASE1_SHA256}")
    safe_print(f"corpus rows : {len(df)}  ({df['timestamp'].min()} -> {last_ts})")
    safe_print(f"window      : trailing {months} month(s), cutoff {cutoff}")
    safe_print(f"exported    : {len(window)} rows  ({first_ts} -> {last_ts})")
    for p in written:
        safe_print(f"output      : {p.relative_to(_ROOT).as_posix()}")
    safe_print(
        f"STATUS      : {PHASE1_STATUS} - NOT AUTHORITATIVE / NOT VALIDATED / "
        "NOT APPROVED / NOT ECONOMICALLY_ADMISSIBLE"
    )
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--months", type=int, default=DEFAULT_MONTHS,
        help=f"trailing window length in calendar months (default: {DEFAULT_MONTHS})",
    )
    ap.add_argument(
        "--output-dir", type=Path, default=Path(DEFAULT_OUTPUT_DIR),
        help=f"destination directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    ap.add_argument(
        "--format", choices=("xlsx", "csv", "both"), default="xlsx",
        help="output format; csv is the backtest-ingestible one (default: xlsx)",
    )
    args = ap.parse_args()
    if args.months < 1:
        raise SystemExit("--months must be >= 1")
    export_window(args.months, args.output_dir, args.format)


if __name__ == "__main__":
    main()
