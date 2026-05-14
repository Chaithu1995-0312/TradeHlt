"""
HummingbotCandleFetcher
================================================================================
Fetches historical OHLCV candles from any hummingbot-supported exchange
(Binance, Bybit, OKX, KuCoin, Gate.io, etc.) and writes CSV files that are
directly consumable by Tradelatest's CandleLoader.

Output CSV columns: datetime, open, high, low, close, volume
Datetime format:   YYYY.MM.DD HH:MM  (matches CandleLoader expected format)

Config section:  "hummingbot_data"  in configs/production/v1_multi_2026_03.json
CLI entry point: scripts/data/fetch_candles_hummingbot.py

Hummingbot is an optional dependency — import succeeds without it; only
HummingbotCandleFetcher.__init__ raises RuntimeError when it is absent.

Bybit compatibility patch
-------------------------
hummingbot's BybitSpotCandles/_get_rest_candles_params uses 'startTime'/'endTime'
but the Bybit v5 API requires 'start'/'end'. We monkey-patch both connector
classes at import time. The patch is idempotent and isolated to this module.
================================================================================
"""

from __future__ import annotations

# ── 1. Standard library ───────────────────────────────────────────────────────
import asyncio
import datetime
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

# ── 2. Path bootstrap (when run as a script) ─────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

# ── 3. Internal imports ───────────────────────────────────────────────────────
from config_layer.production_config import get_prod_section  # type: ignore

# ── 4. Logger ─────────────────────────────────────────────────────────────────
logger = logging.getLogger("hummingbot_candle_fetcher")


# ── 5. Bybit connector patch ──────────────────────────────────────────────────

def _patch_bybit_params() -> None:
    """
    Fix Bybit v5 API param names in both spot and perpetual connectors.

    hummingbot sends 'startTime'/'endTime' but Bybit v5 requires 'start'/'end'.
    Without this patch, the API ignores the date range and returns recent candles.
    Applied once at module import; safe to call multiple times (idempotent).
    """
    try:
        from hummingbot.data_feed.candles_feed.bybit_spot_candles import BybitSpotCandles          # type: ignore
        from hummingbot.data_feed.candles_feed.bybit_spot_candles.constants import (               # type: ignore
            INTERVALS as _SPOT_INTERVALS,
            MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST as _SPOT_MAX,
        )
        from hummingbot.data_feed.candles_feed.bybit_perpetual_candles import BybitPerpetualCandles # type: ignore
        from hummingbot.data_feed.candles_feed.bybit_perpetual_candles.constants import (          # type: ignore
            INTERVALS as _PERP_INTERVALS,
            MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST as _PERP_MAX,
        )
    except Exception as exc:
        logger.debug("Bybit patch skipped (connector not available): %s", exc)
        return

    def _spot_params(self, start_time=None, end_time=None, limit=None):
        if limit is None:
            limit = _SPOT_MAX
        params = {
            "category": "spot",
            "symbol": self._ex_trading_pair,
            "interval": _SPOT_INTERVALS[self.interval],
            "limit": limit,
        }
        if start_time is not None or end_time is not None:
            st = start_time if start_time is not None else (end_time - limit * self.interval_in_seconds)
            et = end_time if end_time is not None else (start_time + limit * self.interval_in_seconds)
            params["start"] = int(st) * 1000   # ms — Bybit v5 uses 'start', not 'startTime'
            params["end"] = int(et) * 1000
        return params

    def _perp_params(self, start_time=None, end_time=None, limit=None):
        if limit is None:
            limit = _PERP_MAX
        params = {
            "category": "linear",
            "symbol": self._ex_trading_pair,
            "interval": _PERP_INTERVALS[self.interval],
            "limit": limit,
        }
        if start_time is not None or end_time is not None:
            st = start_time if start_time is not None else (end_time - limit * self.interval_in_seconds)
            et = end_time if end_time is not None else (start_time + limit * self.interval_in_seconds)
            params["start"] = int(st) * 1000
            params["end"] = int(et) * 1000
        return params

    BybitSpotCandles._get_rest_candles_params = _spot_params       # type: ignore[method-assign]
    BybitPerpetualCandles._get_rest_candles_params = _perp_params  # type: ignore[method-assign]
    logger.debug("Bybit connector params patched (start/end instead of startTime/endTime)")


# ── 6. Optional hummingbot imports ────────────────────────────────────────────

CandlesFactory = None           # type: ignore
CandlesConfig = None            # type: ignore
HistoricalCandlesConfig = None  # type: ignore
_HB_AVAILABLE = False

