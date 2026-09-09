#!/usr/bin/env python
"""
Fetch forex M15 OHLCV data via Yahoo Finance using CME futures.
Loops through date range in overlapping 55-day chunks to get full-year M15 data.

CME futures (REAL volume):
  AUDUSD -> 6A=F      GBPUSD -> 6B=F      USDJPY -> 6J=F (inverted)
  XAUUSD -> GC=F      EURCAD -> 6E=F / 6C=F (derived)

Output: data/yfinance/{INSTRUMENT}_M15.csv  + Excel export

Usage:
    python scripts/data/fetch_forex_yfinance.py --all
    python scripts/data/fetch_forex_yfinance.py --instrument AUDUSD --start 2025-05-22 --end 2026-05-22
    python scripts/data/fetch_forex_yfinance.py --all --append   # merge with existing CSVs
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
import yfinance as yf

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("fetch_forex_yfinance")

_INSTRUMENT_MAP: dict[str, tuple[str | tuple[str, str], bool, bool]] = {
    "AUDUSD": ("6A=F", False, False),
    "GBPUSD": ("6B=F", False, False),
    "USDJPY": ("6J=F", True, False),
    "XAUUSD": ("GC=F", False, False),
    "EURCAD": (("6E=F", "6C=F"), False, True),
}


def _flatten_cols(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    return df


def _download_chunk(ticker: str, chunk_start: str, chunk_end: str) -> pd.DataFrame:
    """Download one chunk of 15m data. Returns empty on failure."""
    for attempt in range(2):
        try:
            df = yf.download(
                ticker,
                start=chunk_start,
                end=chunk_end,
                interval="15m",
                progress=False,
                auto_adjust=False,
            )
            if df is not None and not df.empty:
                return _flatten_cols(df)
        except Exception as e:
            logger.warning("  chunk %s→%s attempt %d: %s", chunk_start, chunk_end, attempt + 1, e)
        _time.sleep(2)
    return pd.DataFrame()


def _generate_chunks(start: str, end: str, chunk_days: int = 55):
    """Generate overlapping chunk (start, end) date strings."""
    s = datetime.strptime(start, "%Y-%m-%d")
    e = datetime.strptime(end, "%Y-%m-%d")
    cur = s
    while cur < e:
        chunk_end = min(cur + timedelta(days=chunk_days), e)
        yield cur.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d")
        cur = chunk_end


def _download_1yr_full(ticker: str, start: str, end: str) -> pd.DataFrame:
    """
    Download full-year 15m data by iterating in overlapping 55-day chunks.
    Concatenates and deduplicates by index.
    """
    all_dfs: list[pd.DataFrame] = []
    for cs, ce in _generate_chunks(start, end):
        logger.info("  chunk %s → %s (%s)", cs, ce, ticker)
        df = _download_chunk(ticker, cs, ce)
        if not df.empty:
            all_dfs.append(df)
            logger.info("    got %d rows", len(df))
        else:
            logger.info("    empty (outside available range)")
        _time.sleep(1.0)

    if not all_dfs:
        return pd.DataFrame()

    combined = pd.concat(all_dfs)
    combined = combined[~combined.index.duplicated(keep="first")]
    combined.sort_index(inplace=True)
    return combined


def fetch_instrument(instrument: str, start_date: str, end_date: str, out_dir: Path,
                     append: bool = False) -> Optional[Path]:
    """Fetch one instrument's M15 data across full date range."""
    instrument = instrument.upper()
    if instrument not in _INSTRUMENT_MAP:
        logger.error("Unknown instrument: %s", instrument)
        return None

    info = _INSTRUMENT_MAP[instrument]
    ticker_info = info[0]
    is_inverse = info[1]
    is_derived = info[2]

    logger.info("=== %s (%s → %s) ===", instrument, start_date, end_date)

    if is_derived and isinstance(ticker_info, tuple):
        t1, t2 = ticker_info
        df_eur = _download_1yr_full(t1, start_date, end_date)
        df_cad = _download_1yr_full(t2, start_date, end_date)
        if df_eur.empty or df_cad.empty:
            logger.error("Failed EURCAD source data")
            return None
        out = pd.DataFrame(index=df_eur.index)
        out["Open"]   = df_eur["Open"]   / df_cad["Open"]
        out["High"]   = df_eur["High"]   / df_cad["Low"]
        out["Low"]    = df_eur["Low"]    / df_cad["High"]
        out["Close"]  = df_eur["Close"]  / df_cad["Close"]
        out["Volume"] = df_eur["Volume"].fillna(0)
    else:
        ticker = str(ticker_info)
        df = _download_1yr_full(ticker, start_date, end_date)
        if df.empty:
            logger.error("No data for %s via %s", instrument, ticker)
            return None
        out = df[["Open", "High", "Low", "Close", "Volume"]].copy()

    # Inverse pairs
    if is_inverse and not is_derived:
        logger.info("  inverting %s", instrument)
        for col in ["Open", "Close"]:
            out[col] = 1.0 / out[col]
        out["High"], out["Low"] = 1.0 / out["Low"], 1.0 / out["High"]

    # Build output DataFrame
    out.rename(columns={
        "Open": "open", "High": "high", "Low": "low",
        "Close": "close", "Volume": "volume",
    }, inplace=True)
    out["timestamp"] = out.index.strftime("%Y-%m-%d %H:%M:%S")
    out["volume"] = out["volume"].fillna(0).astype(int)
    for col in ["open", "high", "low", "close"]:
        out[col] = out[col].round(5)
    out = out[["timestamp", "open", "high", "low", "close", "volume"]]
    out = out.sort_values("timestamp").reset_index(drop=True)

    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"{instrument}_M15.csv"

    # Append mode: merge with existing CSV
    if append and csv_path.exists():
        existing = pd.read_csv(csv_path)
        combined = pd.concat([existing, out], ignore_index=True)
        combined.drop_duplicates(subset=["timestamp"], keep="last", inplace=True)
        combined.sort_values("timestamp", inplace=True)
        combined.reset_index(drop=True)
        out = combined
        logger.info("  merged with existing: %d total rows", len(out))

    out.to_csv(csv_path, index=False)
    logger.info("Wrote %d rows → %s (volume sum: %d)", len(out), csv_path, out["volume"].sum())
    return csv_path


