# Canonical Knowledge Book — Build Plan

## Context

Tradelatest has grown into ~900 doc files and ~1,400 source files across years of experimentation,
research, refactors, and governance work. The knowledge is real but fragmented: `docs/knowledge-map.md`
is already a "map of maps" (which record system answers which question), `docs/topics/` holds 26
one-concept files, `docs/memory/` routes by subsystem, and `docs/architecture/goal.md` is a
near-complete "why this exists" chapter — but nothing sequences these into a single narrative a reader
can walk start-to-finish. The user's ask is exactly that: reconstruct the repository into a **coherent
sequence of ideas** — a book — not a new pile of documentation.

Three Explore passes (repo-wide structure, core pipeline, governance/research/agent layers) confirmed:
**no `docs/book/` or table-of-contents exists yet.** The book is new construction, not a rewrite. The
plan below designs its structure and scopes what gets written in this first pass, consistent with the
repo's own doctrine (CLAUDE.md §6.2 rule 1 "existing-doc-first", §6.2 rule 5 "minimize doc count", the
"Canonical Concept Rule" in the task prompt): **the book teaches and sequences; it does not duplicate**.
Every chapter ends by pointing at the doc/code that actually owns the detail.

## Design decisions

**Location & naming.** New directory `docs/book/`, following the existing `docs/topics/` /
`docs/architecture/` convention (flat files + one index). `docs/book/README.md` is the master
Table of Contents (Parts → chapters, one-line description, status). Chapters are flat files
`docs/book/NN-slug.md` with a global two-digit number (not per-part numbering) so cross-references
stay stable as the book grows — matches the "Living Book" requirement to never renumber.

**Chapter template** (every chapter uses this shape, per the task's Chapter Rules + Cross References
sections):
```
# Chapter NN — Title
Part: <Roman numeral — Part name>
Status of this chapter: <Written | Orientation-level | Planned>

## Why this chapter exists
## What problem it solves
## What you need to already know   (links to earlier chapters)
## The idea                         (the actual teaching content — narrative prose, not API dump)
## Classification                   (Production / Experimental / Research / Legacy / Deprecated / Partial / Unknown — per concept covered)
## Authoritative sources            (source files, config keys, tests — book is a map, code wins)
## Unresolved questions             (only if any — never invented)
## Previous · Next · Related chapters · Relevant memory docs
```

**Canonical Concept Rule enforcement.** Each concept (CRT, Fusion, Decision Engine, Feature Pipeline,
Governance, Promotion, Control Plane, Market Ontology, Execution Planner, Ultron Risk Gate, etc.) gets
exactly one chapter that owns its explanation. Later chapters that touch the same concept link back
instead of re-explaining (e.g., Ch.16 Governance references Ch.06's ontology explanation rather than
re-describing it).

