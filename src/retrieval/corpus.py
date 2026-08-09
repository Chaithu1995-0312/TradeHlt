"""
retrieval/corpus.py — Document discovery across the repository.

Discovers files by domain using glob patterns from RetrievalConfig, reads them
as plain text, and yields Document objects tagged with domain + metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from retrieval.config import RetrievalConfig


@dataclass
class Document:
    """A single source document discovered in the corpus.

    Attributes:
        path: Absolute file path.
        domain: One of the domain keys from RetrievalConfig.domain_patterns.
        content: UTF-8 text content of the file.
        metadata: Additional key/value pairs for filtering and context.
    """
    path: Path
    domain: str
    content: str
    metadata: dict[str, str] = field(default_factory=dict)


class CorpusDiscoverer:
    """Discovers all documents matching the domain patterns in RetrievalConfig.

    This is the **first stage** in the RAG pipeline (discover → chunk → embed → index).
    It is a pure function of the filesystem — same tree → same document set.
    """

    def __init__(self, config: RetrievalConfig) -> None:
        self.config = config

    def discover(self) -> list[Document]:
        """Walk the repository and return all discoverable documents."""
        docs: list[Document] = []
        seen: set[Path] = set()

        for domain, patterns in self.config.domain_patterns.items():
            for pattern in patterns:
                for path in sorted(self.config.repo_root.glob(pattern)):
                    if not path.is_file():
                        continue
                    if self._should_exclude(path):
                        continue
                    if path in seen:
                        continue
                    seen.add(path)
                    doc = self._read_document(path, domain)
                    if doc:
                        docs.append(doc)
        return docs

    def discover_domain(self, domain: str) -> list[Document]:
        """Discover documents for a single domain."""
        patterns = self.config.domain_patterns.get(domain)
        if not patterns:
            return []
        docs: list[Document] = []
        for pattern in patterns:
            for path in sorted(self.config.repo_root.glob(pattern)):
                if not path.is_file():
                    continue
                if self._should_exclude(path):
                    continue
                doc = self._read_document(path, domain)
                if doc:
                    docs.append(doc)
        return docs

    # ── private helpers ────────────────────────────────────────────────────

    def _should_exclude(self, path: Path) -> bool:
        """Check if the path matches any exclusion pattern."""
        for pat in self.config.exclude_patterns:
            if pat in path.parts or pat in str(path):
                return True
        return False

    def _read_document(self, path: Path, domain: str) -> Document | None:
        """Read a file and return a Document, or None if unreadable."""
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError):
            return None
        if len(content) < 10:
            return None  # skip empty / near-empty files
        rel = path.relative_to(self.config.repo_root)
        doc = Document(
            path=path,
            domain=domain,
            content=content,
            metadata={
                "filepath": str(rel),
                "filename": path.name,
                "extension": path.suffix,
                "domain": domain,
            },
        )
        # Enrich metadata for Python files
        if path.suffix == ".py":
            self._enrich_python(doc)
        return doc

    def _enrich_python(self, doc: Document) -> None:
        """Extract top-level class/function names from a Python module."""
        import ast
        try:
            tree = ast.parse(doc.content, filename=str(doc.path))
        except SyntaxError:
            return
        names: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                names.append(node.name)
        if names:
            doc.metadata["symbols"] = ",".join(names[:50])  # cap at 50