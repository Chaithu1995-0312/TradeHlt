"""
market_calendar.py — the MARKET calendar contract (CH-corpus-clock-contract-v1, 2026-10-08).

Canonical timestamps are UTC. Day/week/higher-timeframe boundaries, day-of-week, PDH/PDL and the
weekly range are CALENDAR concepts: they depend on where the market's trading day starts, not on
which broker produced a corpus. A calendar is declared once per asset class in
`configs/data_provenance/market_calendar.json` as an IANA `timezone` + `day_start` ("the market day
starts at this local time"), and maps UTC to the *calendar wall time* whose 00:00 starts the day:

    wall = local(timezone) + ((24h - day_start) mod 24h)

For `fx_metals` (day closes 17:00 America/New_York) that wall time is the grid the MT5 servers'
own stamps already used, so H4/D1/W1 buckets, PDH/PDL and ISO weeks are unchanged by the move of
`Candle.timestamp` to UTC. DST comes from the IANA zone only; no stored offset exists.

Broker timestamp timezone and trading-session/calendar timezone are SEPARATE concepts: nothing here
reads a clock id or a broker. The calendar for a corpus is selected by its INSTRUMENT.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Optional

from data_ingestion.clock_contract import (
    ClockDef, from_utc_scalar, from_utc_series, to_utc_scalar, to_utc_series,
)

CALENDAR_RELPATH = "configs/data_provenance/market_calendar.json"
_REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class CalendarSpec:
    name: str
    timezone: str
    day_start: str                       # 'HH:MM' local time at which the market day starts

    @property
    def _def(self) -> ClockDef:
        # A calendar is "the wall clock of a server whose midnight is `day_start` in `timezone`".
        return ClockDef(clock_id=f"calendar:{self.name}", provider="calendar", broker="-",
                        timezone=self.timezone, server_midnight_local=self.day_start)

    @property
    def is_identity(self) -> bool:
        return self._def.is_identity

    def wall(self, utc: datetime) -> datetime:
        """Naive UTC -> naive calendar wall time (day starts at wall 00:00)."""
        return from_utc_scalar(utc, self._def)

    def wall_series(self, utc):
        return from_utc_series(utc, self._def)

    def to_utc(self, wall: datetime) -> datetime:
        """Inverse of `wall` (e.g. a bucket-start label back to UTC). Ambiguous/nonexistent raise."""
        return to_utc_scalar(wall, self._def)

    def to_utc_series(self, wall):
        return to_utc_series(wall, self._def)


#: identity calendar — the UTC day. Used by constructed data and by callers that bucket UTC as-is.
UTC_CALENDAR = CalendarSpec("utc", "UTC", "00:00")


def _calendar_path() -> Path:
    return _REPO_ROOT / CALENDAR_RELPATH


@lru_cache(maxsize=1)
def load_calendars(path: Optional[str] = None) -> dict:
    p = Path(path) if path else _calendar_path()
    raw = json.loads(p.read_text(encoding="utf-8"))
    out = {}
    for name, spec in raw["calendars"].items():
        missing = [k for k in ("timezone", "day_start") if not spec.get(k)]
        if missing:
            raise ValueError(f"{CALENDAR_RELPATH}: calendar {name!r} missing {missing}")
        cs = CalendarSpec(str(name), str(spec["timezone"]), str(spec["day_start"]))
        cs._def  # validates the IANA zone and HH:MM eagerly
        out[str(name)] = cs
    return out


def get_calendar(name: str) -> CalendarSpec:
    cals = load_calendars()
    if name not in cals:
        raise KeyError(f"market calendar {name!r} is not declared in {CALENDAR_RELPATH} "
                       f"(declared: {sorted(cals)})")
    return cals[name]


def calendar_name_for_instrument(symbol: Optional[str]) -> str:
    """Asset class -> calendar name, via the EXISTING classifier (no second suffix list)."""
    from config_layer.production_config import get_prod_section
    from data_ingestion.dataset_integrity import MarketType, classify_market

    market = classify_market(symbol, get_prod_section("dataset_integrity"))
    return "crypto" if market is MarketType.CRYPTO else "fx_metals"


def calendar_for_instrument(symbol: Optional[str]) -> CalendarSpec:
    return get_calendar(calendar_name_for_instrument(symbol))
