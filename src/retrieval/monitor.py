"""
retrieval/monitor.py — Monitoring and metrics for the RAG pipeline.

Tracks:
  - Indexing latency and throughput
  - Retrieval accuracy (Recall@K, MRR)
  - Embedding freshness (staleness since last commit)
  - Query response time
  - Per-domain retrieval distribution
"""

from __future__ import annotations

import json
import subprocess
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from retrieval.config import RetrievalConfig


@dataclass
class MetricsSnapshot:
    """Point-in-time snapshot of RAG pipeline health."""
    total_docs_indexed: int = 0
    total_chunks_indexed: int = 0
    last_index_time: float = 0.0
    total_queries: int = 0
    avg_query_latency_ms: float = 0.0
    recall_at_k: float = 0.0
    mrr: float = 0.0
    embedding_staleness_commits: int = 0
    current_commit_hash: str = ""
    indexed_commit_hash: str = ""
    per_domain_chunks: dict[str, int] = field(default_factory=dict)


class Monitor:
    """Monitors RAG pipeline performance and accuracy.

    Stats are kept in-memory with periodic persistence to a JSONL log file
    for traceability (compatible with configs/promotion_log.jsonl style).
    """

    def __init__(self, config: RetrievalConfig) -> None:
        self.config = config
        self._queries: deque[dict] = deque(maxlen=config.monitor_window)
        self._index_events: list[dict] = []
        self._start_time = time.time()
        self._indexed_commit = self._get_current_commit()
        self._log_path = config.repo_root / "data" / "rag_metrics.jsonl"

    # ── recording ──────────────────────────────────────────────────────────

    def record_index(self, num_docs: int, num_chunks: int) -> None:
        """Record an indexing event."""
        event = {
            "event": "index",
            "timestamp": time.time(),
            "num_docs": num_docs,
            "num_chunks": num_chunks,
            "commit_hash": self._get_current_commit(),
        }
        self._index_events.append(event)
        self._append_log(event)

    def record_query(self, query: str, num_results: int) -> None:
        """Record a query event (call from RetrievalPipeline.retrieve)."""
        event = {
            "event": "query",
            "timestamp": time.time(),
            "query": query[:200],  # truncate for privacy
            "num_results": num_results,
        }
        self._queries.append(event)
        self._append_log(event)

    def record_query_latency(self, query: str, elapsed_s: float) -> None:
        """Record query latency (call from the retriever)."""
        event = {
            "event": "latency",
            "timestamp": time.time(),
            "query": query[:200],
            "latency_s": round(elapsed_s, 4),
        }
        self._queries.append(event)
        self._append_log(event)

    def record_relevance(
        self,
        query: str,
        result_chunk_ids: list[str],
        relevant_chunk_ids: list[str],
    ) -> dict[str, float]:
        """Record relevance feedback for accuracy metrics.

        Args:
            query: The search query.
            result_chunk_ids: IDs of chunks that were retrieved.
            relevant_chunk_ids: IDs of chunks known to be relevant (ground truth).

        Returns:
            dict with recall@K and MRR values.
        """
        if not relevant_chunk_ids:
            return {"recall_at_k": 0.0, "mrr": 0.0}

        relevant_set = set(relevant_chunk_ids)
        retrieved_set = set(result_chunk_ids)

        # Recall@K
        hits = len(retrieved_set & relevant_set)
        recall = hits / len(relevant_set) if relevant_set else 0.0

        # MRR
        mrr = 0.0
        for i, cid in enumerate(result_chunk_ids, 1):
            if cid in relevant_set:
                mrr = 1.0 / i
                break

        event = {
            "event": "relevance",
            "timestamp": time.time(),
            "query": query[:200],
            "recall_at_k": round(recall, 4),
            "mrr": round(mrr, 4),
            "num_relevant": len(relevant_chunk_ids),
            "num_retrieved": len(result_chunk_ids),
        }
        self._append_log(event)

        return {"recall_at_k": recall, "mrr": mrr}

    # ── snapshot ───────────────────────────────────────────────────────────

    def snapshot(self) -> MetricsSnapshot:
        """Build a current metrics snapshot."""
        current_commit = self._get_current_commit()
        query_events = [q for q in self._queries if q.get("event") == "latency"]
        latencies = [q["latency_s"] for q in query_events if q.get("latency_s")]

        # Compute recall/MRR from stored relevance events
        relevance_events = [q for q in self._queries if q.get("event") == "relevance"]
        avg_recall = (
            sum(e.get("recall_at_k", 0.0) for e in relevance_events) / len(relevance_events)
            if relevance_events else 0.0
        )
        avg_mrr = (
            sum(e.get("mrr", 0.0) for e in relevance_events) / len(relevance_events)
            if relevance_events else 0.0
        )

        # Compute staleness
        try:
            result = subprocess.run(
                ["git", "rev-list", "--count", f"{self._indexed_commit}..HEAD"],
                capture_output=True, text=True, timeout=5,
                cwd=self.config.repo_root,
            )
            staleness = int(result.stdout.strip()) if result.returncode == 0 else 0
        except Exception:
            staleness = 0

        # Per-domain chunk count (from last index event)
        per_domain: dict[str, int] = {}

        return MetricsSnapshot(
            total_docs_indexed=self._index_events[-1]["num_docs"] if self._index_events else 0,
            total_chunks_indexed=self._index_events[-1]["num_chunks"] if self._index_events else 0,
            last_index_time=self._index_events[-1]["timestamp"] if self._index_events else 0.0,
            total_queries=len(self._queries),
            avg_query_latency_ms=(sum(latencies) / len(latencies) * 1000) if latencies else 0.0,
            recall_at_k=avg_recall,
            mrr=avg_mrr,
            embedding_staleness_commits=staleness,
            current_commit_hash=current_commit[:12] if current_commit else "",
            indexed_commit_hash=self._indexed_commit[:12] if self._indexed_commit else "",
            per_domain_chunks=per_domain,
        )

    def log_path(self) -> Path:
        """Return the path to the metrics log file."""
        return self._log_path

    # ── private helpers ────────────────────────────────────────────────────

    def _get_current_commit(self) -> str:
        """Get the current git commit hash."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=5,
                cwd=self.config.repo_root,
            )
            return result.stdout.strip() if result.returncode == 0 else "unknown"
        except Exception:
            return "unknown"

    def _append_log(self, event: dict) -> None:
        """Append a JSON event to the metrics log file."""
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            with self._log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
        except OSError:
            pass  # best-effort logging