#!/usr/bin/env python
"""
CLI: Fetch historical OHLCV candles via hummingbot and write Tradelatest CSVs.

Reads defaults from the 'hummingbot_data' section of the production config;
CLI flags override any config value.

Usage examples
--------------
# Fetch BTCUSDT 15m candles for 2024 from Binance:
    python scripts/data/fetch_candles_hummingbot.py \\
        --start 2024-01-01 --end 2024-12-31

# Override exchange and pair:
    python scripts/data/fetch_candles_hummingbot.py \\
        --exchange bybit --pair ETHUSDT --interval 1h \\
        --start 2025-01-01 --end 2025-06-01 \\
        --out data/hummingbot

# Fetch all instruments listed in config:
    python scripts/data/fetch_candles_hummingbot.py \\
        --start 2024-01-01 --end 2025-01-01 --all-instruments
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

# ── Internal imports (business logic lives in src/, never here) ──────────────
from inout.hummingbot_candle_fetcher import (  # type: ignore
    HummingbotCandleFetcher,
    HummingbotFetcherConfig,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch historical OHLCV candles via hummingbot -> Tradelatest CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--exchange", default=None, help="Exchange connector name (e.g. binance, bybit, okx)")
    parser.add_argument("--pair", default=None, metavar="PAIR", help="Trading pair (e.g. BTCUSDT, ETHUSDT)")
    parser.add_argument("--interval", default=None, help="Candle interval: 1m 3m 5m 15m 30m 1h 4h 1d (default: 15m)")
    parser.add_argument("--start", required=True, metavar="YYYY-MM-DD", help="Start date (UTC, inclusive)")
    parser.add_argument("--end", required=True, metavar="YYYY-MM-DD", help="End date (UTC, exclusive)")
    parser.add_argument("--out", default=None, metavar="DIR", help="Output directory (default: data/hummingbot)")
    parser.add_argument("--all-instruments", action="store_true", help="Fetch all instruments listed in config")
    parser.add_argument(
        "--config",
        default="configs/production/v1_multi_2026_03.json",
        metavar="PATH",
        help="Path to production config JSON",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"ERROR: config not found: {config_path}", file=sys.stderr)
        return 1

    with open(config_path, encoding="utf-8") as fh:
        prod_cfg = json.load(fh)

    # Build hummingbot_data section from config, then apply CLI overrides
    hb_section: dict = dict(prod_cfg.get("hummingbot_data", {}))
    if args.exchange:  hb_section["exchange"]      = args.exchange
    if args.pair:      hb_section["trading_pair"]  = args.pair
    if args.interval:  hb_section["interval"]       = args.interval
    if args.out:       hb_section["output_dir"]     = args.out

    # start/end are always required CLI args
    hb_section["start_date"] = args.start
    hb_section["end_date"]   = args.end

    try:
        cfg = HummingbotFetcherConfig.from_section(hb_section)
        fetcher = HummingbotCandleFetcher(cfg)
    except (KeyError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.all_instruments:
        paths = fetcher.fetch_all_instruments()
        for p in paths:
            print(f"  wrote -> {p}")
        return 0

    try:
        path = fetcher.fetch()
        print(f"  wrote -> {path}")
        return 0
    except Exception as exc:
        print(f"ERROR: fetch failed — {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
