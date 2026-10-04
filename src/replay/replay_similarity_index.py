"""
replay_similarity_index.py
==========================
Similarity search index for replay vectors.

Primary: cosine similarity (lightweight, no matrix required).
Secondary: Mahalanobis similarity (requires precision matrix from training).

FAISS is an optional acceleration backend; NumPy is the mandatory fallback.

Temporal decay: older matches are down-weighted by exp(-lambda * age_days).
"""
from __future__ import annotations

import math
import logging
from typing import List, Optional, Tuple

logger = logging.getLogger("ReplaySimilarityIndex")

try:
    import numpy as np
    _NUMPY_AVAILABLE = True
except ImportError:
    _NUMPY_AVAILABLE = False

try:
    import faiss as _faiss
    _FAISS_AVAILABLE = True
except ImportError:
    _faiss = None
    _FAISS_AVAILABLE = False


def _cosine_similarity(a: list, b: list) -> float:
    """Pure-Python cosine similarity — no NumPy dependency."""
    n = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(n))
    norm_a = math.sqrt(sum(x * x for x in a[:n])) or 1e-12
    norm_b = math.sqrt(sum(x * x for x in b[:n])) or 1e-12
    return max(0.0, min(1.0, dot / (norm_a * norm_b)))


class ReplaySimilarityIndex:
    """
    Nearest-neighbour replay similarity index.

    Build with add_record() / build_index(), then query with search().
    Supports cosine (default) and Mahalanobis (requires precision matrix).

    Parameters
    ----------
    n_features : int
        Expected feature vector dimension.
    decay_lambda : float
        Temporal decay coefficient (default 0.023 ≈ 30-day half-life).
    top_k : int
        Number of neighbours to retrieve per query.
    use_faiss : bool
        Attempt FAISS acceleration (falls back to NumPy if unavailable).
    """

    def __init__(
        self,
        n_features: int,
        decay_lambda: float = 0.023,
        top_k: int = 10,
        use_faiss: bool = True,
    ):
        self._n = n_features
        self._decay_lambda = decay_lambda
        self._top_k = top_k
        self._use_faiss = use_faiss and _FAISS_AVAILABLE

        self._vectors: List[list] = []
        self._metadata: List[dict] = []    # outcome, rr, cluster_id, age_days
        self._precision_matrix: Optional[list] = None   # for Mahalanobis
        self._index = None     # FAISS index (optional)
        self._built = False

    # ── Public API ────────────────────────────────────────────────────────────

    def add_record(self, vector: list, metadata: dict) -> None:
        """
        Add one feature vector + metadata dict.

        Metadata expected keys: outcome, rr, cluster_id, age_days.
        Vector will be truncated/padded to n_features for schema migration safety.
        """
        if len(vector) != self._n:
            # Silently truncate/pad for schema migration
            vector = (list(vector) + [0.0] * self._n)[: self._n]
        self._vectors.append(list(vector))
        self._metadata.append(dict(metadata))
        self._built = False

    def set_precision_matrix(self, P: list) -> None:
        """
        Set precision matrix (inverse covariance) for Mahalanobis similarity.

        P must be an n_features × n_features nested list of floats.
        """
        self._precision_matrix = P

    def build_index(self) -> None:
        """
        Build search index (FAISS inner-product or in-memory NumPy matrix).

        Safe to call multiple times — rebuilds when _built is False.
        No-op when no records have been added.
        """
        if not self._vectors:
            self._built = True
            return

        if self._use_faiss and _FAISS_AVAILABLE and _NUMPY_AVAILABLE:
            try:
                import numpy as np  # noqa: PLC0415
                mat = np.array(self._vectors, dtype=np.float32)
                # L2-normalise for inner-product cosine
                norms = np.linalg.norm(mat, axis=1, keepdims=True)
                norms = np.where(norms == 0, 1.0, norms)
                mat = mat / norms
                idx = _faiss.IndexFlatIP(self._n)
                idx.add(mat)
                self._index = idx
                logger.info(
                    "ReplaySimilarityIndex: FAISS index built (%d vectors, dim=%d)",
                    len(self._vectors), self._n,
                )
            except Exception as exc:
                logger.warning(
                    "ReplaySimilarityIndex: FAISS build failed (%s) — "
                    "falling back to linear scan.", exc,
                )
                self._index = None

        self._built = True

    def search(
        self,
        query: list,
        method: str = "cosine",
        cluster_filter: Optional[int] = None,
    ) -> List[Tuple[float, dict]]:
        """
        Find top-k nearest neighbours with temporal decay weighting.

        Parameters
        ----------
        query          : query feature vector (truncated/padded to n_features)
        method         : "cosine" | "mahalanobis"
        cluster_filter : if set, restrict to records with this cluster_id

        Returns
        -------
        list of (weighted_score, metadata_dict) sorted descending by score.
        Empty list when no records exist.
        """
        if not self._built:
            self.build_index()
        if not self._vectors:
            return []

        # Normalise query length
        query = (list(query) + [0.0] * self._n)[: self._n]

        # FAISS fast-path: cosine only, no cluster filter
        if (
            method == "cosine"
            and self._use_faiss
            and self._index is not None
            and cluster_filter is None
            and _NUMPY_AVAILABLE
        ):
            return self._faiss_search(query)

        # Linear scan (NumPy or pure-Python)
        return self._linear_search(query, method, cluster_filter)

    def aggregate_top_k_stats(self, results: List[Tuple[float, dict]]) -> dict:
        """
        Aggregate win_rate and mean_rr from top-k search results.

        Weights are the decay-adjusted similarity scores returned by search().

        Returns
        -------
        dict with keys: win_rate, mean_rr, n_matched, confidence
        """
        if not results:
            return {
                "win_rate":  0.5,
                "mean_rr":   0.0,
                "n_matched": 0,
                "confidence": 0.0,
            }

        total_weight = sum(s for s, _ in results)
        if total_weight <= 0:
            return {
                "win_rate":   0.5,
                "mean_rr":    0.0,
                "n_matched":  len(results),
                "confidence": 0.0,
            }

        w_wins = sum(s for s, m in results if float(m.get("rr", 0.0)) >= 1.0)
        w_rr   = sum(s * float(m.get("rr", 0.0)) for s, m in results)

        return {
            "win_rate":   round(w_wins / total_weight, 4),
            "mean_rr":    round(w_rr   / total_weight, 4),
            "n_matched":  len(results),
            "confidence": round(min(1.0, total_weight / max(self._top_k, 1)), 4),
        }

    # ── Private ───────────────────────────────────────────────────────────────

    def _faiss_search(self, query: list) -> List[Tuple[float, dict]]:
        """FAISS inner-product cosine search with temporal decay."""
        import numpy as np  # noqa: PLC0415

        q = np.array(query, dtype=np.float32).reshape(1, -1)
        norm = float(np.linalg.norm(q)) or 1.0
        q = q / norm

        k = min(self._top_k, len(self._vectors))
        scores, indices = self._index.search(q, k)

        results: List[Tuple[float, dict]] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            meta = self._metadata[idx]
            age = float(meta.get("age_days", 0.0))
            decay = math.exp(-self._decay_lambda * age)
            results.append((float(score) * decay, meta))

        results.sort(key=lambda x: x[0], reverse=True)
        return results

    def _linear_search(
        self,
        query: list,
        method: str,
        cluster_filter: Optional[int],
    ) -> List[Tuple[float, dict]]:
        """Linear-scan search with optional cluster filter and temporal decay."""
        candidates: List[Tuple[float, dict]] = []

        for vec, meta in zip(self._vectors, self._metadata):
            if cluster_filter is not None and meta.get("cluster_id") != cluster_filter:
                continue

            if method == "mahalanobis" and self._precision_matrix is not None:
                sim = self._mahalanobis_sim(query, vec)
            else:
                sim = _cosine_similarity(query, vec)

            age = float(meta.get("age_days", 0.0))
            decay = math.exp(-self._decay_lambda * age)
            candidates.append((sim * decay, meta))

        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[: self._top_k]

    def _mahalanobis_sim(self, a: list, b: list) -> float:
        """
        Mahalanobis-based similarity via stored precision matrix.

        sim = exp(-0.5 × (a-b)ᵀ P (a-b))

        Clipped to prevent overflow: d² ≤ 500 → exp(-250) ≈ 0.
        """
        P = self._precision_matrix
        n = min(len(a), len(b), len(P))
        delta = [a[i] - b[i] for i in range(n)]

        d_sq = 0.0
        for i in range(n):
            row_dot = sum(float(P[i][j]) * delta[j] for j in range(n))
            d_sq += delta[i] * row_dot

        d_sq = min(max(d_sq, 0.0), 500.0)
        return math.exp(-0.5 * d_sq)

    # ── Introspection helpers ─────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._vectors)

    def __repr__(self) -> str:
        backend = "faiss" if (self._use_faiss and self._index is not None) else "linear"
        return (
            f"ReplaySimilarityIndex(n_features={self._n}, "
            f"n_records={len(self._vectors)}, backend={backend}, "
            f"built={self._built})"
        )
