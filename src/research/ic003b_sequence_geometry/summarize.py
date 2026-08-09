"""Arm S: path-summary vectorization (7 stats × D)."""
from __future__ import annotations

import numpy as np

from research.ic003b_sequence_geometry.schema import STATS_PER_DIM


def path_summary_matrix(Z: np.ndarray) -> np.ndarray:
    """
    Z: (n, N, D) path-relative trajectories.
    Returns X: (n, 7*D) with stats in STATS_PER_DIM order per dim.
    """
    Z = np.asarray(Z, dtype=np.float64)
    Z = np.nan_to_num(Z, nan=0.0, posinf=0.0, neginf=0.0)
    n, N, D = Z.shape
    out = np.zeros((n, 7 * D), dtype=np.float64)
    # vectorized per-dim
    mean = Z.mean(axis=1)
    std = Z.std(axis=1)
    first = Z[:, 0, :]
    last = Z[:, -1, :]
    mn = Z.min(axis=1)
    mx = Z.max(axis=1)
    slope = (last - first) / max(N - 1, 1)
    blocks = [mean, std, first, last, mn, mx, slope]
    assert len(blocks) == len(STATS_PER_DIM)
    for i, block in enumerate(blocks):
        out[:, i * D : (i + 1) * D] = block
    return out


def mflat(Z: np.ndarray) -> np.ndarray:
    Z = np.asarray(Z, dtype=np.float64)
    Z = np.nan_to_num(Z, nan=0.0, posinf=0.0, neginf=0.0)
    n, N, D = Z.shape
    return Z.reshape(n, N * D)
