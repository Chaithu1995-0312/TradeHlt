"""Parquet-backed LexicalIndex: query path must not load JSONL into RAM."""
from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import pytest

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "src"))

from retrieval.index_store import tokenize
from retrieval.lexical import LexicalHit, LexicalIndex

pytest.importorskip("duckdb")
pytest.importorskip("pyarrow")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_parquet(path: Path, rows: list[dict[str, Any]]) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, path, compression="zstd")


def _term_freqs(text: str) -> dict[str, int]:
    freqs: dict[str, int] = {}
    for term in tokenize(text):
        freqs[term] = freqs.get(term, 0) + 1
    return freqs


def _chunk(
    chunk_id: str,
    text: str,
    *,
    truth_class: str = "CURRENT",
    lifecycle_status: str = "LIVE",
    heading: str = "",
    symbols: str = "",
    ids: str = "",
    authority_rank: int = 1,
    filepath: str = "src/example.py",
    start_line: int = 1,
    end_line: int = 10,
) -> dict[str, Any]:
    tokens = tokenize(text)
    return {
        "chunk_id": chunk_id,
        "filepath": filepath,
        "start_line": start_line,
        "end_line": end_line,
        "text": text,
        "content_sha": f"sha-{chunk_id}",
        "truth_class": truth_class,
        "authority_rank": authority_rank,
        "tier_rule": "test",
        "lifecycle_status": lifecycle_status,
        "status_evidence": lifecycle_status,
        "heading": heading,
        "symbols": symbols,
        "ids": ids,
        "confidence": "",
        "validated": "",
        "revalidate_by": "",
        "token_count": len(tokens),
    }


