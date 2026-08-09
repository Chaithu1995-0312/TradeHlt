"""
rag_index.py — CLI entry point for the RAG pipeline.

Usage:
    # Build / rebuild the full index
    python scripts/rag_index.py --rebuild

    # Incremental index (add new chunks since last index)
    python scripts/rag_index.py --incremental

    # Query the index
    python scripts/rag_index.py query "CRT state machine behaviour"

    # Retrieve with domain filter
    python scripts/rag_index.py query "fusion engine" --domain source_code --top-k 5

    # Show metrics
    python scripts/rag_index.py metrics

    # Check enterprise gate
    python scripts/rag_index.py verify "task desc" "proposed code"

    # List discovered documents (dry run)
    python scripts/rag_index.py discover
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Ensure src/ is on the path
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from retrieval import RetrievalPipeline
from retrieval.config import build_default_config
from retrieval.corpus import CorpusDiscoverer
from retrieval.retriever import Retriever
from retrieval.claude_integration import (
    get_context,
    format_context,
    get_formatted_context,
    EnterpriseGate,
)


def cmd_index(args: list[str]) -> None:
    """Build or rebuild the full index."""
    rebuild = "--rebuild" in args
    pipe = RetrievalPipeline()

    if rebuild:
        print("Deleting existing collection...")
        pipe.store.delete_collection()

    t0 = time.time()
    total = pipe.index()
    elapsed = time.time() - t0

    print(f"Indexed {total} chunks in {elapsed:.2f}s ({total / elapsed:.0f} chunks/s)")
    print(f"Vector store location: {pipe.config.chroma_path}")


def cmd_incremental(args: list[str]) -> None:
    """Incremental index — re-index from scratch (simplified)."""
    # For simplicity, this is an alias for --rebuild. A production version
    # would diff the git tree and only re-index changed files.
    cmd_index(["--rebuild"])


def cmd_query(args: list[str]) -> None:
    """Query the index and display results."""
    if not args or args[0].startswith("--"):
        print("Usage: python scripts/rag_index.py query <query_text> [options]")
        return

    query = args[0]
    domain_filter = None
    top_k = 10

    i = 1
    while i < len(args):
        if args[i] == "--domain" and i + 1 < len(args):
            domain_filter = args[i + 1]
            i += 2
        elif args[i] == "--top-k" and i + 1 < len(args):
            top_k = int(args[i + 1])
            i += 2
        else:
            i += 1

    ctx = get_context(query, top_k=top_k, domain_filter=domain_filter, max_tokens=4000)
    print(format_context(ctx))

    print(f"\n--- Metrics ---")
    print(f"Retrieval time: {ctx.retrieval_time_ms}ms")
    print(f"Domains: {', '.join(sorted(ctx.domains_covered))}")
    print(f"Total chunks: {ctx.total_chunks}  ·  ~{ctx.total_tokens} tokens")


def cmd_metrics(args: list[str]) -> None:
    """Display RAG pipeline metrics."""
    pipe = RetrievalPipeline()
    metrics = pipe.metrics()
    print("=== RAG Pipeline Metrics ===")
    print(f"Total docs indexed:     {metrics.total_docs_indexed}")
    print(f"Total chunks indexed:   {metrics.total_chunks_indexed}")
    print(f"Total queries:          {metrics.total_queries}")
    print(f"Avg query latency:      {metrics.avg_query_latency_ms:.1f}ms")
    print(f"Recall@K:               {metrics.recall_at_k:.3f}")
    print(f"MRR:                    {metrics.mrr:.3f}")
    print(f"Embedding staleness:    {metrics.embedding_staleness_commits} commits behind")
    print(f"Current commit:         {metrics.current_commit_hash}")
    print(f"Indexed at commit:      {metrics.indexed_commit_hash}")


def cmd_discover(args: list[str]) -> None:
    """Discover documents without indexing (dry run)."""
    config = build_default_config()
    discoverer = CorpusDiscoverer(config)
    docs = discoverer.discover()
    by_domain: dict[str, list[str]] = {}
    for doc in docs:
        rel = str(doc.path.relative_to(config.repo_root))
        by_domain.setdefault(doc.domain, []).append(rel)

    print(f"Discovered {len(docs)} documents:")
    for domain, paths in sorted(by_domain.items()):
        print(f"\n  {domain} ({len(paths)} files):")
        for p in paths[:10]:
            print(f"    - {p}")
        if len(paths) > 10:
            print(f"    ... and {len(paths) - 10} more")


def cmd_verify(args: list[str]) -> None:
    """Verify enterprise gate."""
    if len(args) < 2:
        print("Usage: python scripts/rag_index.py verify <task_description> <proposed_code>")
        return
    task_desc = args[0]
    proposed = args[1]
    gate = EnterpriseGate()
    result = gate.verify(task_desc, proposed)
    print(f"Grounded: {result['grounded']}")
    print(f"Score:    {result['score']:.3f}")
    print(f"Reason:   {result['reason']}")
    if result.get("retrieved_chunks"):
        print(f"Chunks:   {len(result['retrieved_chunks'])} retrieved")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return

    command = sys.argv[1]
    args = sys.argv[2:]

    commands = {
        "index": cmd_index,
        "incremental": cmd_incremental,
        "query": cmd_query,
        "metrics": cmd_metrics,
        "discover": cmd_discover,
        "verify": cmd_verify,
    }

    if command in commands:
        commands[command](args)
    else:
        print(f"Unknown command: {command}")
        print(__doc__)


if __name__ == "__main__":
    main()