def _to_excel() -> None:
    """Convert all CSVs in data/yfinance to Excel in data/."""
    src_dir = Path("data/yfinance")
    dst_dir = Path("data")
    dst_dir.mkdir(exist_ok=True)
    for csv_path in sorted(src_dir.glob("*_M15.csv")):
        instr = csv_path.stem.replace("_M15", "")
        df = pd.read_csv(csv_path)
        xlsx_path = dst_dir / f"{instr}_M15_1year.xlsx"
        df.to_excel(xlsx_path, index=False, sheet_name="M15")
        logger.info("Excel: %s (%d rows, vol=%d)", xlsx_path.name, len(df), df["volume"].sum())


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch forex M15 with real volume via yfinance CME futures")
    parser.add_argument("--instrument", type=str, help="AUDUSD, EURCAD, GBPUSD, USDJPY, XAUUSD")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--start", type=str, default=None, help="Start YYYY-MM-DD")
    parser.add_argument("--end", type=str, default=None, help="End YYYY-MM-DD")
    parser.add_argument("--out", type=str, default="data/yfinance")
    parser.add_argument("--append", action="store_true", help="Merge with existing CSVs instead of overwrite")
    args = parser.parse_args()

    end   = args.end   or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start = args.start or (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%d")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.all:
        instruments = list(_INSTRUMENT_MAP.keys())
    elif args.instrument:
        instruments = [args.instrument.upper()]
    else:
        print("Specify --instrument or --all")
        return 1

    success = 0
    for instr in instruments:
        path = fetch_instrument(instr, start, end, out_dir, append=args.append)
        if path:
            success += 1

    logger.info("Fetch done: %d/%d. Converting to Excel...", success, len(instruments))
    _to_excel()
    logger.info("All done.")
    return 0 if success == len(instruments) else 1


if __name__ == "__main__":
    raise SystemExit(main())