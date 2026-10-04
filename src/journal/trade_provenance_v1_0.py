"""
trade_provenance_v1_0 — governance lineage (Tier 0B, append, keyed by trade_id).

Answers "why did this trade exist?" — the config / model / promotion context at the moment of the
intent. Churns on its own clock; kept OUT of ``TradeIdentityV1`` so identity stays permanent while
lineage evolves. Append-only: one row per `trade_id` (or per re-capture if lineage is restated).

Field sources: `config_hash`/`config_version` = ``promotion_manager.py:414`` / ``ACTIVE_VERSION``;
`model_version` = ``model_registry.py`` (per-instrument active); `strategy_id`/`promotion_version` =
the governing promotion record. All optional except `trade_id` — provenance is captured
best-effort and never blocks identity. Frozen value object; field evolution bumps SCHEMA_VERSION.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, asdict

SCHEMA_VERSION = "1.0"


def _utc_now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class TradeProvenanceV1:
    """The governance lineage of one execution-intent `trade_id` (why it existed)."""

    trade_id: str
    strategy_id: "str | None" = None
    promotion_version: "str | None" = None
    config_hash: "str | None" = None
    config_version: "str | None" = None
    model_version: "str | None" = None
    captured_at: str = ""
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.trade_id:
            raise ValueError("TradeProvenanceV1.trade_id must be non-empty")
        if not self.captured_at:
            object.__setattr__(self, "captured_at", _utc_now_iso())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "TradeProvenanceV1":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
