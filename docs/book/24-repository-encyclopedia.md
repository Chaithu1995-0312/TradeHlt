# Chapter 24 — Repository Encyclopedia

**Part IX — Toward Full Repository Understanding**
Status of this chapter: Written (charter + remaining-file map, Grok pass 2026-08-07)

> **Also known as:** the Repository Encyclopedia plan — how the Canonical Knowledge Book
> (architecture guide) becomes a file-level encyclopedia without treating every unread file as
> equally important.

## Why this chapter exists

The Canonical Knowledge Book (Chapters 00–23 + A1–A2) explains the **production spine and
governance story**. It was never meant to name every Python file. After the coverage report
(`grok/Book_PDF_File_Coverage_Grok.xlsx`), the natural question is:

> *What about the remaining files? Are they dormant? Unimportant? Or just not chaptered yet?*

This chapter answers that. The remaining files fall into **several categories**. They are **not
all equally important**, and the coverage report already hints at that.

## What problem it solves

Gives a durable plan for “100% repository understanding” that:

1. Preserves the book’s architecture spine (do not rewrite it into a flat file dump).
2. Prioritizes **core omissions** over scripts and dormant packages.
3. Defines what a true **Repository Encyclopedia** entry looks like per significant file.

## What you need to already know

- [Chapter 00](00-quick-start.md) — candle → order spine.
- [Chapter 04](04-architecture-at-a-glance.md) — package map + un-chaptered orientation table.
- [Appendix A2](A2-unresolved-questions.md) — open book gaps.
- Coverage spreadsheet: `grok/Book_PDF_File_Coverage_Grok.xlsx` (regenerate via
  `python grok/book_file_coverage_report.py`).

## The idea

### Current book vs encyclopedia

| Mode | What it optimizes for | File coverage style |
|---|---|---|
| **Canonical Knowledge Book** (Ch.00–23) | Architecture, invariants, production path, research discipline | Concepts + load-bearing files; one chapter can explain dozens of files without naming each |
| **Repository Encyclopedia** (this chapter’s target) | Every significant file: purpose, relationships, entry points, relevance | File- or micro-module entries, prioritized by group A→D below |

The book was written around the **architecture**, not around every source file:

```
Feature Pipeline
        ↓
CRT
        ↓
Fusion
        ↓
Decision
        ↓
Execution
        ↓
Risk Gate
```

…instead of listing `file A, file B, file C, …`. That is why only on the order of **~31 `src/`
files are exactly cited** (~7% of the 456-file src inventory), while **loose package orientation**
reaches roughly **60%** of `src/` — the major concepts and production spine, not every helper.

**If the long-term goal is “100% repository understanding”:** treat the current book as roughly
**60–70% of the knowledge** (concept + spine depth), **not** because 60–70% of files were named,
but because the major architectural concepts and production path were captured. The remaining work
is the **implementation surfaces** under those concepts.

---

### 1. Not covered by the book (~403 files)

From the coverage report (exact `NOT_IN_BOOK` rows against the functionality Excels):

| Area | Not in Book |
|---|---:|
| `src/` | **189** |
| `scripts/` | **214** |
| **Total** | **403** |

This does **not** mean they are useless. It only means the book never discussed them as named
files. Many still sit under packages the book *oriented* (DIR_ORIENTED) — research (142 files),
features, agent, engines, runtime — where the chapter explains the system without enumerating every
module.

**Rule:** `NOT_IN_BOOK ≠ dead code`. Code and active config win on “is this live?”

---

### 2. They naturally split into four groups

#### A. Core but omitted (highest priority)

These are the most important omissions: the book explains the architecture but not every
**implementation** file in the spine packages.

| Package | Inventory files | Exact cited | Not in book (exact) | Notes |
|---|---:|---:|---:|---|
| `config_layer/` | 27 | 7 | 20 | CRT helpers, routers, scorers, builders beyond the named few |
| `core/` | 20 | 4 | 16 | Fusion/decision/risk are cited; many orchestration helpers not |
| `control_plane/` | 11 | 2 | 9 | Beyond `registry.py` / `server.py` |
| `execution/` | 5 | 1 | 4 | Beyond `loop.py` (alerts, overrides, …) |
| `engines/` | 13 | 6 | 0* | Most engines *named*; support modules often DIR-only |
| `runtime/` | 10 | 2 | 0* | `backtest_v2` / live hook oriented; internals not file-listed |
| `features/` | 28 | 2 | 0* | Pipeline + schema cited; registry/math surface oriented |

