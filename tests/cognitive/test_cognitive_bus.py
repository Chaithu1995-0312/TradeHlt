"""
tests/cognitive/test_cognitive_bus.py
======================================
Tests for CognitiveBus (Part 11).

Covers:
    1. emit() is non-blocking (returns immediately even when engines slow)
    2. Drop telemetry: dropped_events incremented when queue is full
    3. health() returns all required keys
    4. Backpressure flag set when drop_rate > 5%
    5. Daemon thread lifecycle: start()/stop()
    6. DecisionSnapshot carries event_id, generation, schema_hash fields
"""
from __future__ import annotations

import sys
import time
import queue
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_SRC = str(Path(__file__).parents[2] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from cognitive.cognitive_bus import CognitiveBus, DecisionSnapshot


def _make_snapshot(**overrides) -> DecisionSnapshot:
    defaults = dict(
        decision_id     = "test0001",
        event_id        = "abcd1234",
        generation      = 1,
        timestamp       = "2026-05-20T00:00:00Z",
        instrument      = "ETHUSDT",
        schema_hash     = "abc123ef12345678",
        features        = {},
        zone_result     = {},
        gaussian_result = {},
        rr_result       = {},
        fusion_result   = {},
        decision        = "EXECUTE",
        cluster_id      = 0,
    )
    defaults.update(overrides)
    return DecisionSnapshot(**defaults)


def _make_bus(config: dict = None) -> CognitiveBus:
    return CognitiveBus(config or {})


# ── Test 1: emit() is non-blocking ───────────────────────────────────────────

def test_emit_nonblocking():
    bus = _make_bus()
    snap = _make_snapshot()
    t0 = time.monotonic()
    bus.emit(snap)
    elapsed_ms = (time.monotonic() - t0) * 1000
    assert elapsed_ms < 50, (
        f"emit() took {elapsed_ms:.1f}ms — expected < 50ms (non-blocking)"
    )


# ── Test 2: Drop telemetry when queue is full ─────────────────────────────────

def test_drop_telemetry():
    """Fill the queue so the next emit() is a drop."""
    bus = _make_bus()
    snap = _make_snapshot()

    # Fill queue to maxsize
    for _ in range(bus._q.maxsize):
        try:
            bus._q.put_nowait(snap)
        except queue.Full:
            break

    dropped_before = bus._dropped_events
    bus.emit(snap)   # should drop (queue full)
    assert bus._dropped_events == dropped_before + 1, (
        "Expected _dropped_events to increment when queue is full"
    )
    assert bus._total_emitted > 0


# ── Test 3: health() returns required keys ────────────────────────────────────

def test_health_keys():
    bus = _make_bus()
    bus.emit(_make_snapshot())
    health = bus.health()
    required = {"total_emitted", "dropped_events", "drop_rate", "queue_size", "backpressure"}
    missing = required - health.keys()
    assert not missing, f"health() missing keys: {missing}"
    assert isinstance(health["drop_rate"],    float)
    assert isinstance(health["backpressure"], bool)
    assert isinstance(health["queue_size"],   int)


# ── Test 4: Backpressure flag when drop_rate > 5% ────────────────────────────

def test_backpressure_flag():
    bus = _make_bus()
    snap = _make_snapshot()

    # Manually set counters to simulate > 5% drop rate
    bus._total_emitted  = 100
    bus._dropped_events = 10   # 10% drop rate

    health = bus.health()
    assert health["backpressure"] is True, (
        f"Expected backpressure=True at 10% drop rate, got: {health}"
    )


# ── Test 5: Daemon thread lifecycle ───────────────────────────────────────────

def test_daemon_lifecycle():
    bus = _make_bus()
    assert bus._thread is None
    assert not bus._running

    bus.start()
    assert bus._running is True
    assert bus._thread is not None
    assert bus._thread.daemon is True, "CognitiveBus thread must be daemon=True"
    assert bus._thread.is_alive()

    bus.stop()
    # Give the thread a moment to stop
    bus._thread.join(timeout=2.0)
    assert not bus._thread.is_alive() or not bus._running


# ── Test 6: DecisionSnapshot required fields ──────────────────────────────────

def test_decision_snapshot_fields():
    snap = _make_snapshot()
    assert hasattr(snap, "event_id"),    "DecisionSnapshot missing event_id"
    assert hasattr(snap, "generation"),  "DecisionSnapshot missing generation"
    assert hasattr(snap, "schema_hash"), "DecisionSnapshot missing schema_hash"
    assert snap.event_id    == "abcd1234"
    assert snap.generation  == 1
    assert snap.schema_hash == "abc123ef12345678"
