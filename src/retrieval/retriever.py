"""
retrieval/retriever.py — Truth-tier retrieval + context assembly.

Returns verbatim spans partitioned by truth class. Never blends CURRENT /
INTENDED / RECORDED into one paragraph. Divergence flags are first-class.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Sequence

from retrieval.config import RetrievalConfig, build_default_config
from retrieval.divergence import DivergenceFlag, detect_divergences
from retrieval.lexical import LexicalHit, LexicalIndex


@dataclass
class HybridResult:
    """A single retrieval hit with provenance and truth-tier fields."""

    chunk_id: str
    text: str
    score: float
    semantic_score: float = 0.0
    keyword_score: float = 0.0
    structural_boost: float = 0.0
    domain: str = ""  # alias of truth_class for back-compat
    filepath: str = ""
    heading: str = ""
    start_line: int = 0
    end_line: int = 0
    truth_class: str = ""
    authority_rank: int = 99
    lifecycle_status: str = "LIVE"
    status_evidence: str = ""
    content_sha: str = ""
    confidence: str = ""
    validated: str = ""
    revalidate_by: str = ""
    ids: str = ""
    symbols: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class ContextAssembly:
    """Tier-partitioned context payload for LLM / control-plane consumption."""

    query: str
    chunks: list[HybridResult]
    total_chunks: int
    total_tokens: int = 0
    retrieval_time_ms: float = 0.0
    domains_covered: set[str] = field(default_factory=set)
    by_truth_class: dict[str, list[HybridResult]] = field(default_factory=dict)
    divergence_flags: list[DivergenceFlag] = field(default_factory=list)
    registry_hits: list[dict[str, Any]] = field(default_factory=list)


def _hit_to_hybrid(h: LexicalHit) -> HybridResult:
    return HybridResult(
        chunk_id=h.chunk_id,
        text=h.text,
        score=h.score,
        keyword_score=h.bm25,
        domain=h.truth_class,
        filepath=h.filepath,
        heading=h.heading,
        start_line=h.start_line,
        end_line=h.end_line,
        truth_class=h.truth_class,
        authority_rank=h.authority_rank,
        lifecycle_status=h.lifecycle_status,
        status_evidence=h.status_evidence,
        content_sha=h.content_sha,
        confidence=h.confidence,
        validated=h.validated,
        revalidate_by=h.revalidate_by,
        ids=h.ids,
        symbols=h.symbols,
        metadata=h.metadata,
    )


class Retriever:
    """Lexical truth-tier retriever with divergence envelope."""

    def __init__(
        self,
        lexical_index: LexicalIndex | None = None,
        config: RetrievalConfig | None = None,
        vector_store: Any = None,  # accepted for back-compat; unused
    ) -> None:
        self.config = config or build_default_config()
        self.index = lexical_index or LexicalIndex(self.config)
        self.store = vector_store  # legacy attribute; prefer self.index

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        domain_filter: str | None = None,
        min_score: float = 0.0,
        max_tokens: int | None = None,
        ensure_domains: list[str] | None = None,
        include_historical: bool = True,
    ) -> ContextAssembly:
        t0 = time.time()
        k = top_k or self.config.top_k_default

        hits = self.index.search(
            query,
            top_k=k * 2 if ensure_domains else k,
            truth_class_filter=domain_filter,
            include_historical=include_historical,
        )
        hybrid = [_hit_to_hybrid(h) for h in hits]

        if min_score > 0.0:
            hybrid = [h for h in hybrid if h.score >= min_score]

        if ensure_domains:
            present = {h.truth_class for h in hybrid}
            for tc in ensure_domains:
                if tc in present:
                    continue
                extra = self.index.search(
                    query, top_k=1, truth_class_filter=tc, include_historical=True
                )
                hybrid.extend(_hit_to_hybrid(h) for h in extra)
            hybrid.sort(key=lambda r: -r.score)
            hybrid = hybrid[:k]
        else:
            hybrid = hybrid[:k]

        total_tokens = 0
        truncated: list[HybridResult] = []
        for hr in hybrid:
            estimated = max(len(hr.text) // 4, 1)
            if max_tokens and total_tokens + estimated > max_tokens:
                break
            total_tokens += estimated
            truncated.append(hr)

        by_class: dict[str, list[HybridResult]] = {}
        for hr in truncated:
            by_class.setdefault(hr.truth_class or hr.domain or "UNKNOWN", []).append(hr)

        flags = detect_divergences(truncated, repo_root=self.config.repo_root)
        registry_hits = self.index.lookup_records(query)

        elapsed = time.time() - t0
        return ContextAssembly(
            query=query,
            chunks=truncated,
            total_chunks=len(truncated),
            total_tokens=total_tokens,
            retrieval_time_ms=round(elapsed * 1000, 2),
            domains_covered=set(by_class),
            by_truth_class=by_class,
            divergence_flags=flags,
            registry_hits=registry_hits,
        )

    def format_for_claude(self, ctx: ContextAssembly) -> str:
        """Tier-partitioned prompt block — never a blended paragraph."""
        lines = [
            "## Retrieved Context (truth-tier RAG)",
            "",
            f"Query: `{ctx.query}`",
            f"Truth classes: {', '.join(sorted(ctx.domains_covered))}",
            f"Retrieval time: {ctx.retrieval_time_ms}ms",
            f"Total spans: {ctx.total_chunks}  ·  ~{ctx.total_tokens} tokens",
            "",
        ]
        if ctx.divergence_flags:
            lines.append("### Divergence flags")
            for fl in ctx.divergence_flags:
                lines.append(
                    f"- **{fl.kind}**: {fl.detail or fl.symbol_or_id} "
                    f"(classes={fl.truth_classes})"
                )
            lines.append("")

        order = ["CURRENT", "RECORDED", "INTENDED", "REFERENCE", "HISTORICAL"]
        seen = set()
        for tc in order + sorted(ctx.by_truth_class):
            if tc in seen or tc not in ctx.by_truth_class:
                continue
            seen.add(tc)
            lines.append(f"### Truth class: {tc}")
            lines.append("")
            for i, chunk in enumerate(ctx.by_truth_class[tc], 1):
                marker = ""
                if chunk.lifecycle_status and chunk.lifecycle_status != "LIVE":
                    marker = f"  ·  **{chunk.lifecycle_status}**"
                lines.append(f"#### [{tc}:{i}] `{chunk.filepath}`{marker}")
                if chunk.heading:
                    lines.append(f"**Section:** {chunk.heading}")
                lines.append(
                    f"**Score:** {chunk.score:.3f}  ·  "
                    f"**Lines:** {chunk.start_line}–{chunk.end_line}  ·  "
                    f"**sha:** `{chunk.content_sha[:12]}`"
                )
                if chunk.confidence:
                    lines.append(f"**Confidence:** {chunk.confidence}")
                lines.append("")
                lines.append("```" + self._suffix(chunk.filepath))
                lines.append(chunk.text[:800])
                if len(chunk.text) > 800:
                    lines.append("... (truncated)")
                lines.append("```")
                lines.append("")

        if ctx.registry_hits:
            lines.append("### Registry records (exact)")
            for rec in ctx.registry_hits[:10]:
                lines.append(
                    f"- `{rec.get('id')}` [{rec.get('type')}] "
                    f"status={rec.get('status')} — {str(rec.get('conclusion', ''))[:160]}"
                )
            lines.append("")

        return "\n".join(lines)

    def format_compact(self, ctx: ContextAssembly) -> str:
        lines = [
            "## RAG: " + ctx.query,
            (
                f"({ctx.total_chunks} spans / {', '.join(sorted(ctx.domains_covered))}, "
                f"{ctx.retrieval_time_ms}ms, flags={len(ctx.divergence_flags)})"
            ),
            "",
        ]
        for i, chunk in enumerate(ctx.chunks[:5], 1):
            excerpt = chunk.text[:200].replace("\n", " ")
            marker = (
                f" [{chunk.lifecycle_status}]"
                if chunk.lifecycle_status not in ("", "LIVE")
                else ""
            )
            lines.append(
                f"{i}. `{chunk.filepath}` [{chunk.truth_class}]{marker} "
                f"L{chunk.start_line}-{chunk.end_line} — {excerpt}…"
            )
        if len(ctx.chunks) > 5:
            lines.append(f"… and {len(ctx.chunks) - 5} more")
        return "\n".join(lines)

    @staticmethod
    def _suffix(filepath: str) -> str:
        ext = filepath.rsplit(".", 1)[-1].lower() if "." in filepath else ""
        return {
            "py": "python",
            "md": "markdown",
            "yaml": "yaml",
            "yml": "yaml",
            "json": "json",
            "jsonl": "json",
        }.get(ext, "")
