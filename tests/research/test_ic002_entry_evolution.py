"""Unit tests for IC-002 entry evolution (schema + path math + tiny synthetic)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from research.ic002_entry_evolution.schema import (
    D,
    N_GRID,
    TRAJECTORY_FEATURE_IDS,
    flatten_Z,
    path_relative_row,
    static_baseline_vector,
)
from research.ic002_entry_evolution.build_trajectories import build_for_N
from research.ic002_entry_evolution.evaluate_separation import _auc, evaluate_N
from research.ic002_entry_evolution.io_util import load_prereg, save_batch, load_batch
from research.ic002_entry_evolution.schema import TrajectoryBatch

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "research-readiness" / "h-ic002-entry-evolution-experiment-definition.json"


def test_prereg_matches_schema_constants():
    data = json.loads(PREREG.read_text(encoding="utf-8"))
    assert tuple(data["trajectory"]["N_grid"]) == N_GRID
    assert tuple(data["trajectory"]["feature_ids"]) == TRAJECTORY_FEATURE_IDS
    assert data["trajectory"]["D"] == D == 15


def test_path_relative_and_flat_dims():
    x0 = [1.0, 2.0, 0.0]
    xk = [2.0, 2.0, 1.0]
    z = path_relative_row(xk, x0)
    assert z[0] == pytest.approx(1.0)
    assert z[1] == pytest.approx(0.0)
    assert abs(z[2]) > 0  # eps denom
    Z = [z, z]
    flat = flatten_Z(Z)
    assert len(flat) == 6
    assert len(static_baseline_vector(x0, 2)) == 6


def test_build_for_N_synthetic(tmp_path):
    import pandas as pd

    # 20 synthetic bars with required feature columns
    n = 30
    data = {"_src_idx": np.arange(n)}
    for f in TRAJECTORY_FEATURE_IDS:
        data[f] = np.linspace(0.1, 1.0, n) + 0.01 * np.arange(n)
    enriched = pd.DataFrame(data)
    src_to_row = {int(s): i for i, s in enumerate(enriched["_src_idx"])}
    entries = [
        {
            "trade_id": "t0",
            "entry_index": 5,
            "entry_timestamp": "2024-01-01 00:00:00",
            "family": "expansion_breakout",
            "direction": "long",
            "outcome": "TP_HIT",
            "feature_body_ratio": 0.5,
        },
        {
            "trade_id": "t1",
            "entry_index": 10,
            "entry_timestamp": "2024-01-01 01:00:00",
            "family": "mean_reversion",
            "direction": "short",
            "outcome": "SL_HIT",
            "feature_body_ratio": 0.5,
        },
    ]
    N = 4
    batch = build_for_N(enriched, src_to_row, entries, N)
    assert len(batch.trade_ids) == 2
    assert batch.Z.shape == (2, N, D)
    assert batch.X0.shape == (2, D)
    assert batch.y == [1, 0]
    # no future: last src used is entry_index+N
    assert max(batch.entry_indices[0] + N for _ in [0]) == 5 + N
    paths = save_batch(tmp_path, batch)
    assert Path(paths["npz"]).exists()
    loaded = load_batch(tmp_path, N)
    assert loaded.trade_ids == batch.trade_ids
    assert loaded.Z.shape == batch.Z.shape


def test_auc_perfect_and_chance():
    y = np.array([0, 0, 0, 1, 1, 1])
    assert _auc(y, np.array([0.1, 0.2, 0.3, 0.7, 0.8, 0.9])) == pytest.approx(1.0)
    # identical scores -> 0.5
    assert _auc(y, np.ones(6) * 0.5) == pytest.approx(0.5)


def test_evaluate_N_smoke(tmp_path):
    # construct random batch large enough for split
    rng = np.random.RandomState(0)
    n, N = 200, 4
    Z = rng.randn(n, N, D)
    X0 = rng.randn(n, D)
    y = (rng.rand(n) > 0.7).astype(int)
    batch = TrajectoryBatch(
        N=N,
        feature_ids=TRAJECTORY_FEATURE_IDS,
        trade_ids=[f"t{i}" for i in range(n)],
        entry_indices=list(range(n)),
        timestamps=[f"2024-01-01 {i//60:02d}:{i%60:02d}:00" for i in range(n)],
        families=["expansion_breakout"] * n,
        directions=["long"] * n,
        y=y.tolist(),
        outcomes=["TP_HIT" if yi else "SL_HIT" for yi in y],
        Z=Z,
        X0=X0,
    )
    save_batch(tmp_path, batch)
    res = evaluate_N(tmp_path, N)
    assert res["N"] == N
    assert res["verdict"] in ("REJECT", "INSUFFICIENT", "RESEARCH_SUPPORTIVE", "SHAPE_ONLY")
    assert "AUC_path_OOS" in res
