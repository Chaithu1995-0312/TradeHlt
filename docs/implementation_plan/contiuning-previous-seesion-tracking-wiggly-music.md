# Refresh the Topic Atlas with T17 — RAG / retrieval

## Context

The Topic Atlas is the running register of this codebase's workflow map: every file
assigned to one owning topic, with two metrics tracked separately (ownership = disjoint
partition; footprint = blast radius). Five topics are mapped (T1–T5), eleven more are
listed as unmapped backlog (T6–T16).

This session mapped a sixth topic — the RAG / retrieval subsystem — and found it was
**absent from the register entirely**: not among the five mapped, not among the eleven
backlog clusters. So the previously reported coverage figures (3.2% ownership / 24.7%
footprint) had an unmeasured hole.

The live atlas file lives in the **previous session's** scratchpad and cannot be updated
from here. This plan writes a refreshed copy into this session's scratchpad, carrying
forward all existing content and folding in T17.

Nothing is published. Nothing in the repo is modified. Read-only measurement only.

## What was measured (already complete — no further research needed)

All figures below were verified read-only at HEAD `c782803` this session.

**T17 owned = 15**, all tracked:
- `src/retrieval/` ×9 — `__init__`, `chunking`, `claude_integration`, `config`, `corpus`,
  `embedding`, `monitor`, `retriever`, `vector_store`
- `scripts/rag_index.py`
- `scripts/evaluation/` ×4 — `__init__.py`, `report.py`, `run_benchmark.py`, `benchmark_100.json`
- `tests/test_retrieval_pipeline.py`

**T17 footprint = 15.** Owned equals footprint — the first closed island in the register.
Zero external consumers: no file outside those 15 imports `retrieval`
(the single `src/control_plane/registry.py` grep hit is the substring in "cove**rag**e").
No `PLAN_REGISTRY` entry, no control-plane command, not on the spine.

**Register arithmetic:**
- Ownership: 12+16+7+10+8+**15** = **68** / 1,665 = **4.1%**. Union 68, overlap 0 — still disjoint.
- Footprint: union 411 + 15 = **426** / 1,665 = **25.6%** (provisional — see below).
- Referenced-only stays **358**; untouched drops 1,254 → **1,239**.
- Footprint raw sum 525 + 15 = 540 vs union 426 → 114 shared, unchanged.

**Provisional caveat to record:** the atlas stores counts, not file lists, so it cannot be
proven that none of T17's 15 files already sat inside the 411. Flag as provisional.

**Source-verified defects (this session, at file:line):**
- Keyword + structural hybrid arms are process-memory only — `vector_store.py:61` is a plain
  dict, rebuilt only inside `persist()` at `:123`. Cold start ⇒ hybrid ≡ semantic-only.
- `--incremental` is a literal alias for `--rebuild` — `rag_index.py:66-70`, comment admits it.
- `chromadb` / `sentence-transformers` undeclared — `pyproject.toml` extras are `hummingbot`,
  `parquet`, `charts`, `live_rail`, `mt5_analytics`. No `rag` extra.
- Neither `venv` nor `.venv` has either dep ⇒ subsystem unrunnable in this clone; the 633 MB
  `data/chroma_db` index (built Jul 27, gitignored via `/data/*`) cannot be opened.
- Not in `GREEN_FLOOR` (31 targets, zero retrieval). `test_retrieval_pipeline.py` collects 17
  tests; 8 exercise `Embedder`/`VectorStore` and would error on the missing deps.
- SITS: `SCR-221 rag_index.py` = `ORPHAN` / `GRANDFATHER_UNCLASSIFIED`; `SCR-165/166/167`
  (evaluation) = `RESEARCH_RUNNER` / `GRANDFATHER_UNCLASSIFIED`.
- Config is a Python dataclass + `RAG_*` env overrides (`config.py:103-110`), zero presence in
  `configs/production/*` ⇒ `HARD_CODED` on the §6.5 ladder.

