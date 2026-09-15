# RAG → Claude LLM Linkage — Design Document (discussion only, no code this session)

## Context

The user asked for a trace of the existing RAG implementation in `Tradelatest` (required
fields, how it works today) plus a design for linking it to the Claude LLM, with pros/cons,
mechanics, and trigger points. This is explicitly a **design/discussion deliverable** — the
user selected "no code yet" when asked. Nothing below authorizes an edit; it is the write-up
to review and, if approved, hand to a future implementation turn.

The motivation surfaced during tracing: the repo's own most recent session log
(`docs/analysis/session-log-archive/session-log-2026-09-09_to_2026-09-09.md:106-113`) already
diagnosed this exact gap in its own words — *"RAG is search not GROUNDED"* — and its
`.grok/PENDING.md` ledger (rows P-LLM-01/02, P-RAG-01) explicitly parked the work of (a) wiring
RAG into an LLM answer path and (b) fixing corpus coverage, pending user authorization. This
document is that authorization conversation.

---

## 1. What exists today (traced from source)

### 1.1 Architecture — it's a lexical (BM25) retrieval core, not a vector-embedding RAG

`src/retrieval/__init__.py:1-9` states the intent directly: *"Truth-tier lexical RAG... DuckDB/
Parquet lexical query core (hand-rolled BM25; no fts extension)... Dense/Chroma is optional
Phase-5 only."*

Pipeline: `CorpusDiscoverer` (`corpus.py`) → `Chunker` (`chunking.py`, AST-aware for `.py`,
heading-aware for `.md`/`.yaml`) → `IndexStore` (`index_store.py`, writes JSONL
system-of-record + Parquet sidecars) → `LexicalIndex` (`lexical.py`, BM25 over DuckDB/Parquet)
→ `Retriever` (`retriever.py`, ranks, truth-tier partitions, assembles context) →
`claude_integration.py` (formats the assembled context as Markdown + runs a grounding check).

**`claude_integration.py` does not call any LLM.** No `anthropic` import, no `messages.create`,
no model name, no HTTP call anywhere in the file or its callers. Its actual job is:
`get_context()`/`format_context()` (produce Markdown), and `GroundingGate` (verify that any
`F-###`/`FM-###`-style id mentioned resolves via `governance.semantic_grounding` to
`GROUNDED`, never smoothing `REFUSED`/`UNKNOWN` into prose — `claude_integration.py:6-8`). The
filename is aspirational, not descriptive of current behavior.

The dense/Chroma path (`vector_store.py`, `embedding.py`, `sentence-transformers`+`torch` as
the `retrieval` extra in `pyproject.toml:29-30`) is **dead code**: it references
`self.config.structural_boost`/`hybrid_alpha`, attributes that don't exist on the current
`RetrievalConfig`; the one test file that exercises it (`tests/test_retrieval_pipeline.py`)
constructs `Document(domain=...)` against a schema where `domain` is now a derived
`@property`, not a constructor field — it would error at fixture setup. `__init__.py:82-89`
documents this deliberately: legacy attributes kept only so old attribute access doesn't crash,
"hybrid_search will fail loud if invoked." **Any Claude-linkage design should build on the live
lexical path and leave the dense/Chroma path alone.**

### 1.2 Required-fields schema (grep-verified, per stage)

| Stage | Type | Required fields | Optional/defaulted |
|---|---|---|---|
| Corpus doc | `Document` (`corpus.py:39-66`) | `path`, `truth_class`, `authority_rank`, `tier_rule`, `content` | `content_sha`, `ids`, `metadata`; `domain` is a read-only property aliasing `truth_class` |
| Chunk | `Chunk` (`chunking.py:27-48`) | `doc_path`, `domain`, `chunk_id`, `text`, `start_line`, `end_line` | `heading`, `metadata` |
| Indexed record | `IndexedChunk` (`index_store.py:47-67`) | `chunk_id`, `filepath`, `start_line`, `end_line`, `text`, `content_sha`, `truth_class`, `authority_rank`, `tier_rule`, `lifecycle_status`, `status_evidence`, `heading`, `symbols`, `ids` | `confidence`, `validated`, `revalidate_by`, `token_count` |
| Query result | `HybridResult` (`retriever.py:19-44`) | `chunk_id`, `text`, `score` | `truth_class`, `authority_rank=99`, `lifecycle_status="LIVE"`, `content_sha`, `confidence`, `ids`, `symbols` |
| Citation validity | contract asserted by `tests/test_retrieval_provenance.py:12-27` | `start_line > 0`, `end_line >= start_line`, non-empty `filepath`, non-empty `content_sha` | — a `HybridResult` failing these is not admissible as evidence |

