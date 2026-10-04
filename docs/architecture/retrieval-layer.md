# retrieval-layer.md — The RAG machinery inside P3

> **Purpose:** specify the truth-tier lexical BM25 retrieval layer that powers **P3 Retrieve**
> of the unified cycle ([`docs/architecture/unified-workflow.md`](unified-workflow.md)).
> It is **information, not authority.** Segments returned are spans + `path:line` + tier —
> the human or session synthesizes. Pairs with `Claude-deepseek.md` §3.
>
> The design is **the existing `src/retrieval/` layer, made honest about its corpus** — eight
> concrete fixes applied on top of the current BM25-over-DuckDB/Parquet implementation.
> No new framework. No hybrid. No dense retrieval. No LLM answerer.

---

## 1. The verdict

```
Truth-tier lexical BM25 over DuckDB + Parquet
  · hand-rolled BM25, no FTS extension
  · path-classified truth tiers
  · content-hash dedupe before postings      (F1)
  · structural chunking with size cap        (F2)
  · oversize file policy                     (F3)
  · generated-view denylist                  (F4)
  · docx extraction path                     (F5)
  · versioned truth-tier classifier          (F6)
  · duplicate-ratio + skew metrics           (F7)
  · chat-export filename classifier          (F8)
  · Chroma / embeddings: BUILT, fenced, off by default
  · no LangChain / LlamaIndex / Pinecone / FAISS
  · no in-repo LLM answerer
```

---

## 2. Truth tiers (P3 classification)

| Tier | Holds | Weight | Verified root examples |
|---|---|---|---|
| CURRENT | `src/`, `scripts/` | 1.5 | `src/`, `scripts/` |
| INTENDED | `configs/`, TSA, plans | 1.3 | `configs/`, `docs/architecture/`, `docs/plans/` |
| RECORDED | findings, governance, session logs | 1.2 | `docs/current-findings.md`, `docs/governance/` |
| REFERENCE | book, reference, schemas | 1.0 | `docs/book/`, `docs/reference/` |
| HISTORICAL | archive, generated, chat exports | 0.4 | `docs/analysis/`, `*.generated.md`, `*-adj-noun.md` |

**The three rules:**

1. **Never blend tiers in one answer.** A retrieved section lands one tier label.
2. **Flag divergence; never adjudicate.** If CURRENT and INTENDED disagree, cite both with the
   tier label and a divergence flag. Do not pick a winner.
3. **RAG is P3 — information, not authority.** No in-repo LLM answerer; no SPINE module imports
   this package at module scope.

---

## 3. The eight fixes

### F1 — Content-hash dedupe before postings
`sha256(normalized_content)` per chunk; identical chunks (e.g. `episode_*.md` copies, `CONTEXT_BUNDLE.md`)
write postings once and record `duplicate_paths`. Metric `duplicate_ratio` in `index_manifest.json`.

### F2 — Chunk size cap + structural splitter
`DEFAULT_MAX_CHUNK_BYTES = 2048` (~400–500 tokens). Prose → split on `##`/`###`; trace files →
split on bar / CRT-state boundary. Chunk row carries `split_strategy`.

### F3 — Oversize file policy
`OVERSIZE_THRESHOLD` default 2 MB → **REFUSE** by default (`SUMMARY_ONLY` only if allowed in
config). Action recorded in `index_manifest.json`.

### F4 — Generated-view denylist
Derived views (`*.generated.md`, `context/*`, `CONTEXT_BUNDLE.md`, `flow_context/*`,
`graph.dot`, `code-map.generated.md`, `module-roles.generated.md`, …) are not grounding.
**Exception:** `code-map.generated.md` + `module-roles.generated.md` **are** indexed as REFERENCE
with `boot_tier=1` + `regenerated_at` — they are the shape pack.

### F5 — Docx extraction path (`src/retrieval/docx.py`, NEW)
stdlib `zipfile` + `xml` → parse `word/document.xml` into same chunk schema; tier by directory
(`ChatGpt workflow/` → INTENDED). 18 files, no `python-docx` dependency.

### F6 — Versioned truth-tier classifier
`configs/retrieval/truth_tier_v1.yaml` maps glob → tier. `index_manifest.json` records the
version so tier drift is visible.

### F7 — Duplicate-ratio + size-skew metrics
`index_manifest.json` corpus block: `total_files_scanned`, `canonical_files`,
`duplicate_ratio`, `total_bytes`, `largest_file_bytes`, `refused_oversize`, `denylisted`,
`docx_extracted`, plus per-tier counts.

### F8 — Chat-export filename classifier
`^(.*)-([a-z]+)-([a-z]+)\.md$` (e.g. `*-eager-blossom.md`) → HISTORICAL: "LLM chat export,
not authored architecture."
---

## 4. Index schema (concrete)

```python
# chunks.parquet
Chunk = {
    chunk_id:        str,     # sha256(normalized_content)  (F1)
    canonical_path:  str,
    duplicate_paths: list[str],
    truth_tier:      str,     # CURRENT|INTENDED|RECORDED|REFERENCE|HISTORICAL
    tier_rule:       str,     # rule in truth_tier_v1.yaml that matched
    line_start:      int, line_end: int,
    heading_path:    list[str],
    symbol:          str | None,
    content:         str, content_len: int,
    split_strategy:  str,     # heading|bar|paragraph
    oversize_action: str,     # FULL|SUMMARY_ONLY|REFUSED
    docx_source:     bool,    # (F5)
}

# postings.parquet
Posting = { term: str, chunk_id: str, tf: int, dl: int }

# index_manifest.json
{
    schema_version: 1,
    generated_at: "…",
    truth_tier_version: 1,
    retrieval_config: {
        bm25_k1: 1.2, bm25_b: 0.75,
        top_k: 10, candidate_n: 600,
        file_routing: {max_files: 8, max_chunks_per_file: 6, boost: 7.0},
        truth_weights: {CURRENT:1.5, INTENDED:1.3, RECORDED:1.2, REFERENCE:1.0, HISTORICAL:0.4}
    },
    corpus: { /* F7 metrics */ },
    retrieval_sha256: "…", source_tree_sha256: "…"
}
```

---

## 5. Integration with the unified cycle (P3)

**Invoked from:** session boot (after P1) · `scripts/rag_index.py query` ·
`GET /api/knowledge/search` (control plane) · CRT dashboard Knowledge page ·
`claude_integration.format_for_claude()` · agent `truth_mode`.

**Never invoked from:** trading spine (`engine_runner`, `execution_planner`,
`ultron_risk_gate`) · promotion path · any module-scope import from a SPINE module.

**Verified existing tests** (the layer is already test-covered): `test_retrieval_determinism.py`,
`test_retrieval_lexical_parquet.py`, `test_retrieval_no_derived_sources.py`,
`test_retrieval_pipeline.py`, `test_retrieval_provenance.py`, `test_retrieval_supersession.py`,
`test_retrieval_truth_tiers.py`.

---

## 6. What NOT to build

| Do not build | Why |
|---|---|
| Hybrid BM25 + dense | two authorities; RRF opaque |
| Embedding refresh pipeline | no live consumer |
| LangChain wrapper | hides control flow |
| Answer-synthesis endpoint | LLM advisory only |
| Reranker model | second scoring authority |
| Multi-vector per-tier index | tier is a boost, not a partition |