**Source-of-truth discipline.** Every claim in the book traces to a real file:line or doc already
verified by the three Explore passes this session (signal-flow.md's 7-step walk, goal.md's invariants,
the engine/fusion/decision/execution/risk file paths, the governance/research/agent directory maps).
Nothing is invented; anywhere evidence was thin, the chapter gets an explicit "Unresolved Questions"
section instead of a guess (per the task's "Missing Knowledge" rule).

**Known doc-drift to surface, not silently fix.** The feature-pipeline chapter (Ch.07) must flag that
`docs/reference/schemas.md` still documents the 38-dim v3.0 tuple while `src/features/feature_schema.py`
is live at 39-dim v4.0 (`CANONICAL_FEATURE_DIM = 39`, F-062 already fixed the code side, the reference
doc appears to lag). Per CLAUDE.md §6.2 this is a `DOC_DRIFT` classification — the book chapter notes it
and points at the authoritative code constant; it does **not** silently patch `schemas.md` as a side
effect of book-writing (that's a separate, explicit doc-drift turn if the user wants it done).

## Scope of this pass

Full 23-chapter skeleton is designed now (all Parts get a README.md entry so the book's shape is
honest and complete), but chapters are written at different depths matched to how well-evidenced they
are, consistent with "Living Book" (later passes deepen without renumbering):

- **Parts I–V (chapters 01–15, the core candle→order spine)** — written in full. This is the
  best-evidenced material: `goal.md`, `signal-flow.md`'s 7-step walk (with failure modes / cross-refs
  already extracted), and verified file paths for ontology → features → CRT → four engines → fusion →
  decision → execution planner → risk gate → live/INOUT.
- **Parts VI–VIII (chapters 16–23, Governance / Research / Agent Intelligence)** — written as solid
  **orientation chapters**: enough narrative to understand what the layer is for, how it's organized,
  and its classification status, with clear pointers into the deep corpus (`docs/reference/governance.md`,
  `docs/current-findings.md` Funding Ledger, `docs/reference/agent-reference.md`) rather than attempting
  to compress ~250 governance files and ~60 research-readiness files into prose. This matches the task's
  own instruction to classify rather than exhaustively narrate ungrounded material.
- **Appendix (A1 Testing, A2 Unresolved Questions rollup)** — short, pointer-style.

## Chapter list (final)

**Part I — Foundations**
01. Why Tradelatest Exists — `docs/architecture/goal.md` §1
02. The Invariants and the Happy Flow — `goal.md` §2–4, `docs/architecture/signal-flow.md`
03. How This Book Fits the Repository's Knowledge — `docs/knowledge-map.md`, `docs/memory/README.md`, `docs/topics/readme.md`, CLAUDE.md §0/§2 (meta chapter; also defines the classification vocabulary used throughout)
04. Architecture at a Glance — `docs/reference/architecture.md`, `docs/architecture/code-map.generated.md` (L0 graph), `module-roles.generated.md`

**Part II — Market Understanding**
05. Data Ingestion and the No-Lookahead Discipline — signal-flow.md Step 1, L1/L2/L3 integrity stack, F-039
06. The Market Ontology — Canonical Semantic Authority — `configs/formulas/market_ontology.yaml`, `MARKET_ONTOLOGY_EVOLUTION_CONTRACT.md`, F-047, CLAUDE.md §6.6
07. The Feature Pipeline and the Canonical Vector — `src/features/feature_pipeline.py`, `feature_schema.py` (39-dim v4.0; flags the schemas.md drift)

**Part III — Market Semantics**
08. The CRT State Machine — the Spine — `src/config_layer/crt_engine_v2.py`, `event-taxonomy.md`; status CLOSED (`crt_closure_report.md`)
09. Interpreters and the Pattern Contract — `src/interpreters/`, Interpreter Contract topic; status Research/Partial (P&F etc. measured, never asserted)

**Part IV — Decision Making**
10. The Four Scoring Engines — CRT-score / Gaussian / Zone Gate / RR, `src/engines/*`; statuses AUDITED (F-036, F-041B, F-038/044/045/059, F-060)
11. Fusion — Combining Independent Signals — `src/core/fusion_engine.py`
12. The Decision Engine — Semantic Approval Only — `src/core/decision_engine.py`, F-048 (RR-gate removal, ownership split with Ultron)

**Part V — Execution**
13. The Execution Planner — From Decision to Order Geometry — `src/config_layer/execution_planner.py` (`ExecutionPlannerV1_2`), F-057 caveat
14. Ultron Risk Gate — the Final Capital Check — `src/core/ultron_risk_gate.py`
15. Live Execution and INOUT — `src/inout/`, `src/live/`; status: INOUT currently archived per `goal.md`

**Part VI — Governance**
16. Config-First Doctrine and the Promotion Path — CLAUDE.md §6.5, `docs/reference/governance.md`, `src/governance/promotion_manager.py`
17. Truth Maintenance — Findings, Closure, and Authority — CLAUDE.md §6.2, `current-findings.md`, `closure_authority_index.json`, `EPISTEMIC_INTEGRITY.md`
18. A Field Guide to `docs/governance/` — orientation over the ~250-file certification ledger, grouped by theme (promotion, closure, lineage audits, ontology contracts, feature-DAG, CRT, OHLCV corpus, MSIP) with pointers, not exhaustive listing

**Part VII — Research**
19. The Research Programs — Falsification as a Discipline — Funding Ledger Programs 1–9 in `current-findings.md`, the Authority Ladder (CLAUDE.md §6.5)
20. The Research Platform — `src/research/` (17 subpackages) and the Edge Research Platform docs, `docs/research-readiness/`

**Part VIII — Agent Intelligence**
21. The AI Automation Agent — `docs/reference/agent-reference.md`, `src/agent/` (modes, tool_registry, `PLAN_REGISTRY` in `plan_compiler.py`)
22. The Control Plane — `src/control_plane/registry.py` (`CommandSpec` catalog), `docs/reference/control-plane.md`
23. Multi-LLM Coordination — CLAUDE.md §13, `multi_llm/MULTI_LLM_PROTOCOL.md`, `multi_llm/roles/`

**Appendix**
A1. Testing the System — `docs/reference/testing.md`
A2. Unresolved Questions (rollup) — collects every chapter's open items in one place

## Execution notes (for the implementation turn)

- Write `docs/book/README.md` first (full TOC with status column), then chapters in order 01→23,
  A1, A2 — each chapter is a small Write, so this is naturally incremental and resumable.
- This repo's CLAUDE.md mandates a `📝 SESSION LOG ENTRY` appended to `assistant_project.md` on every
  response during execution, and the Documentation Drift Protocol applies if any doc-drift is fixed
  (not just flagged) along the way — follow both during implementation, not just at the end.
- After the book exists, propose (don't silently do) one small follow-up: add a `docs/book/README.md`
  row to CLAUDE.md §2's Companion Documentation table so future sessions discover it — this is a
  one-line addition, flagged separately since CLAUDE.md itself is governed content.
- Do not touch `docs/reference/schemas.md`'s 38-dim text as part of this task — flag it in Ch.07 only;
  fixing it is a separate, explicit doc-drift turn.

## Verification

- Every chapter's "Authoritative sources" section resolves (files/paths exist) — spot-check a sample
  with `Read`/`Glob` after writing.
- `docs/book/README.md` links to all 23 chapters + 2 appendix files with no dead links.
- Skim-read Part I→V end-to-end to confirm it reads as one continuous narrative (the book's own success
  criterion) rather than 15 disconnected summaries.
