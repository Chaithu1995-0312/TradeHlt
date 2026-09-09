#!/usr/bin/env python
"""
Fetch 2+ years of crypto M15 OHLCV data via CCXT (Binance).
Has real exchange volume. Handles pagination (1000 candles per call max).

Output: data/yfinance/{PAIR}_M15.csv + Excel export

Usage:
    python scripts/data/fetch_crypto_ccxt.py --all
    python scripts/data/fetch_crypto_ccxt.py --instrument BTCUSDT --start 2024-05-22 --end 2026-05-22
"""

from __future__ import annotations

import argparse
import logging
import sys
import time as _time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("fetch_crypto_ccxt")

_INSTRUMENTS: dict[str, str] = {
    "BTCUSDT": "BTC/USDT",
    "ETHUSDT": "ETH/USDT",
    "SOLUSDT": "SOL/USDT",
    "BNBUSDT": "BNB/USDT",
    "XRPUSDT": "XRP/USDT",
    "DOGEUSDT": "DOGE/USDT",
}


def _ms_to_dt(ms: int) -> str:
    """Convert unix ms timestamp to ISO string."""
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def fetch_instrument(instrument: str, start_date: str, end_date: str,
                     out_dir: Path) -> Optional[Path]:
    """Fetch full historical M15 data for one crypto pair via CCXT."""
    instrument = instrument.upper()
    if instrument not in _INSTRUMENTS:
        logger.error("Unknown instrument: %s (supported: %s)", instrument, list(_INSTRUMENTS.keys()))
        return None

    import ccxt
    exchange = ccxt.binance({
        "enableRateLimit": True,
        "options": {"defaultType": "spot"},
    })

    symbol = _INSTRUMENTS[instrument]
    timeframe = "15m"
    limit = 1000  # max candles per request

    # Convert dates to ms timestamps
    start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)
    end_ts   = int(datetime.strptime(end_date,   "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)

    logger.info("=== %s (%s → %s) ===", instrument, start_date, end_date)

    all_ohlcv: list[list] = []
    since = start_ts
    total_calls = 0

    while since < end_ts:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
            total_calls += 1

            if not ohlcv:
                logger.info("  no more data at %s", _ms_to_dt(since))
                break

            all_ohlcv.extend(ohlcv)

            # Move `since` to last candle timestamp + 1ms
            last_ts = ohlcv[-1][0]
            since = last_ts + 1

            # Log progress every 10 chunks
            if total_calls % 10 == 0:
                progress = (last_ts - start_ts) / (end_ts - start_ts) * 100
                logger.info("  %d calls, %.0f%% complete, latest: %s",
                           total_calls, progress, _ms_to_dt(last_ts))

            # Rate limit: 1200 calls per minute on Binance, sleep 50ms
            _time.sleep(0.05)

        except Exception as e:
            logger.warning("  error at %s: %s — retrying in 5s", _ms_to_dt(since), e)
            _time.sleep(5)

    if not all_ohlcv:
        logger.error("No data fetched for %s", instrument)
        return None

    # Deduplicate by timestamp and sort
    seen: set[int] = set()
    unique: list[list] = []
    for row in all_ohlcv:
        ts = row[0]
        if ts not in seen:
            seen.add(ts)
            unique.append(row)
    unique.sort(key=lambda r: r[0])

    # Filter to exact range
    unique = [r for r in unique if start_ts <= r[0] < end_ts]

    # Build DataFrame
    df = pd.DataFrame(unique, columns=["timestamp_ms", "open", "high", "low", "close", "volume"])
    df["timestamp"] = df["timestamp_ms"].apply(_ms_to_dt)
    df = df[["timestamp", "open", "high", "low", "close", "volume"]]
    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].round(2)
    df["volume"] = df["volume"].round(4)

    df = df.sort_values("timestamp").reset_index(drop=True)

    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"{instrument}_M15.csv"
    df.to_csv(csv_path, index=False)
    logger.info("Wrote %d rows → %s (vol sum: %.2f, API calls: %d)",
               len(df), csv_path, df["volume"].sum(), total_calls)
    return csv_path


def _to_excel() -> None:
    """Convert all CSVs in data/yfinance to Excel in data/."""
    src_dir = Path("data/yfinance")
    dst_dir = Path("data")
    dst_dir.mkdir(exist_ok=True)
    for csv_path in sorted(src_dir.glob("*_M15.csv")):
        instr = csv_path.stem.replace("_M15", "")
        # Skip forex/yahoo files (already have Excel)
        if instr in _INSTRUMENTS:
            df = pd.read_csv(csv_path)
            xlsx_path = dst_dir / f"{instr}_M15_2year.xlsx"
            df.to_excel(xlsx_path, index=False, sheet_name="M15")
            logger.info("Excel: %s (%d rows, vol=%.2f)", xlsx_path.name, len(df), df["volume"].sum())


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch crypto M15 data via CCXT (Binance)")
    parser.add_argument("--instrument", type=str, help="BTCUSDT, ETHUSDT, SOLUSDT")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--start", type=str, default=None, help="Start YYYY-MM-DD")
    parser.add_argument("--end", type=str, default=None, help="End YYYY-MM-DD")
    parser.add_argument("--out", type=str, default="data/yfinance")
    args = parser.parse_args()

    end   = args.end   or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start = args.start or (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%d")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.all:
        instruments = list(_INSTRUMENTS.keys())
    elif args.instrument:
        instruments = [args.instrument.upper()]
    else:
        print("Specify --instrument or --all")
        return 1

    success = 0
    for instr in instruments:
        path = fetch_instrument(instr, start, end, out_dir)
        if path:
            success += 1

    logger.info("Fetch done: %d/%d. Converting to Excel...", success, len(instruments))
    _to_excel()
    logger.info("All done.")
    return 0 if success == len(instruments) else 1


if __name__ == "__main__":
    raise SystemExit(main())