\* “0 not-in-book” can still mean **DIR_ORIENTED** (package mentioned, individual files not deep-read).

**Encyclopedia priority:** future chapters or encyclopedia entries for remaining core
implementation files, engine support, planner helpers, runtime internals.

**Should become:** future book chapters *or* encyclopedia micro-entries under Part IV–V packages.

---

#### B. Sidecar / support modules

These support the system but are not required to understand the trading spine on day one.

Examples from the coverage report (mostly 0 exact cites, full package unread at file level):

| Package | Files | Role |
|---|---:|---|
| `bitnet/` | 23 | Low-bit model surface (inert on active config when disabled) |
| `utils/` | 17 | Shared helpers |
| `retrieval/` | 9 | Retrieval helpers |
| `training/` | 8 | Training pipelines |
| `expansion/` | 6 | Parameter expansion / search |
| `portfolio/` | 6 | Portfolio allocation (built; spine still largely single-candle) |
| `replay/` | 6 | Replay harness support |
| `analytics/` | 5 | Analytics |
| `regime/` | 4 | Regime observers (research-adjacent) |
| `events/` | 2 | Event utilities |
| `search/` | 1 | Search helpers |
| `msip/` | 6 | Shadow market-state (oriented in Ch.18; not spine) |
| `multi_llm/` | 5 | Multi-LLM coordination runtime (Ch.23 orients protocol) |

**Encyclopedia priority:** medium — document when a task touches them; do not block spine literacy.

---

#### C. Dormant / archived

The book intentionally deprioritized these because they are not part of the active production
story (or live only as archive).

| Package | Files | Why deprioritized |
|---|---:|---|
| `strategies/` | 18 | S01–S10 wrappers; mostly scaffold / non-spine |
| `scanner/` | 6 | Sidecar opportunity scanning |
| `journal/` | 6 | Journal path; dormant class |
| `data_ingestion/` | 6 | Alternate ingest surface |
| `llm_research/` | 5 | LLM research experiments |
| `uat/` | 4 | UAT |
| `cognitive/` | 2 | Cognitive bus — sidecar (F-012 class) |
| `feedback/` | 2 | Feedback loop — dormant class |
| `monitoring/` | 2 | Monitoring sidecar |
| `ui/` | 1 | UI remnants |
| `archive/inout_legacy/` | (archived tree) | Parallel execution rail retired 2026-05-02 (Ch.15) |

**Encyclopedia priority:** low — one-line “status: DORMANT / ARCHIVED + replacement path” is enough
unless reopening.

---

#### D. Operational scripts (largest numeric gap)

**214 scripts** are `NOT_IN_BOOK` (of 335 in `scripts_business_functionality.xlsx`). Only ~4
scripts are exactly cited. The book focuses on **what the system is**, not how every utility
script works.

Typical script categories (from the scripts functionality inventory + book intent):

- migrations and repair tools  
- validation utilities  
- report generators  
- governance / census / certification runners  
- one-off research runners (`scripts/research/**`)  
- data preparation and fetch wrappers  
- automation / maintenance  

**Encyclopedia priority:** index by **category + entry point + when to run**, not a narrative
chapter per script. Prefer linking `docs/reference/cli-matrix.md` and
`docs/reference/script-matrix.md` (when present) as the machine index; encyclopedia entries add
purpose and danger notes (write vs read-only).

---

### 3. Why only ~35 files named?

Because the book teaches **flow and purpose**:

| Concept chapter | Explains without listing every file under… |
|---|---|
| Ch.07 Feature pipeline | `src/features/` (28 files) |
| Ch.08 CRT | most of `crt_engine_v2` surface |
| Ch.10 Engines | `src/engines/` (13 files) |
| Ch.11–14 Decision / execution / risk | core spine modules |
| Ch.19–20 Research | `src/research/` (142 files) as a map, not 142 essays |

