"""Phase 5 — replay and query over PRESERVED identity records only.

Joins are field equality of copied primary keys after Identity Check.
Does not recompute L1/L2 from L0. Does not fold occupancy from events.
Does not import feature_pipeline / encoder / crt_engine.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from identity.check import CheckResult
from identity.store import IdentityStore
from identity.tokens import L0_PK, STATUS_PRESERVED, STATUS_UNIDENTIFIED, STATUS_UNJOINABLE


def l0_key(record: Mapping[str, Any]) -> tuple:
    return tuple(record.get(k) for k in L0_PK)


def l4_key(record: Mapping[str, Any]) -> tuple:
    return l0_key(record) + (
        record.get("direction"),
        record.get("entry_px"),
        record.get("sl_px"),
        record.get("geometry_kind"),
        record.get("geometry_schema"),
    )


def occupancy_series_key(record: Mapping[str, Any]) -> tuple:
    return l0_key(record) + (
        record.get("producer_id"),
        record.get("topology_id"),
        record.get("track_id"),
    )


@dataclass
class BarReplay:
    """PRESERVED objects sharing one L0 PK. Occupancy is not an event fold."""

    l0: CheckResult
    l1: list[dict[str, Any]] = field(default_factory=list)
    l2: list[dict[str, Any]] = field(default_factory=list)
    l3_occupancy: list[dict[str, Any]] = field(default_factory=list)
    l3_events: list[dict[str, Any]] = field(default_factory=list)
    l3_event_series: CheckResult | None = None
    l4: list[dict[str, Any]] = field(default_factory=list)
    l5: list[dict[str, Any]] = field(default_factory=list)
    join: str = STATUS_PRESERVED

    @property
    def recovered(self) -> bool:
        return self.l0.preserved and self.join == STATUS_PRESERVED


class IdentityQuery:
    def __init__(self, store: IdentityStore):
        self.store = store

    def scan_checked(self, layer: str) -> list[CheckResult]:
        return self.store.scan(layer)

    def preserved(self, layer: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for r in self.scan_checked(layer):
            if r.status == STATUS_PRESERVED and r.record is not None:
                out.append(dict(r.record))
        return out

    def at_l0(self, l0_record: Mapping[str, Any]) -> BarReplay:
        """Replay one bar. Requires PRESERVED L0. Children join by copied L0 PK only."""
        l0 = self.store.read("L0", l0_record)
        replay = BarReplay(l0=l0)
        if not l0.preserved:
            replay.join = STATUS_UNIDENTIFIED
            return replay
        key = l0_key(l0.record or l0_record)
        replay.l1 = [r for r in self.preserved("L1") if l0_key(r) == key]
        replay.l2 = [r for r in self.preserved("L2") if l0_key(r) == key]
        replay.l3_occupancy = [r for r in self.preserved("L3_OCCUPANCY") if l0_key(r) == key]
        replay.l3_events = [r for r in self.preserved("L3_EVENT") if l0_key(r) == key]
        if replay.l3_events:
            replay.l3_event_series = self.store.read_event_series(replay.l3_events)
        replay.l4 = [r for r in self.preserved("L4") if l0_key(r) == key]
        replay.l5 = [r for r in self.preserved("L5") if l0_key(r) == key]
        return replay

    def outcomes_for_geometry(self, l4_record: Mapping[str, Any]) -> list[dict[str, Any]]:
        """L5 whose copied L4 PK equals a PRESERVED L4. No trade_id alias."""
        parent = self.store.read("L4", l4_record)
        if not parent.preserved or parent.record is None:
            return []
        want = l4_key(parent.record)
        return [r for r in self.preserved("L5") if l4_key(r) == want]
