"""Canonical BenchmarkTradeRecord — common execution/evidence model for all engines.

Every OSS adapter maps native output into this contract.
Missing fields MUST use Presence tokens + FieldProvenance — never invent values.

Distinct from journal.schema.TradeRecord (spine decision journal) and from
research.contracts.Outcome (edge-discovery forward-walk). This is the OSS-lab
normalized ledger only.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional

from oss_lab.contracts.presence import Presence


class Side(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class FieldProvenance:
    """Why a field is PRESENT / UNKNOWN / NOT_AVAILABLE / NOT_APPLICABLE."""

    presence: Presence
    reason: str = ""
    native_field: Optional[str] = None
    source_adapter: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "presence": self.presence.value,
            "reason": self.reason,
            "native_field": self.native_field,
            "source_adapter": self.source_adapter,
        }


def _prov(
    presence: Presence = Presence.PRESENT,
    reason: str = "",
    native_field: Optional[str] = None,
    source_adapter: Optional[str] = None,
) -> FieldProvenance:
    return FieldProvenance(
        presence=presence,
        reason=reason,
        native_field=native_field,
        source_adapter=source_adapter,
    )


UNKNOWN = lambda reason, **kw: _prov(Presence.UNKNOWN, reason=reason, **kw)  # noqa: E731
NA = lambda reason, **kw: _prov(Presence.NOT_AVAILABLE, reason=reason, **kw)  # noqa: E731
NAPP = lambda reason, **kw: _prov(Presence.NOT_APPLICABLE, reason=reason, **kw)  # noqa: E731
PRESENT = lambda reason="", **kw: _prov(Presence.PRESENT, reason=reason, **kw)  # noqa: E731


@dataclass
class BenchmarkTradeRecord:
    """Normalized trade evidence for cross-engine comparison.

    Monetary/R fields may be None when presence is not PRESENT.
    Metric authority computes independently from PRESENT fields only.
    """

    # Identity
    run_id: str
    engine: str
    instrument: str
    timeframe: str

    # Timestamps (ISO-8601 strings or None)
    signal_ts: Optional[str] = None
    decision_ts: Optional[str] = None
    order_ts: Optional[str] = None
    fill_ts: Optional[str] = None

    # Direction / intent
    side: Side = Side.UNKNOWN
    intent: Optional[str] = None

    # Prices
    entry_requested: Optional[float] = None
    entry_filled: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    exit: Optional[float] = None
    exit_reason: Optional[str] = None

    # Size / risk / PnL
    quantity: Optional[float] = None
    initial_risk: Optional[float] = None
    gross_pnl: Optional[float] = None
    fees: Optional[float] = None
    spread_cost: Optional[float] = None
    slippage_cost: Optional[float] = None
    financing_cost: Optional[float] = None
    other_costs: Optional[float] = None
    net_pnl: Optional[float] = None

    # Path statistics (price units unless *_r)
    mfe: Optional[float] = None
    mae: Optional[float] = None
    mfe_r: Optional[float] = None
    mae_r: Optional[float] = None

    # Latency (seconds); clock source required in provenance
    decision_latency: Optional[float] = None
    order_latency: Optional[float] = None
    fill_latency: Optional[float] = None

    # Per-field provenance (field_name -> FieldProvenance)
    field_provenance: dict[str, FieldProvenance] = field(default_factory=dict)

    # Free-form adapter notes (never used as metric inputs)
    adapter_meta: dict[str, Any] = field(default_factory=dict)

    def mark(
        self,
        field_name: str,
        presence: Presence,
        reason: str = "",
        native_field: Optional[str] = None,
        source_adapter: Optional[str] = None,
    ) -> None:
        self.field_provenance[field_name] = FieldProvenance(
            presence=presence,
            reason=reason,
            native_field=native_field,
            source_adapter=source_adapter,
        )

    def presence_of(self, field_name: str) -> Presence:
        p = self.field_provenance.get(field_name)
        if p is not None:
            return p.presence
        # If value is non-None and no explicit mark, treat as PRESENT.
        if getattr(self, field_name, None) is not None:
            return Presence.PRESENT
        return Presence.UNKNOWN

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["side"] = self.side.value if isinstance(self.side, Side) else self.side
        d["field_provenance"] = {
            k: (v.to_dict() if isinstance(v, FieldProvenance) else v)
            for k, v in self.field_provenance.items()
        }
        return d

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "BenchmarkTradeRecord":
        data = dict(raw)
        side = data.get("side", "UNKNOWN")
        if isinstance(side, str):
            data["side"] = Side(side) if side in Side.__members__ else Side.UNKNOWN
        prov_raw = data.pop("field_provenance", {}) or {}
        prov: dict[str, FieldProvenance] = {}
        for k, v in prov_raw.items():
            if isinstance(v, FieldProvenance):
                prov[k] = v
            elif isinstance(v, dict):
                prov[k] = FieldProvenance(
                    presence=Presence(v.get("presence", "UNKNOWN")),
                    reason=str(v.get("reason", "")),
                    native_field=v.get("native_field"),
                    source_adapter=v.get("source_adapter"),
                )
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}
        obj = cls(**filtered)
        obj.field_provenance = prov
        return obj
