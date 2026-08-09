"""
retrieval/claude_integration.py — Integration with Claude Code for RAG-grounded tasks.

This module provides:
  1. A `RAGContextProvider` that Claude Code can call before task execution to
     retrieve relevant context from the codebase.
  2. A `get_context()` function that returns structured context for any query.
  3. A constraint enforcer that ensures code generation and architectural
     recommendations are restricted to retrieved context in enterprise mode.

Architecture:
  - Claude Code calls `get_context(query)` at task start.
  - The context is prepended to the system prompt.
  - `EnterpriseGate.verify()` is called before any code generation to ensure
    the output is grounded in retrieved evidence.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Callable

from retrieval import RetrievalPipeline, HybridResult
from retrieval.config import RetrievalConfig, build_default_config
from retrieval.retriever import ContextAssembly, Retriever


# ── environment flag for enterprise mode ───────────────────────────────────
_ENTERPRISE_MODE = os.environ.get("RAG_ENTERPRISE_MODE", "1") == "1"


# ── singleton pipeline ─────────────────────────────────────────────────────
_pipeline: RetrievalPipeline | None = None


def _get_pipeline() -> RetrievalPipeline:
    """Get or initialize the singleton RetrievalPipeline."""
    global _pipeline
    if _pipeline is None:
        cfg = build_default_config()
        _pipeline = RetrievalPipeline(cfg)
    return _pipeline


# ── public API ─────────────────────────────────────────────────────────────


def get_context(
    query: str,
    top_k: int | None = None,
    domain_filter: str | None = None,
    max_tokens: int = 2000,
    ensure_domains: list[str] | None = None,
) -> ContextAssembly:
    """Retrieve relevant context for a Claude Code task.

    This is the primary entry point. Call it at the start of any task to
    ground the LLM in retrieved evidence from the codebase.

    Args:
        query: The task description or question to search for.
        top_k: Number of chunks to retrieve.
        domain_filter: Optional domain to restrict search.
        max_tokens: Maximum estimated tokens for the context block.
        ensure_domains: Guarantee coverage from these domains.

    Returns:
        ContextAssembly ready for formatting.
    """
    pipe = _get_pipeline()
    retriever = Retriever(pipe.store, pipe.config)
    return retriever.retrieve(
        query=query,
        top_k=top_k or pipe.config.top_k_default,
        domain_filter=domain_filter,
        max_tokens=max_tokens,
        ensure_domains=ensure_domains or ["source_code", "architecture", "governance"],
    )


def format_context(ctx: ContextAssembly, compact: bool = False) -> str:
    """Format a ContextAssembly as a string for inclusion in an LLM prompt.

    Args:
        ctx: The context to format.
        compact: If True, use compact format (for system prompts).

    Returns:
        Formatted markdown string.
    """
    pipe = _get_pipeline()
    retriever = Retriever(pipe.store, pipe.config)
    if compact:
        return retriever.format_compact(ctx)
    return retriever.format_for_claude(ctx)


def get_formatted_context(
    query: str,
    top_k: int | None = None,
    domain_filter: str | None = None,
    max_tokens: int = 2000,
    compact: bool = False,
) -> str:
    """Convenience: retrieve AND format context in one call."""
    ctx = get_context(query, top_k, domain_filter, max_tokens)
    return format_context(ctx, compact=compact)


# ── enterprise mode: constraint enforcement ────────────────────────────────


class EnterpriseGate:
    """Verifies that code generation and recommendations are grounded in evidence.

    In enterprise mode (`RAG_ENTERPRISE_MODE=1`), this gate is called before
    any code generation or architectural recommendation to ensure the output
    cites retrieved context.
    """

    def __init__(self, pipeline: RetrievalPipeline | None = None) -> None:
        self.pipeline = pipeline or _get_pipeline()

    @staticmethod
    def is_active() -> bool:
        """Check if enterprise constraint mode is active."""
        return _ENTERPRISE_MODE

    def verify(
        self,
        task_description: str,
        proposed_code_or_recommendation: str,
        min_chunks: int = 1,
    ) -> dict:
        """Verify that a code/recommendation is grounded in retrieved evidence.

        Args:
            task_description: The original task that prompted this work.
            proposed_code_or_recommendation: The code or recommendation text.
            min_chunks: Minimum number of context chunks required for grounding.

        Returns:
            dict with:
              - grounded: bool — whether the proposal is sufficiently grounded.
              - retrieved_chunks: list of chunk IDs used.
              - score: average relevance score.
              - reason: explanation string.
        """
        if not _ENTERPRISE_MODE:
            return {"grounded": True, "retrieved_chunks": [], "score": 1.0,
                    "reason": "Enterprise mode disabled — no constraint enforced."}

        # Retrieve context for the task
        ctx = get_context(task_description, top_k=10, max_tokens=4000)
        chunk_ids = [c.chunk_id for c in ctx.chunks]
        avg_score = sum(c.score for c in ctx.chunks) / max(len(ctx.chunks), 1)

        if len(ctx.chunks) < min_chunks:
            return {
                "grounded": False,
                "retrieved_chunks": chunk_ids,
                "score": avg_score,
                "reason": (
                    f"Insufficient evidence: only {len(ctx.chunks)} chunks retrieved "
                    f"(need ≥{min_chunks}). Add authoritative documentation before "
                    f"proceeding. Retrieved from: {', '.join(sorted(ctx.domains_covered))}."
                ),
            }

        # Verify the proposal references at least one chunk by filename
        proposal_lower = proposed_code_or_recommendation.lower()
        referenced = [c for c in ctx.chunks if c.filepath.lower() in proposal_lower
                      or (c.heading and c.heading.lower() in proposal_lower)]

        if not referenced:
            return {
                "grounded": False,
                "retrieved_chunks": chunk_ids,
                "score": avg_score,
                "reason": (
                    "Proposed code/recommendation does not explicitly reference "
                    "any retrieved source file. In enterprise mode, all code "
                    "generation must cite its evidence. Include file paths or "
                    "section names from the retrieved context."
                ),
            }

        return {
            "grounded": True,
            "retrieved_chunks": [r.chunk_id for r in referenced],
            "score": avg_score,
            "reason": f"Verified: grounded in {len(referenced)} chunks from retrieved context.",
        }


# ── task decorator ─────────────────────────────────────────────────────────


def rag_grounded(task_fn: Callable) -> Callable:
    """Decorator that automatically retrieves context before task execution.

    Usage::

        @rag_grounded
        def implement_crt_state_machine(task_description: str) -> str:
            # The function receives `_rag_context` as an extra keyword argument
            ...
    """
    import functools

    @functools.wraps(task_fn)
    def wrapper(*args, **kwargs):
        # Extract task description from args or kwargs
        task_desc = kwargs.get("task_description", args[0] if args else "")
        if task_desc:
            ctx = get_context(task_desc)
            kwargs["_rag_context"] = ctx
            kwargs["_rag_context_str"] = format_context(ctx)
        else:
            kwargs["_rag_context"] = None
            kwargs["_rag_context_str"] = ""
        return task_fn(*args, **kwargs)

    return wrapper