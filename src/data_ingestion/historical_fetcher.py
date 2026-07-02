"""
historical_fetcher.py
================================================================================
Multi-pair OHLCV data ingestion into TimescaleDB.

Priority chain (per pair, per timeframe):
  1. TimescaleDB (local) — serve existing rows, fetch only the missing range.
  2. MT5 Python API       — fetch if connected and mt5_enabled=true.
  3. CSV fallback         — read {pair}_{timeframe}.csv from csv_fallback_dir.

Config section: "data_ingestion" in production JSON.

TimescaleDB setup (run once):
    CREATE DATABASE tradelatest;
    -- connect tradelatest
    CREATE EXTENSION IF NOT EXISTS timescaledb;
    CREATE TABLE ohlcv_data (
        ts         TIMESTAMPTZ   NOT NULL,
        pair       TEXT          NOT NULL,
        timeframe  TEXT          NOT NULL,
        open       DOUBLE PRECISION NOT NULL,
        high       DOUBLE PRECISION NOT NULL,
        low        DOUBLE PRECISION NOT NULL,
        close      DOUBLE PRECISION NOT NULL,
        volume     DOUBLE PRECISION NOT NULL
    );
    SELECT create_hypertable('ohlcv_data', 'ts');
    CREATE UNIQUE INDEX ON ohlcv_data (ts, pair, timeframe);
================================================================================
"""

from __future__ import annotations

import csv
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

# ── Path bootstrap ────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config_layer.production_config import get_prod_section  # type: ignore
from data_ingestion.ohlcv_schema import (  # type: ignore
    require_ohlcv_columns, resolve_ohlcv_headers, validate_ohlcv_row,
)
from utils.logging_config import get_flow_logger             # type: ignore

logger = get_flow_logger("DATA_INGESTION")

# ── Optional deps ─────────────────────────────────────────────────────────────

try:
    import psycopg2
    import psycopg2.extras
    _PSYCOPG2_AVAILABLE = True
except ImportError:
    psycopg2 = None  # type: ignore
    _PSYCOPG2_AVAILABLE = False
    logger.warning("psycopg2 not installed — TimescaleDB unavailable. pip install psycopg2-binary")

try:
    import pandas as pd
    _PANDAS_AVAILABLE = True
except ImportError:
    pd = None  # type: ignore
    _PANDAS_AVAILABLE = False
    logger.warning("pandas not installed — data loading will be limited.")

try:
    import MetaTrader5 as mt5
    _MT5_AVAILABLE = True
except ImportError:
    mt5 = None  # type: ignore
    _MT5_AVAILABLE = False

# ── Config load ───────────────────────────────────────────────────────────────

def _load_ingestion_cfg() -> dict:
    cfg = get_prod_section("data_ingestion")
    if not cfg:
        raise RuntimeError(
            "data_ingestion section missing from production config. "
            "Add it to configs/production/v1_multi_2026_03.json."
        )
    return cfg


def _require(cfg: dict, key: str) -> object:
    if key not in cfg:
        raise KeyError(f"Required key '{key}' missing from data_ingestion config.")
    return cfg[key]


_CFG = _load_ingestion_cfg()

_DB_URL:          str   = str(_require(_CFG, "db_url"))
_SCHEMA:          str   = str(_require(_CFG, "schema"))
_TABLE:           str   = str(_require(_CFG, "ohlcv_table"))
_PAIRS:           list  = list(_require(_CFG, "pairs"))
_TIMEFRAMES:      list  = list(_require(_CFG, "timeframes"))
_MT5_ENABLED:     bool  = bool(_require(_CFG, "mt5_enabled"))
_CSV_DIR:         Path  = Path(str(_require(_CFG, "csv_fallback_dir")))
_BATCH_SIZE:      int   = int(_require(_CFG, "batch_size"))
_CONN_TIMEOUT:    int   = int(_require(_CFG, "connection_timeout_sec"))

