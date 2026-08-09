"""
retrieval/ — Enterprise RAG system for the Tradelatest codebase.

Provides semantic chunking, embedding, vector storage (ChromaDB), and hybrid
retrieval (semantic + keyword + structural metadata). Integrates with Claude Code
so every implementation, review, and debugging task is grounded in retrieved evidence.

Authority model:
  - Source documents are NEVER modified by the RAG pipeline — they are read-only.
  - The vector store is a DERIVED VIEW (like context/*.md — gitignored, regenerable).
  - Chunk boundaries follow language constructs (class/function/enum/doctstring), NOT
    fixed token sizes (CLAUDE.md §6.5 — evidence > doctrine: the code's own structure
    is the evidence for chunk boundaries, not a heuristic token budget).

Domains ingested (see also knowledge-map.md):
  - source_code  : Python source under src/ (docstrings + signatures + class bodies)
  - architecture  : docs/architecture/*.md — design decisions, signal flow, maps
  - governance    : docs/governance/*.md, *.json, *.jsonl — contracts, audits, lineage
  - analysis      : docs/analysis/*.md — point-in-time studies (evidence side of F-0xx)
  - intent        : docs/intent/*.md — behavioral contracts, intent-to-code alignment
  - operations    : docs/operations/*.md — runtime state, known illusions, dependency graph
  - config        : configs/**/*.yaml, configs/**/*.json — production config, formulas
  - tests         : tests/**/*.py — test code (guardrails and invariants)
  - research      : results/research/**/*.md, docs/research/**/*.md — frozen experiments

Usage:
    from retrieval import RetrievalPipeline
    pipe = RetrievalPipeline()               # loads existing index or creates one
    docs = pipe.retrieve("CRT state machine behaviour", top_k=5)
    pipe.index()                              # (re)build the full index
    pipe.metrics()                            # index latency, recall@K, MRR
"""

from __future__ import annotations

from retrieval.config import RetrievalConfig, build_default_config
from retrieval.chunking import Chunker, Chunk, chunk_document
from retrieval.embedding import Embedder
from retrieval.vector_store import VectorStore, SearchResult
from retrieval.corpus import CorpusDiscoverer, Document
from retrieval.retriever import Retriever, HybridResult
from retrieval.monitor import Monitor, MetricsSnapshot

__all__ = [
    "RetrievalConfig", "build_default_config",
    "Chunker", "Chunk", "chunk_document",
    "Embedder",
    "VectorStore", "SearchResult",
    "CorpusDiscoverer", "Document",
    "Retriever", "HybridResult",
    "Monitor", "MetricsSnapshot",
]


class RetrievalPipeline:
    """Top-level RAG pipeline: discover → chunk → embed → index → retrieve.

    Usage::

        pipe = RetrievalPipeline()
        pipe.index()                          # one-time build
        results = pipe.retrieve("CRT state machine")
        pipe.monitor.metrics()                # accuracy/latency snapshot
    """

    def __init__(self, config: RetrievalConfig | None = None) -> None:
        self.config = config or build_default_config()
        self.corpus = CorpusDiscoverer(self.config)
        self.chunker = Chunker(self.config)
        self.embedder = Embedder(self.config)
        self.store = VectorStore(self.config)
        self.monitor = Monitor(self.config)

    # ── lifecycle ──────────────────────────────────────────────────────────

    def index(self) -> int:
        """Discover all source documents, chunk, embed, and persist to vector store.

        Returns the total number of chunks indexed.
        """
        docs = self.corpus.discover()
        total = 0
        for doc in docs:
            chunks = self.chunker.chunk(doc)
            if not chunks:
                continue
            embeddings = self.embedder.embed_batch([c.text for c in chunks])
            self.store.add_chunks(chunks, embeddings, doc)
            total += len(chunks)
        self.store.persist()
        self.monitor.record_index(len(docs), total)
        return total

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        domain_filter: str | None = None,
    ) -> list[HybridResult]:
        """Hybrid retrieval across all domains.

        Returns results ranked by fusion score (semantic + keyword + structural boost).
        """
        results = self.store.hybrid_search(query, top_k=top_k, domain_filter=domain_filter)
        self.monitor.record_query(query, len(results))
        return results

    def metrics(self) -> MetricsSnapshot:
        return self.monitor.snapshot()