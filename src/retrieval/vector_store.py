"""
retrieval/vector_store.py — ChromaDB-backed vector store with hybrid search.

Stores chunk embeddings with rich metadata for domain filtering, keyword
fallback, and structural boosting. The store is persistent (ChromaDB on disk)
and supports incremental updates.

This is the **fourth stage** in the RAG pipeline (discover → chunk → embed → index).
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from retrieval.config import RetrievalConfig
from retrieval.chunking import Chunk
from retrieval.corpus import Document


@dataclass
class SearchResult:
    """A single result from the vector store.

    Attributes:
        chunk_id: Unique identifier for the chunk.
        text: The chunk text content.
        score: Cosine similarity score (0-1).
        domain: The document domain.
        filepath: Relative file path of the source document.
        heading: Section heading or construct name.
        metadata: All metadata associated with the chunk.
    """
    chunk_id: str
    text: str
    score: float
    domain: str
    filepath: str
    heading: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


class VectorStore:
    """ChromaDB-backed vector store with hybrid search capabilities.

    Hybrid search combines:
      1. Semantic search (cosine similarity on embeddings)
      2. Keyword search (BM25-style term matching on chunk text)
      3. Structural boost (exact symbol/heading matches)
    """

    def __init__(self, config: RetrievalConfig) -> None:
        self.config = config
        self._client = None
        self._collection = None
        self._keyword_index: dict[str, list[tuple[str, float]]] = {}  # term -> [(chunk_id, tf-idf)]
        self._chunk_texts: dict[str, str] = {}
        self._chunk_metadata: dict[str, dict] = {}
        self._total_docs = 0
        self._total_chunks = 0

    # ── lifecycle ──────────────────────────────────────────────────────────

    def add_chunks(
        self,
        chunks: list[Chunk],
        embeddings: list[list[float]],
        doc: Document,
    ) -> None:
        """Add a batch of chunks (with pre-computed embeddings) to the store."""
        if not chunks or not embeddings:
            return
        assert len(chunks) == len(embeddings), "chunks/embeddings length mismatch"

        collection = self._get_collection()
        ids: list[str] = []
        metadatas: list[dict] = []
        documents: list[str] = []

        for chunk, emb in zip(chunks, embeddings):
            cid = chunk.chunk_id
            ids.append(cid)
            documents.append(chunk.text)
            meta = {
                "chunk_id": cid,
                "domain": chunk.domain,
                "filepath": str(doc.path.relative_to(self.config.repo_root)),
                "filename": doc.path.name,
                "heading": chunk.heading,
                "start_line": str(chunk.start_line),
                "end_line": str(chunk.end_line),
            }
            # Add any extra metadata from the chunk
            for k, v in chunk.metadata.items():
                if k not in meta:
                    meta[k] = v
            metadatas.append(meta)

            # Store for keyword index
            self._chunk_texts[cid] = chunk.text
            self._chunk_metadata[cid] = meta

        # Use upsert with batching to respect ChromaDB's max batch size
        max_batch = 1000
        for batch_start in range(0, len(ids), max_batch):
            batch_end = batch_start + max_batch
            collection.upsert(
                embeddings=embeddings[batch_start:batch_end],
                documents=documents[batch_start:batch_end],
                metadatas=metadatas[batch_start:batch_end],
                ids=ids[batch_start:batch_end],
            )

    def persist(self) -> None:
        """Persist the vector store to disk (ChromaDB does this automatically)."""
        # ChromaDB persists on each add() call; this is a no-op for explicit clarity.
        # Rebuild keyword index for hybrid search
        self._build_keyword_index()

    def hybrid_search(
        self,
        query: str,
        top_k: int = 10,
        domain_filter: str | None = None,
    ) -> list[SearchResult]:
        """Hybrid search: semantic + keyword + structural boost.

        Args:
            query: The search query string.
            top_k: Number of results to return.
            domain_filter: Optional domain to restrict results to.

        Returns:
            Ranked list of SearchResult objects.
        """
        collection = self._get_collection()

        # 1. Semantic search via ChromaDB (use our own embedder for query encoding)
        from retrieval.embedding import Embedder
        embedder = Embedder(self.config)
        query_embedding = embedder.embed(query)

        where = {"domain": domain_filter} if domain_filter else None
        sem_results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k * 2,  # fetch more for fusion
            where=where,
        )

        # 2. Keyword search (BM25-style)
        kw_results = self._keyword_search(query, top_k=top_k * 2, domain_filter=domain_filter)

        # 3. Structural boost: exact symbol/heading matches
        struct_boost = self._structural_boost(query)

        # 4. Fusion: combine scores
        fused = self._fuse_results(sem_results, kw_results, struct_boost, top_k)
        return fused

    # ── keyword search ─────────────────────────────────────────────────────

    def _build_keyword_index(self) -> None:
        """Build an inverted index for keyword search (TF-IDF style)."""
        import math
        self._keyword_index.clear()
        num_docs = len(self._chunk_texts)
        if num_docs == 0:
            return

        # Term frequency per document
        tf: dict[str, dict[str, int]] = {}
        df: dict[str, int] = {}  # document frequency

        for cid, text in self._chunk_texts.items():
            terms = self._tokenize(text)
            tf[cid] = {}
            seen_terms = set()
            for term in terms:
                tf[cid][term] = tf[cid].get(term, 0) + 1
                if term not in seen_terms:
                    df[term] = df.get(term, 0) + 1
                    seen_terms.add(term)

        # Compute TF-IDF scores
        for cid, term_counts in tf.items():
            max_tf = max(term_counts.values()) if term_counts else 1
            for term, count in term_counts.items():
                tf_val = count / max_tf
                idf_val = math.log((num_docs + 1) / (df.get(term, 0) + 1)) + 1
                score = tf_val * idf_val
                if term not in self._keyword_index:
                    self._keyword_index[term] = []
                self._keyword_index[term].append((cid, score))

    def _keyword_search(
        self,
        query: str,
        top_k: int = 10,
        domain_filter: str | None = None,
    ) -> dict[str, float]:
        """BM25-style keyword search over the inverted index."""
        query_terms = self._tokenize(query)
        scores: dict[str, float] = {}

        for term in query_terms:
            for cid, score in self._keyword_index.get(term, []):
                if domain_filter:
                    meta = self._chunk_metadata.get(cid, {})
                    if meta.get("domain") != domain_filter:
                        continue
                scores[cid] = scores.get(cid, 0) + score

        # Normalize by query length
        if query_terms:
            scores = {k: v / len(query_terms) for k, v in scores.items()}

        # Return top_k
        sorted_scores = sorted(scores.items(), key=lambda x: -x[1])[:top_k]
        return dict(sorted_scores)

    def _structural_boost(self, query: str) -> dict[str, float]:
        """Detect exact symbol/heading matches and return boost scores."""
        boost: dict[str, float] = {}
        query_lower = query.lower()

        for cid, meta in self._chunk_metadata.items():
            # Check heading match
            heading = meta.get("heading", "").lower()
            if heading and (heading in query_lower or query_lower in heading):
                boost[cid] = boost.get(cid, 0) + self.config.structural_boost

            # Check symbol match (Python class/function names)
            symbols = meta.get("symbols", "").lower()
            if symbols:
                for sym in symbols.split(","):
                    sym = sym.strip()
                    if sym and (sym in query_lower or query_lower in sym):
                        boost[cid] = boost.get(cid, 0) + self.config.structural_boost

        return boost

    # ── fusion ─────────────────────────────────────────────────────────────

    def _fuse_results(
        self,
        sem_results: dict,
        kw_scores: dict[str, float],
        struct_boost: dict[str, float],
        top_k: int,
    ) -> list[SearchResult]:
        """Fuse semantic + keyword + structural scores into a single ranked list."""
        alpha = self.config.hybrid_alpha
        fused: dict[str, dict] = {}

        # Semantic results
        if sem_results.get("ids"):
            for i, cid_list in enumerate(sem_results["ids"]):
                for j, cid in enumerate(cid_list):
                    sem_score = 1.0 - (j / max(len(cid_list), 1))  # rank-based
                    if cid not in fused:
                        fused[cid] = {"sem": 0.0, "kw": 0.0, "struct": 0.0, "text": "", "meta": {}}
                    fused[cid]["sem"] = max(fused[cid]["sem"], sem_score)
                    if sem_results.get("documents") and sem_results["documents"][i]:
                        fused[cid]["text"] = sem_results["documents"][i][j]
                    if sem_results.get("metadatas") and sem_results["metadatas"][i]:
                        fused[cid]["meta"] = sem_results["metadatas"][i][j]

        # Keyword scores
        for cid, kw_score in kw_scores.items():
            if cid not in fused:
                fused[cid] = {"sem": 0.0, "kw": 0.0, "struct": 0.0, "text": "", "meta": {}}
            fused[cid]["kw"] = kw_score
            if not fused[cid]["text"]:
                fused[cid]["text"] = self._chunk_texts.get(cid, "")
            if not fused[cid]["meta"]:
                fused[cid]["meta"] = self._chunk_metadata.get(cid, {})

        # Structural boost
        for cid, boost in struct_boost.items():
            if cid not in fused:
                fused[cid] = {"sem": 0.0, "kw": 0.0, "struct": 0.0, "text": "", "meta": {}}
            fused[cid]["struct"] = boost
            if not fused[cid]["text"]:
                fused[cid]["text"] = self._chunk_texts.get(cid, "")
            if not fused[cid]["meta"]:
                fused[cid]["meta"] = self._chunk_metadata.get(cid, {})

        # Compute combined score
        results: list[SearchResult] = []
        for cid, scores in fused.items():
            combined = (
                alpha * scores["sem"]
                + (1 - alpha) * scores["kw"]
                + scores["struct"]
            )
            meta = scores.get("meta", {})
            results.append(SearchResult(
                chunk_id=cid,
                text=scores["text"],
                score=combined,
                domain=meta.get("domain", ""),
                filepath=meta.get("filepath", ""),
                heading=meta.get("heading", ""),
                metadata=meta,
            ))

        results.sort(key=lambda r: -r.score)
        return results[:top_k]

    # ── utility ────────────────────────────────────────────────────────────

    def count(self) -> int:
        """Return the number of chunks in the store."""
        collection = self._get_collection()
        return collection.count()

    def delete_collection(self) -> None:
        """Delete the entire collection (for full rebuild)."""
        client = self._get_client()
        try:
            client.delete_collection("tradelatest_rag")
        except Exception:
            pass
        self._collection = None

    # ── private helpers ────────────────────────────────────────────────────

    def _get_client(self):
        if self._client is None:
            import chromadb
            self.config.chroma_path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=str(self.config.chroma_path),
            )
        return self._client

    def _get_collection(self):
        if self._collection is None:
            import chromadb
            client = self._get_client()
            # Use no default embedding function since we pass pre-computed embeddings
            try:
                self._collection = client.get_collection(
                    "tradelatest_rag",
                    embedding_function=None,
                )
            except Exception:
                self._collection = client.create_collection(
                    name="tradelatest_rag",
                    embedding_function=None,
                    metadata={"hnsw:space": "cosine"},
                )
        return self._collection

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Tokenize text into lowercase terms for keyword search."""
        text = text.lower()
        # Split on non-alphanumeric characters (keep underscores)
        terms = re.findall(r'[a-z0-9_]+', text)
        # Filter very short terms and common stopwords
        stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "shall", "can",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "as", "into", "through", "during", "before", "after", "above",
            "below", "between", "out", "off", "over", "under", "again",
            "further", "then", "once", "here", "there", "when", "where",
            "why", "how", "all", "each", "every", "both", "few", "more",
            "most", "other", "some", "such", "no", "nor", "not", "only",
            "own", "same", "so", "than", "too", "very", "just", "because",
            "but", "and", "or", "if", "while", "that", "this", "it", "its",
        }
        return [t for t in terms if len(t) > 2 and t not in stopwords]