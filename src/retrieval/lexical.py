"""
retrieval/lexical.py — BM25 over DuckDB/Parquet (hand-rolled, no fts extension).

Query path reads Parquet sidecars (`chunks.parquet`, `postings.parquet`) via
utils.duckdb_query.open_views. JSONL under data/rag/ remains the build
system-of-record written by index_store.py and is NOT loaded into Python dicts
at query time.

Ranking applies BM25 (k1/b from config) plus truth_class weights, non-LIVE
demotion, exact id/symbol/heading boosts, and a light authority-rank tilt —
the same formula as the former in-memory posting scorer.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from retrieval.config import RetrievalConfig
from retrieval.index_store import tokenize
from retrieval.truth_tier import extract_ids, is_non_live

_ID_IN_QUERY = re.compile(
    r"\b(?:F-\d{3}|FM-\d{3}|SEM-\d{3}|GD-\d{3}|IC-\d{3}|E-\d{3}[A-Z]?|"
    r"(?:CN|BD|CT|JN)-[A-Za-z0-9_]+|CC-[A-Z0-9][A-Z0-9-]*|"
    r"MC-[A-Z0-9][A-Z0-9-]*|MP-[A-Z0-9][A-Z0-9-]*|RF-[A-Z0-9][A-Z0-9.-]*)\b"
)

# Tiny JSONL-only fixtures (tests that never projected Parquet). Production
# JSONL is hundreds of MB and must never take this branch.
_JSONL_FALLBACK_MAX_BYTES = 2_000_000

@dataclass
class LexicalHit:
    chunk_id: str
    text: str
    score: float
    bm25: float
    filepath: str
    start_line: int
    end_line: int
    truth_class: str
    authority_rank: int
    lifecycle_status: str
    status_evidence: str
    heading: str
    symbols: str
    ids: str
    content_sha: str
    confidence: str = ""
    validated: str = ""
    revalidate_by: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


def _as_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _as_int(value: Any, default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default


def _as_float(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default



def _path_components(filepath: str) -> set[str]:
    """Basename, stem, and path components (lowercase) for stem/basename boosts."""
    parts: set[str] = set()
    for raw in filepath.replace("\\", "/").split("/"):
        p = raw.strip()
        if not p:
            continue
        low = p.lower()
        parts.add(low)
        if "." in p:
            stem = p.rsplit(".", 1)[0].lower()
            if stem:
                parts.add(stem)
    return parts


def _is_json_record_noise(chunk: dict[str, Any], max_tokens: int) -> bool:
    """True for governance one-liners / json-record keys that crowd living code."""
    heading = _as_str(chunk.get("heading"), "").lower().strip()
    if heading in {"json-record", "json_record", "jsonl-record", "json-key"}:
        return True
    tok = _as_int(chunk.get("token_count"), 0)
    text = _as_str(chunk.get("text"), "").strip()
    if tok <= 0:
        tok = len(text.split()) if text else 0
    if tok == 0 or tok > max_tokens:
        return False
    if text.startswith('"') and ":" in text[:48]:
        return True
    if text.startswith("{") and len(text) < 96 and ":" in text:
        return True
    return False



# ── query-aware file routing ───────────────────────────────────────────────
# Small, gold-justified alias table. Do NOT grow this into an English→file map.
_FILE_ROUTE_ALIASES: dict[str, tuple[str, ...]] = {
    # architecture questions never name TRADING_SYSTEM_FRAMEWORK.md
    "architecture": ("TRADING_SYSTEM_FRAMEWORK", "docs/architecture"),
    "trading system": ("TRADING_SYSTEM_FRAMEWORK", "docs/architecture"),
    "trading_system": ("TRADING_SYSTEM_FRAMEWORK", "docs/architecture"),
    "system framework": ("TRADING_SYSTEM_FRAMEWORK",),
    "framework": ("TRADING_SYSTEM_FRAMEWORK",),
    # fusion / rr_fusion
    "fusion": ("rr_fusion", "fusion_engine", "src/engines"),
    "rr_fusion": ("rr_fusion", "fusion_engine"),
    "rr fusion": ("rr_fusion", "fusion_engine"),
    # ontology surface
    "ontology": ("crt_state_resolver", "ontology"),
}

_FILE_ROUTE_STOPWORDS = frozenset(
    {
        "what", "when", "where", "which", "while", "whose", "whom", "this", "that",
        "these", "those", "with", "from", "into", "onto", "over", "under", "about",
        "above", "below", "between", "after", "before", "because", "should", "would",
        "could", "their", "there", "here", "have", "has", "had", "been", "being",
        "were", "was", "are", "is", "the", "and", "for", "not", "but", "how", "why",
        "does", "did", "doing", "done", "just", "like", "than", "then", "them",
        "they", "you", "your", "our", "out", "any", "all", "each", "every", "some",
        "such", "only", "also", "more", "most", "other", "into", "file", "files",
        "code", "docs", "doc", "system", "overall", "please", "explain", "describe",
        "tell", "show", "look", "find", "give", "make", "used", "using", "use",
        "true", "false", "null", "none", "type", "data", "info", "information",
    }
)

_EXPLICIT_PATH_RE = re.compile(
    r"(?P<path>(?:[A-Za-z]:)?(?:[\w.-]+[/\\])+[\w.-]+\.(?:py|md|yaml|yml|json|toml|txt))",
    re.IGNORECASE,
)
_BASENAME_RE = re.compile(
    r"\b(?P<base>[\w.-]+\.(?:py|md|yaml|yml|json|toml|txt))\b",
    re.IGNORECASE,
)
_SNAKE_RE = re.compile(r"\b([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\b")
_SCREAMING_RE = re.compile(r"\b([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)\b")
_CAMEL_RE = re.compile(r"\b([A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+)\b")


def _norm_path_key(filepath: str) -> str:
    return filepath.replace("\\", "/").lower().strip()


def _stem_as_path_component(filepath: str, stem: str) -> bool:
    """True when stem matches a path component / basename, not a JSON substring."""
    if not stem or not filepath:
        return False
    stem_l = stem.lower().strip().replace("\\", "/")
    if len(stem_l) < 3:
        return False
    fp = _norm_path_key(filepath)
    # Directory / path-fragment aliases (e.g. docs/architecture)
    if "/" in stem_l:
        return stem_l in fp or fp.endswith(stem_l.rstrip("/")) or f"/{stem_l.strip('/')}/" in f"/{fp}/"
    # Basename / stem as path component
    name = fp.rsplit("/", 1)[-1]
    name_stem = name.rsplit(".", 1)[0] if "." in name else name
    if stem_l == name or stem_l == name_stem:
        return True
    if f"/{stem_l}." in f"/{fp}":
        return True
    for ext in (".py", ".md", ".yaml", ".yml", ".json", ".toml", ".txt"):
        if fp.endswith(f"/{stem_l}{ext}") or name == f"{stem_l}{ext}":
            return True
    # Path component exact match (folder named like the stem)
    parts = [p for p in fp.split("/") if p]
    return stem_l in parts


def extract_file_route_signals(query: str) -> tuple[list[str], list[str]]:
    """Return (stems_or_fragments, governed_ids) extracted from the query.

    Stems are ordered: explicit paths/basenames first, then alias expansions,
    then snake/Camel/SCREAMING tokens. Keep small — caller caps file count.
    """
    q = query or ""
    q_lower = q.lower()
    stems: list[str] = []
    seen: set[str] = set()

    def _add(s: str) -> None:
        s2 = (s or "").strip().replace("\\", "/")
        if not s2:
            return
        key = s2.lower()
        if key in seen:
            return
        # Drop trailing slash for dir fragments but keep path shape
        seen.add(key)
        stems.append(s2)

    for m in _EXPLICIT_PATH_RE.finditer(q):
        p = m.group("path").replace("\\", "/")
        _add(p)
        base = p.rsplit("/", 1)[-1]
        _add(base)
        if "." in base:
            _add(base.rsplit(".", 1)[0])

    for m in _BASENAME_RE.finditer(q):
        base = m.group("base")
        _add(base)
        if "." in base:
            _add(base.rsplit(".", 1)[0])

    # Alias expansions (phrase / keyword → high-traffic gold stems)
    # Longer phrases first.
    alias_keys = sorted(_FILE_ROUTE_ALIASES.keys(), key=len, reverse=True)
    for key in alias_keys:
        if key in q_lower:
            for target in _FILE_ROUTE_ALIASES[key]:
                _add(target)

    for rx in (_SCREAMING_RE, _SNAKE_RE, _CAMEL_RE):
        for m in rx.finditer(q):
            tok = m.group(1)
            if len(tok) < 4:
                continue
            if tok.lower() in _FILE_ROUTE_STOPWORDS:
                continue
            _add(tok)
            # CamelCase → snake-ish stem for path matching
            if rx is _CAMEL_RE:
                snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", tok).lower()
                if snake != tok.lower():
                    _add(snake)

    ids = set(_ID_IN_QUERY.findall(q))
    ids.update(extract_ids(q))
    return stems, sorted(ids)


class LexicalIndex:
    """DuckDB/Parquet BM25 index. Query-time state is a connection + N/avgdl."""

    def __init__(self, config: RetrievalConfig) -> None:
        self.config = config
        # Memory path (tiny JSONL fixtures only). Empty on the Parquet path.
        self._chunks: dict[str, dict[str, Any]] = {}
        self._postings: dict[str, list[tuple[str, int]]] = {}  # term -> [(cid, tf)]
        self._df: dict[str, int] = {}
        self._avgdl: float = 0.0
        self._n_docs: int = 0
        self._loaded = False
        self._con: Any = None  # duckdb connection when parquet-backed
        self._backend: str = ""  # "parquet" | "jsonl"

    # ── paths ──────────────────────────────────────────────────────────────

    def _index_dir(self) -> Path:
        return Path(self.config.index_dir)

    def _chunks_jsonl(self) -> Path:
        fn = getattr(self.config, "chunks_jsonl", None)
        return Path(fn()) if callable(fn) else self._index_dir() / "chunks.jsonl"

    def _postings_jsonl(self) -> Path:
        fn = getattr(self.config, "postings_jsonl", None)
        return Path(fn()) if callable(fn) else self._index_dir() / "postings.jsonl"

    def _records_jsonl(self) -> Path:
        fn = getattr(self.config, "records_jsonl", None)
        return Path(fn()) if callable(fn) else self._index_dir() / "records.jsonl"

    def _chunks_parquet(self) -> Path:
        return self._chunks_jsonl().with_suffix(".parquet")

    def _postings_parquet(self) -> Path:
        return self._postings_jsonl().with_suffix(".parquet")

    def _records_parquet(self) -> Path:
        return self._records_jsonl().with_suffix(".parquet")

    def _close(self) -> None:
        con = self._con
        self._con = None
        if con is not None:
            try:
                con.close()
            except Exception:
                pass

    # ── load ───────────────────────────────────────────────────────────────

    def load(self) -> None:
        self._close()
        self._chunks.clear()
        self._postings.clear()
        self._df.clear()
        self._avgdl = 0.0
        self._n_docs = 0
        self._backend = ""
        self._loaded = False

        chunks_pq = self._chunks_parquet()
        postings_pq = self._postings_parquet()
        if chunks_pq.exists() and postings_pq.exists():
            self._load_parquet(chunks_pq, postings_pq)
            return

        chunks_jsonl = self._chunks_jsonl()
        postings_jsonl = self._postings_jsonl()
        jsonl_ok = chunks_jsonl.is_file() and postings_jsonl.is_file()
        jsonl_bytes = 0
        if jsonl_ok:
            jsonl_bytes = chunks_jsonl.stat().st_size + postings_jsonl.stat().st_size

        if jsonl_ok and jsonl_bytes <= _JSONL_FALLBACK_MAX_BYTES:
            self._load_jsonl(chunks_jsonl, postings_jsonl)
            return

        missing = []
        if not chunks_pq.exists():
            missing.append(str(chunks_pq))
        if not postings_pq.exists():
            missing.append(str(postings_pq))
        hint = (
            f"Lexical Parquet sidecars missing under {self._index_dir()}. "
            f"Expected files: {', '.join(missing) if missing else 'chunks.parquet and postings.parquet'}. "
            "JSONL is the build system-of-record and is not loaded into RAM at query time. "
            "Project sidecars with: python scripts/rag_index.py index --rebuild "
            "(or utils.parquet_store.compact_jsonl on chunks.jsonl and postings.jsonl)."
        )
        if jsonl_ok:
            hint += (
                f" JSONL is present ({jsonl_bytes} bytes) but exceeds the "
                f"{_JSONL_FALLBACK_MAX_BYTES}-byte fixture fallback cap."
            )
        raise FileNotFoundError(hint)

    def _load_parquet(self, chunks_pq: Path, postings_pq: Path) -> None:
        from utils.duckdb_query import duckdb_available, open_views

        if not duckdb_available():
            raise RuntimeError(
                "duckdb is required for Parquet lexical query. "
                "Install it with `pip install tradelatest[parquet]` "
                "(or `pip install duckdb pyarrow`)."
            )
        globs = {
            "chunks": str(chunks_pq).replace("\\", "/"),
            "postings": str(postings_pq).replace("\\", "/"),
        }
        self._con = open_views(globs, read_only=True)
        row = self._con.execute(
            "SELECT COUNT(*)::BIGINT, "
            "COALESCE(AVG(COALESCE(TRY_CAST(token_count AS DOUBLE), 0.0)), 0.0) "
            "FROM chunks"
        ).fetchone()
        self._n_docs = int(row[0] or 0)
        self._avgdl = float(row[1] or 0.0)
        self._backend = "parquet"
        self._loaded = True

    def _load_jsonl(self, chunks_path: Path, postings_path: Path) -> None:
        with chunks_path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                self._chunks[row["chunk_id"]] = row

        with postings_path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                term = row["term"]
                cid = row["chunk_id"]
                tf = int(row["tf"])
                self._postings.setdefault(term, []).append((cid, tf))

        for term, posting in self._postings.items():
            self._df[term] = len({cid for cid, _ in posting})

        lengths = [int(c.get("token_count") or 0) for c in self._chunks.values()]
        self._n_docs = len(self._chunks)
        self._avgdl = (sum(lengths) / self._n_docs) if self._n_docs else 0.0
        self._backend = "jsonl"
        self._loaded = True

    def ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    # ── search ─────────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        top_k: int | None = None,
        truth_class_filter: str | None = None,
        include_historical: bool = True,
    ) -> list[LexicalHit]:
        """Two-stage retrieve: large BM25+routing pool, then rerank to top_k.

        Candidate generation (eval 2026-09-11): raising N finds gold files but
        median rank stays deep — so we fetch candidate_n (default ~600), union
        cheap ID/stem/filepath/symbol/heading routing hits, plus query-aware
        file routing (path/basename/alias → capped files with file_route_boost),
        then rerank with stem boost, short-chunk/json-record penalty, and
        file-level aggregation. Truth classes stay partitioned; DuckDB/Parquet
        remains the query backend.
        """
        self.ensure_loaded()
        k = top_k or self.config.top_k_default
        k1 = self.config.bm25_k1
        b = self.config.bm25_b
        N = max(self._n_docs, 1)
        avgdl = self._avgdl or 1.0
        candidate_n = max(int(getattr(self.config, "candidate_n", 600) or 600), k)

        q_terms = tokenize(query)
        q_ids = set(_ID_IN_QUERY.findall(query))
        q_ids.update(extract_ids(query))
        q_lower = query.lower()
        q_stems = set(q_terms)
        # Underscore identifiers often survive tokenize; keep raw ID tokens too.
        q_stems.update(x.lower() for x in q_ids)

        if self._backend == "parquet":
            scores, chunks = self._bm25_from_parquet(
                q_terms, k1, b, N, avgdl, truth_class_filter, include_historical
            )
        else:
            scores, chunks = self._bm25_from_memory(
                q_terms, k1, b, N, avgdl, truth_class_filter, include_historical
            )

        # Stage 1a: top candidate_n by raw BM25 (before boosts).
        ranked_cids = sorted(scores.keys(), key=lambda c: -scores[c])[:candidate_n]
        pool: set[str] = set(ranked_cids)

        # Stage 1b: union cheap routing adds (IDs / stems / filepath / symbols).
        extra = self._routing_extra_chunks(
            q_terms=q_terms,
            q_ids=q_ids,
            q_stems=q_stems,
            truth_class_filter=truth_class_filter,
            include_historical=include_historical,
        )
        for cid, chunk in extra.items():
            if not self._passes_filters(chunk, truth_class_filter, include_historical):
                continue
            chunks[cid] = chunk
            scores.setdefault(cid, 0.0)
            pool.add(cid)

        # Stage 1c: query-aware file routing (path/basename/alias → file pool).
        file_extra, routed_files = self._file_route_extra_chunks(
            query=query,
            truth_class_filter=truth_class_filter,
            include_historical=include_historical,
        )
        for cid, chunk in file_extra.items():
            if not self._passes_filters(chunk, truth_class_filter, include_historical):
                continue
            chunks[cid] = chunk
            scores.setdefault(cid, 0.0)
            pool.add(cid)

        # Stage 2: finish scoring + file aggregation, then truncate to top_k.
        hits: list[LexicalHit] = []
        for cid in pool:
            chunk = chunks.get(cid)
            if chunk is None:
                continue
            hits.append(
                self._finish_hit(
                    cid,
                    chunk,
                    scores.get(cid, 0.0),
                    q_ids,
                    q_lower,
                    q_stems,
                    routed_files=routed_files,
                )
            )

        hits = self._apply_file_aggregation(hits)
        hits.sort(key=lambda h: -h.score)
        return hits[:k]

    def _bm25_from_memory(
        self,
        q_terms: list[str],
        k1: float,
        b: float,
        N: int,
        avgdl: float,
        truth_class_filter: str | None,
        include_historical: bool,
    ) -> tuple[dict[str, float], dict[str, dict[str, Any]]]:
        scores: dict[str, float] = {}
        used: dict[str, dict[str, Any]] = {}
        for term in q_terms:
            posting = self._postings.get(term)
            if not posting:
                continue
            df = self._df.get(term, 0)
            idf = math.log(1.0 + (N - df + 0.5) / (df + 0.5))
            for cid, tf in posting:
                chunk = self._chunks.get(cid)
                if chunk is None:
                    continue
                if not self._passes_filters(chunk, truth_class_filter, include_historical):
                    continue
                dl = int(chunk.get("token_count") or 0) or 1
                tf_norm = (tf * (k1 + 1.0)) / (tf + k1 * (1.0 - b + b * dl / avgdl))
                scores[cid] = scores.get(cid, 0.0) + idf * tf_norm
                used[cid] = chunk
        return scores, used

    def _bm25_from_parquet(
        self,
        q_terms: list[str],
        k1: float,
        b: float,
        N: int,
        avgdl: float,
        truth_class_filter: str | None,
        include_historical: bool,
    ) -> tuple[dict[str, float], dict[str, dict[str, Any]]]:
        scores: dict[str, float] = {}
        used: dict[str, dict[str, Any]] = {}
        uniq = list(dict.fromkeys(q_terms))
        if not uniq:
            return scores, used

        df_rows = self._con.execute(
            "SELECT term, COUNT(DISTINCT chunk_id)::BIGINT AS df "
            "FROM postings WHERE term IN (SELECT UNNEST(?::VARCHAR[])) "
            "GROUP BY term",
            [uniq],
        ).fetchall()
        df_map = {_as_str(term): int(df or 0) for term, df in df_rows}

        posting_rows = self._con.execute(
            "SELECT term, chunk_id, CAST(tf AS INTEGER) AS tf "
            "FROM postings WHERE term IN (SELECT UNNEST(?::VARCHAR[]))",
            [uniq],
        ).fetchall()
        if not posting_rows:
            return scores, used

        chunk_rows = self._con.execute(
            "SELECT * FROM chunks WHERE chunk_id IN ("
            "  SELECT DISTINCT chunk_id FROM postings "
            "  WHERE term IN (SELECT UNNEST(?::VARCHAR[]))"
            ")",
            [uniq],
        ).fetchall()
        cols = [d[0] for d in self._con.description]
        chunks_by_id = {
            _as_str(row[cols.index("chunk_id")]): dict(zip(cols, row))
            for row in chunk_rows
        }

        for term, cid, tf in posting_rows:
            term_s = _as_str(term)
            cid_s = _as_str(cid)
            chunk = chunks_by_id.get(cid_s)
            if chunk is None:
                continue
            if not self._passes_filters(chunk, truth_class_filter, include_historical):
                continue
            df = df_map.get(term_s, 0)
            idf = math.log(1.0 + (N - df + 0.5) / (df + 0.5))
            dl = _as_int(chunk.get("token_count"), 0) or 1
            tf_i = _as_int(tf, 0)
            tf_norm = (tf_i * (k1 + 1.0)) / (tf_i + k1 * (1.0 - b + b * dl / avgdl))
            scores[cid_s] = scores.get(cid_s, 0.0) + idf * tf_norm
            used[cid_s] = chunk
        return scores, used

    @staticmethod
    def _passes_filters(
        chunk: dict[str, Any],
        truth_class_filter: str | None,
        include_historical: bool,
    ) -> bool:
        tc = _as_str(chunk.get("truth_class"), "")
        if truth_class_filter and tc != truth_class_filter:
            return False
        if not include_historical and tc == "HISTORICAL":
            return False
        return True

    def _finish_hit(
        self,
        cid: str,
        chunk: dict[str, Any],
        bm25: float,
        q_ids: set[str],
        q_lower: str,
        q_stems: set[str] | None = None,
        routed_files: set[str] | None = None,
    ) -> LexicalHit:
        score = bm25
        stems = q_stems or set()

        tc = _as_str(chunk.get("truth_class"), "REFERENCE") or "REFERENCE"
        score *= float(self.config.truth_class_weights.get(tc, 1.0))

        status = _as_str(chunk.get("lifecycle_status"), "LIVE") or "LIVE"
        if is_non_live(status):
            score *= float(self.config.non_live_penalty)

        chunk_ids = {
            x.strip() for x in _as_str(chunk.get("ids"), "").split(",") if x.strip()
        }
        if q_ids and chunk_ids & q_ids:
            score += float(self.config.exact_id_boost)

        symbols = _as_str(chunk.get("symbols"), "").lower()
        if symbols:
            for sym in symbols.split(","):
                sym = sym.strip()
                if sym and (sym in q_lower or q_lower in sym or sym in stems):
                    score += float(self.config.symbol_boost)
                    break

        heading = _as_str(chunk.get("heading"), "").lower()
        if heading and (heading in q_lower or q_lower in heading):
            score += float(self.config.heading_boost)

        filepath = _as_str(chunk.get("filepath"), "")
        path_parts = _path_components(filepath)
        if stems and path_parts and (stems & path_parts):
            # Prefer living code/docs whose basename matches a query token
            # over 1-line JSON keys that only share the token in text.
            score += float(getattr(self.config, "stem_boost", 4.0))

        if routed_files:
            fp_key = _norm_path_key(filepath)
            if fp_key and fp_key in routed_files:
                score += float(getattr(self.config, "file_route_boost", 7.0))

        max_tok = int(getattr(self.config, "short_chunk_max_tokens", 16) or 16)
        tok = _as_int(chunk.get("token_count"), 0)
        stem_hit = bool(stems and path_parts and (stems & path_parts))
        if _is_json_record_noise(chunk, max_tok):
            score *= float(getattr(self.config, "json_record_penalty", 0.35))
        elif 0 < tok <= max_tok and not stem_hit:
            # Demote short non-stem snippets (config keys) without punishing
            # living modules whose basename already matched the query.
            score *= float(getattr(self.config, "short_chunk_penalty", 0.4))

        rank = _as_int(chunk.get("authority_rank"), 99)
        score *= 1.0 / (1.0 + 0.03 * rank)

        start_line = _as_int(chunk.get("start_line"), 0)
        end_line = _as_int(chunk.get("end_line"), 0)
        filepath = _as_str(chunk.get("filepath"), "")
        heading_raw = _as_str(chunk.get("heading"), "")
        symbols_raw = _as_str(chunk.get("symbols"), "")
        ids_raw = _as_str(chunk.get("ids"), "")
        sha = _as_str(chunk.get("content_sha"), "")
        evidence = _as_str(chunk.get("status_evidence"), "")
        confidence = _as_str(chunk.get("confidence"), "")
        validated = _as_str(chunk.get("validated"), "")
        revalidate_by = _as_str(chunk.get("revalidate_by"), "")

        meta = {
            "filepath": filepath,
            "truth_class": tc,
            "authority_rank": str(rank),
            "lifecycle_status": status,
            "status_evidence": evidence,
            "heading": heading_raw,
            "symbols": symbols_raw,
            "ids": ids_raw,
            "content_sha": sha,
            "start_line": str(start_line),
            "end_line": str(end_line),
            "confidence": confidence,
            "validated": validated,
            "revalidate_by": revalidate_by,
            "domain": tc,  # back-compat
        }
        return LexicalHit(
            chunk_id=cid,
            text=_as_str(chunk.get("text"), ""),
            score=score,
            bm25=bm25,
            filepath=filepath,
            start_line=start_line,
            end_line=end_line,
            truth_class=tc,
            authority_rank=rank,
            lifecycle_status=status,
            status_evidence=evidence,
            heading=heading_raw,
            symbols=symbols_raw,
            ids=ids_raw,
            content_sha=sha,
            confidence=confidence,
            validated=validated,
            revalidate_by=revalidate_by,
            metadata=meta,
        )



    def _file_route_extra_chunks(
        self,
        query: str,
        truth_class_filter: str | None,
        include_historical: bool,
    ) -> tuple[dict[str, dict[str, Any]], set[str]]:
        """Dedicated file-routing stage: path/basename/alias → capped file pool.

        Returns (extra_chunks, routed_filepath_keys). Existing ID/stem ILIKE
        routing remains as Stage 1b extras; this stage prefers path-component
        matches so architecture questions reach TRADING_SYSTEM_FRAMEWORK.md.
        """
        stems, route_ids = extract_file_route_signals(query)
        max_files = int(getattr(self.config, "file_route_max_files", 8) or 8)
        per_file = int(getattr(self.config, "file_route_chunks_per_file", 6) or 6)
        if max_files <= 0 or per_file <= 0:
            return {}, set()

        if self._backend == "parquet" and self._con is not None:
            return self._file_route_from_parquet(stems, route_ids, max_files, per_file)
        return self._file_route_from_memory(
            stems,
            route_ids,
            truth_class_filter,
            include_historical,
            max_files,
            per_file,
        )

    def _file_route_from_parquet(
        self,
        stems: list[str],
        route_ids: list[str],
        max_files: int,
        per_file: int,
    ) -> tuple[dict[str, dict[str, Any]], set[str]]:
        con = self._con
        extra: dict[str, dict[str, Any]] = {}
        routed: set[str] = set()
        per_fp: dict[str, int] = {}
        cols: list[str] | None = None

        def _ingest(rows: list, *, mark_route: bool) -> None:
            nonlocal cols
            if cols is None:
                cols = [d[0] for d in con.description]
            for row in rows:
                chunk = dict(zip(cols, row))
                cid = _as_str(chunk.get("chunk_id"), "")
                fp = _as_str(chunk.get("filepath"), "")
                fp_key = _norm_path_key(fp)
                if not cid or not fp_key:
                    continue
                if mark_route:
                    if fp_key not in routed and len(routed) >= max_files:
                        continue
                    routed.add(fp_key)
                elif fp_key not in routed:
                    continue
                if per_fp.get(fp_key, 0) >= per_file:
                    continue
                if cid in extra:
                    continue
                extra[cid] = chunk
                per_fp[fp_key] = per_fp.get(fp_key, 0) + 1

        for gid in route_ids[:8]:
            rows = con.execute(
                "SELECT * FROM chunks WHERE ids ILIKE ? LIMIT ?",
                [f"%{gid}%", max(per_file * 2, 8)],
            ).fetchall()
            _ingest(rows, mark_route=True)

        for stem in stems:
            if len(routed) >= max_files:
                break
            stem_l = stem.lower().replace("\\", "/").strip()
            if len(stem_l) < 3:
                continue
            if "/" in stem_l:
                forward_pats = [f"%{stem_l}%"]
            else:
                forward_pats = [
                    f"%/{stem_l}.%",
                    f"%/{stem_l}.py",
                    f"%/{stem_l}.md",
                    f"%/{stem_l}.yaml",
                    f"%/{stem_l}.yml",
                    f"%/{stem_l}/%",
                    f"{stem_l}.%",
                ]
            clauses = " OR ".join(
                ["lower(replace(filepath, '\\\\', '/')) LIKE ?"] * len(forward_pats)
            )
            lim = max(per_file * max_files, per_file)
            sql = f"SELECT * FROM chunks WHERE ({clauses}) LIMIT {lim}"
            rows = con.execute(sql, forward_pats).fetchall()
            if cols is None and rows:
                cols = [d[0] for d in con.description]
            filtered = []
            for row in rows:
                chunk = dict(zip(cols, row))
                fp = _as_str(chunk.get("filepath"), "")
                if _stem_as_path_component(fp, stem_l):
                    filtered.append(row)
            _ingest(filtered, mark_route=True)

        return extra, routed

    def _file_route_from_memory(
        self,
        stems: list[str],
        route_ids: list[str],
        truth_class_filter: str | None,
        include_historical: bool,
        max_files: int,
        per_file: int,
    ) -> tuple[dict[str, dict[str, Any]], set[str]]:
        extra: dict[str, dict[str, Any]] = {}
        per_fp: dict[str, int] = {}
        id_set = set(route_ids)

        matched_fps: list[str] = []
        matched_set: set[str] = set()
        for stem in stems:
            for _cid, chunk in self._chunks.items():
                if not self._passes_filters(chunk, truth_class_filter, include_historical):
                    continue
                fp = _as_str(chunk.get("filepath"), "")
                fp_key = _norm_path_key(fp)
                if not fp_key or fp_key in matched_set:
                    continue
                if _stem_as_path_component(fp, stem):
                    matched_set.add(fp_key)
                    matched_fps.append(fp_key)
            if len(matched_fps) >= max_files:
                break

        if id_set:
            for _cid, chunk in self._chunks.items():
                ids_raw = _as_str(chunk.get("ids"), "")
                if not any(gid in ids_raw for gid in id_set):
                    continue
                fp_key = _norm_path_key(_as_str(chunk.get("filepath"), ""))
                if fp_key and fp_key not in matched_set:
                    matched_set.add(fp_key)
                    matched_fps.append(fp_key)

        routed = set(matched_fps[:max_files])

        for cid, chunk in self._chunks.items():
            if not self._passes_filters(chunk, truth_class_filter, include_historical):
                continue
            fp_key = _norm_path_key(_as_str(chunk.get("filepath"), ""))
            if fp_key not in routed:
                continue
            if per_fp.get(fp_key, 0) >= per_file:
                continue
            extra[cid] = chunk
            per_fp[fp_key] = per_fp.get(fp_key, 0) + 1

        return extra, routed


    def _routing_extra_chunks(
        self,
        q_terms: list[str],
        q_ids: set[str],
        q_stems: set[str],
        truth_class_filter: str | None,
        include_historical: bool,
    ) -> dict[str, dict[str, Any]]:
        """Cheap candidate *adds* via ID / stem / filepath / symbols / heading.

        These union into the BM25 pool; they do not replace BM25. Candidate-gen
        sweep showed symbol/ID routing was cheap (+1.1% at N=500) but unused at
        query time — wire it here as adds only.
        """
        limit = int(getattr(self.config, "routing_extra_limit", 120) or 120)
        extra: dict[str, dict[str, Any]] = {}
        route_terms: list[str] = []
        for t in list(q_stems) + list(q_terms):
            t = (t or "").strip().lower()
            if len(t) < 3:
                continue
            if t not in route_terms:
                route_terms.append(t)
        route_terms = route_terms[:12]

        if self._backend == "parquet" and self._con is not None:
            self._routing_from_parquet(extra, q_ids, route_terms, limit)
        else:
            self._routing_from_memory(
                extra, q_ids, route_terms, truth_class_filter, include_historical, limit
            )
        return extra

    def _routing_from_parquet(
        self,
        extra: dict[str, dict[str, Any]],
        q_ids: set[str],
        route_terms: list[str],
        limit: int,
    ) -> None:
        con = self._con
        cols = None

        def _ingest(rows: list) -> None:
            nonlocal cols
            if cols is None:
                cols = [d[0] for d in con.description]
            for row in rows:
                chunk = dict(zip(cols, row))
                cid = _as_str(chunk.get("chunk_id"), "")
                if cid and cid not in extra:
                    extra[cid] = chunk
                if len(extra) >= limit:
                    return

        for gid in list(q_ids)[:8]:
            if len(extra) >= limit:
                break
            rows = con.execute(
                "SELECT * FROM chunks WHERE ids ILIKE ? LIMIT 40",
                [f"%{gid}%"],
            ).fetchall()
            _ingest(rows)

        for term in route_terms:
            if len(extra) >= limit:
                break
            pat = f"%{term}%"
            rows = con.execute(
                "SELECT * FROM chunks WHERE "
                "filepath ILIKE ? OR symbols ILIKE ? OR heading ILIKE ? "
                "LIMIT 40",
                [pat, pat, pat],
            ).fetchall()
            _ingest(rows)

    def _routing_from_memory(
        self,
        extra: dict[str, dict[str, Any]],
        q_ids: set[str],
        route_terms: list[str],
        truth_class_filter: str | None,
        include_historical: bool,
        limit: int,
    ) -> None:
        for cid, chunk in self._chunks.items():
            if len(extra) >= limit:
                break
            if not self._passes_filters(chunk, truth_class_filter, include_historical):
                continue
            ids_raw = _as_str(chunk.get("ids"), "")
            fp = _as_str(chunk.get("filepath"), "").lower()
            sym = _as_str(chunk.get("symbols"), "").lower()
            heading = _as_str(chunk.get("heading"), "").lower()
            path_parts = _path_components(fp)
            hit = False
            if q_ids and any(gid in ids_raw for gid in q_ids):
                hit = True
            elif route_terms and (
                any(t in fp or t in sym or t in heading for t in route_terms)
                or bool(path_parts & set(route_terms))
            ):
                hit = True
            if hit:
                extra[cid] = chunk

    def _apply_file_aggregation(self, hits: list[LexicalHit]) -> list[LexicalHit]:
        """Boost chunks from files with multiple matching spans (truth files).

        Stray JSONL one-liners rarely co-occur; living modules / findings docs do.
        """
        boost = float(getattr(self.config, "file_agg_boost", 0.35) or 0.0)
        if boost <= 0.0 or len(hits) < 2:
            return hits
        by_fp: dict[str, list[LexicalHit]] = {}
        for h in hits:
            by_fp.setdefault(h.filepath or "", []).append(h)
        out: list[LexicalHit] = []
        for fp, group in by_fp.items():
            n = len(group)
            if n <= 1 or not fp:
                out.extend(group)
                continue
            factor = 1.0 + boost * math.log1p(n)
            max_s = max(h.score for h in group) or 1.0
            for h in group:
                local = 1.0 + 0.15 * boost * (h.score / max_s)
                out.append(replace(h, score=h.score * factor * local))
        return out


    def lookup_records(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Exact id / substring lookup over typed registry records."""
        q_ids = set(_ID_IN_QUERY.findall(query))
        q_ids.update(extract_ids(query))
        q_lower = query.lower()

        rec_pq = self._records_parquet()
        if rec_pq.exists():
            try:
                return self._lookup_records_parquet(rec_pq, q_ids, q_lower, limit)
            except Exception:
                pass

        path = self._records_jsonl()
        if not path.is_file():
            return []
        out: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if self._record_matches(row, q_ids, q_lower):
                    out.append(row)
                if len(out) >= limit:
                    break
        return out

    def _lookup_records_parquet(
        self,
        rec_pq: Path,
        q_ids: set[str],
        q_lower: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        from utils.duckdb_query import duckdb_available, open_views

        if not duckdb_available():
            raise RuntimeError("duckdb unavailable")
        con = open_views({"records": str(rec_pq).replace("\\", "/")}, read_only=True)
        try:
            rows = con.execute("SELECT * FROM records").fetchall()
            cols = [d[0] for d in con.description]
        finally:
            con.close()
        out: list[dict[str, Any]] = []
        for rec in rows:
            row = dict(zip(cols, rec))
            if self._record_matches(row, q_ids, q_lower):
                out.append(row)
            if len(out) >= limit:
                break
        return out

    @staticmethod
    def _record_matches(row: dict[str, Any], q_ids: set[str], q_lower: str) -> bool:
        rid = _as_str(row.get("id"), "")
        if q_ids and rid in q_ids:
            return True
        if rid and rid.lower() in q_lower:
            return True
        return False
