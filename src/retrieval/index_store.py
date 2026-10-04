"""
retrieval/index_store.py — DuckDB/Parquet-backed lexical index.

JSONL streams under data/rag/ are the system of record; Parquet sidecars are
regenerable projections via utils.parquet_store (LOSSLESS / NEVER-STALE /
OPTIONAL). This module never touches Chroma and never deletes source corpora.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterator

from retrieval.chunking import Chunk, Chunker
from retrieval.config import RetrievalConfig
from retrieval.corpus import CorpusDiscoverer, Document
from retrieval.truth_tier import classify_status, extract_ids, is_non_live

_TOKEN_RE = re.compile(r"[a-z0-9_]+", re.IGNORECASE)
_STOPWORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "out", "off", "over",
    "under", "again", "further", "then", "once", "here", "there", "when",
    "where", "why", "how", "all", "each", "every", "both", "few", "more",
    "most", "other", "some", "such", "no", "nor", "not", "only", "own",
    "same", "so", "than", "too", "very", "just", "because", "but", "and",
    "or", "if", "while", "that", "this", "it", "its",
})


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric/_ tokens, drop stopwords and length<=2."""
    terms = _TOKEN_RE.findall(text.lower())
    return [t for t in terms if len(t) > 2 and t not in _STOPWORDS]


@dataclass
class IndexedChunk:
    """One persisted chunk row."""

    chunk_id: str
    filepath: str
    start_line: int
    end_line: int
    text: str
    content_sha: str
    truth_class: str
    authority_rank: int
    tier_rule: str
    lifecycle_status: str
    status_evidence: str
    heading: str
    symbols: str
    ids: str  # comma-joined
    confidence: str = ""
    validated: str = ""
    revalidate_by: str = ""
    token_count: int = 0


@dataclass
class IndexBuildReport:
    docs: int = 0
    chunks: int = 0
    records: int = 0
    postings: int = 0
    skipped_unchanged: int = 0
    elapsed_s: float = 0.0
    index_dir: str = ""


