"""Unit tests for IC-003B sequence geometry."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from research.ic002_entry_evolution.io_util import save_batch
from research.ic002_entry_evolution.schema import D, TRAJECTORY_FEATURE_IDS, TrajectoryBatch
from research.ic003b_sequence_geometry.dtw import dtw_euclidean, pairwise_dtw
from research.ic003b_sequence_geometry.schema import G1_SSE_RATIO_MAX, PRIMARY_N, STATS_PER_DIM
from research.ic003b_sequence_geometry.summarize import path_summary_matrix
from research.ic003b_sequence_geometry.cluster_euclid import run_arm_s
from research.ic003b_sequence_geometry.continuum import run_arm_c

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "research-readiness" / "h-ic003b-sequence-geometry-experiment-definition.json"


def test_prereg_g1_unchanged():
    data = json.loads(PREREG.read_text(encoding="utf-8"))
    assert data["arms"]["S_path_summary"]["gates"]["G1_sse_ratio_max"] == 0.85
    assert G1_SSE_RATIO_MAX == 0.85
    assert tuple(data["inputs"]["primary_N"]) == PRIMARY_N
    assert data["not_an_amendment_of"] == "H-IC003-001_G1"


def test_path_summary_shape():
    rng = np.random.RandomState(0)
    Z = rng.randn(20, 4, D)
    X = path_summary_matrix(Z)
    assert X.shape == (20, 7 * D)
    assert len(STATS_PER_DIM) == 7


def test_dtw_identity_and_symmetry():
    a = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]])
    b = a.copy()
    assert dtw_euclidean(a, b) == pytest.approx(0.0, abs=1e-6)
    c = np.array([[0.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 2.0, 0.0]])
    d1 = dtw_euclidean(a, c)
    d2 = dtw_euclidean(c, a)
    assert d1 == pytest.approx(d2, rel=1e-6)
    seqs = np.stack([a, c, a], axis=0)
    D = pairwise_dtw(seqs)
    assert D.shape == (3, 3)
    assert D[0, 0] == 0
    assert D[0, 1] == pytest.approx(D[1, 0])


def test_arm_s_and_continuum_smoke():
    rng = np.random.RandomState(1)
    n, N = 300, 4
    Z = rng.randn(n, N, D) * 0.2
    Z[: n // 2, :, 0] += 1.5
    X = path_summary_matrix(Z)
    trade_ids = [f"t{i}" for i in range(n)]
    outcomes = ["TP_HIT" if i < n // 2 else "SL_HIT" for i in range(n)]
    ts = [f"2024-01-01 {i//60:02d}:{i%60:02d}:00" for i in range(n)]
    res = run_arm_s(X, ts, list(range(n)), trade_ids, outcomes, N, role="primary")
    assert res["arm"] == "S"
    assert res["verdict"] in ("LIBRARY_OK", "LIBRARY_FAIL", "INSUFFICIENT")
    c = run_arm_c(Z.reshape(n, N * D), X)
    assert "flags" in c
    assert "reprs" in c