# MT5 timeframe string → API constant mapping (populated if MT5 available)
_MT5_TF_MAP: Dict[str, int] = {}
if _MT5_AVAILABLE and mt5 is not None:
    _MT5_TF_MAP = {
        "M1":  mt5.TIMEFRAME_M1,
        "M5":  mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "H1":  mt5.TIMEFRAME_H1,
        "H4":  mt5.TIMEFRAME_H4,
        "D1":  mt5.TIMEFRAME_D1,
    }


# ============================================================================
# OHLCV ROW
# ============================================================================

class OHLCVRow:
    """Lightweight immutable OHLCV record — avoids pandas dependency in hot path."""

    __slots__ = ("ts", "pair", "timeframe", "open", "high", "low", "close", "volume")

    def __init__(
        self,
        ts:        datetime,
        pair:      str,
        timeframe: str,
        open:      float,
        high:      float,
        low:       float,
        close:     float,
        volume:    float,
    ) -> None:
        self.ts        = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        self.pair      = pair.upper()
        self.timeframe = timeframe.upper()
        self.open      = float(open)
        self.high      = float(high)
        self.low       = float(low)
        self.close     = float(close)
        self.volume    = float(volume)

    def to_tuple(self) -> tuple:
        return (
            self.ts, self.pair, self.timeframe,
            self.open, self.high, self.low, self.close, self.volume,
        )

    def __repr__(self) -> str:
        return (
            f"OHLCVRow({self.pair} {self.timeframe} "
            f"{self.ts.isoformat()} O={self.open} H={self.high} "
            f"L={self.low} C={self.close} V={self.volume})"
        )


# ============================================================================
# DB CONNECTION
# ============================================================================

class _DBConnection:
    """Thin wrapper around psycopg2 connection with context-manager support."""

    def __init__(self, db_url: str, connect_timeout: int) -> None:
        if not _PSYCOPG2_AVAILABLE:
            raise RuntimeError(
                "psycopg2 not available. Install with: pip install psycopg2-binary"
            )
        self._url     = db_url
        self._timeout = connect_timeout
        self._conn    = None

    def __enter__(self):
        self._conn = psycopg2.connect(
            self._url,
            connect_timeout=self._timeout,
        )
        return self._conn

    def __exit__(self, *args):
        if self._conn and not self._conn.closed:
            self._conn.close()


# ============================================================================
# HISTORICAL FETCHER
# ============================================================================