One chapter can explain the purpose of **dozens** of files without naming each one individually.
That is a feature of an architecture guide — and a **gap** for an encyclopedia.

---

### 4. Target: true Repository Encyclopedia

Transform the knowledge book from an **architecture guide** into a **repository encyclopedia**,
where essentially every significant file has a documented:

| Field | Meaning |
|---|---|
| **Purpose** | Why the file exists (user intent / economic role if any) |
| **Relationships** | Imports / callers / callees (point at `module-roles` / code-map when generated) |
| **Entry points** | CLI, tests, agent tools, control-plane commands |
| **Relevance** | Group A/B/C/D + LIVE / SIDECAR / DORMANT / ARCHIVED |
| **Authority** | Research-only vs production-touching; config keys if any |
| **Coverage** | `CITED` / `DIR_ORIENTED` / `NOT_IN_BOOK` from the coverage report |

**Out of encyclopedia scope (still real files):** pure `__pycache__`, generated binaries, bulk
market CSV/XLSX data dumps, and duplicate archives — index existence only, do not narrate.

#### Recommended build order (priority)

| Phase | Scope | Outcome | Status |
|---|---|---|---|
| **E0** | This charter + coverage Excel | Shared vocabulary A–D | **DONE** |
| **E1** | Group A spine packages (`core`, `config_layer`, `runtime`, `execution`, `engines`, `live`, `inout`, `control_plane`) | File-level purpose map for ~94 modules | **DONE** — [`encyclopedia/E1-spine-implementation.md`](encyclopedia/E1-spine-implementation.md) |
| **E1b** | Deep `src/features/` (pipeline + ontology registry, 28 modules) | Feature math authority map | **DONE** — [`encyclopedia/E1b-features-registry.md`](encyclopedia/E1b-features-registry.md) |
| **E2** | Research utilities under `src/research/` (143) + `scripts/research/` (126) — index, not per-file essays | Research encyclopedia layer | **DONE** — [`encyclopedia/E2-research-utilities.md`](encyclopedia/E2-research-utilities.md) |
| **E3** | Governance tooling (`src/governance/` 19 + `scripts/governance/` 31 + `scripts/analysis/` 115 + maintenance 9) | Ops + truth maintenance tools | **DONE** — [`encyclopedia/E3-governance-tooling.md`](encyclopedia/E3-governance-tooling.md) |
| **E4** | Group B sidecars (~100 files: bitnet, utils, training, portfolio, replay, analytics, expansion, regime, msip, multi_llm, retrieval, …) | Support library map | **DONE** — [`encyclopedia/E4-sidecar-modules.md`](encyclopedia/E4-sidecar-modules.md) |
| **E5** | Group C dormant / archived (~69 `src/` + `archive/**`) | Honest “do not reopen without intent” | **DONE** — [`encyclopedia/E5-dormant-modules.md`](encyclopedia/E5-dormant-modules.md) |
| **E6** | Remaining operator scripts (~70: data/training/context/backtest/export/…) | Operator encyclopedia | **DONE** — [`encyclopedia/E6-remaining-scripts.md`](encyclopedia/E6-remaining-scripts.md) |

**E1 note:** Architecture chapters still own deep narrative for CITED spine modules (EngineRunner, CRT, Fusion, …). E1 fills the **omitted implementation files** so Group A is no longer a blank space on the coverage map.

#### Entry format (proposed template for future encyclopedia rows)

```markdown
### `src/path/to/module.py`
- **Group:** A | B | C | D
- **Relevance:** LIVE | SIDECAR | DORMANT | ARCHIVED
- **Purpose:** …
- **Entry points:** …
- **Related chapters:** …
- **Config keys:** … | none
- **Tests:** …
- **Do not confuse with:** …
```

Machine twin (future, optional): append-only JSONL under `docs/book/encyclopedia/` or a generated
sheet sibling to `Book_PDF_File_Coverage_Grok.xlsx` — **generated from inventory + hand overlays**,
never hand-edited mass dumps as sole truth.

---

### 5. Relationship to existing record systems

