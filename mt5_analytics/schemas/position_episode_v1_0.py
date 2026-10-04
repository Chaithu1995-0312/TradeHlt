"""
position_episode_v1_0 — the atomic analytical unit (Phase 2b).

`position_id` is an MT5 *logical* identifier that reopen-after-close can reuse across
multiple lifetimes, so it is NOT a safe analytical key. A **PositionEpisode** is one
fully-closed lifetime of a position: a single (entry → exit) leg with a VWAP basis and
aggregated cashflow. `episode_id` is the deterministic, unique analytical identity and
is the dedup / idempotency key for every layer above reconstruction.

This is a frozen value object. Field evolution must bump SCHEMA_VERSION and add a
migration in `schemas/migration.py` (schema-stable pillar).
"""
from __future__ import annotations

import datetime as _dt
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Sequence

SCHEMA_VERSION = "1.0"

# Direction tokens (match src/research Signal.direction).
LONG = "long"
SHORT = "short"


def to_iso_utc(epoch_or_iso: "int | float | str") -> str:
    """Coerce an MT5 epoch-seconds timestamp (or an ISO string) to ISO-8601 UTC.

    MT5 `deal.time` is integer epoch seconds. Synthetic fixtures may pass ISO strings
    directly; those are returned normalized (Z-suffixed, second precision).
    """
    if isinstance(epoch_or_iso, str):
        s = epoch_or_iso.strip().replace("Z", "+00:00")
        dt = _dt.datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_dt.timezone.utc)
        dt = dt.astimezone(_dt.timezone.utc)
    else:
        dt = _dt.datetime.fromtimestamp(int(epoch_or_iso), tz=_dt.timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def make_episode_id(
    position_id: int, entry_time_iso: str, deal_tickets: Sequence[int]
) -> str:
    """Deterministic unique analytical id: ``{position_id}:{entry_iso}:{hash8}``.

    The deal-ticket-set hash disambiguates the (pathological) case of two episodes of
    one position_id sharing an entry timestamp. Same deals → same id (idempotent).
    """
    compact = entry_time_iso.replace("-", "").replace(":", "").replace("T", "").rstrip("Z")
    digest = hashlib.sha256(
        ",".join(str(t) for t in sorted(deal_tickets)).encode("utf-8")
    ).hexdigest()[:8]
    return f"{position_id}:{compact}:{digest}"


@dataclass(frozen=True)
class PositionEpisode:
    """One fully-closed lifetime of an MT5 position (the canonical analytics unit)."""

    position_id: int            # logical MT5 identifier (reusable across lifetimes)
    episode_id: str             # unique analytical identity (dedup key)
    symbol: str
    direction: str              # "long" | "short"
    entry_time: str             # ISO-8601 UTC (first IN deal)
    exit_time: str              # ISO-8601 UTC (last OUT deal)
    entry_vwap: float           # Σ(price·vol)/Σ(vol) over IN deals
    exit_vwap: float            # Σ(price·vol)/Σ(vol) over OUT deals
    volume: float               # total opened volume (Σ IN volume)
    net_pnl: float              # Σ(profit + swap + commission) across ALL deals
    gross_profit: float         # Σ profit only
    commission: float           # Σ commission
    swap: float                 # Σ swap
    duration_seconds: float
    # NOTE (K-3): an INOUT reversal deal closes one episode AND opens the next, so its
    # ticket appears in both adjacent episodes — `deal_tickets` is NOT a partition.
    deal_tickets: tuple[int, ...] = field(default_factory=tuple)
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict:
        d = asdict(self)
        d["deal_tickets"] = list(self.deal_tickets)
        return d
