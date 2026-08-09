"""
retrieval/retriever.py — The Retriever: high-level retrieval interface with context assembly.

Assembles retrieved chunks into a structured context payload suitable for
inclusion in Claude Code prompts. Supports domain filtering, relevance thresholds,
and dynamic context windowing.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Sequence

from retrieval.config import RetrievalConfig
from retrieval.vector_store import VectorStore, SearchResult


@dataclass
class HybridResult:
    """A single retrieval result with hybrid score and provenance.

    Attributes:
        chunk_id: Unique chunk identifier.
        text: The text content of the chunk.
        score: Combined hybrid score (semantic + keyword + structural).
        semantic_score: Raw semantic similarity score.
        keyword_score: Raw keyword match score.
        structural_boost: Boost from exact structural matches.
        domain: Document domain.
        filepath: Relative file path.
        heading: Section heading or construct name.
        start_line: Start line in the source document.
        end_line: End line in the source document.
        metadata: All metadata from the chunk.
    """
    chunk_id: str
    text: str
    score: float
    semantic_score: float = 0.0
    keyword_score: float = 0.0
    structural_boost: float = 0.0
    domain: str = ""
    filepath: str = ""
    heading: str = ""
    start_line: int = 0
    end_line: int = 0
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class ContextAssembly:
    """A structured context payload for LLM consumption.

    Attributes:
        query: The original query.
        chunks: Retrieved chunks ordered by relevance.
        total_chunks: Total number of relevant chunks found.
        total_tokens: Estimated token count for the assembled context.
        retrieval_time_ms: Time taken for the retrieval in milliseconds.
        domains_covered: Set of domains represented in the results.
    """
    query: str
    chunks: list[HybridResult]
    total_chunks: int
    total_tokens: int = 0
    retrieval_time_ms: float = 0.0
    domains_covered: set[str] = field(default_factory=set)


class Retriever:
    """High-level retriever with context assembly for LLM consumption.

    Wraps VectorStore.hybrid_search() and adds:
      - Result formatting for Claude Code prompts
      - Relevance threshold filtering
      - Token-aware context windowing
      - Per-domain result guarantees (at least N results from each domain)
    """

    def __init__(
        self,
        vector_store: VectorStore,
        config: RetrievalConfig | None = None,
    ) -> None:
        from retrieval.config import build_default_config
        self.store = vector_store
        self.config = config or build_default_config()

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        domain_filter: str | None = None,
        min_score: float = 0.0,
        max_tokens: int | None = None,
        ensure_domains: list[str] | None = None,
    ) -> ContextAssembly:
        """Retrieve and assemble context for the given query.

        Args:
            query: The search query.
            top_k: Number of results to return (default: config.top_k_default).
            domain_filter: Optional domain filter.
            min_score: Minimum combined score threshold.
            max_tokens: Maximum tokens for the assembled context (approximate).
            ensure_domains: Guarantee at least 1 result from each of these domains.

        Returns:
            ContextAssembly with ranked results and metadata.
        """
        t0 = time.time()
        k = top_k or self.config.top_k_default

        # 1. Main retrieval
        results = self.store.hybrid_search(query, top_k=k, domain_filter=domain_filter)

        # 2. Filter by score threshold
        if min_score > 0.0:
            results = [r for r in results if r.score >= min_score]

        # 3. Domain guarantees
        if ensure_domains:
            results = self._ensure_domains(results, query, ensure_domains, k)

        # 4. Convert to HybridResult
        hybrid_results = [
            HybridResult(
                chunk_id=r.chunk_id,
                text=r.text,
                score=r.score,
                domain=r.domain,
                filepath=r.filepath,
                heading=r.heading,
                metadata=r.metadata,
            )
            for r in results
        ]

        # 5. Token-aware truncation
        total_tokens = 0
        truncated: list[HybridResult] = []
        for hr in hybrid_results:
            estimated_tokens = len(hr.text) // 4  # rough estimate
            if max_tokens and total_tokens + estimated_tokens > max_tokens:
                break
            total_tokens += estimated_tokens
            truncated.append(hr)

        elapsed = time.time() - t0
        domains = {r.domain for r in truncated}

        return ContextAssembly(
            query=query,
            chunks=truncated,
            total_chunks=len(truncated),
            total_tokens=total_tokens,
            retrieval_time_ms=round(elapsed * 1000, 2),
            domains_covered=domains,
        )

    def format_for_claude(self, ctx: ContextAssembly) -> str:
        """Format a ContextAssembly into a prompt block for Claude Code.

        The output is a structured markdown section with file references,
        scores, and excerpted text — designed to be prepended to any
        Claude Code task prompt.
        """
        lines = [
            "## Retrieved Context (RAG)",
            "",
            f"Query: `{ctx.query}`",
            f"Domains: {', '.join(sorted(ctx.domains_covered))}",
            f"Retrieval time: {ctx.retrieval_time_ms}ms",
            f"Total chunks: {ctx.total_chunks}  ·  ~{ctx.total_tokens} tokens",
            "",
            "---",
            "",
        ]

        for i, chunk in enumerate(ctx.chunks, 1):
            lines.append(f"### [{i}] {chunk.filepath}")
            if chunk.heading:
                lines.append(f"**Section:** {chunk.heading}")
            lines.append(f"**Domain:** {chunk.domain}  ·  **Score:** {chunk.score:.3f}")
            lines.append(f"**Lines:** {chunk.start_line}–{chunk.end_line}")
            lines.append("")
            lines.append("```" + self._suffix(chunk.filepath))
            lines.append(chunk.text[:600])  # truncate excerpt
            if len(chunk.text) > 600:
                lines.append("... (truncated)")
            lines.append("```")
            lines.append("")

        return "\n".join(lines)

    def format_compact(self, ctx: ContextAssembly) -> str:
        """Format a compact context block (for system prompts with limited space)."""
        lines = [
            "## RAG: " + ctx.query,
            f"({ctx.total_chunks} chunks from {', '.join(sorted(ctx.domains_covered))}, "
            f"{ctx.retrieval_time_ms}ms)",
            "",
        ]
        for i, chunk in enumerate(ctx.chunks[:5], 1):
            excerpt = chunk.text[:200].replace("\n", " ")
            lines.append(f"{i}. `{chunk.filepath}` [{chunk.heading}] — {excerpt}…")
        if len(ctx.chunks) > 5:
            lines.append(f"… and {len(ctx.chunks) - 5} more")
        return "\n".join(lines)

    # ── private helpers ────────────────────────────────────────────────────

    def _ensure_domains(
        self,
        results: list[SearchResult],
        query: str,
        domains: list[str],
        k: int,
    ) -> list[SearchResult]:
        """Guarantee at least one result per specified domain."""
        present = {r.domain for r in results}
        missing = [d for d in domains if d not in present]
        if not missing:
            return results

        # Fetch additional results for missing domains
        for domain in missing:
            extra = self.store.hybrid_search(query, top_k=1, domain_filter=domain)
            results.extend(extra)

        # Re-sort and truncate
        results.sort(key=lambda r: -r.score)
        return results[:k]

    @staticmethod
    def _suffix(filepath: str) -> str:
        """Get the file extension suffix for syntax highlighting."""
        ext = filepath.rsplit(".", 1)[-1].lower() if "." in filepath else ""
        return {
            "py": "python",
            "md": "markdown",
            "yaml": "yaml",
            "yml": "yaml",
            "json": "json",
            "jsonl": "json",
        }.get(ext, "")