def _postings_for(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ch in chunks:
        for term, tf in _term_freqs(ch["text"]).items():
            rows.append({"term": term, "chunk_id": ch["chunk_id"], "tf": tf})
    return rows


@dataclass
class _FixtureConfig:
    index_dir: Path
    top_k_default: int = 10
    bm25_k1: float = 1.2
    bm25_b: float = 0.75
    exact_id_boost: float = 5.0
    symbol_boost: float = 2.0
    heading_boost: float = 1.5
    non_live_penalty: float = 0.25
    truth_class_weights: dict[str, float] = field(
        default_factory=lambda: {
            "CURRENT": 1.5,
            "INTENDED": 1.3,
            "RECORDED": 1.2,
            "REFERENCE": 1.0,
            "HISTORICAL": 0.4,
        }
    )

    def chunks_jsonl(self) -> Path:
        return self.index_dir / "chunks.jsonl"

    def postings_jsonl(self) -> Path:
        return self.index_dir / "postings.jsonl"

    def records_jsonl(self) -> Path:
        return self.index_dir / "records.jsonl"


def _known_corpus() -> list[dict[str, Any]]:
    return [
        _chunk(
            "c-live",
            "rr_fusion is disabled because the fusion layer short-circuits.",
            truth_class="CURRENT",
            heading="Why rr_fusion is disabled",
            symbols="rr_fusion",
            ids="F-016",
            filepath="src/engines/rr_fusion.py",
        ),
        _chunk(
            "c-hist",
            "rr_fusion is disabled in the archived notes.",
            truth_class="HISTORICAL",
            heading="Archive",
            symbols="rr_fusion",
            filepath="docs/implementation_plan/old.md",
        ),
        _chunk(
            "c-other",
            "bananas and mangoes are unrelated fruit examples.",
            truth_class="REFERENCE",
            filepath="docs/reference/fruit.md",
        ),
        _chunk(
            "c-dead",
            "rr_fusion is disabled after retirement of the experiment.",
            truth_class="RECORDED",
            lifecycle_status="SUPERSEDED",
            heading="Retired fusion",
            symbols="rr_fusion",
            filepath="docs/governance/findings.md",
        ),
    ]


def _materialize(index_dir: Path, *, jsonl: bool = True, parquet: bool = True) -> _FixtureConfig:
    chunks = _known_corpus()
    postings = _postings_for(chunks)
    cfg = _FixtureConfig(index_dir=index_dir)
    if jsonl:
        _write_jsonl(cfg.chunks_jsonl(), chunks)
        _write_jsonl(cfg.postings_jsonl(), postings)
        _write_jsonl(
            cfg.records_jsonl(),
            [{"id": "F-016", "type": "finding", "status": "LIVE", "conclusion": "fusion off"}],
        )
    if parquet:
        _write_parquet(cfg.chunks_jsonl().with_suffix(".parquet"), chunks)
        _write_parquet(cfg.postings_jsonl().with_suffix(".parquet"), postings)
        _write_parquet(
            cfg.records_jsonl().with_suffix(".parquet"),
            [{"id": "F-016", "type": "finding", "status": "LIVE", "conclusion": "fusion off"}],
        )
    return cfg


QUERY = "why is rr_fusion disabled"
EXPECTED_TOP = ["c-live", "c-hist", "c-dead"]  # CURRENT > HISTORICAL > SUPERSEDED*RECORDED


def test_search_parquet_backed_tiny_index(tmp_path: Path) -> None:
    cfg = _materialize(tmp_path / "rag")
    idx = LexicalIndex(cfg)  # type: ignore[arg-type]
    hits = idx.search(QUERY, top_k=8)
    assert hits, "expected hits from parquet-backed index"
    assert [h.chunk_id for h in hits][:3] == EXPECTED_TOP
    assert hits[0].truth_class == "CURRENT"
    assert hits[0].filepath == "src/engines/rr_fusion.py"
    assert "rr_fusion" in hits[0].text
    assert idx._backend == "parquet"
    assert idx._con is not None
    assert idx._chunks == {}
    assert idx._postings == {}


def test_ranking_stable_across_two_searches(tmp_path: Path) -> None:
    cfg = _materialize(tmp_path / "rag")
    idx = LexicalIndex(cfg)  # type: ignore[arg-type]
    a = idx.search(QUERY, top_k=8)
    b = idx.search(QUERY, top_k=8)
    assert [h.chunk_id for h in a] == [h.chunk_id for h in b]
    for ha, hb in zip(a, b):
        assert ha.score == pytest.approx(hb.score, rel=1e-12, abs=1e-12)
        assert ha.bm25 == pytest.approx(hb.bm25, rel=1e-12, abs=1e-12)


def test_parquet_only_dir_does_not_need_jsonl(tmp_path: Path) -> None:
    cfg = _materialize(tmp_path / "rag", jsonl=False, parquet=True)
    assert not cfg.chunks_jsonl().exists()
    assert not cfg.postings_jsonl().exists()
    assert cfg.chunks_jsonl().with_suffix(".parquet").is_file()
    idx = LexicalIndex(cfg)  # type: ignore[arg-type]
    hits = idx.search(QUERY, top_k=4)
    assert [h.chunk_id for h in hits][:3] == EXPECTED_TOP
    assert idx._backend == "parquet"
    assert idx._chunks == {}


def test_missing_parquet_fails_loud_when_jsonl_absent(tmp_path: Path) -> None:
    cfg = _FixtureConfig(index_dir=tmp_path / "empty")
    idx = LexicalIndex(cfg)  # type: ignore[arg-type]
    with pytest.raises(FileNotFoundError, match="Parquet sidecars missing"):
        idx.load()


def test_tiny_jsonl_fixture_fallback(tmp_path: Path) -> None:
    cfg = _materialize(tmp_path / "rag", jsonl=True, parquet=False)
    idx = LexicalIndex(cfg)  # type: ignore[arg-type]
    hits = idx.search(QUERY, top_k=4)
    assert [h.chunk_id for h in hits][:3] == EXPECTED_TOP
    assert idx._backend == "jsonl"


def test_include_historical_false_drops_hist(tmp_path: Path) -> None:
    cfg = _materialize(tmp_path / "rag")
    idx = LexicalIndex(cfg)  # type: ignore[arg-type]
    hits = idx.search(QUERY, top_k=8, include_historical=False)
    assert all(h.truth_class != "HISTORICAL" for h in hits)
    assert "c-live" in [h.chunk_id for h in hits]


def test_truth_class_filter(tmp_path: Path) -> None:
    cfg = _materialize(tmp_path / "rag")
    idx = LexicalIndex(cfg)  # type: ignore[arg-type]
    hits = idx.search(QUERY, top_k=8, truth_class_filter="CURRENT")
    assert hits
    assert all(h.truth_class == "CURRENT" for h in hits)


def test_lookup_records_works_without_jsonl(tmp_path: Path) -> None:
    cfg = _materialize(tmp_path / "rag", jsonl=False, parquet=True)
    idx = LexicalIndex(cfg)  # type: ignore[arg-type]
    recs = idx.lookup_records("see F-016 for fusion")
    assert recs and recs[0]["id"] == "F-016"


def test_pipeline_search_uses_temp_index_dir(tmp_path: Path) -> None:
    """RetrievalPipeline must honor a temp index_dir (never production data/rag)."""
    cfg = _materialize(tmp_path / "rag")
    try:
        from retrieval.config import build_default_config
        from retrieval.retriever import Retriever
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"retrieval helpers unavailable: {exc}")

    real = build_default_config()
    real.index_dir = cfg.index_dir
    for name in ("bm25_k1", "bm25_b", "exact_id_boost", "symbol_boost", "heading_boost", "non_live_penalty"):
        if hasattr(real, name):
            setattr(real, name, getattr(cfg, name))
    if hasattr(real, "truth_class_weights"):
        real.truth_class_weights = dict(cfg.truth_class_weights)
    real.chunks_jsonl = cfg.chunks_jsonl  # type: ignore[method-assign]
    real.postings_jsonl = cfg.postings_jsonl  # type: ignore[method-assign]
    real.records_jsonl = cfg.records_jsonl  # type: ignore[method-assign]

    idx = LexicalIndex(real)
    retriever = Retriever(idx, real)
    ctx = retriever.retrieve(QUERY, top_k=5)
    assert ctx.chunks
    assert ctx.chunks[0].chunk_id == "c-live"
    assert idx._backend == "parquet"
    prod = Path(getattr(build_default_config(), "index_dir", _REPO / "data" / "rag"))
    assert Path(real.index_dir) != prod or "rag" in str(tmp_path)


