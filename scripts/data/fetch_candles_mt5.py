#!/usr/bin/env python
"""
CLI: Fetch historical OHLCV candles from a running MetaTrader 5 terminal -> Tradelatest CSV.

Thin wrapper — all logic lives in src/inout/mt5_candle_fetcher.py.

Requirements
------------
  * pip install MetaTrader5
  * The MetaTrader 5 desktop terminal RUNNING and LOGGED IN (free demo is fine).

Usage examples
--------------
# Fetch EURUSD 15min for 2 years (canonical file data/EURUSD_M15.csv):
    python scripts/data/fetch_candles_mt5.py \\
        --pair EURUSD --start 2024-05-01 --end 2026-05-01 --out data

# Gold, where the broker names the symbol "GOLD" but we want data/XAUUSD_M15.csv:
    python scripts/data/fetch_candles_mt5.py \\
        --pair XAUUSD --symbol GOLD --start 2024-05-01 --end 2026-05-01 --out data
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# ── Path bootstrap ─────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve()
_ROOT = _HERE.parent.parent.parent
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

# ── Internal imports (business logic lives in src/, never here) ─────────────
from inout.mt5_candle_fetcher import (  # type: ignore
    MT5CandleFetcher,
    MT5FetcherConfig,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch historical OHLCV candles from MetaTrader 5 -> Tradelatest CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--pair", required=True, metavar="PAIR",
        help="Canonical pair / output stem, e.g. EURUSD, XAUUSD (file is {PAIR}_{TF}.csv).",
    )
    parser.add_argument(
        "--symbol", default=None, metavar="SYM",
        help="Broker symbol name if it differs from --pair (e.g. GOLD for XAUUSD). "
             "Defaults to --pair.",
    )
    parser.add_argument(
        "--timeframe", default="M15",
        help="Candle timeframe: M1 M5 M15 M30 H1 H4 D1 (default: M15).",
    )
    parser.add_argument("--start", required=True, metavar="YYYY-MM-DD", help="Start date (UTC, inclusive)")
    parser.add_argument("--end",   required=True, metavar="YYYY-MM-DD", help="End date (UTC, exclusive)")
    parser.add_argument("--out", default="data", metavar="DIR", help="Output directory (default: data)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])

    pair = args.pair.upper().replace("/", "")
    section = {
        "symbol":     (args.symbol or pair).upper(),
        "timeframe":  args.timeframe.upper(),
        "start_date": args.start,
        "end_date":   args.end,
        "output_dir": args.out,
        "out_name":   pair,   # canonical filename stem, independent of broker symbol
    }

    try:
        cfg = MT5FetcherConfig.from_section(section)
        fetcher = MT5CandleFetcher(cfg)
        path = fetcher.fetch()
        print(f"  wrote -> {path}")
        return 0
    except (KeyError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
