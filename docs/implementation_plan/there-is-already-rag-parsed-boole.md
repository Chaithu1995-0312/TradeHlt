# Complete the RAG — truth-tier retrieval over the Tradelatest corpus

## Context

`src/retrieval/` already contains a 9-module, ~1,590-LOC RAG (corpus → chunk → embed → ChromaDB → hybrid retrieve), a CLI (`scripts/rag_index.py`), a 100-question benchmark (`scripts/evaluation/benchmark_100.json`), and a test file. A 356 MB Chroma index with 149,853 embeddings sits on disk. **None of it works**, and the reasons are structural, not cosmetic:

| # | Defect | Source |
|---|---|---|
| 1 | Deps absent from both venvs and from every `pyproject.toml` extra | `chromadb` / `sentence-transformers` / `torch` not in `venv/Lib/site-packages` |
| 2 | "Hybrid" search **silently degrades to semantic-only** on any reloaded index | `_chunk_texts`/`_keyword_index` populated only inside `add_chunks()` — `vector_store.py:61-63`, no load-from-disk path |
| 3 | Embedding model reloaded **per query** | `vector_store.py:144-146` |
| 4 | Semantic score discards the real cosine distance | `_fuse_results` rank-based — `vector_store.py:264` |
| 5 | Provenance never populated → every citation prints `Lines: 0–0` | `retriever.py:127-138` omits `start_line`/`end_line`/component scores; consumed at `retriever.py:186` |
| 6 | `EnterpriseGate.verify()` is grounding **theater** — checks whether the proposal string contains a filepath substring | `claude_integration.py:174`, while the real 1,498-line grounder `src/governance/semantic_grounding.py` is never called |
| 7 | 85% index skew: 127,481 of 149,853 chunks are `docs/governance` JSONL | one chunk per JSONL line — `chunking.py:277` |
| 8 | `.claude/worktrees/` (near-duplicate trees) not excluded; `Monitor` writes into the real repo during tests | `config.py:89-97`; `monitor.py:54` |

Nothing outside its own CLI/tests imports it, and the benchmark has **never been run** (`results/evaluation/` is empty).

**The design constraint that matters most** is the user's warning that source code may not match intent. That is this repo's defining pathology — F-047, F-048, F-060, F-061, F-085, F-088 are all "code does X, doc claims Y". A conventional RAG retrieves a doc chunk and a code chunk and blends them into one confident paragraph — precisely the collapse `CLAUDE.md` §6.8 forbids ("never collapse CURRENT / INTENDED / RECOMMENDED"). Worse, §6.2 rule 4 mandates append-discipline, so the corpus **holds contradicting records by design**; a retriever blind to `SUPERSEDED`/`RETIRED` will serve retired truth with full confidence.

**So the deliverable is not an answer engine. It is a divergence-surfacing retrieval instrument**: it returns verbatim spans partitioned by truth class, flags when a symbol is described differently across classes, and adjudicates nothing.

**Decisions taken** (user, this session): lexical core now / dense only if the benchmark proves a recall gap · consumer is the control plane + UI · corpus is all of `docs/` plus code.

---

## Design

### Three layers

```
INDEX (build)     discover+classify → chunk → postings → data/rag/*.jsonl → *.parquet + manifest
RETRIEVE (query)  DuckDB: BM25 + exact symbol/ID + tier weight + status demotion
ENVELOPE (answer) tier-partitioned spans + divergence flags + grounding join
```

Storage is **DuckDB over Parquet**, not Chroma: already installed (`duckdb-1.5.5`, `pyarrow-25.0.1`), already this branch's substrate, and a persisted index makes defect #2 impossible by construction. No embedding model ⇒ no per-query model load ⇒ the benchmark's 500 ms criterion becomes meetable for the first time.

### The truth-tier model (the core of the design)

Every chunk carries three orthogonal fields, derived mechanically from its path and content:

**`truth_class`** — mirrors §6.8's forbidden collapse:

