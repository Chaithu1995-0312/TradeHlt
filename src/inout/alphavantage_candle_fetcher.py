"""
AlphaVantageCandleFetcher
================================================================================
Fetches historical FX OHLCV candles from Alpha Vantage's FX_INTRADAY endpoint
and writes CSV files directly consumable by Tradelatest's CandleLoader.

Output CSV columns: datetime, timestamp, open, high, low, close, volume
Datetime format:   YYYY.MM.DD HH:MM  (matches CandleLoader expected format)
Volume:            0.0 (Alpha Vantage FX endpoint does not provide volume)

Config section:  "alphavantage_data"  in configs/production/v1_multi_2026_03.json
CLI entry point: scripts/data/fetch_candles_alphavantage.py

Why Alpha Vantage over Kraken/hummingbot for forex:
  Kraken's hummingbot connector caps historical M15 data at 720 candles (~7.5
  days). Alpha Vantage's FX_INTRADAY endpoint with the 'month' parameter serves
  one full month per request; a year requires 12 calls, well within the free
  tier's 25 req/day limit.

Free API key: https://www.alphavantage.co/support/#api-key
Rate limit:   25 requests/day (free tier). Default delay of 1.2s between
              monthly requests keeps a full-year fetch within a single session.
================================================================================
"""

from __future__ import annotations

# ── 1. Standard library ───────────────────────────────────────────────────────
import csv
import datetime
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

# ── 2. Path bootstrap (when run as a script) ─────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

# ── 3. Internal imports ───────────────────────────────────────────────────────
from config_layer.production_config import get_prod_section  # type: ignore

# ── 4. Logger ─────────────────────────────────────────────────────────────────
logger = logging.getLogger("alphavantage_candle_fetcher")

# ── 5. Constants ──────────────────────────────────────────────────────────────
_AV_BASE_URL = "https://www.alphavantage.co/query"
_AV_FUNCTION = "FX_INTRADAY"
# Alpha Vantage returns timestamps in US/Eastern by default; request UTC via datatype
_REQUEST_TIMEOUT = 30  # seconds


# ── 6. Config helpers ─────────────────────────────────────────────────────────

def _require(cfg: dict, key: str) -> object:
    """Strict accessor — raises KeyError with a helpful message if key is absent."""
    if key not in cfg:
        raise KeyError(
            f"AlphaVantageCandleFetcher: required config key '{key}' missing from "
            f"'alphavantage_data' section. Add it to "
            f"configs/production/v1_multi_2026_03.json."
        )
    return cfg[key]


def _load_av_cfg() -> dict:
    """Load alphavantage_data section from production config. Raises if absent."""
    try:
        cfg = get_prod_section("alphavantage_data")
    except ImportError as exc:
        raise RuntimeError(
            f"Failed to import production_config: {exc}. "
            "Cannot load alphavantage_data settings."
        ) from exc
    if not cfg:
        raise RuntimeError(
            "alphavantage_data section missing from production config JSON. "
            "Add it to configs/production/v1_multi_2026_03.json."
        )
    return cfg


# ── 7. Config dataclass ───────────────────────────────────────────────────────

@dataclass
class AlphaVantageFetcherConfig:
    """Value object derived from the 'alphavantage_data' production JSON section."""

    api_key: str
    from_symbol: str      # e.g. "AUD"
    to_symbol: str        # e.g. "USD"
    interval: str         # e.g. "15min" — Alpha Vantage uses "15min" not "15m"
    start_date: str       # "YYYY-MM-DD" inclusive
    end_date: str         # "YYYY-MM-DD" exclusive
    output_dir: Path
    request_delay_s: float = 1.2  # delay between monthly API calls (rate limiting)

    @classmethod
    def from_prod_config(cls, prod_cfg: dict) -> "AlphaVantageFetcherConfig":
        """Build config from the top-level production JSON dict."""
        s: dict = dict(_require(prod_cfg, "alphavantage_data"))
        return cls.from_section(s)

    @classmethod
    def from_section(cls, section: dict) -> "AlphaVantageFetcherConfig":
        """Build config directly from the alphavantage_data section dict."""
        return cls(
            api_key=str(_require(section, "api_key")),
            from_symbol=str(_require(section, "from_symbol")).upper(),
            to_symbol=str(_require(section, "to_symbol")).upper(),
            interval=str(_require(section, "interval")),
            start_date=str(_require(section, "start_date")),
            end_date=str(_require(section, "end_date")),
            output_dir=Path(str(_require(section, "output_dir"))),
            request_delay_s=float(section.get("request_delay_s", 1.2)),
        )


