"""
retrieval/chunking.py — Semantic chunking by language construct, not fixed token size.

Chunk boundaries follow the code/ document's own structure:
  - Python source: split at class/function/async-function definitions and top-level
    module docstrings. Docstrings are preserved as context for their enclosing block.
  - Markdown: split at heading boundaries (## or ###), preserving the heading as
    semantic context for the following paragraphs.
  - YAML/JSON: split at top-level key boundaries.
  - Generic text: fall back to paragraph-level splitting with overlap.

This is the **second stage** in the RAG pipeline (discover → chunk → embed → index).
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from retrieval.config import RetrievalConfig
from retrieval.corpus import Document


@dataclass
class Chunk:
    """A single chunk derived from a Document.

    Attributes:
        doc_path: The original document path (for provenance).
        domain: The document domain.
        chunk_id: Unique identifier (doc_path + offset).
        text: The chunk text (may include surrounding context).
        start_line: 1-indexed start line in the original document.
        end_line: 1-indexed end line in the original document.
        heading: Optional heading/context label (e.g., class name, ## section).
        metadata: Inherited from Document + chunk-specific additions.
    """
    doc_path: Path
    domain: str
    chunk_id: str
    text: str
    start_line: int
    end_line: int
    heading: str = ""
    metadata: dict[str, str] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.text)


class Chunker:
    """Splits documents into semantically-meaningful chunks.

    Strategy selection by file extension:
      - .py  → PythonCodeChunker
      - .md  → MarkdownChunker
      - .yaml/.yml → YamlChunker
      - .json/.jsonl → JsonChunker
      - else → ParagraphChunker (fallback)
    """

    def __init__(self, config: RetrievalConfig) -> None:
        self.config = config

    def chunk(self, doc: Document) -> list[Chunk]:
        """Chunk a single document into semantically-meaningful pieces."""
        ext = doc.path.suffix.lower()
        lines = doc.content.splitlines()

        if ext == ".py":
            chunks = self._chunk_python(doc, lines)
        elif ext == ".md":
            chunks = self._chunk_markdown(doc, lines)
        elif ext in (".yaml", ".yml"):
            chunks = self._chunk_yaml(doc, lines)
        elif ext in (".json", ".jsonl"):
            chunks = self._chunk_json(doc, lines)
        else:
            chunks = self._chunk_paragraph(doc, lines)

        # Apply max-chars post-processing: if a chunk is too large,
        # split it further at paragraph boundaries.
        final: list[Chunk] = []
        for c in chunks:
            if len(c) <= self.config.chunk_max_chars:
                final.append(c)
            else:
                final.extend(self._split_oversized(c))
        return final

    # ── Python-specific chunking ───────────────────────────────────────────

    def _chunk_python(self, doc: Document, lines: list[str]) -> list[Chunk]:
        """Chunk Python source using AST class/function boundaries."""
        chunks: list[Chunk] = []
        content = doc.content
        try:
            tree = ast.parse(content, filename=str(doc.path))
        except SyntaxError:
            # Fallback to line-level splitting
            return self._chunk_with_overlap(doc, lines)

        # Get top-level nodes sorted by line number
        nodes = [n for n in ast.walk(tree)
                 if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                   ast.AsyncFunctionDef))
                 and hasattr(n, 'lineno') and hasattr(n, 'end_lineno')]
        nodes.sort(key=lambda n: n.lineno)

        prev_end = 1
        for node in nodes:
            start = node.lineno
            end = node.end_lineno or start
            if isinstance(node, ast.Module):
                continue  # handled via module docstring below

            # Extract module-level docstring as its own chunk if not covered
            if start > prev_end and prev_end == 1:
                docstring_lines = lines[0:start - 1]
                docstring_text = "\n".join(d.strip() for d in docstring_lines if d.strip())
                if docstring_text:
                    chunks.append(Chunk(
                        doc_path=doc.path,
                        domain=doc.domain,
                        chunk_id=f"{doc.path}::docstring",
                        text=docstring_text,
                        start_line=1,
                        end_line=start - 1,
                        heading="module-docstring",
                        metadata={**doc.metadata},
                    ))

            # Extract function/class docstring
            docstring = ast.get_docstring(node) or ""
            body_start = start
            if docstring and content.count(docstring, content.find(node.name)) > 0:
                body_start = start + docstring.count("\n") + 1

            chunk_lines = lines[start - 1:end]
            chunk_text = "\n".join(chunk_lines)
            name = getattr(node, 'name', f'<line_{start}>')

            # Ensure unique chunk IDs by appending line number
            unique_id = f"{doc.path}::{name}::L{start}"
            chunks.append(Chunk(
                doc_path=doc.path,
                domain=doc.domain,
                chunk_id=unique_id,
                text=chunk_text,
                start_line=start,
                end_line=end,
                heading=name,
                metadata={
                    **doc.metadata,
                    "construct_type": type(node).__name__,
                    "construct_name": name,
                },
            ))
            prev_end = end + 1

        # Lines after last construct
        if prev_end <= len(lines):
            tail = "\n".join(lines[prev_end - 1:]).strip()
            if tail:
                chunks.append(Chunk(
                    doc_path=doc.path,
                    domain=doc.domain,
                    chunk_id=f"{doc.path}::tail",
                    text=tail,
                    start_line=prev_end,
                    end_line=len(lines),
                    heading="<module-tail>",
                    metadata={**doc.metadata},
                ))

        return chunks

    # ── Markdown chunking ──────────────────────────────────────────────────

    def _chunk_markdown(self, doc: Document, lines: list[str]) -> list[Chunk]:
        """Chunk Markdown at heading (## or ###) boundaries."""
        chunks: list[Chunk] = []
        current_chunk: list[str] = []
        current_heading = ""
        start_line = 1

        for i, line in enumerate(lines, 1):
            heading_match = re.match(r'^(#{2,3})\s+(.+)$', line)
            if heading_match:
                if current_chunk:
                    text = "\n".join(current_chunk).strip()
                    if text:
                        chunks.append(Chunk(
                            doc_path=doc.path,
                            domain=doc.domain,
                            chunk_id=f"{doc.path}::{current_heading or 'preamble'}::L{start_line}",
                            text=text,
                            start_line=start_line,
                            end_line=i - 1,
                            heading=current_heading,
                            metadata={**doc.metadata},
                        ))
                current_chunk = [line]
                current_heading = heading_match.group(2).strip()
                start_line = i
            else:
                current_chunk.append(line)

        # Last chunk
        if current_chunk:
            text = "\n".join(current_chunk).strip()
            if text:
                chunks.append(Chunk(
                    doc_path=doc.path,
                    domain=doc.domain,
                    chunk_id=f"{doc.path}::{current_heading or 'tail'}::L{start_line}",
                    text=text,
                    start_line=start_line,
                    end_line=len(lines),
                    heading=current_heading,
                    metadata={**doc.metadata},
                ))

        return chunks

    # ── YAML chunking ──────────────────────────────────────────────────────

    def _chunk_yaml(self, doc: Document, lines: list[str]) -> list[Chunk]:
        """Chunk YAML at top-level key boundaries."""
        chunks: list[Chunk] = []
        current: list[str] = []
        current_key = ""
        start_line = 1

        for i, line in enumerate(lines, 1):
            key_match = re.match(r'^(\w[\w_]*):', line)
            if key_match and not line.startswith((" ", "\t")):
                if current:
                    text = "\n".join(current).strip()
                    if text:
                        chunks.append(Chunk(
                            doc_path=doc.path,
                            domain=doc.domain,
                            chunk_id=f"{doc.path}::{current_key}::L{start_line}",
                            text=text,
                            start_line=start_line,
                            end_line=i - 1,
                            heading=current_key,
                            metadata={**doc.metadata, "yaml_key": current_key},
                        ))
                current = [line]
                current_key = key_match.group(1)
                start_line = i
            else:
                current.append(line)

        if current:
            text = "\n".join(current).strip()
            if text:
                chunks.append(Chunk(
                    doc_path=doc.path,
                    domain=doc.domain,
                    chunk_id=f"{doc.path}::{current_key or 'root'}::L{start_line}",
                    text=text,
                    start_line=start_line,
                    end_line=len(lines),
                    heading=current_key,
                    metadata={**doc.metadata, "yaml_key": current_key},
                ))
        return chunks

    # ── JSON chunking ──────────────────────────────────────────────────────

    def _chunk_json(self, doc: Document, lines: list[str]) -> list[Chunk]:
        """Chunk JSONL (one JSON object per line) or JSON array at top-level."""
        chunks: list[Chunk] = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped:
                text = stripped[:self.config.chunk_max_chars] if len(stripped) > self.config.chunk_max_chars else stripped
                chunks.append(Chunk(
                    doc_path=doc.path,
                    domain=doc.domain,
                    chunk_id=f"{doc.path}::L{i}",
                    text=text,
                    start_line=i,
                    end_line=i,
                    heading="json-record",
                    metadata={**doc.metadata, "line": str(i)},
                ))
        return chunks

    # ── Paragraph / fallback chunking ──────────────────────────────────────

    def _chunk_paragraph(self, doc: Document, lines: list[str]) -> list[Chunk]:
        """Chunk generic text at paragraph boundaries (double-newline)."""
        return self._chunk_with_overlap(doc, lines)

    def _chunk_with_overlap(self, doc: Document, lines: list[str]) -> list[Chunk]:
        """Split into chunks delimited by blank lines, with configurable overlap."""
        chunks: list[Chunk] = []
        paragraphs = re.split(r'\n\s*\n', doc.content)
        start_line = 1
        for para in paragraphs:
            para_lines = para.splitlines()
            end_line = start_line + len(para_lines) - 1
            text = para.strip()
            if text:
                chunks.append(Chunk(
                    doc_path=doc.path,
                    domain=doc.domain,
                    chunk_id=f"{doc.path}::L{start_line}",
                    text=text,
                    start_line=start_line,
                    end_line=end_line,
                    metadata={**doc.metadata},
                ))
            start_line = end_line + 2
        return chunks

    # ── Oversized chunk splitting ──────────────────────────────────────────

    def _split_oversized(self, chunk: Chunk) -> list[Chunk]:
        """Split an oversized chunk at paragraph boundaries."""
        sub_chunks: list[Chunk] = []
        paragraphs = re.split(r'\n\s*\n', chunk.text)
        current: list[str] = []
        current_len = 0
        sub_idx = 0

        for para in paragraphs:
            para_len = len(para) + 2
            if current_len + para_len > self.config.chunk_max_chars and current:
                text = "\n\n".join(current)
                sub_chunks.append(Chunk(
                    doc_path=chunk.doc_path,
                    domain=chunk.domain,
                    chunk_id=f"{chunk.chunk_id}_sub{sub_idx}",
                    text=text,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    heading=chunk.heading,
                    metadata={**chunk.metadata},
                ))
                current = []
                current_len = 0
                sub_idx += 1
            current.append(para)
            current_len += para_len

        if current:
            text = "\n\n".join(current)
            sub_chunks.append(Chunk(
                doc_path=chunk.doc_path,
                domain=chunk.domain,
                chunk_id=f"{chunk.chunk_id}_sub{sub_idx}",
                text=text,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                heading=chunk.heading,
                metadata={**chunk.metadata},
            ))
        return sub_chunks


def chunk_document(doc: Document, config: RetrievalConfig | None = None) -> list[Chunk]:
    """Convenience function to chunk a single document."""
    from retrieval.config import build_default_config
    cfg = config or build_default_config()
    return Chunker(cfg).chunk(doc)