try:
    from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory       # type: ignore
    from hummingbot.data_feed.candles_feed.data_types import (                         # type: ignore
        CandlesConfig,
        HistoricalCandlesConfig,
    )
    _patch_bybit_params()
    _HB_AVAILABLE = True
except Exception:
    pass  # HummingbotCandleFetcher.__init__ raises with a clear message


# ── 7. Config helpers ─────────────────────────────────────────────────────────

def _require(cfg: dict, key: str) -> object:
    """Strict accessor — raises KeyError with a helpful message if key is absent."""
    if key not in cfg:
        raise KeyError(
            f"HummingbotCandleFetcher: required config key '{key}' missing from "
            f"'hummingbot_data' section. Add it to "
            f"configs/production/v1_multi_2026_03.json."
        )
    return cfg[key]


def _load_hb_cfg() -> dict:
    """Load hummingbot_data section from production config. Raises if absent."""
    try:
        cfg = get_prod_section("hummingbot_data")
    except ImportError as exc:
        raise RuntimeError(
            f"Failed to import production_config: {exc}. "
            "Cannot load hummingbot_data settings."
        ) from exc
    if not cfg:
        raise RuntimeError(
            "hummingbot_data section missing from production config JSON. "
            "Add it to configs/production/v1_multi_2026_03.json."
        )
    return cfg


# ── 8. Config dataclass ───────────────────────────────────────────────────────

@dataclass
class HummingbotFetcherConfig:
    """Value object derived from the 'hummingbot_data' production JSON section."""

    exchange: str
    trading_pair: str
    interval: str
    start_date: str
    end_date: str
    output_dir: Path
    instruments: List[str] = field(default_factory=list)
    max_records_per_request: int = 500

    @classmethod
    def from_prod_config(cls, prod_cfg: dict) -> "HummingbotFetcherConfig":
        """Build config from the top-level production JSON dict."""
        s: dict = dict(_require(prod_cfg, "hummingbot_data"))
        return cls(
            exchange=str(_require(s, "exchange")),
            trading_pair=str(_require(s, "trading_pair")),
            interval=str(_require(s, "interval")),
            start_date=str(_require(s, "start_date")),
            end_date=str(_require(s, "end_date")),
            output_dir=Path(str(_require(s, "output_dir"))),
            instruments=list(s.get("instruments", [])),
            max_records_per_request=int(s.get("max_records_per_request", 500)),
        )

    @classmethod
    def from_section(cls, section: dict) -> "HummingbotFetcherConfig":
        """Build config directly from the hummingbot_data section dict."""
        return cls(
            exchange=str(_require(section, "exchange")),
            trading_pair=str(_require(section, "trading_pair")),
            interval=str(_require(section, "interval")),
            start_date=str(_require(section, "start_date")),
            end_date=str(_require(section, "end_date")),
            output_dir=Path(str(_require(section, "output_dir"))),
            instruments=list(section.get("instruments", [])),
            max_records_per_request=int(section.get("max_records_per_request", 500)),
        )


# ── 9. Public API ─────────────────────────────────────────────────────────────