No `_require()`-style strict config loader exists in `src/retrieval/config.py` (confirmed by
grep across all 12 modules) — enforcement is by dataclass required-positional-fields plus the
provenance-contract test above, not the `example-service.py` fail-fast pattern used elsewhere
in the repo. **If a Claude linkage is built, its own config section should follow the repo's
standard `_require()` pattern** (per `docs/reference/example-service.py`), not replicate this
gap.

### 1.3 Wiring status — what's actually reachable today

Live callers found by sweep:
- `src/control_plane/retrieval_api.py` (`KnowledgeAPI`) → wired into
  `src/control_plane/server.py:2214,2235`, exposed as `/api/knowledge/search` and
  `/api/knowledge/status` (HTTP, localhost:8787 only, per CLAUDE.md §4's control-plane
  constraint).
- `src/control_plane/registry.py:1125-1139` — `CommandSpec(id="knowledge.rag_index", ...)`
  runs `scripts/rag_index.py` as a subprocess, picked up by the control-plane UI automatically.
- `scripts/rag_index.py` — CLI: `index --rebuild`, `query "<q>" --explain`, `discover`,
  `metrics`, `status`, `verify <q> [--ground]`.
- `scripts/evaluation/run_benchmark.py` — scores retrieval quality against expected files.

**Not found anywhere:** any agent-tool registration (`tool_registry.py`/`PLAN_REGISTRY`), any
`anthropic.Anthropic()`/`AsyncAnthropic()` client construction feeding `claude_integration`'s
formatted output, or any reference to `src/retrieval/` from `CLAUDE.md`/`AGENTS.md` (confirmed
independently by the repo's own `.grok/PENDING.md:93`: *"retrieval token count in CLAUDE.md = 0,
in AGENTS.md = 0"*).

### 1.4 Governance status — undeclared

No `F-xxx` finding, no `docs/memory/*.md` ownership, no MIAR/`docs/governance/miar_registry.json`
entry, no `docs/topics/*.md` doc covers `src/retrieval/`. It is a live-but-ungoverned subsystem —
per CLAUDE.md §6.6, any change here that alters what a downstream consumer sees should register
a canonical node / finding the same turn it ships, not leave it undeclared indefinitely.

### 1.5 Precedent — Claude API is already used elsewhere in this repo

`src/control_plane/context_report.py` (`ContextReportAPI.context_analysis()`,
per `docs/topics/context-report.md:19,24`) already calls the Anthropic API — reads
`ANTHROPIC_API_KEY` via a local `_load_dotenv()`, uses model `claude-haiku-4-5`. This is a
**second, independent** integration point from the one this design proposes, and is itself
missing from `docs/reference/architecture.md`'s §5 External Integrations table (which lists
only llama.cpp / Groq / BitNet). Two implications: (a) there's a working in-repo pattern to
copy for key-loading and error handling; (b) the architecture doc has a pre-existing gap that
a RAG-Claude linkage would widen unless both get documented together.

### 1.6 Corpus coverage gap (explicitly in scope per your answer)

`.grok/PENDING.md:94` (row P-RAG-01): the last full reindex omitted `CLAUDE.md`,
`docs/current-findings.md`, `docs/topics/`, `docs/memory/`, `docs/book/`, `scripts/`, and the
Semantic OS yaml files from `configs/include_patterns`. A Claude-answering layer built on top of
this index would confidently answer questions while blind to the governance doctrine, the
findings ledger, and the memory index — the exact failure mode RAG is supposed to prevent
(hallucination), just moved one level up (the retrieval step silently omits the ground truth
instead of the LLM inventing it). **Fixing `RetrievalConfig.include_patterns` /
`exclude_patterns` (`config.py:121-172`) to cover these paths, and rerunning
`scripts/rag_index.py index --rebuild`, is a prerequisite step in the plan below — not an
afterthought.**