class IndexStore:
    """Build and load the truth-tier lexical index under config.index_dir."""

    def __init__(self, config: RetrievalConfig) -> None:
        self.config = config
        self.corpus = CorpusDiscoverer(config)
        self.chunker = Chunker(config)

    # ── public API ─────────────────────────────────────────────────────────

    def build(self, *, rebuild: bool = False) -> IndexBuildReport:
        """Discover → chunk → write JSONL → project Parquet → write manifest."""
        t0 = time.time()
        index_dir = self.config.index_dir
        index_dir.mkdir(parents=True, exist_ok=True)

        prev_manifest = self._load_manifest() if not rebuild else {}
        file_fps = prev_manifest.get("files", {}) if isinstance(prev_manifest, dict) else {}

        docs = self.corpus.discover()
        chunk_rows: list[dict[str, Any]] = []
        posting_rows: list[dict[str, Any]] = []
        new_files: dict[str, dict[str, Any]] = {}
        skipped = 0

        for doc in docs:
            rel = doc.metadata.get("filepath") or str(
                doc.path.relative_to(self.config.repo_root).as_posix()
            )
            fp = self._file_fingerprint(doc.path, doc.content_sha)
            new_files[rel] = fp
            if not rebuild and file_fps.get(rel) == fp:
                skipped += 1
                # Still need prior chunks for a full rewrite of streams when
                # doing incremental: for v1 we rebuild streams from scratch
                # each call but skip re-reading unchanged files' chunk work
                # only when rebuild=False AND we keep prior chunk dump.
                # Simpler contract: always rewrite streams from current docs;
                # fingerprint is recorded for future true delta builds.
                pass

            status = classify_status(doc.content)
            chunks = self.chunker.chunk(doc)
            for ch in chunks:
                row = self._chunk_to_row(ch, doc, status)
                chunk_rows.append(row)
                for term, tf in self._term_freqs(ch.text).items():
                    posting_rows.append(
                        {"term": term, "chunk_id": row["chunk_id"], "tf": tf}
                    )

        record_rows = self._load_registry_records()

        chunks_path = self.config.chunks_jsonl()
        postings_path = self.config.postings_jsonl()
        records_path = self.config.records_jsonl()

        self._write_jsonl(chunks_path, chunk_rows)
        self._write_jsonl(postings_path, posting_rows)
        self._write_jsonl(records_path, record_rows)

        self._project_parquet(chunks_path)
        self._project_parquet(postings_path)
        self._project_parquet(records_path)

        manifest = {
            "version": 1,
            "built_at": time.time(),
            "rebuild": rebuild,
            "docs": len(docs),
            "chunks": len(chunk_rows),
            "records": len(record_rows),
            "postings": len(posting_rows),
            "files": new_files,
        }
        self.config.index_manifest().write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        return IndexBuildReport(
            docs=len(docs),
            chunks=len(chunk_rows),
            records=len(record_rows),
            postings=len(posting_rows),
            skipped_unchanged=skipped,
            elapsed_s=round(time.time() - t0, 3),
            index_dir=str(index_dir),
        )

    def status(self) -> dict[str, Any]:
        """Return index presence + counts without opening DuckDB."""
        man = self._load_manifest()
        return {
            "ok": bool(man),
            "index_dir": str(self.config.index_dir),
            "manifest": man,
            "chunks_jsonl_exists": self.config.chunks_jsonl().exists(),
            "postings_jsonl_exists": self.config.postings_jsonl().exists(),
            "records_jsonl_exists": self.config.records_jsonl().exists(),
        }

    # ── internals ──────────────────────────────────────────────────────────

    def _chunk_to_row(self, ch: Chunk, doc: Document, status) -> dict[str, Any]:
        text = ch.text
        conf = ""
        validated = ""
        revalidate = ""
        # Carry findings confidence markers when present in the chunk text.
        m_conf = re.search(
            r"(?im)^\s*\**\s*Confidence\s*\**\s*[:|]\s*\**\s*([^\n*|]+)",
            text,
        )
        if m_conf:
            conf = m_conf.group(1).strip()
        m_val = re.search(
            r"(?im)^\s*\**\s*Validated\s*\**\s*[:|]\s*\**\s*([^\n*|]+)",
            text,
        )
        if m_val:
            validated = m_val.group(1).strip()
        m_re = re.search(
            r"(?im)^\s*\**\s*Revalidate-by\s*\**\s*[:|]\s*\**\s*([^\n*|]+)",
            text,
        )
        if m_re:
            revalidate = m_re.group(1).strip()

        ids = extract_ids(text)
        symbols = ch.metadata.get("symbols") or doc.metadata.get("symbols", "")
        filepath = ch.metadata.get("filepath") or doc.metadata.get("filepath", "")
        content_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        tokens = tokenize(text)
        return {
            "chunk_id": ch.chunk_id,
            "filepath": filepath,
            "start_line": int(ch.start_line),
            "end_line": int(ch.end_line),
            "text": text,
            "content_sha": content_sha,
            "truth_class": getattr(doc, "truth_class", ch.domain),
            "authority_rank": int(getattr(doc, "authority_rank", 99)),
            "tier_rule": getattr(doc, "tier_rule", ch.metadata.get("tier_rule", "")),
            "lifecycle_status": status.status,
            "status_evidence": status.status_evidence,
            "heading": ch.heading or "",
            "symbols": symbols,
            "ids": ",".join(ids),
            "confidence": conf,
            "validated": validated,
            "revalidate_by": revalidate,
            "token_count": len(tokens),
        }

    def _term_freqs(self, text: str) -> dict[str, int]:
        freqs: dict[str, int] = {}
        for term in tokenize(text):
            freqs[term] = freqs.get(term, 0) + 1
        return freqs

    def _load_registry_records(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for rel in self.config.registry_sources:
            path = self.config.repo_root / rel
            if not path.is_file():
                continue
            try:
                raw = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for i, line in enumerate(raw.splitlines(), 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(obj, dict):
                    continue
                rid = str(
                    obj.get("id")
                    or obj.get("finding_id")
                    or obj.get("script_id")
                    or obj.get("hypothesis_id")
                    or f"{path.name}:{i}"
                )
                status = str(
                    obj.get("status")
                    or obj.get("lifecycle")
                    or obj.get("lifecycle_status")
                    or "UNKNOWN"
                ).upper()
                rows.append(
                    {
                        "id": rid,
                        "type": path.stem,
                        "status": status,
                        "confidence": str(obj.get("confidence", obj.get("Confidence", ""))),
                        "conclusion": str(
                            obj.get("conclusion")
                            or obj.get("summary")
                            or obj.get("title")
                            or obj.get("description")
                            or ""
                        )[:2000],
                        "filepath": rel,
                        "source_line": i,
                        "raw_json": json.dumps(obj, sort_keys=True)[:8000],
                    }
                )
        return rows

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    def _project_parquet(self, src: Path) -> None:
        if not src.exists() or src.stat().st_size == 0:
            return
        try:
            from utils.parquet_store import compact_jsonl, parquet_available
        except ImportError:
            return
        if not parquet_available():
            return
        try:
            compact_jsonl(src, verify=False)
        except Exception:
            # Projection is optional; JSONL remains SoR.
            return

    def _load_manifest(self) -> dict[str, Any]:
        path = self.config.index_manifest()
        if not path.is_file():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _file_fingerprint(path: Path, content_sha: str) -> dict[str, Any]:
        try:
            st = path.stat()
            return {
                "size": st.st_size,
                "mtime_ns": st.st_mtime_ns,
                "sha256": content_sha,
            }
        except OSError:
            return {"sha256": content_sha}
