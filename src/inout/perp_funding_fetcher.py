"""
PerpFundingFetcher
================================================================================
Acquires Binance USDⓈ-M **perpetual** carry/basis inputs and writes CSV files
time-aligned to the existing Binance **spot** OHLCV in ``data/``:

  * funding-rate history  (the *carry* signal, native 8h cadence)
  * premium-index history (the *basis* signal, native M15 cadence)

This is a **pure acquisition layer** — transport only. It does NOT forward-fill,
M15-align, or otherwise interpret the series; the downstream carry/basis
interpreter owns alignment. Acquisition stays lossless; epistemic boundaries
stay intact (data ≠ evidence ≠ edge — CLAUDE.md §6.5 Authority Ladder).

Open interest is intentionally NOT fetched: Binance's public
``futures/data/openInterestHist`` retains only ~30 days, so it cannot match the
multi-year spot window. Funding + basis have full public history.

Output files (gitignored ``data/perp/``; cadence is part of the schema identity):
    {SYMBOL}_FUNDING_8H.csv   columns: timestamp,funding_rate
    {SYMBOL}_BASIS_M15.csv    columns: timestamp,premium_index

Timestamp format ``YYYY-MM-DD HH:MM:SS`` (UTC) — byte-identical to ``data/*_M15.csv``
so the future cross-sectional panel inner-join (``research.cross_sectional.load_panel``)
does not suffer silent sparsity.

Config section:  "perp_funding_data"  in the active production config.
CLI entry point: scripts/data/fetch_perp_funding.py

ISOLATION:     stdlib HTTP only (urllib) — no new dependencies.
DETERMINISM:   normalizers dedup + sort on the integer-ms key; CSV writer pins
               ``lineterminator="\\n"`` → byte-identical re-runs.
NO-LOOKAHEAD:  acquisition only; this module measures nothing.
================================================================================
"""

from __future__ import annotations

# ── 1. Standard library ───────────────────────────────────────────────────────
import csv
import json
import logging
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Tuple

# ── 2. Path bootstrap (when imported via a script) ────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

# ── 3. Internal imports ───────────────────────────────────────────────────────
from config_layer.production_config import get_prod_section  # type: ignore

# ── 4. Logger ─────────────────────────────────────────────────────────────────
logger = logging.getLogger("perp_funding_fetcher")

# ── 5. Constants ──────────────────────────────────────────────────────────────
# Endpoint defaults live here (config may override) so a future Bybit/OKX venue
# is a config swap, not a code change.
_FUNDING_PATH = "/fapi/v1/fundingRate"
_BASIS_PATH = "/fapi/v1/premiumIndexKlines"
_TS_FMT = "%Y-%m-%d %H:%M:%S"          # exact spot-CSV format — DO NOT change

# Output schema (cadence in filename + value column name)
_FUNDING_SUFFIX = "_FUNDING_8H.csv"
_FUNDING_COL = "funding_rate"
_BASIS_SUFFIX = "_BASIS_M15.csv"
_BASIS_COL = "premium_index"

SIGNAL_FUNDING = "funding"
SIGNAL_BASIS = "basis"


# ── 6. Time helpers (pure) ────────────────────────────────────────────────────

def _date_to_ms(date_str: str) -> int:
    """Parse a 'YYYY-MM-DD' UTC date to unix-ms (midnight UTC)."""
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _ms_to_str(ms: int) -> str:
    """Format unix-ms as the spot-CSV UTC string 'YYYY-MM-DD HH:MM:SS'.

    Presentation only — called at write time, never mixed into transport/identity.
    """
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime(_TS_FMT)


# ── 7. Config helpers ─────────────────────────────────────────────────────────

def _require(cfg: dict, key: str) -> object:
    """Strict accessor — raises KeyError if the key is absent (no silent defaults)."""
    if key not in cfg:
        raise KeyError(
            f"PerpFundingFetcher: required config key '{key}' missing from "
            f"'perp_funding_data' section. Add it to the active production config."
        )
    return cfg[key]


def _load_perp_cfg() -> dict:
    """Load the 'perp_funding_data' section from the active production config."""
    try:
        cfg = get_prod_section("perp_funding_data")
    except ImportError as exc:  # pragma: no cover - import wiring
        raise RuntimeError(
            f"Failed to import production_config: {exc}. "
            "Cannot load perp_funding_data settings."
        ) from exc
    if not cfg:
        raise RuntimeError(
            "perp_funding_data section missing from production config JSON. "
            "Add it to the active production config."
        )
    return cfg