This encyclopedia does **not** replace:

| System | Still owns |
|---|---|
| Code | Behavior |
| `docs/topics/` | Always-synced concept dossiers |
| `docs/memory/*` | Edit-time reading order |
| `docs/current-findings.md` | Validated conclusions |
| Functionality Excels | File inventory + summaries |
| Coverage Excel | Book citation status |
| CLI / script matrices | How to run X |

The encyclopedia **joins** them: file → purpose → chapter → tests → run entry.

---

## Classification

| Concept | Status |
|---|---|
| Canonical Knowledge Book (Ch.00–23) | Production architecture guide |
| Remaining-file groups A–D | Charter — **authoritative prioritization for future work** |
| Full prioritized encyclopedia | **E0–E6 + E1b + JSONL DONE** |
| E1 spine implementation map | [`encyclopedia/E1-spine-implementation.md`](encyclopedia/E1-spine-implementation.md) |
| E1b features / registry map | [`encyclopedia/E1b-features-registry.md`](encyclopedia/E1b-features-registry.md) (28 modules) |
| E2 research utilities index | [`encyclopedia/E2-research-utilities.md`](encyclopedia/E2-research-utilities.md) (269 files) |
| E3 governance tooling index | [`encyclopedia/E3-governance-tooling.md`](encyclopedia/E3-governance-tooling.md) (~174 files) |
| E4 sidecar modules map | [`encyclopedia/E4-sidecar-modules.md`](encyclopedia/E4-sidecar-modules.md) (~100 files) |
| E5 dormant / archived map | [`encyclopedia/E5-dormant-modules.md`](encyclopedia/E5-dormant-modules.md) (~69 + archive) |
| E6 remaining operator scripts | [`encyclopedia/E6-remaining-scripts.md`](encyclopedia/E6-remaining-scripts.md) (~70 scripts) |
| Machine JSONL twin | [`encyclopedia/encyclopedia_rows.jsonl`](encyclopedia/encyclopedia_rows.jsonl) (~813 rows; regenerate via `grok/build_encyclopedia_jsonl.py`) |
| Coverage report | Generated tooling (`grok/book_file_coverage_report.py`) |

## Authoritative sources

- `grok/Book_PDF_File_Coverage_Grok.xlsx` — CITED / DIR / NOT_IN_BOOK counts.
- `results/analysis/src_business_functionality.xlsx` — 456 src files.
- `scripts_business_functionality.xlsx` — 335 scripts.
- `docs/book/README.md` — book TOC.
- `docs/architecture/module-roles.generated.md` — one-line roles when regenerated.
- `docs/reference/cli-matrix.md` / script matrix — runnable surfaces.
- [Chapter 04](04-architecture-at-a-glance.md), [Chapter 15](15-live-execution-and-inout.md),
  [A2](A2-unresolved-questions.md).

## Unresolved questions

- Whether encyclopedia entries live only as chapters, as a JSONL registry, or both (recommended:
  hand-written priority entries + generated inventory join).
- Whether Group D should be 100% prose or mostly matrix + danger tags (recommended: matrix-first).
- E1 Group A map is written; optional **E1b** for full `src/features/` file rows remains open.
- **E0–E6 + E1b + JSONL twin complete** (documentation layer).
- **Semantic coverage** is a *different* layer — measured by
  [`REPOSITORY_COVERAGE_DASHBOARD.md`](../governance/REPOSITORY_COVERAGE_DASHBOARD.md)
  (Concept/Boundary/Journey/Contract/Authority/Evidence/…). Encyclopedia alone cannot claim
  “entire codebase covered.”

---
**Previous:** [Chapter 23 — Multi-LLM Coordination](23-multi-llm-coordination.md) · **Next:** [Appendix A1 — Testing](A1-testing.md) (or continue encyclopedia E1)
**Related:** [Chapter 00 — Quick Start](00-quick-start.md) · [Chapter 04 — Architecture at a Glance](04-architecture-at-a-glance.md) · [A2 — Unresolved Questions](A2-unresolved-questions.md)
**Memory:** `docs/memory/architecture-memory.md` before expanding spine package entries.
