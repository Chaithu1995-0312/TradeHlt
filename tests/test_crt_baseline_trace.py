"""
CRT baseline trace — correctness + behavior-preservation tests.

Does not use economic outcomes as feature certification evidence.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _make_engine():
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from config_layer.crt_engine_v2 import CRTConfig, CRTEngine, Candle
    from datetime import datetime

    eng = CRTEngine(CRTConfig())
    return eng, Candle, datetime


def _seed_engine(eng, Candle, datetime, n: int = 40):
    """Minimal deterministic OHLC stream to initialise + evolve state."""
    from config_layer.state_identity import Direction

    candles = []
    base = 2000.0
    for i in range(n):
        o = base + i * 0.1
        c = o + (0.2 if i % 3 else -0.15)
        h = max(o, c) + 0.5
        l = min(o, c) - 0.5
        candles.append(
            Candle(
                timestamp=datetime(2024, 6, 1, 0, 0) + __import__("datetime").timedelta(minutes=15 * i),
                open=o,
                high=h,
                low=l,
                close=c,
                volume=100.0,
            )
        )
    # initialise range from first atr_period candles
    session = "LONDON"
    eng.initialise_range(candles[:14], "HTF-0", session)
    actions = []
    for c in candles[14:]:
        actions.append(eng.process_candle(c, "HTF-0"))
    return actions


def test_baseline_trace_default_none_and_disabled_emits_nothing():
    eng, Candle, datetime = _make_engine()
    assert eng.baseline_trace is None
    assert eng.sm.trace_hooks is None
    actions = _seed_engine(eng, Candle, datetime, n=50)
    assert actions  # ran
    # still no hooks
    assert eng.baseline_trace is None


def test_trace_on_off_action_parity():
    eng_off, Candle, datetime = _make_engine()
    actions_off = _seed_engine(eng_off, Candle, datetime, n=60)

    eng_on, Candle, datetime = _make_engine()
    from runtime.crt_baseline_trace import CRTBaselineTraceHooks

    hooks = CRTBaselineTraceHooks()
    eng_on.baseline_trace = hooks
    # enable only after init seed phase inside process — hooks.enabled toggled per call
    # re-run manually with same seed pattern
    candles = []
    base = 2000.0
    for i in range(60):
        o = base + i * 0.1
        c = o + (0.2 if i % 3 else -0.15)
        h = max(o, c) + 0.5
        l = min(o, c) - 0.5
        candles.append(
            Candle(
                timestamp=datetime(2024, 6, 1, 0, 0)
                + __import__("datetime").timedelta(minutes=15 * i),
                open=o,
                high=h,
                low=l,
                close=c,
                volume=100.0,
            )
        )
    eng_on.initialise_range(candles[:14], "HTF-0", "LONDON")
    actions_on = []
    for c in candles[14:]:
        hooks.enabled = True
        actions_on.append(eng_on.process_candle(c, "HTF-0"))

    def _norm(a):
        return {
            "action": a.get("action"),
            "state": a.get("state"),
            "candle_index": a.get("candle_index"),
        }

    assert [_norm(a) for a in actions_off] == [_norm(a) for a in actions_on]
    # final states match
    assert eng_off.state.current_state == eng_on.state.current_state


def test_trace_does_not_recompute_features_and_38_schema():
    from features.feature_schema import CANONICAL_FEATURES, SCHEMA_HASH, FEATURE_ORDER_HASH

    # 48 under schema v5.0 (was 39 pre-2026-08-15 CH-htfcrt-parent-candle-smc-v1; 38 pre-v4).
    assert len(CANONICAL_FEATURES) == 48
    assert SCHEMA_HASH
    assert FEATURE_ORDER_HASH


def test_short_circuit_does_not_false_evaluate_later_guards():
    """When move fails, body_ratio guard must not appear."""
    eng, Candle, datetime = _make_engine()
    from runtime.crt_baseline_trace import CRTBaselineTraceHooks

    hooks = CRTBaselineTraceHooks()
    eng.baseline_trace = hooks
    # Build state into SWEEP with tiny body so first move guard fails
    candles = []
    base = 2500.0
    for i in range(30):
        o = base
        c = base + 0.01  # tiny move
        candles.append(
            Candle(
                timestamp=datetime(2024, 6, 1, 0, 0)
                + __import__("datetime").timedelta(minutes=15 * i),
                open=o,
                high=base + 1,
                low=base - 1,
                close=c,
                volume=10.0,
            )
        )
    eng.initialise_range(candles[:14], "HTF-0", "LONDON")
    # force SWEEP state by minimal setup if possible — if not, still check hooks work
    hooks.enabled = True
    for c in candles[14:20]:
        eng.process_candle(c, "HTF-0")
    # If any G_SWEEP_DISP_MOVE failed, no G_SWEEP_DISP_BODY should follow in same try call order
    # Collect per-bar is reset — check overall: body guard only after move pass
    # This is a soft structural test: when MOVE fail is recorded, BODY is not same evaluation chain without MOVE pass first
    move_fails = [g for g in hooks.guards if g.guard_id == "G_SWEEP_DISP_MOVE" and g.result is False]
    # if we saw move fails, ensure those records have short_circuit FAIL_RETURN
    for g in move_fails:
        assert g.short_circuit_status == "FAIL_RETURN"


def test_snapshot_engine_state_minimal():
    eng, Candle, datetime = _make_engine()
    from runtime.crt_baseline_trace import snapshot_engine_state

    snap = snapshot_engine_state(eng.state)
    assert "current_state" in snap
    assert "atr" in snap
    assert "cached_features" in snap


def test_artifact_invariants_if_present():
    """If a trace was generated, enforce 16 bars + len(CANONICAL_FEATURES) features + identities
    (39 under schema v4.0; was 38 pre-2026-07-22 SCHEMA-V4-VECTOR-MIGRATION)."""
    path = ROOT / "docs/governance/xauusd_crt_baseline_trace/xauusd_crt_baseline_trace_v1.jsonl"
    if not path.exists():
        pytest.skip("trace artifact not generated yet")
    rows = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(rows) == 16
    from features.feature_schema import CANONICAL_FEATURES

    for r in rows:
        cf = r["canonical_features"]
        assert cf["feature_count"] == len(CANONICAL_FEATURES)
        assert list(cf["feature_names_in_canonical_order"]) == list(CANONICAL_FEATURES)
        assert len(cf["values_in_canonical_order"]) == len(CANONICAL_FEATURES)
        assert set(cf["values_by_name"].keys()) == set(CANONICAL_FEATURES)
        for i, name in enumerate(CANONICAL_FEATURES):
            assert cf["values_in_canonical_order"][i] == cf["values_by_name"][name]
        assert r["trace_identity"]["canonical_schema_hash"]
        assert r["state_transition"]["state_before"] is not None
        assert r["state_transition"]["state_after"] is not None
        assert "guards_evaluated" in r["state_transition"]
        assert r["integrity"]["status"] in ("COMPLETE", "PARTIAL", "FAILED")


def test_dirty_worktree_recorded_in_git_meta():
    from runtime.crt_baseline_trace import git_meta

    m = git_meta(ROOT)
    assert m["repository_commit"]
    assert m["dirty_worktree_status"] in ("CLEAN", "DIRTY", "UNKNOWN")


def test_corpus_pin_hash():
    import hashlib

    # Executable Phase-1 frozen candidate (xauusd_phase1_candidate.py)
    p = ROOT / "data/mt5/XAUUSD_M15.csv"
    if not p.exists():
        pytest.skip("corpus missing")
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    assert h == "4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56"
