#!/usr/bin/env python
"""
CLI: Fetch Binance perp funding-rate + premium-index (basis) history -> CSV.

Pure acquisition layer to unblock the carry/basis research axis. Reads defaults
from the 'perp_funding_data' section of the active production config; CLI flags
override. Writes data/perp/{SYMBOL}_FUNDING_8H.csv + {SYMBOL}_BASIS_M15.csv,
time-aligned (UTC) to the existing spot OHLCV in data/.

Business logic lives in src/inout/perp_funding_fetcher.py — this is a thin wrapper.

Usage examples
--------------
# All configured instruments, full 2-year spot window:
    python scripts/data/fetch_perp_funding.py --all --start 2024-05-22 --end 2026-05-22

# One instrument, funding only:
    python scripts/data/fetch_perp_funding.py --instrument BNBUSDT \\
        --start 2024-05-22 --end 2026-05-22 --signals funding

Public Binance fapi — no API key required. Open interest is NOT fetched
(public history is ~30-day retention only; funding/basis have full history).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# ── Path bootstrap ─────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve()
_ROOT = _HERE.parent.parent.parent
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

# ── Internal imports (business logic lives in src/, never here) ─────────────
from inout.perp_funding_fetcher import (  # type: ignore
    PerpFetcherConfig,
    PerpFundingFetcher,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

_DEFAULT_CONFIG = "configs/production/v2_multi_2026_04.json"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch Binance perp funding + basis history -> CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--instrument", default=None, help="Single symbol, e.g. BNBUSDT")
    parser.add_argument("--all", action="store_true", help="Fetch every configured instrument")
    parser.add_argument("--start", required=True, metavar="YYYY-MM-DD", help="Start date (UTC, inclusive)")
    parser.add_argument("--end", required=True, metavar="YYYY-MM-DD", help="End date (UTC, exclusive)")
    parser.add_argument(
        "--signals", default="funding,basis",
        help="Comma-separated subset of {funding,basis} (default: funding,basis)",
    )
    parser.add_argument("--out", default=None, metavar="DIR", help="Output directory (default: config out_dir)")
    parser.add_argument("--config", default=_DEFAULT_CONFIG, metavar="PATH", help="Path to production config JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"ERROR: config not found: {config_path}", file=sys.stderr)
        return 1

    with open(config_path, encoding="utf-8") as fh:
        prod_cfg = json.load(fh)

    section: dict = dict(prod_cfg.get("perp_funding_data", {}))
    if not section:
        print(
            "ERROR: 'perp_funding_data' section missing from config. "
            "Add it to the active production config.",
            file=sys.stderr,
        )
        return 1

    if args.out:
        section["out_dir"] = args.out

    signals = tuple(s.strip().lower() for s in args.signals.split(",") if s.strip())

    try:
        cfg = PerpFetcherConfig.from_section(section)
        fetcher = PerpFundingFetcher(cfg)
    except (KeyError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.all:
        instruments = list(cfg.instruments)
    elif args.instrument:
        instruments = [args.instrument.upper()]
    else:
        print("ERROR: specify --instrument SYMBOL or --all", file=sys.stderr)
        return 1

    success = 0
    for instr in instruments:
        try:
            paths = fetcher.fetch(instr, args.start, args.end, signals)
            for sig, path in paths.items():
                print(f"  {instr} {sig} -> {path}")
            success += 1
        except Exception as exc:  # noqa: BLE001 - report-and-continue per instrument
            print(f"ERROR: {instr} fetch failed — {exc}", file=sys.stderr)

    print(f"Done: {success}/{len(instruments)} instrument(s) fetched.")
    return 0 if success == len(instruments) else 1


if __name__ == "__main__":
    raise SystemExit(main())
