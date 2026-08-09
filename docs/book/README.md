# The Tradelatest Book

> **What this is.** A cover-to-cover reconstruction of this repository as a sequence of ideas,
> not a pile of files. Read it in order and you should understand *why* Tradelatest exists, *how*
> a candle becomes (or doesn't become) an order, and *where* every governance, research, and agent
> layer sits around that spine — without jumping between 900 documents to assemble the picture
> yourself.
>
> **What this is not.** A replacement for the code, for `CLAUDE.md`, or for the existing reference
> docs (`docs/reference/`), memory docs (`docs/memory/`), or topic docs (`docs/topics/`). This book
> is a *map*. Every chapter ends with the file paths that are the real, authoritative source — when
> the book and the code disagree, **the code wins** (per `CLAUDE.md` §0's hierarchy, which this book
> inherits). See [Chapter 3](03-how-this-book-fits.md) for exactly how the book relates to those
> other record systems.
>
> **Living document.** New chapters are added and existing ones are deepened over time; chapter
> numbers never change once assigned, so links stay stable. See "How this book evolves" below.

---

## How to read this

- **Just need the mechanics?** Start at [Chapter 00 — Quick Start](00-quick-start.md) (one candle's
  journey, load-bearing surfaces, known defects) — then jump to deeper chapters as needed.
- **New to the repo (full narrative)?** Start at Chapter 1 and read straight through Part V
  (chapters 01–15). That is the complete, coherent story of one candle's journey from raw OHLCV to
  an approved (or rejected) order — the spine everything else in the repo hangs off.
- **Already know the spine, need one layer?** Jump straight to the Part that covers it (table
  below) — each chapter is self-contained given the "What you need to already know" prerequisites
  it lists.
- **Looking for a specific concept** (CRT, Fusion, Ultron, Promotion, ...)? Use the Concept Index
  at the bottom of this file — it points to the *one* chapter that owns that concept's explanation,
  per the book's Canonical Concept Rule.

### Grok review pass (2026-08-07)

A structured review of the first PDF export drove narrative fixes **in this book only** (no trading
system code changes): Quick Start; INOUT resolution; Program 9 coverage; ATR/F-057 proposed
remediations; Measurement Contract path; MSIP brief; un-chaptered package map; A2 rollup update.
Reading PDFs with `Grok` in the filename under `grok/` are regenerated from this tree.

---

## Table of Contents

### Part I — Foundations
Why the system exists, what must never break, and how to navigate everything else.

| # | Chapter | Status |
|---|---|---|
| 00 | [Quick Start — One Candle's Journey](00-quick-start.md) | Written (Grok review) |
| 01 | [Why Tradelatest Exists](01-why-tradelatest-exists.md) | Written |
| 02 | [The Invariants and the Happy Flow](02-invariants-and-happy-flow.md) | Written |
| 03 | [How This Book Fits the Repository's Knowledge](03-how-this-book-fits.md) | Written |
| 04 | [Architecture at a Glance](04-architecture-at-a-glance.md) | Written |

### Part II — Market Understanding
Turning raw candles into a trustworthy, meaningful numeric surface.

| # | Chapter | Status |
|---|---|---|
| 05 | [Data Ingestion and the No-Lookahead Discipline](05-data-ingestion-no-lookahead.md) | Written |
| 06 | [The Market Ontology — Canonical Semantic Authority](06-market-ontology.md) | Written |
| 07 | [The Feature Pipeline and the Canonical Vector](07-feature-pipeline.md) | Written |

### Part III — Market Semantics
Giving the numeric surface structure: states, transitions, and patterns.

| # | Chapter | Status |
|---|---|---|
| 08 | [The CRT State Machine — the Spine](08-crt-state-machine.md) | Written |
| 09 | [Interpreters and the Pattern Contract](09-interpreters-pattern-contract.md) | Written |

### Part IV — Decision Making
Turning structure into a single execute/reject decision.

| # | Chapter | Status |
|---|---|---|
| 10 | [The Four Scoring Engines](10-four-scoring-engines.md) | Written |
| 11 | [Fusion — Combining Independent Signals](11-fusion.md) | Written |
| 12 | [The Decision Engine — Semantic Approval Only](12-decision-engine.md) | Written |

### Part V — Execution
Turning a decision into order geometry, and geometry into a capital-safe order.

| # | Chapter | Status |
|---|---|---|
| 13 | [The Execution Planner — From Decision to Order Geometry](13-execution-planner.md) | Written |
| 14 | [Ultron Risk Gate — the Final Capital Check](14-ultron-risk-gate.md) | Written |
| 15 | [Live Execution and INOUT](15-live-execution-and-inout.md) | Written |

### Part VI — Governance
How a config earns the right to run in production, and how the repo keeps its own truth honest.

| # | Chapter | Status |
|---|---|---|
| 16 | [Config-First Doctrine and the Promotion Path](16-config-first-and-promotion.md) | Written |
| 17 | [Truth Maintenance — Findings, Closure, and Authority](17-truth-maintenance.md) | Written |
| 18 | [A Field Guide to docs/governance/](18-field-guide-governance.md) | Orientation-level |

### Part VII — Research
How the repo tries — and mostly fails, on purpose and by design — to find a tradeable edge.
**Numeric program results live in Chapter 19's data table** (not only narrative). Platform paths and
artifact roots are in Chapter 20. PDF readers: use the bookmarks for "Chapter 19" / "Chapter 20",
or open `grok/Tradelatest-Canonical-Knowledge-Book-Research-Grok.pdf`.

| # | Chapter | Status |
|---|---|---|
| 19 | [The Research Programs — Falsification as a Discipline](19-research-programs.md) | Written (results table) |
| 20 | [The Research Platform — src/research/](20-research-platform.md) | Written (data map) |

### Part VIII — Agent Intelligence
The layers that let an LLM (or a human) operate the system through natural language.

| # | Chapter | Status |
|---|---|---|
| 21 | [The AI Automation Agent](21-ai-automation-agent.md) | Orientation-level |
| 22 | [The Control Plane](22-control-plane.md) | Orientation-level |
| 23 | [Multi-LLM Coordination](23-multi-llm-coordination.md) | Orientation-level |

### Part IX — Toward Full Repository Understanding
From architecture guide toward file-level coverage of the remaining surfaces.

| # | Chapter | Status |
|---|---|---|
| 24 | [Repository Encyclopedia](24-repository-encyclopedia.md) | Written (charter + remaining-file map) |
| E1 | [Encyclopedia E1 — Spine Implementation](encyclopedia/E1-spine-implementation.md) | **DONE** (Group A file map) |
| E1b | [Encyclopedia E1b — Features & Registry](encyclopedia/E1b-features-registry.md) | **DONE** (28 feature modules) |
| JSONL | [encyclopedia_rows.jsonl](encyclopedia/encyclopedia_rows.jsonl) | **GENERATED** (~813 rows) |
| Coverage | [REPOSITORY_COVERAGE_DASHBOARD.md](../governance/REPOSITORY_COVERAGE_DASHBOARD.md) | **Semantic coverage scores (NOT_YET)** |
| E2 | [Encyclopedia E2 — Research Utilities](encyclopedia/E2-research-utilities.md) | **DONE** (program/driver/package index) |
| E3 | [Encyclopedia E3 — Governance Tooling](encyclopedia/E3-governance-tooling.md) | **DONE** (promote/registry/DAG/analysis index) |
| E4 | [Encyclopedia E4 — Sidecar Modules](encyclopedia/E4-sidecar-modules.md) | **DONE** (Group B support packages) |
| E5 | [Encyclopedia E5 — Dormant / Archived](encyclopedia/E5-dormant-modules.md) | **DONE** (Group C + archive) |
| E6 | [Encyclopedia E6 — Remaining Scripts](encyclopedia/E6-remaining-scripts.md) | **DONE** (operator residual ~70) |

### Appendix

| # | Chapter | Status |
|---|---|---|
| A1 | [Testing the System](A1-testing.md) | Written |
| A2 | [Unresolved Questions (rollup)](A2-unresolved-questions.md) | Written (Grok review update) |

---

## Concept Index (Canonical Concept Rule)

Each concept below has exactly one chapter that owns its explanation. Other chapters that touch it
link back here instead of re-explaining it.

| Concept | Canonical chapter |
|---|---|
| Quick Start / spine sketch | [Ch.00](00-quick-start.md) |
| Market Ontology | [Ch.06](06-market-ontology.md) |
| Feature Pipeline / `CANONICAL_FEATURES` | [Ch.07](07-feature-pipeline.md) |
| CRT (state machine) | [Ch.08](08-crt-state-machine.md) |
| Gaussian / Zone Gate / RR engines | [Ch.10](10-four-scoring-engines.md) |
| Fusion | [Ch.11](11-fusion.md) |
| Decision Engine | [Ch.12](12-decision-engine.md) |
| Execution Planner (`ExecutionPlannerV1_2`) | [Ch.13](13-execution-planner.md) |
| Ultron Risk Gate | [Ch.14](14-ultron-risk-gate.md) |
| Promotion / `PromotionManager` | [Ch.16](16-config-first-and-promotion.md) |
| Config Validation / `ConfigValidator` | [Ch.16](16-config-first-and-promotion.md) |
| Findings / Closure / Authority Ladder | [Ch.17](17-truth-maintenance.md) |
| Control Plane / `CommandSpec` | [Ch.22](22-control-plane.md) |
| AI Automation Agent / `PLAN_REGISTRY` | [Ch.21](21-ai-automation-agent.md) |
| Multi-LLM Protocol | [Ch.23](23-multi-llm-coordination.md) |
| Program 9 (M5 non-directional) | [Ch.19](19-research-programs.md) |
| MSIP (shadow market state) | [Ch.18](18-field-guide-governance.md) |
| Repository Encyclopedia (remaining files A–D) | [Ch.24](24-repository-encyclopedia.md) |

---

## How this book evolves

Per the book's own charter: when the repository changes, **only the affected chapter is updated**
— chapter numbers and links are permanent. If a new concept needs a canonical home, it gets a new
chapter number appended at the end of its Part's range (never a renumber). Governance/Research/
Agent Intelligence chapters (16–23) are marked "Orientation-level" — they are accurate but
deliberately not exhaustive over their much larger source corpora (~250 files in `docs/governance/`,
~475 files across `src/research/` + `docs/research-readiness/`); deepening them is future book work,
tracked in [A2](A2-unresolved-questions.md).

**Source of truth:** this book is generated understanding, not authority. On any conflict between
a chapter and the code/config it describes, the code/config wins — see `CLAUDE.md` §0 and §4.0 for
the repo's own precedence rules, which this book does not override.