class HistoricalFetcher:
    """
    Multi-pair OHLCV data ingestion with TimescaleDB storage.

    Typical usage
    -------------
        fetcher = HistoricalFetcher()

        # Load 5 years of EUR/USD H1 into DB
        count = fetcher.fetch_and_store(
            pair="EURUSD", timeframe="H1",
            start="2020-01-01", end="2025-01-01",
        )

        # Query back for backtesting
        rows = fetcher.load(pair="EURUSD", timeframe="H1",
                            start="2023-01-01", end="2024-01-01")
    """

    def __init__(self, config: Optional[dict] = None) -> None:
        self._cfg     = config or _CFG
        self._db_url  = self._cfg.get("db_url", _DB_URL)
        self._table   = f'{self._cfg.get("schema", _SCHEMA)}.{self._cfg.get("ohlcv_table", _TABLE)}'
        self._batch   = int(self._cfg.get("batch_size", _BATCH_SIZE))
        self._timeout = int(self._cfg.get("connection_timeout_sec", _CONN_TIMEOUT))
        self._csv_dir = Path(self._cfg.get("csv_fallback_dir", str(_CSV_DIR)))

    # ── Public API ────────────────────────────────────────────────────────────

    def fetch_and_store(
        self,
        pair:      str,
        timeframe: str,
        start:     str,
        end:       str,
    ) -> int:
        """
        Fetch OHLCV data for the given range and store it in TimescaleDB.

        Data is only fetched for the gap between what is already stored and
        the requested range (incremental / no-duplicate strategy).

        Returns the number of new rows inserted.
        """
        pair      = pair.upper()
        timeframe = timeframe.upper()

        start_dt = _parse_date(start)
        end_dt   = _parse_date(end)

        stored_start, stored_end = self._stored_range(pair, timeframe)

        # Determine missing ranges (before stored and after stored)
        ranges_to_fetch: List[Tuple[datetime, datetime]] = []
        if stored_start is None:
            ranges_to_fetch.append((start_dt, end_dt))
        else:
            if start_dt < stored_start:
                ranges_to_fetch.append((start_dt, stored_start))
            if end_dt > stored_end:
                ranges_to_fetch.append((stored_end, end_dt))

        if not ranges_to_fetch:
            logger.info(
                "%s %s: already have %s→%s, nothing to fetch.",
                pair, timeframe, start, end,
            )
            return 0

        total_inserted = 0
        for fetch_start, fetch_end in ranges_to_fetch:
            rows = self._fetch_rows(pair, timeframe, fetch_start, fetch_end)
            if rows:
                inserted = self._insert_rows(rows)
                total_inserted += inserted
                logger.info(
                    "%s %s: inserted %d rows (%s → %s)",
                    pair, timeframe, inserted,
                    fetch_start.date(), fetch_end.date(),
                )
            else:
                logger.warning(
                    "%s %s: no data returned for %s → %s",
                    pair, timeframe, fetch_start.date(), fetch_end.date(),
                )

        return total_inserted

    def load(
        self,
        pair:      str,
        timeframe: str,
        start:     str,
        end:       str,
    ) -> List[OHLCVRow]:
        """
        Load rows from TimescaleDB for the given range.
        Falls back to CSV if DB unavailable or empty.

        Returns list of OHLCVRow sorted by ts ascending.
        """
        pair      = pair.upper()
        timeframe = timeframe.upper()
        start_dt  = _parse_date(start)
        end_dt    = _parse_date(end)

        if _PSYCOPG2_AVAILABLE:
            try:
                return self._load_from_db(pair, timeframe, start_dt, end_dt)
            except Exception as exc:
                logger.warning(
                    "DB load failed for %s %s (%s) — falling back to CSV.",
                    pair, timeframe, exc,
                )

        return self._load_from_csv(pair, timeframe, start_dt, end_dt)

    def load_pairs(
        self,
        pairs:      Optional[List[str]] = None,
        timeframes: Optional[List[str]] = None,
        start:      str = "2020-01-01",
        end:        str = "2025-01-01",
    ) -> Dict[str, Dict[str, List[OHLCVRow]]]:
        """
        Load multiple pairs and timeframes.

        Returns {pair: {timeframe: [OHLCVRow, ...]}}
        """
        pairs      = [p.upper() for p in (pairs or _PAIRS)]
        timeframes = [t.upper() for t in (timeframes or _TIMEFRAMES)]

        result: Dict[str, Dict[str, List[OHLCVRow]]] = {}
        for pair in pairs:
            result[pair] = {}
            for tf in timeframes:
                rows = self.load(pair, tf, start, end)
                if not rows:
                    logger.warning("No data for %s %s — check source.", pair, tf)
                result[pair][tf] = rows
                logger.info(
                    "Loaded %s %s: %d candles",
                    pair, tf, len(rows),
                )
        return result

    def detect_gaps(
        self,
        pair:      str,
        timeframe: str,
        start:     str,
        end:       str,
    ) -> List[Tuple[datetime, datetime]]:
        """
        Detect timestamp gaps larger than expected candle interval.
        Returns list of (gap_start, gap_end) tuples.
        Logs a WARNING per gap — does not raise.
        """
        rows = self.load(pair, timeframe, start, end)
        if len(rows) < 2:
            return []

        interval_sec = _tf_to_seconds(timeframe)
        gaps: List[Tuple[datetime, datetime]] = []

        for i in range(1, len(rows)):
            delta = (rows[i].ts - rows[i - 1].ts).total_seconds()
            if delta > interval_sec * 1.5:
                gap = (rows[i - 1].ts, rows[i].ts)
                gaps.append(gap)
                logger.warning(
                    "Gap detected in %s %s: %s → %s (%.0f min missing)",
                    pair, timeframe,
                    rows[i - 1].ts.isoformat(),
                    rows[i].ts.isoformat(),
                    (delta - interval_sec) / 60,
                )

        return gaps

    # ── Private — DB layer ────────────────────────────────────────────────────

    def _stored_range(
        self, pair: str, timeframe: str
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Returns (min_ts, max_ts) already in DB, or (None, None) if empty."""
        if not _PSYCOPG2_AVAILABLE:
            return None, None
        sql = f"""
            SELECT MIN(ts), MAX(ts) FROM {self._table}
            WHERE pair = %s AND timeframe = %s
        """
        try:
            with _DBConnection(self._db_url, self._timeout) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (pair, timeframe))
                    row = cur.fetchone()
                    if row and row[0] is not None:
                        return row[0], row[1]
        except Exception as exc:
            logger.warning("Could not query stored range: %s", exc)
        return None, None

    def _insert_rows(self, rows: List[OHLCVRow]) -> int:
        """Batch-insert rows using ON CONFLICT DO NOTHING (idempotent)."""
        if not _PSYCOPG2_AVAILABLE or not rows:
            return 0

        sql = f"""
            INSERT INTO {self._table} (ts, pair, timeframe, open, high, low, close, volume)
            VALUES %s
            ON CONFLICT (ts, pair, timeframe) DO NOTHING
        """
        inserted = 0
        with _DBConnection(self._db_url, self._timeout) as conn:
            with conn.cursor() as cur:
                for batch in _batched(rows, self._batch):
                    tuples = [r.to_tuple() for r in batch]
                    psycopg2.extras.execute_values(cur, sql, tuples)
                    inserted += cur.rowcount
            conn.commit()
        return inserted

    def _load_from_db(
        self,
        pair:      str,
        timeframe: str,
        start_dt:  datetime,
        end_dt:    datetime,
    ) -> List[OHLCVRow]:
        sql = f"""
            SELECT ts, pair, timeframe, open, high, low, close, volume
            FROM {self._table}
            WHERE pair = %s AND timeframe = %s
              AND ts >= %s AND ts < %s
            ORDER BY ts ASC
        """
        rows: List[OHLCVRow] = []
        with _DBConnection(self._db_url, self._timeout) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (pair, timeframe, start_dt, end_dt))
                for rec in cur.fetchall():
                    rows.append(OHLCVRow(*rec))
        return rows

    # ── Private — MT5 layer ───────────────────────────────────────────────────

    def _fetch_rows(
        self,
        pair:      str,
        timeframe: str,
        start_dt:  datetime,
        end_dt:    datetime,
    ) -> List[OHLCVRow]:
        """Try MT5, fall back to CSV."""
        if _MT5_ENABLED and _MT5_AVAILABLE and mt5 is not None:
            rows = self._fetch_from_mt5(pair, timeframe, start_dt, end_dt)
            if rows:
                return rows
            logger.warning(
                "MT5 returned 0 rows for %s %s — trying CSV fallback.", pair, timeframe
            )
        return self._load_from_csv(pair, timeframe, start_dt, end_dt)

    def _fetch_from_mt5(
        self,
        pair:      str,
        timeframe: str,
        start_dt:  datetime,
        end_dt:    datetime,
    ) -> List[OHLCVRow]:
        tf_const = _MT5_TF_MAP.get(timeframe)
        if tf_const is None:
            logger.warning("MT5: unknown timeframe %s", timeframe)
            return []
        if not mt5.initialize():
            logger.warning("MT5: initialize() failed — %s", mt5.last_error())
            return []
        rates = mt5.copy_rates_range(pair, tf_const, start_dt, end_dt)
        mt5.shutdown()
        if rates is None or len(rates) == 0:
            return []
        return [
            OHLCVRow(
                ts=datetime.fromtimestamp(r["time"], tz=timezone.utc),
                pair=pair, timeframe=timeframe,
                open=r["open"], high=r["high"],
                low=r["low"], close=r["close"],
                volume=float(r["tick_volume"]),
            )
            for r in rates
        ]

    # ── Private — CSV fallback ────────────────────────────────────────────────

    def _load_from_csv(
        self,
        pair:      str,
        timeframe: str,
        start_dt:  datetime,
        end_dt:    datetime,
    ) -> List[OHLCVRow]:
        # Matches existing CSV naming convention: EURUSD_M15.csv
        csv_path = self._csv_dir / f"{pair}_{timeframe}.csv"
        if not csv_path.exists():
            logger.warning("CSV not found: %s", csv_path)
            return []

        rows: List[OHLCVRow] = []
        with open(csv_path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            # Phase 1 — resolve each mandatory column to an actual header (case +
            # known synonyms permitted). volume must be present (no auto-create).
            resolved = resolve_ohlcv_headers(reader.fieldnames or [])
            require_ohlcv_columns(
                resolved.keys(), source=f"Historical dataset {csv_path}"
            )
            o_key, h_key, l_key, c_key, v_key = (
                resolved["open"], resolved["high"], resolved["low"],
                resolved["close"], resolved["volume"],
            )
            for line in reader:
                ts = _parse_csv_ts(line)
                if ts is None:
                    continue
                if not (start_dt <= ts < end_dt):
                    continue
                # Strict numeric access (no .get default) + value-integrity gate.
                o = float(line[o_key]); h = float(line[h_key])
                l = float(line[l_key]); c = float(line[c_key])
                vol = float(line[v_key])
                validate_ohlcv_row(
                    o, h, l, c, vol, source=f"Historical dataset {csv_path}"
                )
                rows.append(OHLCVRow(
                    ts=ts, pair=pair, timeframe=timeframe,
                    open=o, high=h, low=l, close=c, volume=vol,
                ))

        return rows


# ============================================================================
# UTILITIES
# ============================================================================

def _parse_date(date_str: str) -> datetime:
    """Parse YYYY-MM-DD or ISO-8601 string to UTC-aware datetime."""
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date string: {date_str!r}")


def _parse_csv_ts(row: dict) -> Optional[datetime]:
    """Try common CSV timestamp column names."""
    for col in ("time", "timestamp", "datetime", "date", "Time", "Date"):
        val = row.get(col)
        if val:
            try:
                return _parse_date(str(val))
            except ValueError:
                pass
    return None


def _tf_to_seconds(timeframe: str) -> float:
    """Candle interval in seconds for gap detection."""
    mapping = {
        "M1": 60, "M5": 300, "M15": 900,
        "H1": 3600, "H4": 14400, "D1": 86400,
    }
    return float(mapping.get(timeframe.upper(), 900))


def _batched(items: list, size: int) -> Iterator[list]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


# ============================================================================
# CLI
# ============================================================================

def _main(argv: List[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Fetch and store OHLCV data.")
    parser.add_argument("--pair",      required=True)
    parser.add_argument("--timeframe", required=True)
    parser.add_argument("--start",     required=True, help="YYYY-MM-DD")
    parser.add_argument("--end",       required=True, help="YYYY-MM-DD")
    parser.add_argument("--all-pairs", action="store_true",
                        help="Fetch all configured pairs (ignores --pair)")
    args = parser.parse_args(argv)

    fetcher = HistoricalFetcher()

    if args.all_pairs:
        for pair in _PAIRS:
            for tf in _TIMEFRAMES:
                count = fetcher.fetch_and_store(pair, tf, args.start, args.end)
                print(f"{pair} {tf}: {count} rows inserted")
    else:
        count = fetcher.fetch_and_store(args.pair, args.timeframe, args.start, args.end)
        print(f"{args.pair} {args.timeframe}: {count} rows inserted")

    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
