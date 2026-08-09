"""Unit tests for IC-003 shape library builder."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from research.ic002_entry_evolution.io_util import save_batch
from research.ic002_entry_evolution.schema import D, TRAJECTORY_FEATURE_IDS, TrajectoryBatch
from research.ic003_shapes.build_library import build_for_N, build_all
from research.ic003_shapes.schema import K_GRID, PRIMARY_N

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "research-readiness" / "h-ic003-shape-library-experiment-definition.json"


def test_prereg_k_grid():
    data = json.loads(PREREG.read_text(encoding="utf-8"))
    assert tuple(data["clustering"]["k_grid"]) == K_GRID
    assert tuple(data["inputs"]["primary_N"]) == PRIMARY_N


def _synthetic_batch(tmp: Path, N: int = 4, n: int = 400) -> Path:
    rng = np.random.RandomState(1)
    # two blobs in path space
    Z = rng.randn(n, N, D) * 0.1
    Z[: n // 2, :, 0] += 2.0
    Z[n // 2 :, :, 0] -= 2.0
    X0 = rng.randn(n, D)
    y = [1 if i < n // 2 else 0 for i in range(n)]
    batch = TrajectoryBatch(
        N=N,
        feature_ids=TRAJECTORY_FEATURE_IDS,
        trade_ids=[f"t{i}" for i in range(n)],
        entry_indices=list(range(n)),
        timestamps=[f"2024-06-01 {i // 60:02d}:{i % 60:02d}:00" for i in range(n)],
        families=["expansion_breakout"] * n,
        directions=["long"] * n,
        y=y,
        outcomes=["TP_HIT" if yi else "SL_HIT" for yi in y],
        Z=Z,
        X0=X0,
    )
    save_batch(tmp, batch)
    return tmp


def test_build_for_N_synthetic(tmp_path):
    ic002 = _synthetic_batch(tmp_path, N=4, n=400)
    res = build_for_N(ic002, 4, role="primary")
    assert res["N"] == 4
    assert res["k_star"] in K_GRID
    assert res["verdict"] in ("LIBRARY_OK", "LIBRARY_FAIL", "INSUFFICIENT")
    assert len(res.get("shapes") or []) == res["k_star"]
    assert len(res.get("assignments") or []) == 400


def test_build_all_writes_artifacts(tmp_path):
    ic002 = tmp_path / "ic002"
    ic002.mkdir()
    for N in (4, 16):
        _synthetic_batch(ic002, N=N, n=300)
    # also N=8 diagnostic
    _synthetic_batch(ic002, N=8, n=300)
    out = tmp_path / "ic003"
    results = build_all(
        ic002_dir=ic002,
        out_dir=out,
        primary_N=(4, 16),
        diagnostic_N=(8,),
    )
    assert (out / "REPORT.md").exists()
    assert (out / "SHAPE_LIBRARY.md").exists()
    assert (out / "representative_shapes.jsonl").exists()
    assert (out / "manifest.json").exists()
    assert "program_verdict" in results