# ── 8. Public API ─────────────────────────────────────────────────────────────

class AlphaVantageCandleFetcher:
    """
    Fetches historical FX OHLCV candles from Alpha Vantage and writes
    Tradelatest-compatible CSV files.

    Batches requests by calendar month using the Alpha Vantage 'month'
    parameter. Each call returns up to ~2,000 M15 bars for that month.
    A year of data requires 12 API calls, well within the free tier limit.

    Output CSV has columns: datetime, timestamp, open, high, low, close, volume
    where `datetime` is `YYYY.MM.DD HH:MM` (UTC) and volume is always 0.0.

    Parameters
    ----------
    cfg : AlphaVantageFetcherConfig
        Fetcher configuration.

    Raises
    ------
    ValueError
        If the interval is not supported by Alpha Vantage FX_INTRADAY.
    """

    SUPPORTED_INTERVALS = {"1min", "5min", "15min", "30min", "60min"}

    def __init__(self, cfg: AlphaVantageFetcherConfig) -> None:
        if cfg.interval not in self.SUPPORTED_INTERVALS:
            raise ValueError(
                f"Unsupported interval '{cfg.interval}'. "
                f"Alpha Vantage FX_INTRADAY supports: {sorted(self.SUPPORTED_INTERVALS)}"
            )
        self._cfg = cfg
        self._cfg.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(
            "AlphaVantageCandleFetcher ready | %s%s interval=%s out=%s",
            cfg.from_symbol, cfg.to_symbol, cfg.interval, cfg.output_dir,
        )

    @classmethod
    def from_prod_config(cls, prod_cfg: dict) -> "AlphaVantageCandleFetcher":
        """Factory: build from the top-level production config dict."""
        return cls(AlphaVantageFetcherConfig.from_prod_config(prod_cfg))

    def fetch(self) -> Path:
        """
        Fetch all calendar months in [start_date, end_date), concatenate,
        sort by timestamp, and write to a single CSV.

        Returns
        -------
        Path
            Absolute path to the written CSV file.

        Raises
        ------
        RuntimeError
            If no candles were returned across the entire date range.
        """
        months = self._months_in_range()
        pair = f"{self._cfg.from_symbol}{self._cfg.to_symbol}"
        logger.info(
            "Fetching %s %s | %s -> %s (%d monthly request(s))",
            pair, self._cfg.interval,
            self._cfg.start_date, self._cfg.end_date, len(months),
        )

        all_rows: List[dict] = []
        for i, (year, month) in enumerate(months):
            if i > 0:
                time.sleep(self._cfg.request_delay_s)
            try:
                rows = self._fetch_month(year, month)
                logger.info("  %04d-%02d: %d candles", year, month, len(rows))
                all_rows.extend(rows)
            except RuntimeError as exc:
                logger.warning("  %04d-%02d skipped: %s", year, month, exc)

        if not all_rows:
            raise RuntimeError(
                f"No candles returned for {pair} on Alpha Vantage "
                f"({self._cfg.start_date} -> {self._cfg.end_date}). "
                "Check the pair symbols and API key."
            )

        # Filter strictly to [start_date, end_date) in case AV returns adjacent months
        start_dt = datetime.datetime.strptime(self._cfg.start_date, "%Y-%m-%d").replace(
            tzinfo=datetime.timezone.utc
        )
        end_dt = datetime.datetime.strptime(self._cfg.end_date, "%Y-%m-%d").replace(
            tzinfo=datetime.timezone.utc
        )
        all_rows = [r for r in all_rows if start_dt <= r["_dt"] < end_dt]
        all_rows.sort(key=lambda r: r["_dt"])

        out_path = self._write_csv(all_rows, pair)
        logger.info("Wrote %d candles -> %s", len(all_rows), out_path)
        return out_path

    # ── Private helpers ───────────────────────────────────────────────────────

    def _fetch_month(self, year: int, month: int) -> List[dict]:
        """
        Fetch one calendar month of FX_INTRADAY candles from Alpha Vantage.

        Returns a list of row dicts with keys: _dt, timestamp, open, high,
        low, close. Raises RuntimeError on API errors or empty responses.
        """
        params = {
            "function": _AV_FUNCTION,
            "from_symbol": self._cfg.from_symbol,
            "to_symbol": self._cfg.to_symbol,
            "interval": self._cfg.interval,
            "outputsize": "full",
            "month": f"{year:04d}-{month:02d}",
            "apikey": self._cfg.api_key,
        }
        url = f"{_AV_BASE_URL}?{urllib.parse.urlencode(params)}"
        logger.debug("GET %s", url.replace(self._cfg.api_key, "***"))

        try:
            with urllib.request.urlopen(url, timeout=_REQUEST_TIMEOUT) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Network error fetching Alpha Vantage: {exc}") from exc

        # Alpha Vantage signals errors via top-level "Information" or "Error Message"
        if "Error Message" in raw:
            raise RuntimeError(f"Alpha Vantage API error: {raw['Error Message']}")
        if "Information" in raw:
            raise RuntimeError(f"Alpha Vantage rate limit or info: {raw['Information']}")
        if "Note" in raw:
            raise RuntimeError(f"Alpha Vantage note (likely rate limit): {raw['Note']}")

        series_key = f"Time Series FX ({self._cfg.interval})"
        series: dict = raw.get(series_key, {})
        if not series:
            raise RuntimeError(
                f"No time series data in Alpha Vantage response for "
                f"{year:04d}-{month:02d}. Series key expected: '{series_key}'."
            )

        rows: List[dict] = []
        for ts_str, ohlc in series.items():
            # AV timestamps are in US/Eastern by default; treat as UTC for forex
            # (forex markets are 24h and AV's FX series uses UTC-aligned boundaries)
            dt = datetime.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=datetime.timezone.utc
            )
            rows.append({
                "_dt": dt,
                "timestamp": dt.strftime("%Y-%m-%d %H:%M:%S"),
                "open":  ohlc["1. open"],
                "high":  ohlc["2. high"],
                "low":   ohlc["3. low"],
                "close": ohlc["4. close"],
            })
        return rows

    def _months_in_range(self) -> List[Tuple[int, int]]:
        """
        Generate (year, month) tuples covering [start_date, end_date).
        Includes the month containing start_date; excludes months after end_date.
        """
        start = datetime.datetime.strptime(self._cfg.start_date, "%Y-%m-%d")
        end = datetime.datetime.strptime(self._cfg.end_date, "%Y-%m-%d")
        result: List[Tuple[int, int]] = []
        cur = datetime.datetime(start.year, start.month, 1)
        while cur < end:
            result.append((cur.year, cur.month))
            # advance one month
            if cur.month == 12:
                cur = datetime.datetime(cur.year + 1, 1, 1)
            else:
                cur = datetime.datetime(cur.year, cur.month + 1, 1)
        return result

    def _write_csv(self, rows: List[dict], pair: str) -> Path:
        """
        Write sorted rows to a Tradelatest-compatible CSV.

        Columns: datetime (YYYY.MM.DD HH:MM), timestamp (YYYY-MM-DD HH:MM:SS),
                 open, high, low, close, volume (always 0.0 — AV FX has no volume).
        """
        filename = f"{pair}_{self._cfg.interval}.csv"
        out_path = self._cfg.output_dir / filename

        with open(out_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=["datetime", "timestamp", "open", "high", "low", "close", "volume"],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow({
                    "datetime":  row["_dt"].strftime("%Y.%m.%d %H:%M"),
                    "timestamp": row["timestamp"],
                    "open":      row["open"],
                    "high":      row["high"],
                    "low":       row["low"],
                    "close":     row["close"],
                    "volume":    "0.0",
                })

        return out_path.resolve()