# ── 8. Config dataclass ───────────────────────────────────────────────────────

@dataclass
class PerpFetcherConfig:
    """Value object derived from the 'perp_funding_data' production JSON section."""

    base_url: str
    instruments: Tuple[str, ...]
    funding_path: str
    basis_path: str
    interval: str            # e.g. "15m"
    request_timeout_s: float
    request_delay_s: float
    max_limit: int
    out_dir: Path

    @classmethod
    def from_prod_config(cls, prod_cfg: dict) -> "PerpFetcherConfig":
        """Build config from the top-level production JSON dict."""
        section: dict = dict(_require(prod_cfg, "perp_funding_data"))  # type: ignore[arg-type]
        return cls.from_section(section)

    @classmethod
    def from_section(cls, section: dict) -> "PerpFetcherConfig":
        """Build config directly from the perp_funding_data section dict (strict)."""
        instruments = tuple(str(s).upper() for s in _require(section, "instruments"))  # type: ignore[arg-type]
        return cls(
            base_url=str(_require(section, "base_url")).rstrip("/"),
            instruments=instruments,
            funding_path=str(_require(section, "funding_path")),
            basis_path=str(_require(section, "basis_path")),
            interval=str(_require(section, "interval")),
            request_timeout_s=float(_require(section, "request_timeout_s")),
            request_delay_s=float(_require(section, "request_delay_s")),
            max_limit=int(_require(section, "max_limit")),
            out_dir=Path(str(_require(section, "out_dir"))),
        )


# ── 9. Public API ─────────────────────────────────────────────────────────────

