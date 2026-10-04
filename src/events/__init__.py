# Canonical Event Fabric — universal event envelope for all cross-component telemetry.
from events.event_fabric import (
    EventType,
    make_event_envelope,
    make_decision_snapshot_envelope,
    current_generation,
)

__all__ = [
    "EventType",
    "make_event_envelope",
    "make_decision_snapshot_envelope",
    "current_generation",
]