def test_reference_bm25_matches_in_memory_and_parquet(tmp_path: Path) -> None:
    """Parquet path scores match the in-memory formula on the same fixture."""
    mem_cfg = _materialize(tmp_path / "mem", jsonl=True, parquet=False)
    pq_cfg = _materialize(tmp_path / "pq", jsonl=False, parquet=True)
    mem = LexicalIndex(mem_cfg)  # type: ignore[arg-type]
    pq = LexicalIndex(pq_cfg)  # type: ignore[arg-type]
    mem_hits = {h.chunk_id: h for h in mem.search(QUERY, top_k=10)}
    pq_hits = {h.chunk_id: h for h in pq.search(QUERY, top_k=10)}
    assert set(mem_hits) == set(pq_hits)
    assert [h.chunk_id for h in mem.search(QUERY, top_k=10)] == [
        h.chunk_id for h in pq.search(QUERY, top_k=10)
    ]
    for cid, mh in mem_hits.items():
        ph = pq_hits[cid]
        assert ph.score == pytest.approx(mh.score, rel=1e-9, abs=1e-9)
        assert ph.bm25 == pytest.approx(mh.bm25, rel=1e-9, abs=1e-9)


def _noise_corpus() -> list[dict[str, Any]]:
    """Living module vs CURRENT 1-line JSON key — classic candidate-gen noise."""
    live = _chunk(
        "c-code",
        (
            "rr_fusion is disabled because the fusion layer short-circuits "
            "when the gate rejects the secondary signal. See engine wiring "
            "in the rr_fusion module for the authoritative CURRENT behavior."
        ),
        truth_class="CURRENT",
        heading="Why rr_fusion is disabled",
        symbols="rr_fusion",
        ids="F-016",
        filepath="src/engines/rr_fusion.py",
        start_line=10,
        end_line=40,
    )
    json_hit = _chunk(
        "c-json",
        '"rr_fusion": {',
        truth_class="CURRENT",
        heading="json-record",
        symbols="rr_fusion",
        filepath="configs/production/runtime_flags.json",
        start_line=88,
        end_line=88,
        authority_rank=1,
    )
    # Force tiny token_count for the JSON one-liner (matches production shape).
    json_hit["token_count"] = 1
    other = _chunk(
        "c-other",
        "unrelated bananas mangoes fruit salad recipe notes.",
        truth_class="REFERENCE",
        filepath="docs/reference/fruit.md",
    )
    return [live, json_hit, other]