**Corpus gap (the sharpest finding).** `config.py:65-85` indexes ~1,449 tracked files across
9 domains — `src/**/*.py` (512), `tests/**/*.py` (430), `configs/**` (69), and four
*non-recursive* `docs/` subtrees. It does **not** index the documents CLAUDE.md §0 designates
as the memory hierarchy: `CLAUDE.md`, `README.md`, `active_models.yaml`, `assistant_project.md`,
`docs/current-findings.md`, `docs/knowledge-map.md`, `docs/timeline.md`, `docs/memory/` (8),
`docs/topics/` (29), `docs/reference/` (15), `docs/book/` (36), `docs/design/` (17),
`docs/implementation_plan/` (195), `scripts/` (428), `multi_llm/` (57), `tools/` (20).

## Prior art honoured

An existing OBSERVATION_ONLY review of this subsystem sits at
`docs/analysis/session-log-archive/session-log-2026-07-23_to_2026-08-02.md:71`. Its claims were
re-verified at source rather than restated (§1.1). Four confirmed, three facts are new to this
session (unrunnable / ungated / unregistered), and the corpus-exclusion list extends further
than the review recorded (it missed `docs/book/`, `docs/memory/`, `scripts/`, `multi_llm/`).

## The single file to write

`C:\Users\Hi\AppData\Local\Temp\claude\D--Tradelatest\52bcfdcd-ad63-4054-9947-62bdb396f4e7\scratchpad\artifact_topic_atlas.html`

Copy the existing atlas verbatim — same CSS token set, three-tab structure, tab-persistence
script, table markup — and apply these edits only:

1. **Header** — ownership `3.2% / 53` → `4.1% / 68`; footprint `24.7% / 411` → `25.6% / 426`.
2. **Meter + legend** — widths `4.1% / 21.5% / 74.4%`; legend `owned · 68`,
   `referenced only · 358`, `untouched · 1,239`; update the `aria-label`.
3. **Mapped topics table** — append T17 row (`src/retrieval/`, own 15 / 0.9%, foot 15 / 0.9%);
   update `tfoot` union to 68 / 4.1% / 426 / 25.6%.
4. **Disjoint flag** — raw sum `12+16+7+10+8+15 = 68`, union 68, overlap 0; footprint sum
   540 vs union 426.
5. **New flag (good)** — closed island: owned == footprint, zero inbound consumers; this is
   why referenced-only did not move.
6. **New flag (warn)** — footprint 426 is provisional; the register stores counts, not file
   lists, so the 15 cannot be proven absent from the prior 411.
7. **Unmapped backlog** — add a note that `src/retrieval` appeared in none of the eleven
   clusters, which is why it takes the next free id (T17) rather than slotting into T6–T16.
8. **Cross-layer log** — two new rows:
   - *RAG index cannot see the memory hierarchy* (verified) — the exclusion list above.
   - *A whole subsystem was missing from the register* (verified) — methodology note: the
     backlog was built from top-level package clusters, and `src/retrieval` was skipped by
     both passes; T14 was mislabelled here first before the backlog table was read.
9. **Backlog / Yet to fix** — four new rows:
   - `Y7` RAG deps undeclared in `pyproject` and absent from both venvs → unrunnable; 633 MB
     index unreadable.
   - `Y8` RAG corpus globs miss the §0 memory hierarchy → extend `domain_patterns`.
   - `Y9` RAG ungated — not in `GREEN_FLOOR`; SITS marks `rag_index.py` `ORPHAN`.
   - `Y10` RAG config `HARD_CODED` (dataclass + `RAG_*` env vars, zero `configs/` presence),
     §6.5 ladder violation.
10. **Nav counts** — Coverage `6`, Cross-Layer `9`, Backlog `11`.
11. **Footer** — keep HEAD `c782803`, keep "nothing committed".

## Constraints held throughout

- No agent/subagent runs (user hard constraint) — all measurement was done inline.
- No publishing. The file is written to the scratchpad only; no Artifact call.
- No repository file is created, edited, or committed.
- The §6 SESSION LOG entry is **shown in the response but not persisted** to
  `assistant_project.md`, because that write is out of scope for this turn; the response
  states this explicitly rather than implying the mandate was met.

## Verification

1. Open the written file and confirm the three tabs render and switch (tab state persists
   via `localStorage`).
2. Check the arithmetic renders consistently: header 68 / 426, `tfoot` 68 / 426, meter legend
   68 + 358 + 1,239 = 1,665.
3. Confirm the T17 row and all four new Y rows are present, and nav counts read 6 / 9 / 11.
4. Confirm no repo file changed: `git status --porcelain` output identical to session start.
