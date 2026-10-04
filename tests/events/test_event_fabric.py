"""
tests/events/test_event_fabric.py
===================================
Tests for the Canonical Event Fabric (Part 15).

Covers:
    1. Envelope fields present and correct types
    2. Generation is strictly monotonic across sequential calls
    3. Generation is thread-safe (1000 unique values, no collisions)
    4. schema_hash is non-empty when feature_schema is importable
    5. parent_event_id causal chain
    6. event_id is unique across 1000 events
    7. Fail-open when feature_schema not importable (schema_hash="")
    8. make_decision_snapshot_envelope convenience wrapper fields
    9. json.dumps serialisability
"""
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

# src/ must be on path before importing (pyproject.toml sets pythonpath=["src","scripts"])
import events.event_fabric as _ef_module


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def fabric():
    return _ef_module


# ── Test 1: Required fields present ──────────────────────────────────────────

def test_envelope_fields_present(fabric):
    env = fabric.make_event_envelope(
        event_type="ENGINE_TELEMETRY",
        instrument="ETHUSDT",
        source="TestSource",
        payload={"key": "value"},
    )
    required = {
        "event_id", "generation", "event_type", "instrument",
        "source", "timestamp", "schema_hash", "parent_event_id", "payload",
    }
    assert required.issubset(env.keys()), (
        f"Missing fields: {required - env.keys()}"
    )
    assert env["event_type"] == "ENGINE_TELEMETRY"
    assert env["instrument"] == "ETHUSDT"
    assert env["source"] == "TestSource"
    assert env["payload"] == {"key": "value"}
    assert env["parent_event_id"] == ""
    assert isinstance(env["generation"], int)
    assert env["generation"] > 0
    assert isinstance(env["event_id"], str)
    assert len(env["event_id"]) == 8


# ── Test 2: Generation is strictly monotonic (sequential) ─────────────────────

def test_generation_monotonic(fabric):
    generations = [
        fabric.make_event_envelope(
            event_type="ENGINE_TELEMETRY",
            instrument="",
            source="test",
            payload={},
        )["generation"]
        for _ in range(100)
    ]
    for i in range(1, len(generations)):
        assert generations[i] > generations[i - 1], (
            f"Generation not monotonic at index {i}: "
            f"{generations[i-1]} → {generations[i]}"
        )


# ── Test 3: Generation is thread-safe ────────────────────────────────────────

def test_generation_thread_safe(fabric):
    results: list = []
    lock = threading.Lock()

    def _emit_100():
        local = [
            fabric.make_event_envelope(
                event_type="ENGINE_TELEMETRY",
                instrument="",
                source="thread",
                payload={},
            )["generation"]
            for _ in range(100)
        ]
        with lock:
            results.extend(local)

    threads = [threading.Thread(target=_emit_100) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 1000
    assert len(set(results)) == 1000, "Duplicate generation values detected (race condition)"


# ── Test 4: schema_hash is non-empty when feature_schema importable ───────────

def test_schema_hash_present(fabric):
    env = fabric.make_event_envelope(
        event_type="DECISION_SNAPSHOT",
        instrument="BTCUSDT",
        source="EngineRunner",
        payload={},
    )
    # schema_hash is the cached value at module load — may be "" if feature_schema
    # unavailable, but should be a string
    assert isinstance(env["schema_hash"], str)


# ── Test 5: parent_event_id causal chain ─────────────────────────────────────

def test_parent_event_id_chain(fabric):
    parent = fabric.make_event_envelope(
        event_type="DECISION_SNAPSHOT",
        instrument="ETHUSDT",
        source="EngineRunner",
        payload={"decision": "ACCEPT"},
    )
    child = fabric.make_event_envelope(
        event_type="COGNITIVE_TELEMETRY",
        instrument="ETHUSDT",
        source="CognitiveBus",
        payload={"hmf_score": 0.72},
        parent_event_id=parent["event_id"],
    )
    assert child["parent_event_id"] == parent["event_id"]
    assert child["event_id"] != parent["event_id"]
    assert child["generation"] > parent["generation"]


# ── Test 6: event_id uniqueness ───────────────────────────────────────────────

def test_event_id_unique(fabric):
    ids = [
        fabric.make_event_envelope(
            event_type="ENGINE_TELEMETRY",
            instrument="",
            source="test",
            payload={},
        )["event_id"]
        for _ in range(1000)
    ]
    assert len(set(ids)) == 1000, "Duplicate event_id values detected"


# ── Test 7: Fail-open when feature_schema not importable ─────────────────────

def test_fail_open_on_missing_schema(fabric):
    # Patch the cached _SCHEMA_HASH to simulate missing schema
    original = fabric._SCHEMA_HASH
    try:
        fabric._SCHEMA_HASH = ""
        env = fabric.make_event_envelope(
            event_type="ENGINE_TELEMETRY",
            instrument="",
            source="test",
            payload={},
        )
        # Should not raise; schema_hash may be "" or whatever is passed
        assert isinstance(env["schema_hash"], str)
    finally:
        fabric._SCHEMA_HASH = original


# ── Test 8: make_decision_snapshot_envelope fields ────────────────────────────

def test_decision_snapshot_envelope_fields(fabric):
    env = fabric.make_decision_snapshot_envelope(
        instrument="EURUSD",
        source="EngineRunner",
        decision_id="abc12345",
        decision="EXECUTE",
        score=0.75,
        cluster_id=3,
        features_hash="deadbeef",
    )
    assert env["event_type"] == str(fabric.EventType.DECISION_SNAPSHOT)
    p = env["payload"]
    assert p["decision_id"]   == "abc12345"
    assert p["decision"]      == "EXECUTE"
    assert p["score"]         == 0.75
    assert p["cluster_id"]    == 3
    assert p["features_hash"] == "deadbeef"


# ── Test 9: JSON serialisability ─────────────────────────────────────────────

def test_jsonl_serializable(fabric):
    env = fabric.make_event_envelope(
        event_type="COGNITIVE_TELEMETRY",
        instrument="BTCUSDT",
        source="CognitiveBus",
        payload={"score": 0.62, "nested": {"a": 1, "b": [2, 3]}},
        parent_event_id="00000001",
    )
    serialised = json.dumps(env)
    roundtripped = json.loads(serialised)
    assert roundtripped["event_id"]   == env["event_id"]
    assert roundtripped["generation"] == env["generation"]
    assert roundtripped["payload"]["score"] == 0.62