def test_stem_boost_beats_json_record_snippet(tmp_path: Path) -> None:
    """Filepath-stem match must outrank a 1-line JSON key CURRENT hit."""
    chunks = _noise_corpus()
    postings = _postings_for(chunks)
    cfg = _FixtureConfig(index_dir=tmp_path / "rag")
    _write_parquet(cfg.chunks_jsonl().with_suffix(".parquet"), chunks)
    _write_parquet(cfg.postings_jsonl().with_suffix(".parquet"), postings)
    try:
        from retrieval.config import RetrievalConfig

        real = RetrievalConfig(index_dir=cfg.index_dir)
        for name in (
            "bm25_k1",
            "bm25_b",
            "exact_id_boost",
            "symbol_boost",
            "heading_boost",
            "non_live_penalty",
            "truth_class_weights",
        ):
            if hasattr(cfg, name):
                setattr(real, name, getattr(cfg, name))
        idx_cfg: Any = real
    except Exception:
        idx_cfg = cfg
    idx = LexicalIndex(idx_cfg)  # type: ignore[arg-type]
    hits = idx.search(QUERY, top_k=5)
    assert hits, "expected hits"
    assert hits[0].chunk_id == "c-code", [(h.chunk_id, h.filepath, h.score) for h in hits]
    assert "rr_fusion.py" in hits[0].filepath
    json_ranks = [i for i, h in enumerate(hits) if h.chunk_id == "c-json"]
    code_rank = [i for i, h in enumerate(hits) if h.chunk_id == "c-code"][0]
    if json_ranks:
        assert code_rank < json_ranks[0]


def test_candidate_pool_and_filters_still_work(tmp_path: Path) -> None:
    """Larger candidate_n keeps fixture order; filters still partition classes."""
    cfg = _materialize(tmp_path / "rag")
    try:
        from retrieval.config import RetrievalConfig

        real = RetrievalConfig(index_dir=cfg.index_dir, candidate_n=400)
        for name in (
            "bm25_k1",
            "bm25_b",
            "exact_id_boost",
            "symbol_boost",
            "heading_boost",
            "non_live_penalty",
            "truth_class_weights",
        ):
            if hasattr(cfg, name):
                setattr(real, name, getattr(cfg, name))
        idx_cfg: Any = real
    except Exception:
        idx_cfg = cfg
    idx = LexicalIndex(idx_cfg)  # type: ignore[arg-type]
    hits = idx.search(QUERY, top_k=8)
    assert [h.chunk_id for h in hits][:3] == EXPECTED_TOP
    hist = idx.search(QUERY, top_k=8, include_historical=False)
    assert all(h.truth_class != "HISTORICAL" for h in hist)
    cur = idx.search(QUERY, top_k=8, truth_class_filter="CURRENT")
    assert cur and all(h.truth_class == "CURRENT" for h in cur)