class HummingbotCandleFetcher:
    """
    Fetches historical M15 (or any interval) OHLCV candles from a hummingbot-
    supported exchange and writes Tradelatest-compatible CSV files.

    Output CSV has columns: datetime, open, high, low, close, volume
    where `datetime` is formatted as `YYYY.MM.DD HH:MM` (UTC).

    Parameters
    ----------
    cfg : HummingbotFetcherConfig
        Fetcher configuration derived from production JSON.

    Raises
    ------
    RuntimeError
        If hummingbot is not installed when __init__ is called.
    """

    SUPPORTED_INTERVALS = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"}

    def __init__(self, cfg: HummingbotFetcherConfig) -> None:
        if not _HB_AVAILABLE:
            raise RuntimeError(
                "hummingbot package is required for HummingbotCandleFetcher. "
                "Install it with: pip install hummingbot  "
                "or: pip install -e '.[hummingbot]'"
            )
        if cfg.interval not in self.SUPPORTED_INTERVALS:
            raise ValueError(
                f"Unsupported interval '{cfg.interval}'. "
                f"Choose from: {sorted(self.SUPPORTED_INTERVALS)}"
            )
        self._cfg = cfg
        self._cfg.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(
            "HummingbotCandleFetcher ready | exchange=%s interval=%s out=%s",
            cfg.exchange, cfg.interval, cfg.output_dir,
        )

    @classmethod
    def from_prod_config(cls, prod_cfg: dict) -> "HummingbotCandleFetcher":
        """Factory: build from the top-level production config dict."""
        return cls(HummingbotFetcherConfig.from_prod_config(prod_cfg))

    def fetch(self, instrument: Optional[str] = None) -> Path:
        """Synchronous wrapper — fetch candles and write CSV. Returns output path."""
        return asyncio.run(self.fetch_async(instrument))

    async def fetch_async(self, instrument: Optional[str] = None) -> Path:
        """
        Fetch historical candles for `instrument` (or config trading_pair) and
        write a CSV compatible with Tradelatest's CandleLoader.

        Returns
        -------
        Path
            Absolute path to the written CSV file.
        """
        pair = instrument or self._cfg.trading_pair
        logger.info(
            "Fetching %s | %s -> %s on %s",
            pair, self._cfg.start_date, self._cfg.end_date, self._cfg.exchange,
        )

        # Step 1: create candle connector via CandlesConfig
        spot_cfg = CandlesConfig(
            connector=self._cfg.exchange,
            trading_pair=pair,
            interval=self._cfg.interval,
            max_records=self._cfg.max_records_per_request,
        )
        candle = CandlesFactory.get_candle(spot_cfg)

        # Step 2: fetch paginated historical data (start/end in seconds)
        hist_cfg = HistoricalCandlesConfig(
            connector_name=self._cfg.exchange,
            trading_pair=pair,
            interval=self._cfg.interval,
            start_time=_date_to_s(self._cfg.start_date),
            end_time=_date_to_s(self._cfg.end_date),
        )
        df = await candle.get_historical_candles(hist_cfg)

        if df is None or df.empty:
            raise RuntimeError(
                f"No candles returned for {pair} on {self._cfg.exchange} "
                f"({self._cfg.start_date} -> {self._cfg.end_date}). "
                "Check the trading pair name and exchange connector."
            )

        out_path = self._write_csv(df, pair)
        logger.info("Wrote %d candles -> %s", len(df), out_path)
        return out_path

    def fetch_all_instruments(self) -> List[Path]:
        """Fetch candles for every instrument listed in config.instruments."""
        targets = self._cfg.instruments or [self._cfg.trading_pair]
        paths: List[Path] = []
        for instr in targets:
            try:
                path = self.fetch(instrument=instr)
                paths.append(path)
            except Exception as exc:
                logger.error("Failed to fetch %s: %s", instr, exc)
        return paths

    def _write_csv(self, df, pair: str) -> Path:
        """
        Select and rename hummingbot columns to Tradelatest-compatible CSV.

        Columns written:
          datetime   - YYYY.MM.DD HH:MM  (CandleLoader format)
          timestamp  - YYYY-MM-DD HH:MM:SS UTC (FeaturePipeline: pd.to_datetime)
          open/high/low/close/volume
        """
        out = df[["timestamp", "open", "high", "low", "close", "volume"]].copy()
        out["datetime"] = out["timestamp"].apply(_s_to_datetime_str)
        out["timestamp"] = out["timestamp"].apply(_s_to_iso_str)
        out = out[["datetime", "timestamp", "open", "high", "low", "close", "volume"]]

        filename = f"{pair.replace('/', '')}_{self._cfg.interval}.csv"
        out_path = self._cfg.output_dir / filename
        out.to_csv(out_path, index=False)
        return out_path.resolve()


# ── 10. Private utilities ─────────────────────────────────────────────────────

def _date_to_s(date_str: str) -> int:
    """Convert 'YYYY-MM-DD' to UTC Unix timestamp in seconds.

    HistoricalCandlesConfig.start_time / end_time use seconds internally
    (see CandlesBase._round_timestamp_to_interval_multiple which does
    timestamp % interval_in_seconds, and ensure_timestamp_in_seconds which
    converts raw candle timestamps to seconds before pagination math).
    """
    dt = datetime.datetime.strptime(date_str, "%Y-%m-%d").replace(
        tzinfo=datetime.timezone.utc
    )
    return int(dt.timestamp())


def _s_to_datetime_str(ts: float) -> str:
    """Convert a seconds-based candle timestamp to 'YYYY.MM.DD HH:MM' (UTC)."""
    dt = datetime.datetime.fromtimestamp(float(ts), tz=datetime.timezone.utc)
    return dt.strftime("%Y.%m.%d %H:%M")


def _s_to_iso_str(ts: float) -> str:
    """Convert a seconds-based candle timestamp to ISO-8601 UTC string.

    Used for the 'timestamp' column consumed by FeaturePipeline.compute_context
    via pd.to_datetime().
    """
    dt = datetime.datetime.fromtimestamp(float(ts), tz=datetime.timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S")
