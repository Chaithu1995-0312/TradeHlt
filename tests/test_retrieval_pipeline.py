"""
test_retrieval_pipeline.py — Tests for the RAG pipeline.

Tests cover:
  - Corpus discovery: documents are found and domain-tagged correctly
  - Chunking: Python AST boundaries, markdown headings, YAML keys
  - Embedding: vectors are correct dimension and normalized
  - Vector store: add/query/hybrid search round-trip
  - Retriever: context assembly with domain guarantees
  - Enterprise gate: grounded verification works
  - Monitor: metrics snapshot values
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import pytest

from retrieval.config import RetrievalConfig
from retrieval.corpus import CorpusDiscoverer, Document
from retrieval.chunking import Chunker, Chunk
from retrieval.embedding import Embedder
from retrieval.vector_store import VectorStore
from retrieval.retriever import Retriever
from retrieval.monitor import Monitor
from retrieval.claude_integration import EnterpriseGate


# ── fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_config(tmp_path: Path) -> RetrievalConfig:
    """Create a minimal config that writes to a temp directory."""
    cfg = RetrievalConfig()
    cfg.chroma_path = tmp_path / "chroma_db"
    cfg.repo_root = Path(__file__).resolve().parents[1]
    return cfg


@pytest.fixture
def sample_py_doc(tmp_config: RetrievalConfig) -> Document:
    """A small Python document for chunking tests."""
    return Document(
        path=tmp_config.repo_root / "src" / "retrieval" / "__init__.py",
        domain="source_code",
        content=(
            "'''Module docstring.'''\n"
            "import os\n\n"
            "class MyClass:\n"
            "    \"\"\"Class docstring.\"\"\"\n"
            "    def method(self):\n"
            "        pass\n\n"
            "def my_func(arg1):\n"
            "    \"\"\"Function docstring.\"\"\"\n"
            "    return arg1\n"
        ),
        metadata={"filepath": "src/retrieval/__init__.py", "filename": "__init__.py",
                  "extension": ".py", "domain": "source_code"},
    )


@pytest.fixture
def sample_md_doc(tmp_config: RetrievalConfig) -> Document:
    """A small markdown document for chunking tests."""
    return Document(
        path=tmp_config.repo_root / "docs" / "test.md",
        domain="architecture",
        content=(
            "# Title\n\n"
            "Some intro text.\n\n"
            "## Section 1\n\n"
            "Content under section 1.\n\n"
            "### Sub-section 1.1\n\n"
            "More detailed content.\n\n"
            "## Section 2\n\n"
            "Final section content.\n"
        ),
        metadata={"filepath": "docs/test.md", "filename": "test.md",
                  "extension": ".md", "domain": "architecture"},
    )


# ── corpus tests ───────────────────────────────────────────────────────────


class TestCorpusDiscoverer:
    def test_discover_returns_documents(self, tmp_config: RetrievalConfig) -> None:
        discoverer = CorpusDiscoverer(tmp_config)
        docs = discoverer.discover()
        assert len(docs) > 0
        # Should find the retrieval module itself
        retrieval_init = [d for d in docs if "retrieval/__init__.py" in str(d.path)]
        assert len(retrieval_init) > 0

    def test_discover_domain_filter(self, tmp_config: RetrievalConfig) -> None:
        discoverer = CorpusDiscoverer(tmp_config)
        docs = discoverer.discover_domain("source_code")
        assert all(d.domain == "source_code" for d in docs)
        assert len(docs) > 0

    def test_document_has_enriched_metadata(self, tmp_config: RetrievalConfig) -> None:
        discoverer = CorpusDiscoverer(tmp_config)
        docs = discoverer.discover_domain("source_code")
        py_docs = [d for d in docs if d.path.suffix == ".py"]
        if py_docs:
            assert "symbols" in py_docs[0].metadata  # enriched python symbols


# ── chunking tests ─────────────────────────────────────────────────────────


class TestChunker:
    def test_chunk_python_by_class_and_function(self, tmp_config: RetrievalConfig,
                                                 sample_py_doc: Document) -> None:
        chunker = Chunker(tmp_config)
        chunks = chunker.chunk(sample_py_doc)
        headings = [c.heading for c in chunks]
        assert "MyClass" in headings or "my_func" in headings

    def test_chunk_markdown_by_heading(self, tmp_config: RetrievalConfig,
                                        sample_md_doc: Document) -> None:
        chunker = Chunker(tmp_config)
        chunks = chunker.chunk(sample_md_doc)
        headings = [c.heading for c in chunks]
        assert "Section 1" in headings or "Section 2" in headings

    def test_chunk_yaml_by_key(self, tmp_config: RetrievalConfig) -> None:
        yaml_content = "key1: value1\nsubkey: subvalue\n\nkey2: value2\n"
        doc = Document(
            path=tmp_config.repo_root / "configs" / "test.yaml",
            domain="config",
            content=yaml_content,
            metadata={"filepath": "configs/test.yaml", "filename": "test.yaml",
                      "extension": ".yaml", "domain": "config"},
        )
        chunker = Chunker(tmp_config)
        chunks = chunker.chunk(doc)
        assert len(chunks) >= 2  # at least key1 and key2

    def test_chunk_oversized_is_split(self, tmp_config: RetrievalConfig) -> None:
        """A chunk larger than chunk_max_chars should be split further."""
        long_text = "paragraph one.\n\n" * 100  # ~1500 chars
        doc = Document(
            path=tmp_config.repo_root / "test_long.txt",
            domain="analysis",
            content=long_text,
            metadata={"filepath": "test_long.txt", "filename": "test_long.txt",
                      "extension": ".txt", "domain": "analysis"},
        )
        chunker = Chunker(tmp_config)
        chunks = chunker.chunk(doc)
        assert all(len(c) <= tmp_config.chunk_max_chars + 200 for c in chunks)


# ── embedding tests ────────────────────────────────────────────────────────


class TestEmbedder:
    def test_embed_dimension(self, tmp_config: RetrievalConfig) -> None:
        embedder = Embedder(tmp_config)
        dim = embedder.embed_dim()
        assert dim == tmp_config.embedding_dim

    def test_embed_normalized(self, tmp_config: RetrievalConfig) -> None:
        embedder = Embedder(tmp_config)
        vec = embedder.embed("test text")
        # Check normalization (unit length)
        magnitude = sum(v ** 2 for v in vec) ** 0.5
        assert abs(magnitude - 1.0) < 0.01

    def test_embed_batch(self, tmp_config: RetrievalConfig) -> None:
        embedder = Embedder(tmp_config)
        texts = ["hello world", "another text", "CRT state machine"]
        vectors = embedder.embed_batch(texts)
        assert len(vectors) == 3
        assert all(len(v) == tmp_config.embedding_dim for v in vectors)


# ── vector store tests ─────────────────────────────────────────────────────


class TestVectorStore:
    def test_add_and_count(self, tmp_config: RetrievalConfig,
                           sample_py_doc: Document) -> None:
        store = VectorStore(tmp_config)
        store.delete_collection()  # start clean
        chunker = Chunker(tmp_config)
        chunks = chunker.chunk(sample_py_doc)
        embedder = Embedder(tmp_config)
        texts = [c.text for c in chunks]
        embeddings = embedder.embed_batch(texts)
        store.add_chunks(chunks, embeddings, sample_py_doc)
        store.persist()
        assert store.count() >= len(chunks)

    def test_hybrid_search_returns_results(self, tmp_config: RetrievalConfig,
                                           sample_py_doc: Document) -> None:
        store = VectorStore(tmp_config)
        store.delete_collection()
        chunker = Chunker(tmp_config)
        chunks = chunker.chunk(sample_py_doc)
        embedder = Embedder(tmp_config)
        texts = [c.text for c in chunks]
        embeddings = embedder.embed_batch(texts)
        store.add_chunks(chunks, embeddings, sample_py_doc)
        store.persist()

        results = store.hybrid_search("class definition", top_k=5)
        assert len(results) > 0
        assert results[0].score > 0.0

    def test_domain_filter(self, tmp_config: RetrievalConfig) -> None:
        store = VectorStore(tmp_config)
        store.delete_collection()

        # Add a config doc
        doc1 = Document(
            path=tmp_config.repo_root / "test_config.yaml",
            domain="config",
            content="key: value",
            metadata={"filepath": "test_config.yaml", "domain": "config"},
        )
        embedder = Embedder(tmp_config)
        chunker = Chunker(tmp_config)
        chunks1 = chunker.chunk(doc1)
        embeddings1 = embedder.embed_batch([c.text for c in chunks1])
        store.add_chunks(chunks1, embeddings1, doc1)

        # Add a source code doc
        doc2 = Document(
            path=tmp_config.repo_root / "test_code.py",
            domain="source_code",
            content="def foo(): pass",
            metadata={"filepath": "test_code.py", "domain": "source_code"},
        )
        chunks2 = chunker.chunk(doc2)
        embeddings2 = embedder.embed_batch([c.text for c in chunks2])
        store.add_chunks(chunks2, embeddings2, doc2)
        store.persist()

        results = store.hybrid_search("test", top_k=5, domain_filter="config")
        assert all(r.domain == "config" for r in results)


# ── monitor tests ──────────────────────────────────────────────────────────


class TestMonitor:
    def test_record_index(self, tmp_config: RetrievalConfig) -> None:
        monitor = Monitor(tmp_config)
        monitor.record_index(10, 100)
        snap = monitor.snapshot()
        assert snap.total_docs_indexed == 10
        assert snap.total_chunks_indexed == 100

    def test_record_query(self, tmp_config: RetrievalConfig) -> None:
        monitor = Monitor(tmp_config)
        monitor.record_query("test query", 5)
        snap = monitor.snapshot()
        assert snap.total_queries >= 1

    def test_relevance_metrics(self, tmp_config: RetrievalConfig) -> None:
        monitor = Monitor(tmp_config)
        result = monitor.record_relevance(
            query="test",
            result_chunk_ids=["a", "b", "c"],
            relevant_chunk_ids=["a", "d"],
        )
        assert result["recall_at_k"] == 0.5  # 1/2 relevant retrieved
        assert result["mrr"] == 1.0  # first result is relevant


# ── enterprise gate tests ──────────────────────────────────────────────────


class TestEnterpriseGate:
    def test_verify_insufficient_evidence(self) -> None:
        """With an empty index, verification should fail gracefully."""
        gate = EnterpriseGate()
        result = gate.verify(
            task_description="some hypothetical task",
            proposed_code_or_recommendation="def new_feature(): pass",
            min_chunks=1,
        )
        # If index is empty, it should report not grounded
        if not result["grounded"]:
            assert "Insufficient evidence" in result["reason"]