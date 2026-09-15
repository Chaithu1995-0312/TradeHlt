"""
retrieval/corpus.py — Truth-classified document discovery.

Walks the include patterns from RetrievalConfig, drops excluded paths,
classifies every survivor through `retrieval.truth_tier`, and returns Document
objects carrying their truth class, authority rank, content hash and governed
ids.

This is the **first stage** of the pipeline (discover -> chunk -> index).
It is a pure function of the filesystem: same tree -> same document set, in a
deterministic order. That determinism is what makes the index reproducible and
is asserted by `tests/test_retrieval_determinism.py`.

Two defects in the previous implementation are fixed here:

  1. `_should_exclude` tested `pattern in str(path)` against the whole absolute
     path. With "archive" in the exclusion list that silently dropped
     `docs/analysis/session-log-archive/` (1,374 entries the user explicitly
     wants indexed), and on some machines the repo's own parent directory name
     could match and empty the corpus. Exclusion is now segment- and
     prefix-precise.
  2. Near-duplicate trees (`.claude/worktrees/`, `reports/_ours_backup/`) were
     indexed alongside the real files, so one question had two answers and one
     of them was stale. They are excluded, and an additional content-hash
     dedupe catches any copy that slips past the path rules.
"""

from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from retrieval.config import RetrievalConfig
from retrieval.truth_tier import classify_path, extract_ids


@dataclass
class Document:
    """A single classified source document.

    Attributes:
        path: Absolute file path.
        truth_class: CURRENT / INTENDED / RECORDED / REFERENCE / HISTORICAL.
        authority_rank: Within-class ordering; 0 is most authoritative.
        tier_rule: Id of the classification rule that matched (auditability).
        content: UTF-8 text content.
        content_sha: SHA-256 of the content, used for dedupe and freshness.
        ids: Governed ids (F-/FM-/SEM-/CC-...) found in the document.
        metadata: Additional key/value pairs.
    """
    path: Path
    truth_class: str
    authority_rank: int
    tier_rule: str
    content: str
    content_sha: str = ""
    ids: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)

    # `domain` is retained as an alias so existing callers and the benchmark
    # harness keep working; the truth class is the real axis now.
    @property
    def domain(self) -> str:
        return self.truth_class


class CorpusDiscoverer:
    """Discovers and truth-classifies every document in the configured corpus."""

    def __init__(self, config: RetrievalConfig) -> None:
        self.config = config

    # ── public API ─────────────────────────────────────────────────────────

    def discover(self) -> list[Document]:
        """Walk the repository and return all indexable documents.

        Deterministic: paths are globbed, de-duplicated, and sorted before
        reading, so two runs over an unchanged tree return an identical list.
        """
        candidates: set[Path] = set()
        for pattern in self.config.include_patterns:
            for path in self.config.repo_root.glob(pattern):
                if path.is_file():
                    candidates.add(path)

        docs: list[Document] = []
        seen_hashes: dict[str, Path] = {}

        for path in sorted(candidates):
            rel = self._relative(path)
            if rel is None or self._should_exclude(rel):
                continue
            # Registries are loaded as typed records by index_store, not chunked
            # as text — this is what kills the 85% governance-JSONL skew.
            if rel in self.config.registry_sources:
                continue
            assignment = classify_path(rel)
            if not assignment.indexable:
                continue
            doc = self._read_document(path, rel, assignment)
            if doc is None:
                continue
            # Content-hash dedupe: the backstop for any near-duplicate copy the
            # path exclusions missed. First path wins (sorted order => stable).
            if doc.content_sha in seen_hashes:
                continue
            seen_hashes[doc.content_sha] = path
            docs.append(doc)

        return docs

    def discover_class(self, truth_class: str) -> list[Document]:
        """Discover documents belonging to a single truth class."""
        return [d for d in self.discover() if d.truth_class == truth_class]

    # Back-compat alias for the previous domain-keyed API.
    def discover_domain(self, domain: str) -> list[Document]:
        """Deprecated alias for `discover_class`."""
        return self.discover_class(domain)

    # ── private helpers ────────────────────────────────────────────────────

    def _relative(self, path: Path) -> str | None:
        """Repo-relative POSIX path, or None if the path escapes the root."""
        try:
            return path.relative_to(self.config.repo_root).as_posix()
        except ValueError:
            return None

    def _should_exclude(self, rel: str) -> bool:
        """Segment- and prefix-precise exclusion against a repo-relative path.

        A pattern matches when it is a path prefix, a whole path segment, or a
        filename suffix (e.g. ".generated.md"). Crucially it is NOT a bare
        substring test against the absolute path, which is what previously
        dropped `session-log-archive/` via the "archive" rule.
        """
        segments = rel.split("/")
        for pattern in self.config.exclude_patterns:
            pat = pattern.replace("\\", "/").strip()
            if not pat:
                continue
            if pat.endswith("/"):
                if rel.startswith(pat) or f"/{pat}" in f"/{rel}":
                    return True
                continue
            if pat.startswith("."):
                # Suffix rule (".generated.md") or dot-segment (".venv").
                if rel.endswith(pat) or pat in segments:
                    return True
                continue
            if "/" in pat:
                if rel == pat or rel.startswith(pat + "/") or f"/{pat}/" in f"/{rel}":
                    return True
                continue
            if pat in segments:
                return True
            # Filename-fragment rule (e.g. "master_crypto_training").
            if pat in segments[-1]:
                return True
        return False

    def _read_document(self, path: Path, rel: str, assignment) -> Document | None:
        """Read a file into a classified Document, or None if unusable."""
        try:
            if path.stat().st_size > self.config.max_file_bytes:
                return None
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        if len(content.strip()) < 10:
            return None

        doc = Document(
            path=path,
            truth_class=assignment.truth_class,
            authority_rank=assignment.authority_rank,
            tier_rule=assignment.rule,
            content=content,
            content_sha=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            ids=extract_ids(content),
            metadata={
                "filepath": rel,
                "filename": path.name,
                "extension": path.suffix,
                "truth_class": assignment.truth_class,
                "authority_rank": str(assignment.authority_rank),
                "tier_rule": assignment.rule,
            },
        )
        if path.suffix == ".py":
            self._enrich_python(doc)
        return doc

    def _enrich_python(self, doc: Document) -> None:
        """Extract class/function names from a Python module for symbol search.

        Exact symbol matching is the single highest-value signal for this
        corpus — queries here are overwhelmingly symbol-shaped
        ("UltronRiskGate", "rr_fusion", "compute_crt_levels").
        """
        try:
            tree = ast.parse(doc.content, filename=str(doc.path))
        except (SyntaxError, ValueError):
            return
        names: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                names.append(node.name)
        if names:
            # Deterministic and capped, so the metadata cannot bloat the index.
            doc.metadata["symbols"] = ",".join(sorted(set(names))[:80])