| Class | Sources | Meaning |
|---|---|---|
| `CURRENT` | `configs/production/ACTIVE_VERSION` + active config, `src/**`, `tests/**`, `scripts/**` | what actually executes / is enforced |
| `INTENDED` | `configs/formulas/*.yaml`, `MODEL_INTENT_AUTHORITY_REGISTER.md`, `docs/governance/semantic_os/*.yaml` | what things are supposed to mean |
| `RECORDED` | `docs/current-findings.md`, `data/findings.jsonl`, `closure_authority_index.json`, CLAUDE.md Truths Index | registered conclusions, with `Confidence` |
| `REFERENCE` | `docs/reference/`, `docs/book/`, `docs/topics/`, `docs/memory/`, `docs/architecture/` | explanatory; drifts |
| `HISTORICAL` | `docs/analysis/`, `docs/implementation_plan/`, `docs/plans/`, `docs/research-readiness/`, session-log archive | point-in-time, explicitly **not living** |
| `DERIVED` | `context/*.md`, `**/*.generated.md` | never truth → **excluded from the index** |

**`authority_rank`** (0-7) — encodes §4.0 Runtime Truth Precedence for intra-class ordering.

**`lifecycle_status`** ∈ `LIVE · SUPERSEDED · RETIRED · KILLED · FROZEN · CLOSED · OPEN · UNKNOWN`, lifted from the source text (findings rows, closure index, ontology `lifecycle:` keys). Non-`LIVE` chunks stay indexed (history is preserved per §6.2 rule 4) but are **demoted and always rendered with their marker** — never silently ranked beside live truth.

The `HISTORICAL` class is load-bearing given the chosen corpus width: 200 implementation plans + 152 analyses + 68 plans + 1,374 archived log entries would otherwise drown the ~40 files that are actually authoritative.

### Divergence detection — mechanical only

Four checks, all decidable without semantic reasoning. The retriever **never picks a winner** (§6.8: "the reviewer does not pick a winner"); a conflict is emitted in `TruthConflict` shape (§6.2 rule 3) for the caller to adjudicate.

1. `co_retrieval_divergence` — one symbol/ID appears in top-K chunks from ≥2 truth classes → present both, flag.
2. `superseded_hit` — a top-K result is non-`LIVE` → always surfaced with its marker.
3. `stale_citation` — a retrieved chunk cites a `path:line` that no longer resolves; reuse the ±30-line window logic already in `tests/test_doc_citations.py`.
4. `confidence_carry` — findings chunks carry `Confidence` and `Validated`/`Revalidate-by` verbatim.

**Explicitly out of scope:** the system does *not* claim to detect that code semantically contradicts intent. It surfaces co-retrieval; a human or session adjudicates.

### Grounding join (§6.7 / CT-008)

Retrieval is not grounding. Chunk metadata extracts ids (`F-\d+`, `FM-\d+`, `SEM-\d+`, `MC-*`, `CN-/BD-/CT-/JN-/CC-*`); an optional `--ground` step routes each asserted id through `src/governance/semantic_grounding.py` and surfaces `GROUNDED · UNKNOWN · AMBIGUOUS · UNANSWERABLE · REFUSED` **verbatim**. `REFUSED` must never be smoothed into prose. This replaces the fake `EnterpriseGate`.

### Anti-hallucination invariant

