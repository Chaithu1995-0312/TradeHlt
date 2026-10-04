"""
tests/replay/test_replay_memory_engine.py
==========================================
Tests for ReplayMemoryEngine (Part 4).

Covers:
    1. Empty logs dir → loaded=True, records=[], no crash
    2. query() with no records → returns _empty_result structure
    3. Cluster stats built correctly from synthetic JSONL
    4. Decay weighting: older records contribute less to win rate
    5. Determinism: same JSONL twice → identical query() results
    6. max_records cap: only max_records kept
    7. run_header lines not counted as records
    8. get_replay_features() returns all 9 required keys
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

import pytest

# Ensure src/ is on path
_SRC = str(Path(__file__).parents[2] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from replay.replay_memory_engine import ReplayMemoryEngine


# ── helpers ───────────────────────────────────────────────────────────────────

_FEATURES_35 = {
    f"feat_{i}": float(i) * 0.01
    for i in range(35)
}

def _make_record(
    outcome: str = "TP_HIT",
    rr: float = 2.0,
    cluster_id: int = 0,
    ts: str = "2026-01-01 00:00:00",
) -> dict:
    return {
        "timestamp":        ts,
        "instrument":       "ETHUSDT",
        "direction":        "long",
        "outcome":          outcome,
        "rr_achieved":      rr,
        "duration_candles": 10,
        "mfe":              0.002,
        "mae":              -0.001,
        "features":         dict(_FEATURES_35),
    }


def _write_jsonl(path: Path, records: list, include_header: bool = True) -> None:
    with path.open("w", encoding="utf-8") as fh:
        if include_header:
            header = {
                "type":       "run_header",
                "run_id":     "test_run",
                "instrument": "ETHUSDT",
                "started_at": "2026-01-01T00:00:00Z",
            }
            fh.write(json.dumps(header) + "\n")
        for rec in records:
            fh.write(json.dumps(rec) + "\n")


# ── Test 1: Empty dir ─────────────────────────────────────────────────────────

def test_load_empty_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = ReplayMemoryEngine(opportunities_dir=tmpdir)
        engine.load()
        assert engine._loaded is True
        assert engine._records == []
        assert engine._cluster_stats == {}


# ── Test 2: query() with no records → _empty_result ─────────────────────────

def test_query_no_records():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = ReplayMemoryEngine(opportunities_dir=tmpdir)
        result = engine.query(feature_vector=[0.0] * 35, cluster_id=0)
        assert "historical_winrate" in result
        assert "matched_cluster"    in result
        assert result["sample_size"] == 0
        assert result["historical_winrate"] == 0.5   # neutral fallback


# ── Test 3: Cluster stats built from synthetic JSONL ─────────────────────────

def test_cluster_stats_built():
    with tempfile.TemporaryDirectory() as tmpdir:
        opp_path = Path(tmpdir) / "ETHUSDT" / "20260101_000000" / "opportunities.jsonl"
        opp_path.parent.mkdir(parents=True)

        records = (
            [_make_record("TP_HIT", 2.0) for _ in range(10)]
            + [_make_record("SL_HIT", -1.0) for _ in range(10)]
        )
        _write_jsonl(opp_path, records)

        engine = ReplayMemoryEngine(
            opportunities_dir=tmpdir,
            min_cluster_samples=5,
        )
        engine.load()

        assert len(engine._records) >= 15   # some may be filtered by staleness
        assert 0 in engine._cluster_stats   # cluster 0 populated


# ── Test 4: Decay weighting ───────────────────────────────────────────────────

def test_decay_weighting():
    """Older records should contribute less to the decayed win rate."""
    with tempfile.TemporaryDirectory() as tmpdir:
        opp_path = Path(tmpdir) / "ETHUSDT" / "r1" / "opportunities.jsonl"
        opp_path.parent.mkdir(parents=True)

        # 5 very old TP_HIT (large age) + 5 fresh SL_HIT
        old_ts  = "2020-01-01 00:00:00"   # very old → low weight
        new_ts  = "2026-05-20 00:00:00"   # recent → high weight

        records = (
            [_make_record("TP_HIT",  2.0, ts=old_ts) for _ in range(5)]
            + [_make_record("SL_HIT", -1.0, ts=new_ts) for _ in range(5)]
        )
        _write_jsonl(opp_path, records)

        engine = ReplayMemoryEngine(
            opportunities_dir=tmpdir,
            min_cluster_samples=3,
            staleness_threshold_days=9999,
        )
        engine.load()
        result = engine.query(feature_vector=[0.0] * 35, cluster_id=0)

        # Decayed win rate should be heavily influenced by recent SL_HITs → < 0.5
        assert result["historical_winrate"] < 0.5, (
            f"Expected decayed win rate < 0.5, got {result['historical_winrate']}"
        )


# ── Test 5: Determinism ───────────────────────────────────────────────────────

def test_determinism():
    with tempfile.TemporaryDirectory() as tmpdir:
        opp_path = Path(tmpdir) / "ETHUSDT" / "r1" / "opportunities.jsonl"
        opp_path.parent.mkdir(parents=True)

        records = [_make_record("TP_HIT", 2.0) for _ in range(20)]
        _write_jsonl(opp_path, records)

        engine1 = ReplayMemoryEngine(opportunities_dir=tmpdir, min_cluster_samples=3)
        engine2 = ReplayMemoryEngine(opportunities_dir=tmpdir, min_cluster_samples=3)

        r1 = engine1.query(feature_vector=[0.1] * 35, cluster_id=0)
        r2 = engine2.query(feature_vector=[0.1] * 35, cluster_id=0)

        assert r1["historical_winrate"] == r2["historical_winrate"]
        assert r1["sample_size"]        == r2["sample_size"]


# ── Test 6: max_records cap ──────────────────────────────────────────────────

def test_max_records_cap():
    with tempfile.TemporaryDirectory() as tmpdir:
        opp_path = Path(tmpdir) / "ETHUSDT" / "r1" / "opportunities.jsonl"
        opp_path.parent.mkdir(parents=True)

        records = [_make_record("TP_HIT", 2.0) for _ in range(100)]
        _write_jsonl(opp_path, records)

        engine = ReplayMemoryEngine(
            opportunities_dir=tmpdir,
            max_records=50,
            min_cluster_samples=1,
        )
        engine.load()
        assert len(engine._records) <= 50


# ── Test 7: run_header not counted as record ──────────────────────────────────

def test_run_header_skipped():
    with tempfile.TemporaryDirectory() as tmpdir:
        opp_path = Path(tmpdir) / "ETHUSDT" / "r1" / "opportunities.jsonl"
        opp_path.parent.mkdir(parents=True)

        records = [_make_record("TP_HIT", 2.0) for _ in range(10)]
        # Write with header (3 headers actually)
        with opp_path.open("w") as fh:
            for _ in range(3):
                fh.write(json.dumps({"type": "run_header", "run_id": "x"}) + "\n")
            for r in records:
                fh.write(json.dumps(r) + "\n")

        engine = ReplayMemoryEngine(
            opportunities_dir=tmpdir,
            min_cluster_samples=1,
        )
        engine.load()
        # Should have at most 10 records, not 13
        assert len(engine._records) <= 10


# ── Test 8: get_replay_features() returns all required keys ──────────────────

def test_replay_features_keys():
    _REQUIRED_KEYS = {
        "historical_winrate",
        "historical_rr",
        "historical_drawdown",
        "cluster_stability",
        "replay_density",
        "failure_frequency",
        "trap_frequency",
        "transition_probability",
        "market_state_entropy",
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = ReplayMemoryEngine(opportunities_dir=tmpdir)
        features = engine.get_replay_features(cluster_id=0)
        missing = _REQUIRED_KEYS - features.keys()
        assert not missing, f"Missing keys in get_replay_features(): {missing}"