class PerpFundingFetcher:
    """Fetch Binance perp funding-rate + premium-index (basis) history to CSV.

    The single network seam is :meth:`_get_json`; tests monkeypatch it for
    deterministic, offline coverage. Normalizers are pure ``@staticmethod`` and
    operate on integer-ms keys.
    """

    def __init__(self, cfg: PerpFetcherConfig) -> None:
        self._cfg = cfg
        self._cfg.out_dir.mkdir(parents=True, exist_ok=True)
        logger.info(
            "PerpFundingFetcher ready | base=%s interval=%s out=%s instruments=%s",
            cfg.base_url, cfg.interval, cfg.out_dir, ",".join(cfg.instruments),
        )

    @classmethod
    def from_prod_config(cls, prod_cfg: dict) -> "PerpFundingFetcher":
        """Factory: build from the top-level production config dict."""
        return cls(PerpFetcherConfig.from_prod_config(prod_cfg))

    # ── orchestration ─────────────────────────────────────────────────────────

    def fetch(
        self,
        instrument: str,
        start: str,
        end: str,
        signals: Iterable[str] = (SIGNAL_FUNDING, SIGNAL_BASIS),
    ) -> dict[str, Path]:
        """Fetch the requested signals for one instrument over [start, end).

        Parameters
        ----------
        instrument : str   e.g. "BNBUSDT"
        start, end : str   'YYYY-MM-DD' UTC (start inclusive, end exclusive)
        signals    : iterable of {"funding", "basis"}

        Returns
        -------
        dict[str, Path]   signal name -> written CSV path
        """
        symbol = instrument.upper()
        start_ms, end_ms = _date_to_ms(start), _date_to_ms(end)
        wanted = set(signals)
        written: dict[str, Path] = {}

        if SIGNAL_FUNDING in wanted:
            raw = self._paginate_funding(symbol, start_ms, end_ms)
            rows = self._normalize_funding(raw)
            rows = [(ts, v) for ts, v in rows if start_ms <= ts < end_ms]
            path = self._cfg.out_dir / f"{symbol}{_FUNDING_SUFFIX}"
            self._write_csv(path, _FUNDING_COL, rows)
            logger.info("%s funding: %d rows -> %s", symbol, len(rows), path)
            written[SIGNAL_FUNDING] = path

        if SIGNAL_BASIS in wanted:
            raw = self._paginate_klines(symbol, start_ms, end_ms)
            rows = self._normalize_basis(raw)
            rows = [(ts, v) for ts, v in rows if start_ms <= ts < end_ms]
            path = self._cfg.out_dir / f"{symbol}{_BASIS_SUFFIX}"
            self._write_csv(path, _BASIS_COL, rows)
            logger.info("%s basis: %d rows -> %s", symbol, len(rows), path)
            written[SIGNAL_BASIS] = path

        return written

    def fetch_all(
        self,
        start: str,
        end: str,
        signals: Iterable[str] = (SIGNAL_FUNDING, SIGNAL_BASIS),
    ) -> dict[str, dict[str, Path]]:
        """Fetch the requested signals for every configured instrument."""
        out: dict[str, dict[str, Path]] = {}
        for instr in self._cfg.instruments:
            out[instr] = self.fetch(instr, start, end, signals)
        return out

    # ── network seam (the only I/O) ───────────────────────────────────────────

    def _get_json(self, path: str, params: dict) -> list:
        """GET base_url+path?params and parse JSON. The single network call."""
        url = f"{self._cfg.base_url}{path}?{urllib.parse.urlencode(params)}"
        logger.debug("GET %s", url)
        try:
            with urllib.request.urlopen(url, timeout=self._cfg.request_timeout_s) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Network error fetching {path}: {exc}") from exc

    # ── pagination (advance-or-raise) ─────────────────────────────────────────

    def _paginate_funding(self, symbol: str, start_ms: int, end_ms: int) -> List[dict]:
        """Page the fundingRate endpoint; raise if a page fails to advance."""
        def last_time(page: list) -> int:
            return int(page[-1]["fundingTime"])

        return self._paginate(
            symbol, start_ms, end_ms, self._cfg.funding_path,
            extra={}, last_time=last_time,
        )

    def _paginate_klines(self, symbol: str, start_ms: int, end_ms: int) -> List[list]:
        """Page the premiumIndexKlines endpoint; raise if a page fails to advance."""
        def last_time(page: list) -> int:
            return int(page[-1][0])  # kline openTime (ms)

        return self._paginate(
            symbol, start_ms, end_ms, self._cfg.basis_path,
            extra={"interval": self._cfg.interval}, last_time=last_time,
        )

    def _paginate(self, symbol, start_ms, end_ms, path, extra, last_time) -> list:
        """Shared cursor pagination with a strict progress guard.

        Advances ``startTime`` past the last event time each page. If a page does
        not strictly advance (API bug / repeated last page), raise rather than
        hang — most pagination failures stall, they do not crash.
        """
        out: list = []
        cursor = start_ms
        prev_last: int | None = None
        while cursor < end_ms:
            params = {"symbol": symbol, "startTime": cursor, "endTime": end_ms,
                      "limit": self._cfg.max_limit, **extra}
            page = self._get_json(path, params)
            if not page:
                break
            out.extend(page)
            cur_last = last_time(page)
            if prev_last is not None and cur_last <= prev_last:
                raise RuntimeError(
                    f"{path} pagination not advancing for {symbol}: "
                    f"last={cur_last} <= prev={prev_last}"
                )
            prev_last = cur_last
            if len(page) < self._cfg.max_limit:
                break
            cursor = cur_last + 1
            time.sleep(self._cfg.request_delay_s)
        return out

    # ── pure normalizers (integer-ms keyed; unit-tested seams) ────────────────

    @staticmethod
    def _normalize_funding(raw: Iterable[dict]) -> List[Tuple[int, float]]:
        """Raw fundingRate list -> sorted, deduped [(fundingTime_ms, rate)]."""
        seen: set[int] = set()
        out: List[Tuple[int, float]] = []
        for r in raw:
            ts = int(r["fundingTime"])
            if ts in seen:
                continue
            seen.add(ts)
            out.append((ts, float(r["fundingRate"])))
        out.sort(key=lambda x: x[0])
        return out

    @staticmethod
    def _normalize_basis(raw: Iterable[list]) -> List[Tuple[int, float]]:
        """Raw premiumIndexKlines list -> sorted, deduped [(openTime_ms, close)]."""
        seen: set[int] = set()
        out: List[Tuple[int, float]] = []
        for k in raw:
            ts = int(k[0])           # openTime
            if ts in seen:
                continue
            seen.add(ts)
            out.append((ts, float(k[4])))  # close = premium index
        out.sort(key=lambda x: x[0])
        return out

    # ── deterministic CSV writer ──────────────────────────────────────────────

    def _write_csv(self, path: Path, value_col: str, rows: Iterable[Tuple[int, float]]) -> None:
        """Write [(ts_ms, value)] as 'timestamp,<value_col>'.

        ``lineterminator="\\n"`` + ``encoding="utf-8"`` + ``newline=""`` pin the
        bytes across platforms so re-runs are byte-identical.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh, lineterminator="\n")
            writer.writerow(["timestamp", value_col])
            for ts, val in rows:
                writer.writerow([_ms_to_str(ts), val])
