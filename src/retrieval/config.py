"""
retrieval/config.py — Configuration for the truth-tier retrieval pipeline.

All tunables live here. Defaults are sized for this repository's real corpus
(~1,584 Python modules, ~874 markdown docs, plus the governed registries).

What changed and why
--------------------
The previous configuration keyed the corpus by *topic* domain ("source_code",
"architecture", ...). That is the wrong axis for this repository: it cannot
express the difference between a doc that describes intent and code that
executes, which is precisely the distinction CLAUDE.md 6.8 forbids collapsing.
The corpus is now a flat include-list, and each discovered path is classified by
`retrieval.truth_tier` into a truth class. Filtering, weighting and result
partitioning all key off that class.

Three exclusion classes are load-bearing rather than cosmetic:
  * `logs/` (39 GB) is not a text corpus. Its correct retrieval surface is
    DuckDB over Parquet (`scripts/analysis/query_trace.py`); indexing it would
    be both useless and ruinous.
  * `context/` and `*.generated.md` are DERIVED views (MULTI_LLM_PROTOCOL 5
    rule 1). Indexing them beside their sources yields duplicate, drift-prone
    answers for the same question.
  * `.claude/worktrees/`, `msip_1_verification_package/` and
    `reports/_ours_backup/` hold near-duplicate copies of the tree.

`data/mt5/*.csv` is never opened: a direct read there would trip the shrink-only
ratchet in `scripts/analysis/corpus_read_lint.py`. The OHLCV corpus is not
knowledge and has no place in this index.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class RetrievalConfig:
    """Configuration for the truth-tier retrieval pipeline.

    Attributes:
        repo_root: Absolute path to the repository root.
        index_dir: Directory holding the JSONL index and its Parquet sidecars.
        metrics_log_path: Explicit metrics log location. When None it derives
            from `index_dir`, so an overridden root cannot leak writes into the
            real repository during tests.
        chroma_path: Legacy dense-vector store location. Retained only for the
            conditional Phase-5 dense reranker; unused by the lexical core.
        embedding_model / embedding_dim: Dense-phase settings, unused today.
        chunk_max_chars: Soft cap per chunk; language constructs may override.
        chunk_overlap_chars: Overlap between adjacent fallback chunks.
        top_k_default: Default number of results.
        bm25_k1 / bm25_b: Okapi BM25 term-saturation and length-normalisation.
        exact_id_boost: Additive boost when a query names a governed id
            (F-048, FM-031, CC-*) that a chunk carries. Deliberately the
            largest boost: in this repository an id match is near-certain
            relevance, and it is the query shape that dense retrieval handles
            worst.
        symbol_boost: Additive boost for an exact Python symbol match.
        heading_boost: Additive boost for a section-heading match.
        truth_class_weights: Multiplicative weight per truth class.
        non_live_penalty: Multiplier applied to SUPERSEDED / RETIRED / KILLED /
            FROZEN / CONFLICTED chunks. Demoted, never dropped -- 6.2 rule 4
            keeps history, and a demoted result is always rendered with its
            marker.
        include_patterns: Recursive globs defining the corpus.
        exclude_patterns: Path segments / globs excluded before classification.
        registry_sources: JSONL registries loaded as typed records rather than
            chunked as text (see index_store), which is what removes the 85%
            index skew the previous per-line chunker produced.
        max_file_bytes: Skip pathologically large files.
    """
    repo_root: Path = _REPO_ROOT
    index_dir: Path = _REPO_ROOT / "data" / "rag"
    metrics_log_path: Path | None = None
    chroma_path: Path = _REPO_ROOT / "data" / "chroma_db"
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384
    chunk_max_chars: int = 1500
    chunk_overlap_chars: int = 200
    top_k_default: int = 10

    # ── lexical ranking ────────────────────────────────────────────────────
    bm25_k1: float = 1.2
    bm25_b: float = 0.75
    exact_id_boost: float = 4.0
    symbol_boost: float = 2.5
    heading_boost: float = 1.5

    # ── truth-tier ranking ─────────────────────────────────────────────────
    truth_class_weights: dict[str, float] = field(default_factory=lambda: {
        "CURRENT": 1.25,     # what actually executes
        "RECORDED": 1.20,    # registered conclusions, carrying Confidence
        "INTENDED": 1.15,    # what things are supposed to mean
        "REFERENCE": 1.00,   # explanatory; drifts
        # Heavy demotion: with the full docs/ tree indexed, HISTORICAL material
        # outnumbers living truth roughly 10:1 (200 implementation plans, 152
        # analyses, 1,374 archived log entries vs ~40 authoritative files).
        # Without this it drowns the corpus.
        "HISTORICAL": 0.55,
        "DERIVED": 0.0,      # excluded at discovery; belt-and-braces
    })
    non_live_penalty: float = 0.35

    # Two-stage retrieve (eval 2026-09-11): N=100→6.3% refs, N=500→23%,
    # N=5000→81% but median rank ~1119. Fetch candidate_n then rerank.
    candidate_n: int = 600
    stem_boost: float = 4.0
    short_chunk_penalty: float = 0.4
    short_chunk_max_tokens: int = 8
    json_record_penalty: float = 0.35
    file_agg_boost: float = 0.35
    routing_extra_limit: int = 120
    file_route_boost: float = 7.0
    file_route_max_files: int = 8
    file_route_chunks_per_file: int = 6

    # ── corpus scope ───────────────────────────────────────────────────────
    include_patterns: list[str] = field(default_factory=lambda: [
        # Root-level truth surface
        "CLAUDE.md",
        "README.md",
        "active_models.yaml",
        "assistant_project.md",
        "llm_project_assistant.md",
        # Documentation (full tree — user-selected breadth)
        "docs/**/*.md",
        "docs/governance/**/*.yaml",
        "docs/governance/**/*.yml",
        "docs/governance/**/*.json",
        # Meaning authority
        "configs/formulas/**/*.yaml",
        "configs/formulas/**/*.yml",
        # Runtime authority
        "configs/production/ACTIVE_VERSION",
        "configs/production/*.json",
        "configs/**/*.yaml",
        "configs/**/*.json",
        # Code
        "src/**/*.py",
        "tests/**/*.py",
        "scripts/**/*.py",
    ])

    exclude_patterns: list[str] = field(default_factory=lambda: [
        # Build / environment noise
        "__pycache__",
        ".git",
        ".pytest_cache",
        "node_modules",
        "venv",
        ".venv",
        # Near-duplicate trees. Without these the same file is answered twice
        # from two paths, and one copy is silently stale.
        ".claude/worktrees",
        "msip_1_verification_package",
        "reports/_ours_backup",
        ".grok/scratch-design",
        # Derived views — never truth (also enforced in truth_tier).
        "context/",
        ".generated.md",
        # Not a text corpus: 39 GB of runtime streams. Query these through
        # DuckDB over Parquet (scripts/analysis/query_trace.py) instead.
        "logs/",
        # Derived / payload data
        "data/chroma_db",
        "data/rag",
        "data/mt5",
        "master_crypto_training",
    ])

    registry_sources: list[str] = field(default_factory=lambda: [
        "data/findings.jsonl",
        "data/hypothesis_registry.jsonl",
        "data/framework_registry.jsonl",
        "data/script_registry.jsonl",
        "data/jsonl_claim_catalog.jsonl",
    ])

    max_file_bytes: int = 2_000_000
    index_batch_size: int = 32
    monitor_window: int = 1000

    # ── derived paths ──────────────────────────────────────────────────────

    def chunks_jsonl(self) -> Path:
        """System-of-record chunk stream (JSONL, per repo convention)."""
        return self.index_dir / "chunks.jsonl"

    def postings_jsonl(self) -> Path:
        """Inverted-index posting stream (term, chunk_id, tf)."""
        return self.index_dir / "postings.jsonl"

    def records_jsonl(self) -> Path:
        """Typed registry records (findings, script registry, ...)."""
        return self.index_dir / "records.jsonl"

    def index_manifest(self) -> Path:
        """Per-source-file fingerprints, enabling real incremental indexing."""
        return self.index_dir / "index_manifest.json"

    def resolved_metrics_log(self) -> Path:
        """Metrics log location, honouring an overridden root.

        The previous implementation hardcoded `repo_root/data/rag_metrics.jsonl`
        while test fixtures overrode only `chroma_path`, so every test run wrote
        into the real repository (the synthetic entries dated 2026-09-05 in
        data/rag_metrics.jsonl are exactly that leak).
        """
        if self.metrics_log_path is not None:
            return self.metrics_log_path
        return self.index_dir / "rag_metrics.jsonl"


def build_default_config() -> RetrievalConfig:
    """Build a RetrievalConfig, overriding from environment variables."""
    cfg = RetrievalConfig()
    if os.environ.get("RAG_INDEX_DIR"):
        cfg.index_dir = Path(os.environ["RAG_INDEX_DIR"])
    if os.environ.get("RAG_CHROMA_PATH"):
        cfg.chroma_path = Path(os.environ["RAG_CHROMA_PATH"])
    if os.environ.get("RAG_EMBEDDING_MODEL"):
        cfg.embedding_model = os.environ["RAG_EMBEDDING_MODEL"]
    if os.environ.get("RAG_TOP_K"):
        cfg.top_k_default = int(os.environ["RAG_TOP_K"])
    if os.environ.get("RAG_CANDIDATE_N"):
        try:
            cfg.candidate_n = max(1, int(os.environ["RAG_CANDIDATE_N"]))
        except ValueError:
            pass
    return cfg
