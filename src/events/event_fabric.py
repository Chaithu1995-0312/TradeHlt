"""
event_fabric.py
===============
Canonical Event Fabric for the Tradelatest runtime.

Every cross-component event (decision, cognitive telemetry, engine telemetry,
decision lineage, drift audit) is wrapped in a canonical envelope that provides:
  - event_id       : 8-char hex UUID fragment — unique per event
  - generation     : monotonic per-process counter — total ordering within session
  - event_type     : one of EventType constants — filter/route by type
  - instrument     : symbol (e.g. "ETHUSDT") — filter by instrument
  - source         : originating component name — causal attribution
  - timestamp      : ISO-8601 UTC string
  - schema_hash    : FEATURE_ORDER_HASH at emission time — detect schema drift
  - parent_event_id: event_id of the triggering event (for causal chains)
  - payload        : event-type-specific data

Generation counter is per-process, monotonic, thread-safe.
It is NOT cross-process — do not use it to correlate events across restarts.
Use event_id for correlation; use generation for ordering within one session.

Schema hash: FEATURE_ORDER_HASH from feature_schema.py.
If a downstream record's schema_hash differs from the current FEATURE_ORDER_HASH,
that record was produced under a different schema — truncation or retraining needed.

Usage:
    from events.event_fabric import make_event_envelope, EventType
    record = make_event_envelope(
        event_type      = EventType.DECISION_SNAPSHOT,
        instrument      = "ETHUSDT",
        source          = "EngineRunner",
        payload         = {"decision": "ACCEPT", "score": 0.72},
        parent_event_id = "",
    )
    # record["event_id"], record["generation"], record["schema_hash"] all populated

Architectural invariants:
  1. Every cross-component JSONL write uses make_event_envelope().
  2. generation is strictly monotonic within one process lifetime.
  3. parent_event_id creates causal chains (COGNITIVE_TELEMETRY → DECISION_SNAPSHOT).
  4. schema_hash is the passive drift detector — no code path checks it at runtime;
     offline audit tools compare it against the current FEATURE_ORDER_HASH.
  5. event_fabric is always enabled — no kill switch.
"""
from __future__ import annotations

import threading
import time
import uuid as _uuid
from enum import Enum
from typing import Optional


# ── Event type constants ──────────────────────────────────────────────────────

class EventType(str, Enum):
    DECISION_SNAPSHOT       = "DECISION_SNAPSHOT"
    COGNITIVE_TELEMETRY     = "COGNITIVE_TELEMETRY"
    ENGINE_TELEMETRY        = "ENGINE_TELEMETRY"
    DECISION_LINEAGE        = "DECISION_LINEAGE"
    DRIFT_AUDIT             = "DRIFT_AUDIT"
    REPLAY_QUERY            = "REPLAY_QUERY"
    FEATURE_SNAPSHOT        = "FEATURE_SNAPSHOT"
    REGIME_CLASSIFICATION   = "REGIME_CLASSIFICATION"
    QUEUE_HEALTH            = "QUEUE_HEALTH"   # CognitiveBus health snapshots
    TRADE_LIFECYCLE         = "TRADE_LIFECYCLE"  # M1: trade ENTRY/EXIT/REJECT (enveloped dual-write)
    STATE_TRANSITION        = "STATE_TRANSITION"  # M2: CRT state-machine transitions (enveloped dual-write)


# ── Thread-safe generation counter ───────────────────────────────────────────

class _GenerationCounter:
    """
    Thread-safe monotonic integer counter.
    Each call to next() returns a unique, strictly-increasing generation value.
    Per-process; NOT persistent across restarts.
    """
    def __init__(self) -> None:
        self._lock  = threading.Lock()
        self._value = 0

    def next(self) -> int:
        with self._lock:
            self._value += 1
            return self._value

    @property
    def current(self) -> int:
        return self._value


# Module-level singleton — one per process
_GENERATION = _GenerationCounter()


def current_generation() -> int:
    """Return the current generation value without incrementing."""
    return _GENERATION.current


# ── Schema hash resolver ──────────────────────────────────────────────────────

def _resolve_schema_hash() -> str:
    """Return FEATURE_ORDER_HASH from feature_schema. Fail-open: '' on ImportError."""
    try:
        from features.feature_schema import FEATURE_ORDER_HASH  # noqa: PLC0415
        return FEATURE_ORDER_HASH
    except Exception:
        return ""


# Cached at module load time — fixed for the process lifetime.
_SCHEMA_HASH: str = _resolve_schema_hash()


# ── Public API ────────────────────────────────────────────────────────────────

def make_event_envelope(
    event_type:       str,
    instrument:       str,
    source:           str,
    payload:          dict,
    schema_hash:      str = "",
    parent_event_id:  str = "",
) -> dict:
    """
    Create a canonical event envelope.

    Parameters
    ----------
    event_type       : EventType constant (or raw string for forward compat)
    instrument       : instrument symbol (e.g. "ETHUSDT"; "" for system-level events)
    source           : originating component name (e.g. "EngineRunner", "CognitiveBus")
    payload          : event-specific data dict (caller-owned; not deep-copied)
    schema_hash      : FEATURE_ORDER_HASH — auto-filled from cached module value if ""
    parent_event_id  : event_id of the triggering parent event ("" = root event)

    Returns
    -------
    dict — canonical event record; json.dumps()-safe when payload is json-safe.

    Performance note:
    make_event_envelope() is O(1) — uuid hex + lock acquire/release + strftime.
    Execution plane impact: < 1 μs on modern hardware. Safe to call per-bar.
    """
    return {
        "event_id":        _uuid.uuid4().hex[:8],
        "generation":      _GENERATION.next(),
        "event_type":      str(event_type),
        "instrument":      instrument,
        "source":          source,
        "timestamp":       time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "schema_hash":     schema_hash if schema_hash else _SCHEMA_HASH,
        "parent_event_id": parent_event_id,
        "payload":         payload,
    }


def make_decision_snapshot_envelope(
    instrument:    str,
    source:        str,
    decision_id:   str,
    decision:      str,
    score:         float,
    cluster_id:    int,
    features_hash: str = "",
) -> dict:
    """
    Convenience wrapper for DECISION_SNAPSHOT events.

    Parameters
    ----------
    features_hash : optional SHA-256[:8] of the canonical feature vector values
                    (distinct from schema_hash which hashes feature *names*).
                    Used to detect identical market states across sessions.
    """
    return make_event_envelope(
        event_type = EventType.DECISION_SNAPSHOT,
        instrument = instrument,
        source     = source,
        payload    = {
            "decision_id":   decision_id,
            "decision":      decision,
            "score":         round(float(score), 4),
            "cluster_id":    int(cluster_id),
            "features_hash": features_hash,
        },
    )
