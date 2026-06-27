"""
MT5CandleFetcher
================================================================================
Fetches historical OHLCV candles from a running MetaTrader 5 terminal and writes
CSV files directly consumable by Tradelatest's CandleLoader.

Output CSV columns: timestamp, open, high, low, close, volume
Timestamp format:   YYYY-MM-DD HH:MM:SS  (UTC, from the bar epoch r["time"])
Volume:             tick_volume (MT5 provides real per-bar tick volume)

Config section:  "mt5_data"  (optional — the CLI builds it from args)
CLI entry point: scripts/data/fetch_candles_mt5.py

Why MT5 for FX/metals:
  Alpha Vantage's FX_INTRADAY is premium-only; Kraken/hummingbot caps M15 history
  at ~720 bars. A running MT5 terminal (free demo account) serves native M15 bars
  in UTC with real volume — no timezone conversion and no M1->M15 resampling, the
  failure modes a free-CSV ingester would carry.

Requirements:
  * `pip install MetaTrader5`
  * The MT5 desktop terminal RUNNING and LOGGED IN (the API attaches over IPC).

The conversion mirrors historical_fetcher._fetch_from_mt5 (copy_rates_range ->
UTC datetime -> O/H/L/C/tick_volume); this module adds the direct CSV writer that
historical_fetcher (TimescaleDB-centric) does not provide.
================================================================================
"""

from __future__ import annotations

# ── 1. Standard library ───────────────────────────────────────────────────────
import csv
import datetime
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

# ── 2. Path bootstrap (when run as a script) ─────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

# ── 3. Logger ─────────────────────────────────────────────────────────────────
logger = logging.getLogger("mt5_candle_fetcher")

# ── 4. Optional dependency (fail-soft import; fail-fast at construction) ──────
try:
    import MetaTrader5 as mt5  # type: ignore
    _MT5_AVAILABLE = True
except Exception:  # pragma: no cover - exercised only when the wheel is absent
    mt5 = None  # type: ignore
    _MT5_AVAILABLE = False


# ── 5. Config helpers ─────────────────────────────────────────────────────────

def _require(cfg: dict, key: str) -> object:
    """Strict accessor — raises KeyError with a helpful message if key is absent."""
    if key not in cfg:
        raise KeyError(
            f"MT5CandleFetcher: required config key '{key}' missing from the "
            f"'mt5_data' section / CLI args."
        )
    return cfg[key]


# ── 6. Config dataclass ───────────────────────────────────────────────────────

@dataclass
class MT5FetcherConfig:
    """Value object for an MT5 fetch request."""

    symbol: str            # broker symbol, e.g. "EURUSD" or the broker's gold name "XAUUSD"/"GOLD"
    timeframe: str         # "M15"
    start_date: str        # "YYYY-MM-DD" inclusive (UTC)
    end_date: str          # "YYYY-MM-DD" exclusive (UTC)
    output_dir: Path
    out_name: Optional[str] = None   # output stem override (canonical pair, e.g. "XAUUSD")

    @classmethod
    def from_section(cls, section: dict) -> "MT5FetcherConfig":
        """Build config directly from an mt5_data section dict."""
        return cls(
            symbol=str(_require(section, "symbol")).upper(),
            timeframe=str(_require(section, "timeframe")).upper(),
            start_date=str(_require(section, "start_date")),
            end_date=str(_require(section, "end_date")),
            output_dir=Path(str(_require(section, "output_dir"))),
            out_name=(str(section["out_name"]).upper() if section.get("out_name") else None),
        )


# ── 7. Public API ─────────────────────────────────────────────────────────────

