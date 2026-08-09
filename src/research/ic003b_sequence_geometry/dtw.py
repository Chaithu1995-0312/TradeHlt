"""Deterministic DTW with Sakoe-Chiba band (Arm T)."""
from __future__ import annotations

import numpy as np

from research.ic003b_sequence_geometry.schema import DTW_RADIUS_FRAC


def sakoe_chiba_radius(N: int, frac: float = DTW_RADIUS_FRAC) -> int:
    return max(1, int(np.floor(frac * N)))


def dtw_euclidean(a: np.ndarray, b: np.ndarray, radius: int | None = None) -> float:
    """
    a, b: (N, C) sequences.
    Standard DTW with optional Sakoe-Chiba window.
    """
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    n, c = a.shape
    m = b.shape[0]
    if radius is None:
        radius = sakoe_chiba_radius(max(n, m))
    # cost matrix with inf
    INF = 1e18
    D = np.full((n + 1, m + 1), INF, dtype=np.float64)
    D[0, 0] = 0.0
    for i in range(1, n + 1):
        j0 = max(1, i - radius)
        j1 = min(m, i + radius)
        ai = a[i - 1]
        for j in range(j0, j1 + 1):
            cost = float(np.sum((ai - b[j - 1]) ** 2))
            D[i, j] = cost + min(D[i - 1, j], D[i, j - 1], D[i - 1, j - 1])
    return float(np.sqrt(D[n, m])) if np.isfinite(D[n, m]) else INF


def pairwise_dtw(seqs: np.ndarray, radius: int | None = None) -> np.ndarray:
    """seqs: (n, N, C) → symmetric (n, n) distance matrix.

    Parallelized over upper-triangle pairs for practical IC-003B runtimes.
    """
    n = seqs.shape[0]
    D = np.zeros((n, n), dtype=np.float64)
    if n == 0:
        return D
    if radius is None:
        radius = sakoe_chiba_radius(seqs.shape[1])
    pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]

    def _one(pair):
        i, j = pair
        return i, j, dtw_euclidean(seqs[i], seqs[j], radius=radius)

    # Thread pool: release GIL on numpy inner loops somewhat; good enough for n<=3000
    try:
        from concurrent.futures import ThreadPoolExecutor
        import os

        workers = min(8, max(2, (os.cpu_count() or 4)))
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for i, j, d in ex.map(_one, pairs, chunksize=max(1, len(pairs) // (workers * 8))):
                D[i, j] = D[j, i] = d
    except Exception:
        for i, j in pairs:
            d = dtw_euclidean(seqs[i], seqs[j], radius=radius)
            D[i, j] = D[j, i] = d
    return D


def dtw_to_medoids(seqs: np.ndarray, medoid_seqs: np.ndarray, radius: int | None = None):
    """
    seqs: (n, N, C), medoid_seqs: (k, N, C)
    returns labels (n,) and distances (n,)
    """
    n = seqs.shape[0]
    k = medoid_seqs.shape[0]
    labels = np.zeros(n, dtype=np.int32)
    dists = np.zeros(n, dtype=np.float64)
    if radius is None:
        radius = sakoe_chiba_radius(seqs.shape[1])

    def _one(i: int):
        best_d, best_c = 1e18, 0
        si = seqs[i]
        for c in range(k):
            d = dtw_euclidean(si, medoid_seqs[c], radius=radius)
            if d < best_d:
                best_d, best_c = d, c
        return i, best_c, best_d

    try:
        from concurrent.futures import ThreadPoolExecutor
        import os

        workers = min(8, max(2, (os.cpu_count() or 4)))
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for i, best_c, best_d in ex.map(_one, range(n), chunksize=max(1, n // (workers * 8))):
                labels[i] = best_c
                dists[i] = best_d
    except Exception:
        for i in range(n):
            i2, best_c, best_d = _one(i)
            labels[i2] = best_c
            dists[i2] = best_d
    return labels, dists