The retriever returns **verbatim spans with resolvable provenance** — never paraphrase, never synthesis. Every result carries `filepath`, real `start_line`/`end_line` (fixing defect #5), and a `content_sha`. A citation that cannot be opened is not evidence.

### Registries become records, not chunks

`data/findings.jsonl` (100), `script_registry.jsonl` (458), `framework_registry.jsonl` (41), `hypothesis_registry.jsonl` (20), `jsonl_claim_catalog.jsonl` (55) load into a **typed DuckDB table** with real columns (`id, type, status, confidence, conclusion`) rather than blob-chunked text. This kills defect #7's skew *and* turns "what is F-048's status" into an exact lookup instead of a fuzzy match.

### Hard exclusions

`logs/**` (39 GB — the correct surface is `scripts/analysis/query_trace.py`; RAG indexes only its schemas/manifests) · `data/master_crypto_training.jsonl` (396 MB × 10 copies) · `data/chroma_db` · `.claude/worktrees/**` · `msip_1_verification_package/`, `reports/_ours_backup/` (duplicate `assistant_project.md`) · `venv`, `.venv` · `context/**`, `**/*.generated.md`. A `content_sha` dedupe pass is the backstop. The indexer must never open `data/mt5/*.csv` — that would trip the shrink-only ratchet in `scripts/analysis/corpus_read_lint.py`.

---

## Implementation

### Phase 0 — Quarantine, make brokenness loud
- `src/retrieval/vector_store.py`: replace the silent keyword-index degradation with a **fail-loud** guard — an unloaded index raises rather than returning semantic-only results labelled "hybrid". Defect #2 must never again be invisible.
- Fix `monitor.py:54` test pollution (`_log_path` must honour an overridden root, not always `repo_root/data/`).
- Leave the stale 356 MB `data/chroma_db` on disk (gitignored derived data, user's to delete); stop referencing it.

### Phase 1 — Truth-tier corpus + index
- **New** `src/retrieval/truth_tier.py` — path → (`truth_class`, `authority_rank`), and text → `lifecycle_status`. Pure, table-driven, no I/O.
- Rewrite `config.py` `domain_patterns` → recursive tier patterns per the table above; extend `exclude_patterns` with the hard-exclusion list.
- `corpus.py`: keep `_enrich_python` AST symbol extraction; add ID extraction and `content_sha`; add dedupe.
- `chunking.py`: keep as-is (the AST/heading-aware chunker is genuinely good) except `_chunk_json:277` — route registries to the record loader instead of per-line chunking.
- **New** `src/retrieval/index_store.py` — writes `data/rag/chunks.jsonl` + `postings.jsonl`, projects to Parquet, and pins a sidecar manifest (per-file `sha256`/`mtime`/`size`). **Reuse `src/utils/parquet_store.py`** — its LOSSLESS / NEVER-STALE / OPTIONAL contract and manifest pattern is exactly this need; do not rebuild it. Manifest deltas give real incremental indexing (today `cmd_incremental` is an alias for full rebuild).

### Phase 2 — Retrieval + envelope
- **New** `src/retrieval/lexical.py` — BM25 in DuckDB SQL (tf in postings, df via `GROUP BY`). Hand-rolled, **not** the `fts` extension: that needs a network install and would break determinism.
- **New** `src/retrieval/divergence.py` — the four mechanical checks.
- Rewrite `retriever.py` to emit a tier-partitioned `ContextAssembly` with populated provenance; keep `format_for_claude` / `format_compact` signatures.
- Replace `EnterpriseGate` in `claude_integration.py` with a real `semantic_grounding` join.
- **Reuse** `src/utils/duckdb_query.py` for the in-memory view layer.

### Phase 3 — Benchmark (first real run)
- Run `scripts/evaluation/run_benchmark.py`. **Validate the gold set first** — its 100 questions were authored against the old domain map and may cite paths this corpus scopes differently. Adjust the gold set where it is stale, and say so; do not assume `recall@5 ≥ 0.90` is a meaningful bar until the questions are verified.
- Record the numbers honestly, including misses. This is the evidence gate for Phase 5.

### Phase 4 — Control plane + UI (the chosen consumer)
Follow the `ContextReportAPI` template exactly (stateless, no `__init__`, returns `{"ok": bool, ...}`, never raises, dependency injected):
- **New** `src/control_plane/retrieval_api.py` → `KnowledgeAPI.search_payload(...)`, `.status_payload()`.
- `server.py`: instantiate beside `ContextReportAPI` (`:2191`) → add param to `create_handler` (`:1581`) → pass in `start()` (`:2212`) → add `GET /api/knowledge/search` + `/api/knowledge/status` branches in `do_GET` **before** the `/ui_kits/` branch at `:1807`, using the `query.get(k,[default])[0]` idiom from `/api/trades` (`:1706-1717`).
- `ui_kits/crt_dashboard/apiClient.js`: `fetchKnowledgeSearch`.
- **New** `page7_knowledge.jsx` + `<script>` tag in `index.html:25-34` (before `app.jsx`) + `PAGES` entry (`app.jsx:280-290`) + `SIDEBAR_SECTIONS`/`SIDEBAR_PAGE_MAP` (`shared.jsx:193-247`). The UI renders the tier partition and divergence flags as first-class — not a flat result list.
- **New** `CommandSpec` `knowledge.rag_index` in `core_command_specs()` (`registry.py`, before `:1118`) + entries in `_WORKFLOW_STAGE_BY_COMMAND` / `_QUICKSTART_NOTES_BY_COMMAND` / `_RECOMMENDED_NEXT_BY_COMMAND`.

### Phase 5 — Dense rerank (conditional)
Only if Phase 3 shows the lexical core actually missing recall. Adds a `retrieval` extra to `pyproject.toml` and an optional reranker behind an import guard; the lexical core stays mandatory and unchanged. Evidence before doctrine (§6.5).

---

## Governance obligations (non-optional, same turn)

- **SITS registration** for every new script: `script_census.py --write-stubs` → `seed_script_registry.py` → `generate_script_matrix.py`. Unregistered paths fail the GREEN_FLOOR coverage test.
- **Regenerate `docs/reference/cli-matrix.md`** — a new `CommandSpec` fails `tests/test_cli_matrix_sync.py` and `tests/test_control_plane_doc_alignment.py:17-21` until you do.
- **SESSION LOG entry** in `assistant_project.md` (§6) — this touches `src/**`, so the `commit-msg` hook requires a same-day entry.
- **Topic doc** under `docs/topics/` for the retrieval concept (§6.4).
- No `params`-block edit ⇒ **no config rehash** required.

## Verification

**Baseline first** (§1.5): capture the green-floor failure count *before* any edit, so a pre-existing red is not misread as a regression.

```bash
venv/Scripts/python.exe scripts/maintenance/check_governance_invariants.py --all
```

New test floors:
| File | Asserts |
|---|---|
| `tests/test_retrieval_truth_tiers.py` | every corpus path classifies to exactly one `truth_class`; zero unclassified |
| `tests/test_retrieval_determinism.py` | same tree → byte-identical index (mirrors `test_context_compiler.py`'s build-twice pattern) |
| `tests/test_retrieval_no_derived_sources.py` | `context/**` and `*.generated.md` never appear in the index |
| `tests/test_retrieval_supersession.py` | a `SUPERSEDED`/`RETIRED` record is never returned unmarked |
| `tests/test_retrieval_provenance.py` | every result has a resolvable filepath and a non-zero line range |
| `tests/test_retrieval_pipeline.py` | existing — fix the fixture pollution, extend for the new store |

End-to-end:
```bash
venv/Scripts/python.exe scripts/rag_index.py index --rebuild
venv/Scripts/python.exe scripts/rag_index.py query "why is rr_fusion disabled" --explain
venv/Scripts/python.exe scripts/evaluation/run_benchmark.py
```

The `--explain` run is the real acceptance test: that query must return the F-038 finding (`RECORDED`), the active-config disable (`CURRENT`), and the F-044 gate mis-specification (`RECORDED`) **as separate tier-partitioned spans with a divergence flag**, not as one blended paragraph.

Control plane: start the server, `GET http://localhost:8787/api/knowledge/search?q=...`, confirm JSON shape and the new UI tab renders tiers + flags.

## Risks

- **Benchmark gold set may be stale** — authored pre-rewrite. Verify before trusting any recall number.
- **Corpus width** (user's choice) means `HISTORICAL` outnumbers living truth ~10:1. If demotion tuning proves insufficient in Phase 3, the fallback is to gate `HISTORICAL` behind an explicit opt-in flag rather than weight it.
- **Index size** — ~1,584 `.py` + 874 `.md` + registries. Expect materially fewer than 149,853 chunks once the JSONL skew is removed; if Parquet/BM25 latency exceeds the 500 ms bar, partition postings by `truth_class`.
