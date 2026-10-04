"""
tests/replay/test_replay_similarity_index.py
=============================================
Tests for ReplaySimilarityIndex (Part 5).

Covers:
    1. Self-similarity: query with same vector → score ≈ 1.0 (before decay)
    2. Decay reduces older matches vs. fresh ones
    3. Cluster filter restricts results to matching cluster_id
    4. Empty index → search() returns []
    5. aggregate_top_k_stats() computes correct win_rate from known labels
    6. Linear and FAISS paths give similar results (if FAISS available)
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

_SRC = str(Path(__file__).parents[2] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from replay.replay_similarity_index import ReplaySimilarityIndex


_N = 10   # feature dimension for tests


def _make_index(*records) -> ReplaySimilarityIndex:
    """Helper: build a fresh index with given (vector, metadata) tuples."""
    idx = ReplaySimilarityIndex(n_features=_N, top_k=5, use_faiss=False)
    for vec, meta in records:
        idx.add_record(vec, meta)
    idx.build_index()
    return idx


# ── Test 1: Self-similarity ───────────────────────────────────────────────────

def test_cosine_self_similarity():
    vec = [0.1 * i for i in range(1, _N + 1)]
    meta = {"rr": 2.0, "cluster_id": 0, "age_days": 0.0, "outcome": "TP_HIT"}
    idx = _make_index((vec, meta))
    results = idx.search(vec, method="cosine")
    assert len(results) == 1
    score, _ = results[0]
    # decay = exp(0) = 1.0; cosine of identical vectors = 1.0
    assert abs(score - 1.0) < 1e-4, f"Expected ~1.0, got {score}"


# ── Test 2: Decay reduces older matches ──────────────────────────────────────

def test_decay_reduces_old_matches():
    vec = [1.0] * _N
    fresh_meta  = {"rr": 2.0, "cluster_id": 0, "age_days": 0.0,  "outcome": "TP_HIT"}
    old_meta    = {"rr": 2.0, "cluster_id": 0, "age_days": 90.0, "outcome": "TP_HIT"}

    fresh_idx = _make_index((vec, fresh_meta))
    old_idx   = _make_index((vec, old_meta))

    fresh_score, _ = fresh_idx.search(vec)[0]
    old_score,   _ = old_idx.search(vec)[0]

    assert fresh_score > old_score, (
        f"Expected fresh score ({fresh_score:.4f}) > old score ({old_score:.4f})"
    )


# ── Test 3: Cluster filter ────────────────────────────────────────────────────

def test_cluster_filter():
    vec = [1.0] * _N
    meta_0 = {"rr": 2.0, "cluster_id": 0, "age_days": 0.0, "outcome": "TP_HIT"}
    meta_1 = {"rr": 2.0, "cluster_id": 1, "age_days": 0.0, "outcome": "TP_HIT"}

    idx = _make_index((vec, meta_0), (vec, meta_1))

    results_0 = idx.search(vec, cluster_filter=0)
    results_1 = idx.search(vec, cluster_filter=1)

    assert all(m["cluster_id"] == 0 for _, m in results_0), \
        "cluster_filter=0 returned records from other clusters"
    assert all(m["cluster_id"] == 1 for _, m in results_1), \
        "cluster_filter=1 returned records from other clusters"


# ── Test 4: Empty index ───────────────────────────────────────────────────────

def test_empty_index():
    idx = ReplaySimilarityIndex(n_features=_N)
    results = idx.search([0.5] * _N)
    assert results == []


# ── Test 5: aggregate_top_k_stats ────────────────────────────────────────────

def test_aggregate_stats():
    # 3 wins (rr=2.0) + 2 losses (rr=-1.0), equal weights (age=0)
    vec = [1.0] * _N
    records = [
        (vec, {"rr": 2.0,  "cluster_id": 0, "age_days": 0.0, "outcome": "TP_HIT"}),
        (vec, {"rr": 2.0,  "cluster_id": 0, "age_days": 0.0, "outcome": "TP_HIT"}),
        (vec, {"rr": 2.0,  "cluster_id": 0, "age_days": 0.0, "outcome": "TP_HIT"}),
        (vec, {"rr": -1.0, "cluster_id": 0, "age_days": 0.0, "outcome": "SL_HIT"}),
        (vec, {"rr": -1.0, "cluster_id": 0, "age_days": 0.0, "outcome": "SL_HIT"}),
    ]
    idx = _make_index(*records)
    results = idx.search(vec)
    stats = idx.aggregate_top_k_stats(results)

    assert stats["n_matched"] == 5
    assert abs(stats["win_rate"] - 0.60) < 0.05, (
        f"Expected win_rate ≈ 0.60, got {stats['win_rate']}"
    )
    # mean_rr ≈ (3×2 + 2×-1) / 5 = 4/5 = 0.8
    assert abs(stats["mean_rr"] - 0.8) < 0.1, (
        f"Expected mean_rr ≈ 0.8, got {stats['mean_rr']}"
    )


# ── Test 6: FAISS / NumPy parity ─────────────────────────────────────────────

def test_faiss_numpy_parity():
    """Both backends should produce results within ±0.05 of each other."""
    try:
        import faiss as _  # noqa
        _faiss_available = True
    except ImportError:
        _faiss_available = False

    vec = [0.1 * i for i in range(1, _N + 1)]
    meta = {"rr": 2.0, "cluster_id": 0, "age_days": 0.0, "outcome": "TP_HIT"}

    np_idx    = _make_index((vec, meta))  # use_faiss=False by default in _make_index
    np_score, _ = np_idx.search(vec)[0]

    if _faiss_available:
        faiss_idx = ReplaySimilarityIndex(n_features=_N, use_faiss=True)
        faiss_idx.add_record(vec, meta)
        faiss_idx.build_index()
        results = faiss_idx.search(vec)
        assert results, "FAISS search returned no results"
        faiss_score, _ = results[0]
        assert abs(faiss_score - np_score) < 0.05, (
            f"FAISS score {faiss_score:.4f} differs from NumPy score {np_score:.4f} by > 0.05"
        )
    else:
        pytest.skip("FAISS not installed — skipping FAISS parity test")
