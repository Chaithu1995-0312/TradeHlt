"""
trade_execution_link_v1_0 — transport correlation layer (Tier 0B, disposable).

Answers "how did the identity map onto broker reality?" — the ONLY place venue / magic / comment /
tickets live. Per ``docs/reference/trade_identity_contract.md`` invariant #5 (**`magic != identity`**):
this record is *best-effort*; its loss or mutation must NEVER change a ``TradeIdentityV1``. Swapping
MT5 → FIX rewrites THIS schema; identity is untouched.

Append model: one correlation row per (trade_id, order attempt). Broker retries share a `trade_id`
and emit additional rows (contract: ``1 trade_id : 1..N order attempts``). Optional fields fill in as
reality resolves (order → deal → position → reconstructed episode). Frozen value object; field
evolution bumps SCHEMA_VERSION + migration.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, asdict

SCHEMA_VERSION = "1.0"


def _utc_now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class TradeExecutionLinkV1:
    """A best-effort correlation from an execution-intent `trade_id` to broker transport."""

    trade_id: str                        # opaque execution-intent id (authoritative)
    venue: str                           # e.g. "MT5" — the transport this row describes
    magic: "int | None" = None           # MT5 correlation carrier — NOT identity
    comment: "str | None" = None         # MT5 correlation carrier — NOT identity
    order_ticket: "int | None" = None
    deal_ticket: "int | None" = None
    position_id: "int | None" = None
    episode_id: "str | None" = None      # PositionEpisode.episode_id, once reconstructed
    created_at: str = ""
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.trade_id:
            raise ValueError("TradeExecutionLinkV1.trade_id must be non-empty")
        if not self.venue:
            raise ValueError("TradeExecutionLinkV1.venue must be non-empty")
        if not self.created_at:
            object.__setattr__(self, "created_at", _utc_now_iso())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "TradeExecutionLinkV1":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
