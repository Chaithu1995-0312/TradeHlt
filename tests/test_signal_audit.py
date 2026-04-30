"""
tests/test_signal_audit.py

Tests for core/signal_audit.py — SignalAuditRecorder.
"""

import json
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.signal_audit import SignalAuditRecorder


# ──────────────────────────────────────────────────────────────────────────────
# Test 3: Full bar lifecycle writes one valid JSON line
# ──────────────────────────────────────────────────────────────────────────────

def test_audit_recorder_full_lifecycle(tmp_path):
    log_path = str(tmp_path / "audit.jsonl")
    recorder = SignalAuditRecorder(debug_mode=True, log_path=log_path)

    recorder.start_bar("bar_001", "2026-04-09T10:00:00Z", 1.2345)
    recorder.record_zone({"passed": True, "score": 0.72, "reason": "zone_passed"})
    recorder.record_engines({
        "crt":      {"score": 0.60},
        "gaussian": {"score": 0.55},
        "zone_gate":{"score": 0.72},
        "rr":       {"score": 0.65},
    })
    recorder.record_fusion({"final_score": 0.62, "variance": 0.02, "entropy": 1.1})
    recorder.record_risk({"decision": "approve", "risk_reason": "ok"})
    recorder.finalize("execute", "all_conditions_met")
    recorder.flush()

    lines = open(log_path, encoding="utf-8").readlines()
    assert len(lines) == 1, "Exactly one JSON line expected per bar"

    record = json.loads(lines[0])
    assert record["bar_id"]   == "bar_001"
    assert record["price"]    == pytest.approx(1.2345)
    assert record["decision"] == "execute"
    assert record["reason"]   == "all_conditions_met"
    assert "zone"    in record
    assert "engines" in record
    assert "fusion"  in record
    assert "risk"    in record
    assert record["zone"]["passed"] is True


# ──────────────────────────────────────────────────────────────────────────────
# Test 4: Leak detection triggers when zone pass rate > 80%
# ──────────────────────────────────────────────────────────────────────────────

def test_audit_leak_detection_triggers(tmp_path):
    recorder = SignalAuditRecorder(
        debug_mode=True,
        log_path=str(tmp_path / "audit.jsonl"),
    )

    for i in range(100):
        recorder.start_bar(str(i), "", 1.0)
        recorder.record_zone({"passed": True, "score": 0.9})
        recorder.record_fusion({"final_score": 0.7})
        recorder.finalize("reject", "low_score")
        recorder.flush()

    warnings = recorder.check_leak_rates()
    assert any("zone" in w.lower() for w in warnings), \
        f"Expected zone leak warning, got: {warnings}"


# ──────────────────────────────────────────────────────────────────────────────
# Test 5: debug_mode=False → zero overhead (no file, no side-effects)
# ──────────────────────────────────────────────────────────────────────────────

def test_audit_noop_when_debug_false(tmp_path):
    log_path = str(tmp_path / "audit.jsonl")
    recorder = SignalAuditRecorder(debug_mode=False, log_path=log_path)

    recorder.start_bar("x", "2026-01-01", 1.0)
    recorder.record_zone({"passed": True, "score": 0.8})
    recorder.record_engines({"crt": {"score": 0.7}})
    recorder.record_fusion({"final_score": 0.75})
    recorder.finalize("execute", "ok")
    recorder.flush()

    # No file should be written
    assert not os.path.exists(log_path), "No file should be created when debug_mode=False"
    # Internal state should stay empty
    assert recorder._current == {}


# ──────────────────────────────────────────────────────────────────────────────
# Test: Multiple bars — each gets its own line
# ──────────────────────────────────────────────────────────────────────────────

def test_audit_multiple_bars_appended(tmp_path):
    log_path = str(tmp_path / "audit.jsonl")
    recorder = SignalAuditRecorder(debug_mode=True, log_path=log_path)

    for i in range(5):
        recorder.start_bar(f"bar_{i:03d}", "", float(i))
        recorder.finalize("reject", "test")
        recorder.flush()

    lines = open(log_path, encoding="utf-8").readlines()
    assert len(lines) == 5

    ids = [json.loads(l)["bar_id"] for l in lines]
    assert ids == [f"bar_{i:03d}" for i in range(5)]


# ──────────────────────────────────────────────────────────────────────────────
# Test: flush() on empty _current does not write a line
# ──────────────────────────────────────────────────────────────────────────────

def test_flush_without_start_bar_is_noop(tmp_path):
    log_path = str(tmp_path / "audit.jsonl")
    recorder = SignalAuditRecorder(debug_mode=True, log_path=log_path)
    recorder.flush()  # no start_bar called

    if os.path.exists(log_path):
        assert open(log_path).read() == ""


# ──────────────────────────────────────────────────────────────────────────────
# Test: summary() returns correct counts
# ──────────────────────────────────────────────────────────────────────────────

def test_summary_counts(tmp_path):
    recorder = SignalAuditRecorder(
        debug_mode=True,
        log_path=str(tmp_path / "audit.jsonl"),
    )

    for i in range(10):
        recorder.start_bar(str(i), "", 1.0)
        recorder.record_zone({"passed": True, "score": 0.8})
        recorder.record_fusion({"final_score": 0.7})
        recorder.finalize("execute" if i < 3 else "reject", "test")
        recorder.flush()

    s = recorder.summary()
    assert s["total_bars"]  == 10
    assert s["zone_passes"] == 10   # all zones passed
    assert s["trade_count"] == 3
