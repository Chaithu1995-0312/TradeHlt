"""
trade_identity_v1_0 — the sacred minimum trade identity (Tier 0A).

`TradeIdentityV1` is the SMALLEST IMMUTABLE TRUTH that links a prediction (alert) to
everything that later references a trade. It carries ONLY fields that no future
venue / config / model / workflow change can ever touch — `trade_id`, `alert_id`,
`created_at`.

Deliberately NOT here (each is a separate bounded context keyed by `trade_id`, added
in Tier 0B so identity stays permanent while they churn):
  * symbol / direction        → recoverable via `alert_id`; not duplicated here
  * magic / comment / tickets / episode_id / position_id → transport (TradeExecutionLinkV1)
  * config_hash / model_version / promotion / strategy_id → governance (TradeProvenanceV1)
  * approval state machine     → human workflow (ExecutionIntentV1)

Frozen value object. Field evolution MUST bump SCHEMA_VERSION and add a migration
(schema-stable pillar), mirroring ``mt5_analytics/schemas/position_episode_v1_0.py``.
Reconciles with the existing ``TradeRecord.trade_id`` (``src/journal/schema.py``) — this
is the canonical minter of that id, not a second notion.
"""
from __future__ import annotations

import datetime as _dt
import uuid as _uuid
from dataclasses import dataclass, asdict

SCHEMA_VERSION = "1.0"

_IDENTITY_FIELDS = ("trade_id", "alert_id", "created_at")


def _utc_now_iso() -> str:
    """Current time as ISO-8601 UTC, second precision (matches PositionEpisode.to_iso_utc)."""
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def mint_trade_id() -> str:
    """Mint a fresh, OPAQUE, unique trade_id for one intent-to-trade.

    `trade_id` is the EXECUTION-INTENT identity: minted once at the decision-to-act
    (``ExecutionIntentV1`` PROPOSED), transport/venue-independent, stable forever. It is a
    bare ``uuid4().hex`` and embeds NOTHING — no ``alert_id``, symbol, venue, or timestamp.
    The research lineage (``alert_id``) is carried as a SEPARATE field, never encoded here;
    downstream must NEVER parse a trade_id. Contract: ``docs/reference/trade_identity_contract.md``.
    """
    return _uuid.uuid4().hex


@dataclass(frozen=True)
class TradeIdentityV1:
    """The permanent, transport-independent identity of a single intent-to-trade."""

    trade_id: str            # canonical permanent id (minted at intent)
    alert_id: str            # prediction lineage (the originating alert)
    created_at: str          # ISO-8601 UTC — when the identity was minted
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        # Fail-fast: no silent null identity (no soft defaults, per §6.5).
        for name in _IDENTITY_FIELDS:
            if not getattr(self, name):
                raise ValueError(f"TradeIdentityV1.{name} must be non-empty")

    @classmethod
    def new(
        cls,
        alert_id: str,
        *,
        trade_id: "str | None" = None,
        created_at: "str | None" = None,
    ) -> "TradeIdentityV1":
        """Mint a new identity from an `alert_id`.

        `trade_id` / `created_at` are injectable so callers (and tests) can supply
        deterministic values; otherwise they are minted / stamped now.
        """
        return cls(
            trade_id=trade_id or mint_trade_id(),
            alert_id=alert_id,
            created_at=created_at or _utc_now_iso(),
        )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "TradeIdentityV1":
        allowed = set(_IDENTITY_FIELDS) | {"schema_version"}
        return cls(**{k: v for k, v in d.items() if k in allowed})
