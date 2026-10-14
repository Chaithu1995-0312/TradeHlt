"""
clock_contract.py — the Corpus Clock Contract (CH-corpus-clock-contract-v1, 2026-10-08).

WHAT THIS IS
------------
A corpus's `timestamp` column is written on SOME clock. This module is the single place that knows
how a configured clock maps to canonical UTC. Nothing is inferred:

    dataset / registry record --declares--> clock_id (+ provider + broker)
    configs/data_provenance/ohlcv_clock_registry.json "clocks"[clock_id] --defines--> the mapping
    corpus_store.load() --normalizes ONCE--> canonical UTC `timestamp` (+ `source_timestamp`)

A clock definition is `timezone` (IANA) + `server_midnight_local`: "the server's 00:00 is this local
time in `timezone`". The conversion is one uniform rule

    local = server_wall - ((24h - server_midnight_local) mod 24h)
    utc   = zoneinfo(timezone).localize(local)       # DST comes ONLY from the IANA rules

so a MT5 server that runs on "New York close = server midnight" is `America/New_York` +
`17:00`, a UTC feed is `UTC` + `00:00`, and a plain named-zone feed is `<zone>` + `00:00`. No
`UTC+2/UTC+3` seasonal offsets exist anywhere in this contract, and the registry schema REJECTS any
offset-valued field (`wall_offset`, `utc_offset`, ...). `observed_utc_offsets` is allowed as EVIDENCE
and is never read by the converter.

WHAT THIS IS NOT
----------------
It does not detect, guess, or review a clock. `clock_detector` stays advisory (zero admission
authority). A dataset with no configured clock identity does not enter the research system.

ONCE-ONLY NORMALIZATION
-----------------------
`normalize_view()` is the only entry that turns source-clock timestamps into canonical UTC and it
refuses a view that is already canonical (`DoubleNormalizationError`).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time as dtime, timedelta
from typing import Any, Iterable, Mapping, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from data_ingestion.ohlcv_schema import ClockProvenanceError

CONTRACT_VERSION = "clock-contract/1"
CANONICAL_TIMEZONE = "UTC"

CLOCK_STATE_SOURCE = "source"
CLOCK_STATE_CANONICAL = "canonical_utc"

#: fields a clock definition may carry. Anything else (in particular a stored offset) is refused.
_ALLOWED_CLOCK_FIELDS = frozenset({
    "provider", "broker", "server", "timezone", "server_midnight_local",
    "evidence", "observed_utc_offsets", "note",
})
_REQUIRED_CLOCK_FIELDS = ("provider", "broker", "timezone", "server_midnight_local")
#: stored-offset spellings that must never become conversion inputs.
_FORBIDDEN_OFFSET_FIELDS = frozenset({
    "wall_offset", "utc_offset", "offset", "offset_hours", "offset_minutes", "fixed_offset",
    "dst_offset", "seasonal_offset", "utc_plus", "gmt_offset",
})


class ClockNormalizationError(ClockProvenanceError):
    """A timestamp could not be mapped to UTC (ambiguous / nonexistent local instant, bad cell)."""


class DoubleNormalizationError(ClockProvenanceError):
    """Canonical UTC was passed through source-clock normalization a second time."""


def _parse_hhmm(clock_id: str, raw: Any) -> dtime:
    try:
        h, m = str(raw).split(":")
        t = dtime(int(h), int(m))
    except (ValueError, TypeError) as exc:
        raise ValueError(f"clock {clock_id!r}: server_midnight_local={raw!r} must be 'HH:MM'") from exc
    return t


@dataclass(frozen=True)
class ClockDef:
    """One configured clock: who produced the timestamps and how they map to UTC."""
    clock_id: str
    provider: str
    broker: str
    timezone: str
    server_midnight_local: str            # 'HH:MM' local wall time at which the server clock reads 00:00
    server: str = ""
    evidence: tuple = ()
    observed_utc_offsets: tuple = ()      # evidence only; never read by the converter

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def shift(self) -> timedelta:
        """Server wall time minus local wall time (computed, never stored)."""
        t = _parse_hhmm(self.clock_id, self.server_midnight_local)
        local_midnight = timedelta(hours=t.hour, minutes=t.minute)
        return (timedelta(hours=24) - local_midnight) % timedelta(hours=24)

    @property
    def is_identity(self) -> bool:
        """True when server wall time already IS UTC wall time (UTC zone, no shift)."""
        return self.timezone == "UTC" and self.shift == timedelta(0)

    def triple(self) -> tuple:
        return (self.provider, self.broker, self.clock_id)

    def describe(self) -> dict:
        return {
            "clock_id": self.clock_id, "provider": self.provider, "broker": self.broker,
            "server": self.server, "timezone": self.timezone,
            "server_midnight_local": self.server_midnight_local,
            "canonical_timezone": CANONICAL_TIMEZONE, "contract_version": CONTRACT_VERSION,
        }


def parse_clock_defs(raw: Mapping[str, Mapping[str, Any]]) -> dict[str, ClockDef]:
    """Validate and parse the registry's `clocks` table. Fail-closed on anything unknown."""
    if not isinstance(raw, Mapping):
        raise ClockProvenanceError("clock registry 'clocks' must be an object {clock_id: definition}")
    out: dict[str, ClockDef] = {}
    for cid, spec in raw.items():
        if not isinstance(spec, Mapping):
            raise ClockProvenanceError(f"clock {cid!r}: definition must be an object")
        bad = sorted(set(spec) & _FORBIDDEN_OFFSET_FIELDS)
        if bad:
            raise ClockProvenanceError(
                f"clock {cid!r}: stored offset field(s) {bad} are refused. The mapping derives from "
                f"`timezone` (IANA) + `server_midnight_local` only; offsets may appear as "
                f"`observed_utc_offsets` evidence, never as conversion inputs."
            )
        unknown = sorted(set(spec) - _ALLOWED_CLOCK_FIELDS)
        if unknown:
            raise ClockProvenanceError(f"clock {cid!r}: unknown field(s) {unknown}")
        missing = [k for k in _REQUIRED_CLOCK_FIELDS if not str(spec.get(k, "")).strip()]
        if missing:
            raise ClockProvenanceError(f"clock {cid!r}: missing required field(s) {missing}")
        tz = str(spec["timezone"])
        try:
            ZoneInfo(tz)
        except (ZoneInfoNotFoundError, ValueError, KeyError) as exc:
            raise ClockProvenanceError(f"clock {cid!r}: timezone {tz!r} is not a valid IANA zone") from exc
        _parse_hhmm(cid, spec["server_midnight_local"])
        out[str(cid)] = ClockDef(
            clock_id=str(cid), provider=str(spec["provider"]), broker=str(spec["broker"]),
            timezone=tz, server_midnight_local=str(spec["server_midnight_local"]),
            server=str(spec.get("server", "")),
            evidence=tuple(spec.get("evidence", ())),
            observed_utc_offsets=tuple(spec.get("observed_utc_offsets", ())),
        )
    return out


