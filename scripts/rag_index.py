"""
rag_index.py — CLI for the truth-tier lexical RAG pipeline.

Usage:
    python scripts/rag_index.py index --rebuild
    python scripts/rag_index.py query "why is rr_fusion disabled" --explain
    python scripts/rag_index.py discover
    python scripts/rag_index.py metrics
    python scripts/rag_index.py status
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from retrieval import RetrievalPipeline
from retrieval.config import build_default_config
from retrieval.corpus import CorpusDiscoverer
from retrieval.claude_integration import (
    get_context,
    format_context,
    GroundingGate,
)


def cmd_index(args: list[str]) -> None:
    rebuild = "--rebuild" in args or "index" == (args[0] if args else "")
    # also accept bare: rag_index.py --rebuild
    rebuild = "--rebuild" in args
    pipe = RetrievalPipeline()
    t0 = time.time()
    total = pipe.index(rebuild=rebuild or True)
    elapsed = time.time() - t0
    print(f"Indexed {total} chunks in {elapsed:.2f}s")
    print(f"Index dir: {pipe.config.index_dir}")
    st = pipe.index_store.status()
    print(json.dumps({k: st[k] for k in st if k != "manifest"}, indent=2))


def cmd_query(args: list[str]) -> None:
    if not args or args[0].startswith("--"):
        print("Usage: python scripts/rag_index.py query <query_text> [--explain] [--top-k N]")
        return
    query = args[0]
    top_k = 10
    explain = "--explain" in args
    domain_filter = None
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

    pipe = RetrievalPipeline()
    ctx = pipe.retrieve_assembly(query, top_k=top_k, domain_filter=domain_filter)
    print(pipe.retriever.format_for_claude(ctx) if explain else format_context(ctx))
    print("\n--- Metrics ---")
    print(f"Retrieval time: {ctx.retrieval_time_ms}ms")
    print(f"Truth classes: {', '.join(sorted(ctx.domains_covered))}")
    print(f"Spans: {ctx.total_chunks}  ·  flags: {len(ctx.divergence_flags)}")
    if explain and ctx.divergence_flags:
        print("--- Divergence ---")
        for fl in ctx.divergence_flags:
            print(f"  [{fl.kind}] {fl.detail}")


def cmd_metrics(_args: list[str]) -> None:
    pipe = RetrievalPipeline()
    metrics = pipe.metrics()
    print("=== RAG Pipeline Metrics ===")
    print(f"Total docs indexed:     {metrics.total_docs_indexed}")
    print(f"Total chunks indexed:   {metrics.total_chunks_indexed}")
    print(f"Total queries:          {metrics.total_queries}")
    print(f"Avg query latency:      {metrics.avg_query_latency_ms:.1f}ms")
    print(f"Recall@K:               {metrics.recall_at_k:.3f}")
    print(f"MRR:                    {metrics.mrr:.3f}")


def cmd_status(_args: list[str]) -> None:
    pipe = RetrievalPipeline()
    print(json.dumps(pipe.index_store.status(), indent=2, default=str))


def cmd_discover(_args: list[str]) -> None:
    config = build_default_config()
    discoverer = CorpusDiscoverer(config)
    docs = discoverer.discover()
    by_class: dict[str, list[str]] = {}
    for doc in docs:
        rel = doc.metadata.get("filepath", str(doc.path))
        by_class.setdefault(doc.truth_class, []).append(rel)
    print(f"Discovered {len(docs)} documents:")
    for tc, paths in sorted(by_class.items()):
        print(f"\n  {tc} ({len(paths)} files):")
        for p in paths[:10]:
            print(f"    - {p}")
        if len(paths) > 10:
            print(f"    ... and {len(paths) - 10} more")


def cmd_verify(args: list[str]) -> None:
    if len(args) < 1:
        print("Usage: python scripts/rag_index.py verify <query_or_claim> [--ground]")
        return
    query = args[0]
    gate = GroundingGate()
    result = gate.verify(query, ground="--ground" in args)
    print(json.dumps(result, indent=2, default=str))


def main() -> None:
    argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        return
    # Allow: python scripts/rag_index.py --rebuild
    if argv[0] in ("--rebuild", "--incremental"):
        cmd_index(argv)
        return
    command = argv[0]
    args = argv[1:]
    commands = {
        "index": cmd_index,
        "incremental": lambda a: cmd_index(["--rebuild"] + a),
        "query": cmd_query,
        "metrics": cmd_metrics,
        "discover": cmd_discover,
        "verify": cmd_verify,
        "status": cmd_status,
    }
    if command in commands:
        commands[command](args)
    else:
        print(f"Unknown command: {command}")
        print(__doc__)


if __name__ == "__main__":
    main()
