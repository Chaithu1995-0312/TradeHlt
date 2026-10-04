"""
retrieval/ — Truth-tier lexical RAG for the Tradelatest corpus.

DuckDB/Parquet lexical query core (hand-rolled BM25; no fts extension).
JSONL under data/rag/ is the build system-of-record; LexicalIndex queries
Parquet sidecars at search time and does not load the corpus into Python dicts.
Dense/Chroma is optional Phase-5 only. Results are partitioned by truth class;
divergence is surfaced, never adjudicated.
"""

from __future__ import annotations

from retrieval.config import RetrievalConfig, build_default_config
from retrieval.chunking import Chunker, Chunk, chunk_document
from retrieval.corpus import CorpusDiscoverer, Document
from retrieval.retriever import Retriever, HybridResult, ContextAssembly
from retrieval.monitor import Monitor, MetricsSnapshot
from retrieval.index_store import IndexStore, IndexBuildReport
from retrieval.lexical import LexicalIndex, LexicalHit
from retrieval.divergence import DivergenceFlag, detect_divergences
from retrieval.truth_tier import (
    classify_path,
    classify_status,
    extract_ids,
    TierAssignment,
    StatusAssignment,
)

# Legacy exports (still importable; Chroma path is fail-loud / unused by pipeline)
try:
    from retrieval.embedding import Embedder
except Exception:  # pragma: no cover
    Embedder = None  # type: ignore
try:
    from retrieval.vector_store import VectorStore, SearchResult
except Exception:  # pragma: no cover
    VectorStore = None  # type: ignore
    SearchResult = None  # type: ignore

__all__ = [
    "RetrievalConfig",
    "build_default_config",
    "Chunker",
    "Chunk",
    "chunk_document",
    "CorpusDiscoverer",
    "Document",
    "Retriever",
    "HybridResult",
    "ContextAssembly",
    "Monitor",
    "MetricsSnapshot",
    "IndexStore",
    "IndexBuildReport",
    "LexicalIndex",
    "LexicalHit",
    "DivergenceFlag",
    "detect_divergences",
    "classify_path",
    "classify_status",
    "extract_ids",
    "TierAssignment",
    "StatusAssignment",
    "Embedder",
    "VectorStore",
    "SearchResult",
    "RetrievalPipeline",
]


class RetrievalPipeline:
    """Truth-tier pipeline: discover → chunk → index (JSONL/Parquet) → retrieve."""

    def __init__(self, config: RetrievalConfig | None = None) -> None:
        self.config = config or build_default_config()
        self.corpus = CorpusDiscoverer(self.config)
        self.chunker = Chunker(self.config)
        self.index_store = IndexStore(self.config)
        self.lexical = LexicalIndex(self.config)
        self.monitor = Monitor(self.config)
        self.retriever = Retriever(self.lexical, self.config)
        # Legacy attribute kept so old callers referencing pipe.store don't crash
        # on attribute access; hybrid_search will fail loud if invoked.
        self.store = None
        if VectorStore is not None:
            try:
                self.store = VectorStore(self.config)
            except Exception:
                self.store = None

    def index(self, *, rebuild: bool = False) -> int:
        report = self.index_store.build(rebuild=rebuild)
        self.monitor.record_index(report.docs, report.chunks)
        # Force reload on next query
        self.lexical._loaded = False
        return report.chunks

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        domain_filter: str | None = None,
    ) -> list[HybridResult]:
        ctx = self.retriever.retrieve(
            query, top_k=top_k, domain_filter=domain_filter
        )
        self.monitor.record_query(query, len(ctx.chunks))
        return ctx.chunks

    def retrieve_assembly(
        self,
        query: str,
        top_k: int = 10,
        domain_filter: str | None = None,
        max_tokens: int | None = None,
    ) -> ContextAssembly:
        ctx = self.retriever.retrieve(
            query,
            top_k=top_k,
            domain_filter=domain_filter,
            max_tokens=max_tokens,
        )
        self.monitor.record_query(query, len(ctx.chunks))
        self.monitor.record_query_latency(query, ctx.retrieval_time_ms / 1000.0)
        return ctx

    def metrics(self) -> MetricsSnapshot:
        return self.monitor.snapshot()