def require_exact_identity(clock: ClockDef, *, provider: Optional[str], broker: Optional[str],
                           clock_id: Optional[str], where: str) -> None:
    """The declared provider/broker/clock_id must EXACTLY match the configured clock."""
    declared = (provider, broker, clock_id)
    if declared != clock.triple():
        raise ClockProvenanceError(
            f"{where}: declared (provider, broker, clock_id)={declared} does not exactly match the "
            f"configured clock {clock.clock_id!r} = {clock.triple()}. No guessing: fix the declaration "
            f"or the clock definition."
        )


# ── conversion ────────────────────────────────────────────────────────────────────────────────
def to_utc_scalar(ts: datetime, clock: ClockDef) -> datetime:
    """Source-clock wall time -> naive UTC wall time. Ambiguous / nonexistent instants raise."""
    if ts.tzinfo is not None:
        raise ClockNormalizationError(f"to_utc_scalar expects a naive source-clock timestamp, got {ts!r}")
    if clock.is_identity:
        return ts
    local = ts - clock.shift
    z = clock.zone
    a = local.replace(tzinfo=z, fold=0)
    b = local.replace(tzinfo=z, fold=1)
    # nonexistent (spring-forward gap): round-trip through UTC does not reproduce the wall time.
    from datetime import timezone as _tz
    rt = a.astimezone(_tz.utc).astimezone(z).replace(tzinfo=None)
    if rt != local:
        raise ClockNormalizationError(
            f"clock {clock.clock_id!r}: local instant {local} does not exist in {clock.timezone} (DST gap)")
    if a.utcoffset() != b.utcoffset():
        raise ClockNormalizationError(
            f"clock {clock.clock_id!r}: local instant {local} is ambiguous in {clock.timezone} (DST overlap)")
    return a.astimezone(_tz.utc).replace(tzinfo=None)


def from_utc_scalar(utc: datetime, clock: ClockDef) -> datetime:
    """Inverse of `to_utc_scalar` (audit / source-clock comparison, and the calendar wall mapping).
    An AWARE timestamp (live bars carry tz-aware UTC) is first reduced to naive UTC."""
    if utc.tzinfo is not None:
        from datetime import timezone as _tz0
        utc = utc.astimezone(_tz0.utc).replace(tzinfo=None)
    if clock.is_identity:
        return utc
    from datetime import timezone as _tz
    local = utc.replace(tzinfo=_tz.utc).astimezone(clock.zone).replace(tzinfo=None)
    return local + clock.shift


def to_utc_series(ts, clock: ClockDef):
    """Vectorized `to_utc_scalar` for a naive datetime64 pandas Series (index preserved)."""
    import pandas as pd

    if getattr(ts.dt, "tz", None) is not None:
        raise ClockNormalizationError("to_utc_series expects naive source-clock timestamps")
    if clock.is_identity:
        return ts
    local = ts - clock.shift
    try:
        aware = local.dt.tz_localize(clock.timezone, ambiguous="raise", nonexistent="raise")
    except Exception as exc:  # pytz/zoneinfo raise their own AmbiguousTimeError/NonExistentTimeError
        raise ClockNormalizationError(
            f"clock {clock.clock_id!r}: a source timestamp is ambiguous/nonexistent in {clock.timezone}: {exc}"
        ) from exc
    return aware.dt.tz_convert("UTC").dt.tz_localize(None)


def from_utc_series(utc, clock: ClockDef):
    """Vectorized inverse (naive UTC Series -> source-clock wall Series)."""
    if clock.is_identity:
        return utc
    aware = utc.dt.tz_localize("UTC").dt.tz_convert(clock.timezone).dt.tz_localize(None)
    return aware + clock.shift


# ── once-only guard ───────────────────────────────────────────────────────────────────────────
def normalize_view(state: str, clock: ClockDef, ts):
    """Normalize a SOURCE-state timestamp Series to canonical UTC. Refuses canonical input."""
    if state != CLOCK_STATE_SOURCE:
        raise DoubleNormalizationError(
            f"timestamps are already {state!r}; they cannot be passed through source-clock "
            f"normalization ({clock.clock_id}) again.")
    return to_utc_series(ts, clock)