class MT5CandleFetcher:
    """
    Fetches historical OHLCV candles from a running MetaTrader 5 terminal and
    writes a Tradelatest-compatible CSV.

    A single `copy_rates_range` call covers the whole window (2yr M15 ≈ 52k bars,
    well within MT5 limits). Output CSV columns: timestamp, open, high, low,
    close, volume — timestamp is UTC `YYYY-MM-DD HH:MM:SS`, volume is tick_volume.

    Raises
    ------
    RuntimeError
        If the MetaTrader5 package is missing, the terminal can't be reached, the
        symbol is unknown to the broker, or no bars are returned.
    ValueError
        If the timeframe is not supported.
    """

    # MT5 timeframe string -> API constant is resolved lazily (mt5 may be None at import).
    SUPPORTED_TIMEFRAMES = {"M1", "M5", "M15", "M30", "H1", "H4", "D1"}

    def __init__(self, cfg: MT5FetcherConfig) -> None:
        if not _MT5_AVAILABLE or mt5 is None:
            raise RuntimeError(
                "MetaTrader5 package not installed. Run: pip install MetaTrader5"
            )
        if cfg.timeframe not in self.SUPPORTED_TIMEFRAMES:
            raise ValueError(
                f"Unsupported timeframe '{cfg.timeframe}'. "
                f"Supported: {sorted(self.SUPPORTED_TIMEFRAMES)}"
            )
        self._cfg = cfg
        self._cfg.output_dir.mkdir(parents=True, exist_ok=True)
        self._tf_const = self._tf_map()[cfg.timeframe]
        logger.info(
            "MT5CandleFetcher ready | symbol=%s tf=%s out=%s",
            cfg.symbol, cfg.timeframe, cfg.output_dir,
        )

    @staticmethod
    def _tf_map() -> dict:
        return {
            "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
        }

    def fetch(self) -> Path:
        """Fetch [start_date, end_date) and write a single sorted, de-duped CSV."""
        start_dt = datetime.datetime.strptime(self._cfg.start_date, "%Y-%m-%d").replace(
            tzinfo=datetime.timezone.utc
        )
        end_dt = datetime.datetime.strptime(self._cfg.end_date, "%Y-%m-%d").replace(
            tzinfo=datetime.timezone.utc
        )

        if not mt5.initialize():
            raise RuntimeError(
                f"MT5 initialize() failed: {mt5.last_error()}. "
                "Is the MetaTrader 5 terminal running and logged into an account?"
            )
        try:
            # Ensure the symbol is selected in Market Watch before requesting rates.
            if not mt5.symbol_select(self._cfg.symbol, True):
                raise RuntimeError(
                    f"MT5 symbol_select failed for '{self._cfg.symbol}': {mt5.last_error()}. "
                    "Check the broker's symbol name (pass --symbol to override)."
                )
            # Tick precision for this instrument (EURUSD=5, USDJPY=3, XAUUSD=2) — used to
            # round away float64 representation noise so the CSV matches the canonical files.
            info = mt5.symbol_info(self._cfg.symbol)
            digits = int(info.digits) if info is not None else None
            rates = mt5.copy_rates_range(
                self._cfg.symbol, self._tf_const, start_dt, end_dt
            )
        finally:
            mt5.shutdown()

        if rates is None or len(rates) == 0:
            raise RuntimeError(
                f"MT5 returned 0 candles for {self._cfg.symbol} {self._cfg.timeframe} "
                f"({self._cfg.start_date} -> {self._cfg.end_date}). The broker may not "
                "serve this history — scroll the chart back in the terminal to force a "
                "download, or try another broker/demo."
            )

        rows: List[dict] = []
        for r in rates:
            dt = datetime.datetime.fromtimestamp(int(r["time"]), tz=datetime.timezone.utc)
            if not (start_dt <= dt < end_dt):
                continue   # match the [start, end) convention of the AV fetcher
            rows.append({
                "_dt":    dt,
                "open":   self._px(r["open"], digits),
                "high":   self._px(r["high"], digits),
                "low":    self._px(r["low"], digits),
                "close":  self._px(r["close"], digits),
                "volume": int(r["tick_volume"]),
            })
        rows.sort(key=lambda x: x["_dt"])

        # De-dupe by timestamp (keep first) — defensive; MT5 bars are already unique.
        seen: set = set()
        uniq: List[dict] = []
        for r in rows:
            if r["_dt"] in seen:
                continue
            seen.add(r["_dt"])
            uniq.append(r)

        return self._write_csv(uniq)

    # Probe depths (days back from now) for the max-recent fallback. The broker serves a
    # limited intraday history (a 2yr M5 copy_rates_range returns 0 entirely), so we find the
    # DEEPEST recent window it will serve via copy_rates_range (which triggers a server download,
    # unlike copy_rates_from_pos, which only reads the empty local cache).
    _PROBE_DAYS = (30, 60, 90, 120, 180, 270, 365, 540, 730)

    def fetch_recent(self, _count: int | None = None) -> Path:
        """Fetch the DEEPEST recent window the broker serves for this timeframe, via a
        copy_rates_range depth probe (used when the full window returns 0 — typically M5).

        `_count` is accepted for call-site compatibility but ignored: depth is the broker's,
        not a bar count. Writes the deepest non-empty window; the result still flows through the
        same strict gate. Raises if even the shallowest probe is empty."""
        now = datetime.datetime.now(tz=datetime.timezone.utc).replace(second=0, microsecond=0)
        if not mt5.initialize():
            raise RuntimeError(
                f"MT5 initialize() failed: {mt5.last_error()}. Is the terminal running?"
            )
        try:
            if not mt5.symbol_select(self._cfg.symbol, True):
                raise RuntimeError(
                    f"MT5 symbol_select failed for '{self._cfg.symbol}': {mt5.last_error()}."
                )
            info = mt5.symbol_info(self._cfg.symbol)
            digits = int(info.digits) if info is not None else None
            best_rates = None
            best_days = 0
            for days in self._PROBE_DAYS:
                start = now - datetime.timedelta(days=days)
                rates = mt5.copy_rates_range(self._cfg.symbol, self._tf_const, start, now)
                if rates is not None and len(rates) > 0:
                    best_rates, best_days = rates, days   # keep going deeper
                else:
                    break                                  # deeper start won't help
        finally:
            mt5.shutdown()

        if best_rates is None or len(best_rates) == 0:
            raise RuntimeError(
                f"MT5 returned 0 candles for {self._cfg.symbol} {self._cfg.timeframe} at every "
                f"probe depth {self._PROBE_DAYS}. Open the chart in the terminal to populate it."
            )
        logger.info("max-recent: %s %s served deepest at ~%d days (%d bars)",
                    self._cfg.symbol, self._cfg.timeframe, best_days, len(best_rates))
        rows = self._rows_from_rates(best_rates, digits, window=None)
        return self._write_csv(rows)

    @staticmethod
    def discover_symbols(substrings: List[str]) -> List[str]:
        """Broker symbols whose name OR group-path contains any of `substrings` (case-insensitive).
        Used to auto-discover crypto (e.g. group path 'Crypto\\BTCUSD'). Requires the terminal."""
        if not _MT5_AVAILABLE or mt5 is None:
            raise RuntimeError("MetaTrader5 package not installed. Run: pip install MetaTrader5")
        if not mt5.initialize():
            raise RuntimeError(f"MT5 initialize() failed: {mt5.last_error()}.")
        try:
            subs = [s.upper() for s in substrings]
            found: set = set()
            for s in (mt5.symbols_get() or []):
                name = s.name.upper()
                path = getattr(s, "path", "").upper()
                if any(sub in name or sub in path for sub in subs):
                    found.add(s.name)
            return sorted(found)
        finally:
            mt5.shutdown()

    # ── Private helpers ───────────────────────────────────────────────────────

    def _rows_from_rates(self, rates, digits: Optional[int], window) -> List[dict]:
        """Convert MT5 rates -> sorted, de-duped row dicts. `window`=(start_dt,end_dt) applies
        the [start,end) filter; None keeps all (max-recent path)."""
        rows: List[dict] = []
        for r in rates:
            dt = datetime.datetime.fromtimestamp(int(r["time"]), tz=datetime.timezone.utc)
            if window is not None and not (window[0] <= dt < window[1]):
                continue
            rows.append({
                "_dt": dt, "open": self._px(r["open"], digits), "high": self._px(r["high"], digits),
                "low": self._px(r["low"], digits), "close": self._px(r["close"], digits),
                "volume": int(r["tick_volume"]),
            })
        rows.sort(key=lambda x: x["_dt"])
        seen: set = set()
        uniq: List[dict] = []
        for r in rows:
            if r["_dt"] in seen:
                continue
            seen.add(r["_dt"])
            uniq.append(r)
        return uniq

    @staticmethod
    def _px(value, digits: Optional[int]) -> float:
        """Coerce a price to a clean float at the instrument's tick precision."""
        v = float(value)
        return round(v, digits) if digits is not None else v

    def _write_csv(self, rows: List[dict]) -> Path:
        """Write rows to a canonical `{stem}_{timeframe}.csv` (timestamp,O,H,L,C,volume)."""
        stem = self._cfg.out_name or self._cfg.symbol
        out_path = self._cfg.output_dir / f"{stem}_{self._cfg.timeframe}.csv"
        with open(out_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
            for r in rows:
                writer.writerow([
                    r["_dt"].strftime("%Y-%m-%d %H:%M:%S"),
                    r["open"], r["high"], r["low"], r["close"], r["volume"],
                ])
        logger.info("Wrote %d candles -> %s", len(rows), out_path)
        return out_path.resolve()
