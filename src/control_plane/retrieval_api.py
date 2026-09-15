"""
retrieval_api.py — KnowledgeAPI: truth-tier RAG surface for the control plane.

Follows ContextReportAPI / RunReportAPI shape:
  - Returns {"ok": bool, ...}, never raises to the HTTP layer
  - Dependency-injected pipeline when provided
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))


class KnowledgeAPI:
    """Truth-tier retrieval payloads for /api/knowledge/*."""

    def __init__(self, pipeline: Any | None = None) -> None:
        self._pipeline = pipeline

    def _pipe(self) -> Any:
        if self._pipeline is not None:
            return self._pipeline
        from retrieval import RetrievalPipeline

        self._pipeline = RetrievalPipeline()
        return self._pipeline

    def status_payload(self) -> dict[str, Any]:
        try:
            pipe = self._pipe()
            st = pipe.index_store.status()
            return {"ok": True, **st}
        except Exception as exc:  # noqa: BLE001 — API never raises
            return {"ok": False, "error": str(exc)}

    def search_payload(
        self,
        q: str,
        top_k: int = 10,
        truth_class: str | None = None,
        include_historical: bool = True,
        explain: bool = False,
    ) -> dict[str, Any]:
        try:
            if not q or not str(q).strip():
                return {"ok": False, "error": "q is required"}
            pipe = self._pipe()
            ctx = pipe.retriever.retrieve(
                str(q),
                top_k=int(top_k),
                domain_filter=truth_class or None,
                include_historical=bool(include_historical),
            )
            spans = []
            for c in ctx.chunks:
                spans.append(
                    {
                        "chunk_id": c.chunk_id,
                        "filepath": c.filepath,
                        "start_line": c.start_line,
                        "end_line": c.end_line,
                        "truth_class": c.truth_class,
                        "authority_rank": c.authority_rank,
                        "lifecycle_status": c.lifecycle_status,
                        "status_evidence": c.status_evidence,
                        "heading": c.heading,
                        "score": c.score,
                        "content_sha": c.content_sha,
                        "confidence": c.confidence,
                        "text": c.text,
                        "ids": c.ids,
                    }
                )
            by_class = {
                tc: [
                    {
                        "chunk_id": c.chunk_id,
                        "filepath": c.filepath,
                        "start_line": c.start_line,
                        "end_line": c.end_line,
                        "lifecycle_status": c.lifecycle_status,
                        "score": c.score,
                        "heading": c.heading,
                        "text": c.text[:500],
                    }
                    for c in lst
                ]
                for tc, lst in ctx.by_truth_class.items()
            }
            flags = [
                {
                    "kind": f.kind,
                    "symbol_or_id": f.symbol_or_id,
                    "truth_classes": f.truth_classes,
                    "chunk_ids": f.chunk_ids,
                    "detail": f.detail,
                    "conflict": f.conflict,
                }
                for f in ctx.divergence_flags
            ]
            out: dict[str, Any] = {
                "ok": True,
                "query": ctx.query,
                "retrieval_time_ms": ctx.retrieval_time_ms,
                "total_spans": ctx.total_chunks,
                "truth_classes": sorted(ctx.domains_covered),
                "by_truth_class": by_class,
                "spans": spans,
                "divergence_flags": flags,
                "registry_hits": ctx.registry_hits,
            }
            if explain:
                out["formatted"] = pipe.retriever.format_for_claude(ctx)
            return out
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc), "query": q}