def _architecture_corpus() -> list[dict[str, Any]]:
    """Gold architecture doc vs noisy governance JSON one-liners."""
    gold = _chunk(
        "c-arch",
        (
            "The trading system is organized as a layered framework: ingestion, "
            "feature resolution, engines, and execution. This document describes "
            "the overall architecture of the living trading system."
        ),
        truth_class="INTENDED",
        heading="Trading System Framework",
        symbols="TRADING_SYSTEM_FRAMEWORK",
        filepath="docs/architecture/TRADING_SYSTEM_FRAMEWORK.md",
        start_line=1,
        end_line=80,
    )
    noise_rows = []
    for i in range(12):
        noise_rows.append(
            _chunk(
                f"c-noise-{i}",
                f'"architecture_note_{i}": "overall trading system checklist item {i}"',
                truth_class="CURRENT",
                heading="json-record",
                symbols="",
                filepath="docs/governance/findings_archive.jsonl",
                start_line=100 + i,
                end_line=100 + i,
                authority_rank=1,
            )
        )
        noise_rows[-1]["token_count"] = 3
    other = _chunk(
        "c-fruit",
        "bananas mangoes fruit salad recipe notes unrelated to trading.",
        truth_class="REFERENCE",
        filepath="docs/reference/fruit.md",
    )
    return [gold, other, *noise_rows]


def test_file_route_architecture_ranks_gold_first(tmp_path: Path) -> None:
    """Alias/file-route boost must surface TRADING_SYSTEM_FRAMEWORK at rank #1."""
    chunks = _architecture_corpus()
    postings = _postings_for(chunks)
    cfg = _FixtureConfig(index_dir=tmp_path / "rag-arch")
    _write_parquet(cfg.chunks_jsonl().with_suffix(".parquet"), chunks)
    _write_parquet(cfg.postings_jsonl().with_suffix(".parquet"), postings)
    from retrieval.config import RetrievalConfig

    real = RetrievalConfig(index_dir=cfg.index_dir)
    for name in (
        "bm25_k1",
        "bm25_b",
        "exact_id_boost",
        "symbol_boost",
        "heading_boost",
        "non_live_penalty",
        "truth_class_weights",
        "file_route_boost",
        "file_route_max_files",
        "file_route_chunks_per_file",
    ):
        if hasattr(cfg, name):
            setattr(real, name, getattr(cfg, name))
    idx = LexicalIndex(real)
    hits = idx.search("What is the overall architecture of the trading system?", top_k=5)
    assert hits, "expected hits"
    assert hits[0].chunk_id == "c-arch", [(h.chunk_id, h.filepath, round(h.score, 3)) for h in hits]
    assert "TRADING_SYSTEM_FRAMEWORK" in hits[0].filepath


def test_file_route_explicit_path_still_routes(tmp_path: Path) -> None:
    """Explicit path fragment in the query must route that file into the pool."""
    chunks = [
        _chunk(
            "c-target",
            "CRT engine computes displacement and structure context for entries.",
            truth_class="CURRENT",
            heading="CRTEngine",
            symbols="CRTEngine",
            filepath="src/engines/crt_engine.py",
            start_line=1,
            end_line=40,
        ),
        _chunk(
            "c-noise",
            '"crt_engine": {',
            truth_class="CURRENT",
            heading="json-record",
            filepath="configs/production/runtime_flags.json",
            start_line=10,
            end_line=10,
        ),
        _chunk(
            "c-other",
            "unrelated bananas mangoes fruit salad.",
            truth_class="REFERENCE",
            filepath="docs/reference/fruit.md",
        ),
    ]
    chunks[1]["token_count"] = 1
    postings = _postings_for(chunks)
    cfg = _FixtureConfig(index_dir=tmp_path / "rag-path")
    _write_parquet(cfg.chunks_jsonl().with_suffix(".parquet"), chunks)
    _write_parquet(cfg.postings_jsonl().with_suffix(".parquet"), postings)
    from retrieval.config import RetrievalConfig

    real = RetrievalConfig(index_dir=cfg.index_dir)
    idx = LexicalIndex(real)
    hits = idx.search("explain src/engines/crt_engine.py behavior", top_k=5)
    assert hits
    assert hits[0].chunk_id == "c-target", [(h.chunk_id, h.filepath, round(h.score, 3)) for h in hits]
