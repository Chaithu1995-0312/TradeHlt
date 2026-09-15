"""
retrieval/claude_integration.py — Claude / control-plane integration for truth-tier RAG.

Retrieval is NOT grounding. Optional --ground routes asserted ids through
src/governance/semantic_grounding.py and surfaces statuses verbatim
(GROUNDED / UNKNOWN / AMBIGUOUS / UNANSWERABLE / REFUSED). REFUSED is never
smoothed into prose.
"""

from __future__ import annotations

import os
from typing import Any, Callable

from retrieval import RetrievalPipeline
from retrieval.config import build_default_config
from retrieval.retriever import ContextAssembly, Retriever
from retrieval.truth_tier import extract_ids

_ENTERPRISE_MODE = os.environ.get("RAG_ENTERPRISE_MODE", "1") == "1"
_pipeline: RetrievalPipeline | None = None


def _get_pipeline() -> RetrievalPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = RetrievalPipeline(build_default_config())
    return _pipeline


def get_context(
    query: str,
    top_k: int | None = None,
    domain_filter: str | None = None,
    max_tokens: int = 2000,
    ensure_domains: list[str] | None = None,
) -> ContextAssembly:
    pipe = _get_pipeline()
    return pipe.retrieve_assembly(
        query=query,
        top_k=top_k or pipe.config.top_k_default,
        domain_filter=domain_filter,
        max_tokens=max_tokens,
    )


def format_context(ctx: ContextAssembly, compact: bool = False) -> str:
    pipe = _get_pipeline()
    if compact:
        return pipe.retriever.format_compact(ctx)
    return pipe.retriever.format_for_claude(ctx)


def get_formatted_context(
    query: str,
    top_k: int | None = None,
    domain_filter: str | None = None,
    max_tokens: int = 2000,
    compact: bool = False,
) -> str:
    ctx = get_context(query, top_k, domain_filter, max_tokens)
    return format_context(ctx, compact=compact)


def _ground_ids(ids: list[str]) -> list[dict[str, Any]]:
    """Route each id through semantic_grounding; never invent a status."""
    results: list[dict[str, Any]] = []
    try:
        from governance import semantic_grounding as sg  # type: ignore
    except Exception as exc:  # noqa: BLE001
        return [
            {
                "id": i,
                "status": "UNANSWERABLE",
                "detail": f"semantic_grounding import failed: {exc}",
            }
            for i in ids
        ]

    # Prefer a public API if present; otherwise report UNKNOWN rather than faking.
    ground_fn = None
    for name in ("ground", "ground_id", "verify_id", "lookup", "adjudicate"):
        cand = getattr(sg, name, None)
        if callable(cand):
            ground_fn = cand
            break

    for i in ids:
        if ground_fn is None:
            results.append(
                {
                    "id": i,
                    "status": "UNKNOWN",
                    "detail": "semantic_grounding has no callable ground/lookup API",
                }
            )
            continue
        try:
            raw = ground_fn(i)
        except Exception as exc:  # noqa: BLE001
            results.append({"id": i, "status": "UNANSWERABLE", "detail": str(exc)})
            continue

        status = None
        detail = ""
        if isinstance(raw, dict):
            status = (
                raw.get("status")
                or raw.get("verdict")
                or raw.get("grounding_status")
            )
            detail = str(raw.get("detail") or raw.get("reason") or raw)
        else:
            status = str(raw)
            detail = str(raw)
        status_u = str(status or "UNKNOWN").upper()
        # Never smooth REFUSED
        if "REFUSED" in status_u:
            status_u = "REFUSED"
        results.append({"id": i, "status": status_u, "detail": detail, "raw": raw})
    return results


class GroundingGate:
    """Real grounding join — replaces filepath-substring EnterpriseGate theater."""

    def __init__(self, pipeline: RetrievalPipeline | None = None) -> None:
        self.pipeline = pipeline or _get_pipeline()

    @staticmethod
    def is_active() -> bool:
        return _ENTERPRISE_MODE

    def verify(self, query: str, ground: bool = True) -> dict[str, Any]:
        ctx = self.pipeline.retrieve_assembly(query, top_k=10)
        ids: list[str] = []
        for ch in ctx.chunks:
            ids.extend([x for x in (ch.ids or "").split(",") if x])
        ids.extend(extract_ids(query))
        # de-dupe preserve order
        seen: set[str] = set()
        uniq: list[str] = []
        for i in ids:
            if i not in seen:
                seen.add(i)
                uniq.append(i)

        grounded = _ground_ids(uniq) if ground and uniq else []
        refused = [g for g in grounded if g.get("status") == "REFUSED"]
        return {
            "ok": True,
            "query": query,
            "spans": len(ctx.chunks),
            "truth_classes": sorted(ctx.domains_covered),
            "divergence_flags": [
                {"kind": f.kind, "detail": f.detail, "symbol_or_id": f.symbol_or_id}
                for f in ctx.divergence_flags
            ],
            "ids": uniq,
            "grounding": grounded,
            "refused": refused,
            "note": (
                "REFUSED must never be smoothed into prose"
                if refused
                else "retrieval is not grounding; statuses are verbatim"
            ),
        }


# Back-compat alias — old name still importable
class EnterpriseGate(GroundingGate):
    """Deprecated alias for GroundingGate."""

    def verify(  # type: ignore[override]
        self,
        task_description: str,
        proposed_code_or_recommendation: str = "",
        min_chunks: int = 1,
        ground: bool = True,
    ) -> dict:
        result = GroundingGate.verify(self, task_description, ground=ground)
        # Preserve old keys for callers that still expect them
        result["grounded"] = not bool(result.get("refused")) and result.get("spans", 0) >= min_chunks
        result["retrieved_chunks"] = [c.chunk_id for c in self.pipeline.retrieve_assembly(task_description).chunks]
        result["score"] = 1.0 if result["grounded"] else 0.0
        result["reason"] = result.get("note", "")
        _ = proposed_code_or_recommendation  # intentionally unused — substring theater removed
        return result


def rag_grounded(task_fn: Callable) -> Callable:
    import functools

    @functools.wraps(task_fn)
    def wrapper(*args, **kwargs):
        task_desc = kwargs.get("task_description", args[0] if args else "")
        if task_desc:
            ctx = get_context(str(task_desc))
            kwargs["_rag_context"] = ctx
            kwargs["_rag_context_str"] = format_context(ctx)
        else:
            kwargs["_rag_context"] = None
            kwargs["_rag_context_str"] = ""
        return task_fn(*args, **kwargs)

    return wrapper