---

## 2. Design: linking the RAG layer to Claude

### 2.1 Recommended shape

Add a **new, additive module** — `src/retrieval/answer.py` (name TBD) — that:

1. Calls the existing `Retriever.retrieve()` → `ContextAssembly` (unchanged, live code).
2. Runs the existing `GroundingGate` over any governed ids in the assembled context
   (unchanged, live code) — **any `REFUSED`/`AMBIGUOUS`/`UNANSWERABLE` id is stripped or
   flagged before the prompt is built, never smoothed over**, per the module's own stated
   contract (`claude_integration.py:6-8`).
3. Builds a prompt: system message = truth-tier-partitioned context
   (`Retriever.format_for_claude`, already exists) + an instruction to answer only from the
   supplied context and say "not found in retrieved context" otherwise; user message = the
   query.
4. Calls the Anthropic Messages API (new: a thin client wrapper following the
   `docs/reference/example-service.py` pattern — optional-import guard, circuit breaker,
   `fail_count_disable`, timeout, matching how `llm_inference_client.py` already treats Groq/
   local-llama as a **tie-breaker, never a hot-path dependency**, CLAUDE.md §4).
5. Returns a structured result: `{answer, citations: [HybridResult...], grounding_status,
   model, latency_ms}` — never bare prose, so a caller can render citations and refuse to
   display an answer whose citations fail the provenance contract (§1.2 table, row 5).

Config: a new `retrieval.claude_answer` section in whichever config carries it (NOT
`configs/production/*.json` — those are trading-strategy configs, confirmed zero RAG keys
there; a new `configs/rag/` or a section read via `RetrievalConfig` extension is the right
home), strictly `_require()`'d: `model` (default `claude-haiku-4-5`, matching the existing
`context_report.py` precedent — cheap, fast, appropriate for a Q&A-over-retrieved-context task
that doesn't need frontier reasoning), `max_tokens`, `timeout_s`, `fail_count_disable`,
`enabled` (defaults `false` until explicitly turned on).

### 2.2 Pros

- **Reuses everything live and tested** — lexical retrieval, truth-tier partitioning,
  provenance contract, and the grounding gate are already built, tested (7 test files), and
  wired into the control plane. The only new code is the LLM call + prompt assembly.
- **Closes the repo's own named gap** ("RAG is search not GROUNDED") — turns a search tool
  into an answer tool while keeping the anti-hallucination discipline (`GroundingGate`,
  provenance contract) already designed into the retrieval layer.
- **Matches an existing, working pattern** — `context_report.py`'s Anthropic call is a template
  for key-loading, model choice, and error handling; no new integration pattern needs to be
  invented.
- **Naturally multi-surface** — once `answer()` exists as a plain function, exposing it via CLI,
  HTTP, or an agent tool (§3) is three thin wrappers around one core, not three separate builds.
- **Cheap and optional by construction** — `enabled: false` default + circuit breaker means this
  never becomes a hot-path dependency, consistent with CLAUDE.md §4's LLM-tie-breaker doctrine.

### 2.3 Cons / risks

- **Corpus is known-incomplete today** (§1.6) — until include_patterns are fixed and the index
  rebuilt, any answer risks being confidently wrong-by-omission (can't cite CLAUDE.md or
  current-findings.md if they were never indexed). Must ship together, not sequentially, or
  the "grounded answer" claim is false on day one.
- **New external dependency + secret handling** — `ANTHROPIC_API_KEY` must be read the same
  way `context_report.py` does (env var via `_load_dotenv()`), never printed/logged; CLAUDE.md's
  blanket "never read `.env`" rule applies to me as the assistant, not to the runtime code
  itself, but the runtime code must still never leak the key value into logs/JSONL artifacts.
- **Cost and latency per call** — every "ask" becomes a network round-trip to Anthropic;
  needs the same `fail_count_disable`/timeout circuit breaker as the existing
  `llm_inference_client.py` so a flaky network never blocks a caller.
