"""Synthetic BC-4 volume-semantics scorer tests -- no live MT5.

Mirrors the BC-2 floor's discipline: synthetic-cannot-prove, one report shape, and the
two verdicts (volume_semantic_verdict / artifact_binding / h_real_status) kept separate
rather than collapsed into one flag.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from research.ohlcv_probe_report import SOURCE_LIVE, SOURCE_SYNTHETIC
from research.ohlcv_volume_semantics import (
    BINDING_BOUND,
    BINDING_CONTRADICTED,
    BINDING_NOT_TESTED,
    BINDING_UNCONFIRMED,
    FRESHNESS_SECONDS,
    H_REAL_NOT_REJECTED,
    H_REAL_NOT_TESTED,
    H_REAL_REJECTED,
    MIN_TEST1_BARS,
    VERDICT_APPROXIMATE,
    VERDICT_CONFIRMED,
    VERDICT_CONTRADICTED,
    VERDICT_INSUFFICIENT,
    ProbeSnapshot,
    _score_test1,
    _score_test2,
    score_volume_semantics,
)

UTC = timezone.utc
NOW = datetime(2026, 9, 2, 23, 0, 0, tzinfo=UTC)


def _bar(minutes_before_close: int, tick_volume: int, ticks_all, real_volume: int = 0) -> dict:
    close_t = NOW - timedelta(minutes=minutes_before_close)
    T = close_t - timedelta(minutes=15)
    return {
        "T": T,
        "tick_volume": tick_volume,
        "real_volume": real_volume,
        "ticks_all": ticks_all,
    }


# ── Test 1: semantic identity ───────────────────────────────────────────────────
def test_exact_match_confirms():
    bars = [_bar(m, 1000 + m, 1000 + m) for m in (5, 20, 35)]
    r = _score_test1(bars, now_broker=NOW)
    assert r["volume_semantic_verdict"] == VERDICT_CONFIRMED
    assert r["test1_exact_match_rate"] == 1.0
    assert r["h_real_status"] == H_REAL_REJECTED  # real_volume=0 on every bar


def test_small_directional_gap_is_approximate_not_confirmed():
    bars = [_bar(m, 1000, 1005) for m in (5, 20, 35)]  # ticks_all slightly > tick_volume
    r = _score_test1(bars, now_broker=NOW)
    assert r["volume_semantic_verdict"] == VERDICT_APPROXIMATE
    assert r["volume_semantic_verdict"] != VERDICT_CONFIRMED


def test_large_mismatch_contradicts():
    bars = [_bar(m, 1000, 50) for m in (5, 20, 35)]
    r = _score_test1(bars, now_broker=NOW)
    assert r["volume_semantic_verdict"] == VERDICT_CONTRADICTED


def test_fewer_than_min_bars_is_insufficient():
    bars = [_bar(5, 1000, 1000)]
    r = _score_test1(bars, now_broker=NOW)
    assert len(bars) < MIN_TEST1_BARS
    assert r["volume_semantic_verdict"] == VERDICT_INSUFFICIENT
    assert r["h_real_status"] == H_REAL_NOT_TESTED


def test_stale_bars_outside_freshness_window_are_dropped():
    # bars older than FRESHNESS_SECONDS must not be scored, even if ticks_all is present
    stale_minutes = FRESHNESS_SECONDS // 60 + 30
    bars = [_bar(stale_minutes, 1000, 1000) for _ in range(5)]
    r = _score_test1(bars, now_broker=NOW)
    assert r["volume_semantic_verdict"] == VERDICT_INSUFFICIENT
    assert r["test1_n_scored"] == 0


def test_bars_missing_ticks_all_are_dropped():
    bars = [_bar(m, 1000, None) for m in (5, 20, 35)]
    r = _score_test1(bars, now_broker=NOW)
    assert r["volume_semantic_verdict"] == VERDICT_INSUFFICIENT
    assert r["test1_n_scored"] == 0


def test_h_real_not_rejected_when_real_volume_present():
    bars = [_bar(m, 1000, 1000, real_volume=50) for m in (5, 20, 35)]
    r = _score_test1(bars, now_broker=NOW)
    assert r["h_real_status"] == H_REAL_NOT_REJECTED


# ── Test 2: artifact binding ────────────────────────────────────────────────────
def test_exact_binding_is_bound():
    samples = [{"T": "x", "frozen_volume": v, "refetched_tick_volume": v} for v in (100, 200, 300)]
    r = _score_test2(samples)
    assert r["artifact_binding"] == BINDING_BOUND


def test_constant_offset_is_contradicted():
    samples = [
        {"T": "x", "frozen_volume": v, "refetched_tick_volume": v + 7} for v in (100, 200, 300)
    ]
    r = _score_test2(samples)
    assert r["artifact_binding"] == BINDING_CONTRADICTED
    assert "offset" in r["test2_reason"]


def test_scattered_mismatch_is_unconfirmed_not_contradicted():
    samples = [
        {"T": "x", "frozen_volume": 100, "refetched_tick_volume": 103},
        {"T": "x", "frozen_volume": 200, "refetched_tick_volume": 198},
        {"T": "x", "frozen_volume": 300, "refetched_tick_volume": 305},
    ]
    r = _score_test2(samples)
    assert r["artifact_binding"] == BINDING_UNCONFIRMED


def test_no_refetched_bars_is_not_tested():
    samples = [{"T": "x", "frozen_volume": 100, "refetched_tick_volume": None}]
    r = _score_test2(samples)
    assert r["artifact_binding"] == BINDING_NOT_TESTED


# ── D3-equivalent: synthetic fixtures never flip governance ────────────────────
def test_synthetic_confirmed_is_not_executable_proof():
    snap = ProbeSnapshot(
        fetched_at=NOW,
        symbol="XAUUSD",
        source=SOURCE_SYNTHETIC,
        payload={
            "test1_bars": [_bar(m, 1000, 1000) for m in (5, 20, 35)],
            "test2_samples": [],
        },
    )
    r = score_volume_semantics(snap, now_broker=NOW, verify_admitted=False)
    assert r["volume_semantic_verdict"] == VERDICT_CONFIRMED
    assert r["source_a"] == SOURCE_SYNTHETIC
    assert r["executable_volume_semantic_proof"] is False


def test_live_confirmed_without_admitted_match_is_not_proof():
    snap = ProbeSnapshot(
        fetched_at=NOW,
        symbol="XAUUSD",
        source=SOURCE_LIVE,
        wall_clock_skew_seconds=-10800.0,
        payload={
            "test1_bars": [_bar(m, 1000, 1000) for m in (5, 20, 35)],
            "test2_samples": [],
        },
    )
    r = score_volume_semantics(snap, now_broker=NOW, verify_admitted=False)
    assert r["volume_semantic_verdict"] == VERDICT_CONFIRMED
    assert r["admitted_sha256_match"] is None
    assert r["executable_volume_semantic_proof"] is False


# ── staleness guard (shared module) ─────────────────────────────────────────────
def test_stale_live_snapshot_is_insufficient():
    from research.ohlcv_probe_report import STALE_THRESHOLD_SECONDS

    snap = ProbeSnapshot(
        fetched_at=NOW,
        symbol="XAUUSD",
        source=SOURCE_LIVE,
        wall_clock_skew_seconds=float(STALE_THRESHOLD_SECONDS + 1),
        payload={"test1_bars": [_bar(m, 1000, 1000) for m in (5, 20, 35)], "test2_samples": []},
    )
    r = score_volume_semantics(snap, now_broker=NOW, verify_admitted=False)
    assert r["volume_semantic_verdict"] == VERDICT_INSUFFICIENT
    assert "stale_feed" in r["test1_reason"]


def test_healthy_broker_offset_is_not_stale():
    snap = ProbeSnapshot(
        fetched_at=NOW,
        symbol="XAUUSD",
        source=SOURCE_LIVE,
        wall_clock_skew_seconds=-10799.0,  # measured, healthy UTC+3 offset
        payload={"test1_bars": [_bar(m, 1000, 1000) for m in (5, 20, 35)], "test2_samples": []},
    )
    r = score_volume_semantics(snap, now_broker=NOW, verify_admitted=False)
    assert r["volume_semantic_verdict"] == VERDICT_CONFIRMED


# ── two verdicts stay separate, never collapsed into one flag (D1-equivalent) ──
def test_verdicts_are_reported_independently():
    snap = ProbeSnapshot(
        fetched_at=NOW,
        symbol="XAUUSD",
        source=SOURCE_SYNTHETIC,
        payload={
            "test1_bars": [_bar(m, 1000, 50) for m in (5, 20, 35)],  # -> CONTRADICTED
            "test2_samples": [
                {"T": "x", "frozen_volume": v, "refetched_tick_volume": v} for v in (1, 2, 3)
            ],  # -> BOUND
        },
    )
    r = score_volume_semantics(snap, now_broker=NOW, verify_admitted=False)
    assert r["volume_semantic_verdict"] == VERDICT_CONTRADICTED
    assert r["artifact_binding"] == BINDING_BOUND
    # a CONTRADICTED semantic verdict must not silently downgrade an independently BOUND binding
