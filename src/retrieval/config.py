"""
retrieval/config.py — Configuration for the RAG pipeline.

All tunables are surfaced here. The default config is production-sensible for
this codebase (~200K lines of Python + ~500 docs). Override via env vars or
by passing a RetrievalConfig instance to RetrievalPipeline().
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class RetrievalConfig:
    """Configuration for the RAG pipeline.

    Attributes:
        repo_root: Absolute path to the repository root.
        chroma_path: Directory for ChromaDB persistent storage.
        embedding_model: Sentence-transformers model name.
        embedding_dim: Dimensionality of the embedding model output.
        chunk_max_chars: Maximum characters per chunk (soft cap — language
            constructs override this).
        chunk_overlap_chars: Overlap between adjacent chunks in characters.
        top_k_default: Default number of results to return.
        hybrid_alpha: Weight for semantic vs keyword score (0=keyword only,
            1=semantic only, 0.5=balanced).
        structural_boost: Multiplier for structural metadata matches
            (e.g., exact class/function name match).
        domain_weights: Per-domain boost factors for reranking.
        index_batch_size: Number of chunks to embed in a single batch.
        monitor_window: Number of recent queries to keep for metrics.
        git_commit_cmd: Command to get the latest commit hash for freshness.
    """
    repo_root: Path = _REPO_ROOT
    chroma_path: Path = _REPO_ROOT / "data" / "chroma_db"
    embedding_model: str = "all-MiniLM-L6-v2"  # 384-dim, fast, good for code
    embedding_dim: int = 384
    chunk_max_chars: int = 1500
    chunk_overlap_chars: int = 200
    top_k_default: int = 10
    hybrid_alpha: float = 0.7
    structural_boost: float = 1.5
    domain_weights: dict[str, float] = field(default_factory=lambda: {
        "source_code": 1.2,
        "architecture": 1.1,
        "governance": 1.0,
        "analysis": 0.9,
        "intent": 1.1,
        "operations": 1.0,
        "config": 0.8,
        "tests": 0.9,
        "research": 0.8,
    })
    index_batch_size: int = 32
    monitor_window: int = 1000
    git_commit_cmd: str = "git rev-parse HEAD"

    # ── domain → glob patterns ─────────────────────────────────────────────
    domain_patterns: dict[str, list[str]] = field(default_factory=lambda: {
        "source_code": ["src/**/*.py"],
        "architecture": ["docs/architecture/*.md"],
        "governance": [
            "docs/governance/*.md",
            "docs/governance/*.json",
            "docs/governance/*.jsonl",
        ],
        "analysis": ["docs/analysis/*.md"],
        "intent": ["docs/intent/*.md"],
        "operations": ["docs/operations/*.md"],
        "config": [
            "configs/**/*.yaml",
            "configs/**/*.json",
        ],
        "tests": ["tests/**/*.py"],
        "research": [
            "docs/research/**/*.md",
            "results/research/**/*.md",
        ],
    })

    # ── files / dirs to exclude ─────────────────────────────────────────────
    exclude_patterns: list[str] = field(default_factory=lambda: [
        "__pycache__",
        ".git",
        "node_modules",
        "venv",
        ".venv",
        "archive",
        "data/chroma_db",
    ])


def build_default_config() -> RetrievalConfig:
    """Build a RetrievalConfig, overriding from environment variables."""
    cfg = RetrievalConfig()
    if os.environ.get("RAG_CHROMA_PATH"):
        cfg.chroma_path = Path(os.environ["RAG_CHROMA_PATH"])
    if os.environ.get("RAG_EMBEDDING_MODEL"):
        cfg.embedding_model = os.environ["RAG_EMBEDDING_MODEL"]
    if os.environ.get("RAG_TOP_K"):
        cfg.top_k_default = int(os.environ["RAG_TOP_K"])
    if os.environ.get("RAG_HYBRID_ALPHA"):
        cfg.hybrid_alpha = float(os.environ["RAG_HYBRID_ALPHA"])
    return cfg