- **No governance coverage yet** — per CLAUDE.md §6.6, shipping this without a finding /
  topic doc / MIAR entry the same turn would itself be a drift violation. The implementation
  turn (not this design turn) needs to register one.
- **Concurrent-session risk** — `git status` shows most of `src/retrieval/` already
  modified-uncommitted, and 4 files (`truth_tier.py`, `divergence.py`, `index_store.py`,
  `lexical.py`) are untracked. Per prior-session memory
  (`feedback_concurrent_claude_sessions.md`), this repo often has other Claude sessions active
  concurrently — an implementation turn must check `git status`/`git stash list` again
  immediately before touching these files, not assume this trace is still current.
- **Second undocumented Anthropic call site** — adds to the architecture-doc gap already noted
  in §1.5; the doc-sync (CLAUDE.md §6.3/§6.4) should update `docs/reference/architecture.md` §5
  to list Claude/Anthropic as an integration, covering both call sites, not just the new one.

### 2.4 How it works, end to end (one query)

```
User/agent query
   │
   ▼
Retriever.retrieve(query)              # existing, live — BM25 over DuckDB/Parquet
   │  → ContextAssembly (truth-tier partitioned HybridResults)
   ▼
GroundingGate.verify(ids in context)   # existing, live — REFUSED ids never pass through
   │  → grounding_status per id
   ▼
format_for_claude(assembly)            # existing, live — Markdown, tier-partitioned
   │
   ▼
[NEW] answer.ask(query, assembly)      # builds system+user messages, calls Anthropic
   │     - fail-open/circuit-breaker if Anthropic unreachable → returns "context only" mode
   ▼
{answer, citations, grounding_status, model, latency_ms}
   │
   ▼
Caller renders answer + citations (CLI prints / HTTP returns JSON / agent tool returns APPROVE-shaped result)
```

### 2.5 How to trigger (phased, all reuse the same core `answer()` function)

1. **CLI** (`scripts/rag_index.py ask "<query>"`) — smallest surface, easiest to test in
   isolation, no server dependency. Natural first cut.
2. **Control-plane HTTP** (`/api/knowledge/ask` next to the existing `/api/knowledge/search`
   and `/api/knowledge/status` in `server.py`/`retrieval_api.py`) — makes it usable from the
   localhost:8787 UI once the CLI proves the core works.
3. **Agent tool** (`src/agent/tool_registry.py` + `PLAN_REGISTRY` entry) — the highest-value
   surface long-term (lets the deterministic agent intent router dispatch a "knowledge
   question" intent here, per `docs/reference/agent-reference.md`'s existing 14-intent/20-tool
   architecture) but touches the most files and should come after 1–2 are proven.
4. **Doctrine dispatch** (CLAUDE.md/AGENTS.md pointer) — per `.grok/PENDING.md:93`, the RAG
   layer currently isn't referenced from either bootloader at all, so no coding LLM (Claude or
   Grok) currently knows to reach for it. Adding a one-line pointer in CLAUDE.md's companion-doc
   table (§2) once a topic doc exists is what would make this self-discoverable in future
   sessions, closing the "dispatch gap, not missing product" diagnosis from the 2026-09-09
   session log.

---

## 3. What this design turn does NOT do

- No code is written or modified this session (per your answer).
- No reindex is triggered (per the repo's own parked P-RAG-01 note — the corpus-coverage fix
  in §1.6 is *planned* here, not executed).
- No finding/MIAR/topic doc is registered yet — that belongs to the implementation turn, filed
  the same turn code ships, per CLAUDE.md §6.6.

## 4. If approved, suggested next-turn scope (not authorized yet — for discussion)

A first implementation turn, if greenlit, would reasonably be scoped to: (a) fix
`RetrievalConfig.include_patterns`/`exclude_patterns` for the missing doctrine paths + rebuild
the index; (b) add `src/retrieval/answer.py` + config section + the CLI `ask` command only
(surface #1); (c) file the governance doc-sync (finding + topic doc) in the same turn. HTTP
endpoint, agent-tool registration, and doctrine dispatch would be explicit follow-up turns, each
re-confirmed before starting given the concurrent-session risk noted in §2.3.
