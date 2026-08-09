"""
retrieval/embedding.py — Embedding pipeline using sentence-transformers.

Loads a SentenceTransformer model (default: all-MiniLM-L6-v2, 384-dim) and
provides batched embedding for text chunks. The embedder is thread-safe for
concurrent retrieval but should be loaded once and reused.

This is the **third stage** in the RAG pipeline (discover → chunk → embed → index).
"""

from __future__ import annotations

import time
from typing import Sequence

from retrieval.config import RetrievalConfig


class Embedder:
    """Lightweight wrapper around a SentenceTransformer model.

    The model is loaded lazily on first use to avoid import-time downloads.
    """

    def __init__(self, config: RetrievalConfig) -> None:
        self.config = config
        self._model = None
        self._model_name = config.embedding_model

    # ── public API ─────────────────────────────────────────────────────────

    def embed(self, text: str) -> list[float]:
        """Embed a single text string into a fixed-dimension vector."""
        return self._get_model().encode(text, normalize_embeddings=True).tolist()

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed a batch of texts into vectors.

        Batching improves throughput via GPU/CPU parallelism.
        """
        model = self._get_model()
        vectors = model.encode(
            list(texts),
            batch_size=self.config.index_batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [v.tolist() for v in vectors]

    def embed_dim(self) -> int:
        """Return the dimensionality of the embedding vectors."""
        return self._get_model().get_sentence_embedding_dimension()

    # ── private helpers ────────────────────────────────────────────────────

    def _get_model(self):
        """Lazy-load the SentenceTransformer model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            t0 = time.time()
            self._model = SentenceTransformer(
                self._model_name,
                cache_folder=str(self.config.repo_root / "data" / "models"),
            )
            elapsed = time.time() - t0
            # Log model load time (accessible via monitor)
            self._load_time = elapsed
        return self._model