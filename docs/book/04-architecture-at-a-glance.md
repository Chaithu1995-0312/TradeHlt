# Chapter 04 — Architecture at a Glance

**Part I — Foundations**
Status of this chapter: Written

## Why this chapter exists

Chapters 1–3 gave the *why* and the *how to navigate*. Before descending into Part II's per-concept
chapters, a reader needs one honest picture of the *shape* of the codebase: how big each piece is,
what depends on what, and where the boundaries are. This chapter is that picture, built from the
repo's own auto-generated architecture artifacts rather than re-derived by hand (so it stays
verifiable against `docs/architecture/code-map.generated.md` and `module-roles.generated.md`
whenever they're regenerated).

## What problem it solves

`src/` alone has 1,400+ files across 36 subpackages. Without a map, "where does this change land?"
is a search problem every time. This chapter turns it into a lookup.

## What you need to already know

[Chapter 2](02-invariants-and-happy-flow.md) — the decision spine this map is organized around.

## The idea

### The repository is not one clean package

At the repo root, alongside the real source tree, sit years of working-repo residue: PDFs, zip
backups, ad-hoc probe scripts, planning artifacts. The load-bearing top-level entries are:

| Directory | Purpose | Approx. size |
|---|---|---|
| `src/` | The application itself | 1,400+ files, 36 subpackages |
| `scripts/` | CLI/operational entry points (thin wrappers over `src/`) | 500+ files, 18 subdirs |
| `docs/` | The knowledge corpus this book sits inside | ~900 files |
| `configs/` | Production/research/experimental config surface | ~65 files |
| `tests/` | Pytest suite, mirrors `src/` structure | ~1,200 files |
| `multi_llm/` | Multi-LLM coordination protocol (see [Ch.23](23-multi-llm-coordination.md)) | ~33 files |
| `data/`, `models/`, `results/` | Market data, trained artifacts, run outputs (mostly generated) | large, non-canonical |
| `CLAUDE.md` | The root AI-agent operating manual | — |
| `assistant_project.md` | The append-only session log — the spine of *history* (see [Ch.03](03-how-this-book-fits.md)) | — |

### The 36 `src/` subpackages

Grouped roughly by the Part of this book that covers them (a subpackage not yet covered by a
written chapter is marked so honestly rather than guessed at):

| Subpackage | Covers | Book chapter |
|---|---|---|
| `features/` | Feature schema/pipeline/formulas | [Ch.07](07-feature-pipeline.md) |
| `config_layer/` | CRT engine, config schema/validation/goal schema, execution planner | [Ch.06](06-market-ontology.md), [Ch.08](08-crt-state-machine.md), [Ch.13](13-execution-planner.md) |
| `engines/` | The four scoring engines | [Ch.10](10-four-scoring-engines.md) |
| `interpreters/` | Pattern interpreter contract (P&F, Wyckoff, ...) | [Ch.09](09-interpreters-pattern-contract.md) |
| `core/` | `EngineRunner`, `FusionEngine`, `DecisionEngine`, `UltronRiskGate`, core protocols | [Ch.11](11-fusion.md), [Ch.12](12-decision-engine.md), [Ch.14](14-ultron-risk-gate.md) |
| `runtime/` | Backtest engine (`backtest_v2.py`), live engine hook | [Ch.05](05-data-ingestion-no-lookahead.md) |
| `inout/`, `live/`, `execution/` | Live path: `inout/` = data fetchers; archived strategy rail under `archive/inout_legacy/` | [Ch.15](15-live-execution-and-inout.md) |
| `governance/` | Promotion, validators, registries, audit trail | [Ch.16](16-config-first-and-promotion.md) |
| `agent/` | AI automation agent (modes, tools, plan compiler) | [Ch.21](21-ai-automation-agent.md) |
| `control_plane/` | Command registry / orchestration | [Ch.22](22-control-plane.md) |
| `multi_llm/` | Multi-LLM coordination runtime | [Ch.23](23-multi-llm-coordination.md) |
| `research/` | Research programs (416 files — the largest subpackage by far) | [Ch.19](19-research-programs.md), [Ch.20](20-research-platform.md) |
| `bitnet/` | Low-bit zone-gate model | [Ch.10](10-four-scoring-engines.md) |
| `training/` | Model training pipelines | [Ch.16](16-config-first-and-promotion.md) (feeds the Training kitchen feeder) |
| `expansion/`, `journal/`, `replay/`, `portfolio/`, `regime/`, `retrieval/`, `strategies/`, `msip/`, `scanner/`, `feedback/`, `cognitive/`, `monitoring/`, `data_ingestion/`, `uat/`, `llm_research/`, `analytics/`, `events/`, `validation_access/`, `search/`, `logs/`, `ui/`, `utils/` | Sidecar / offline / supporting — see orientation table below | Not each given a full chapter; MSIP brief in [Ch.18](18-field-guide-governance.md) |

### Orientation map — packages without a dedicated chapter (Grok review pass)

These packages are **real code**, but they are either off the live decision spine by design
(`DORMANT` / sidecar), research-only, or supporting infrastructure. This table is an orientation
aid, not a claim that each deserves a full chapter tomorrow.

| Package | One-line role | Typical posture |
|---|---|---|
| `msip/` | Shadow Market State Vector + emitters | Research/shadow — brief in [Ch.18](18-field-guide-governance.md) |
| `replay/` | Deterministic replay / harness support | Supporting runtime research |
| `portfolio/` | Portfolio allocation / validation helpers | Built; spine still single-candle (see findings F-013 class) |
| `regime/` | Regime labeling / observers | Research interpreters + diagnostics |
| `strategies/` | S01–S10 strategy modules | Mostly wrapper/scaffold; CRT wrapper is the familiar one |
| `scanner/` | Opportunity / setup scanning | Sidecar; not the live single-candle spine |
| `expansion/` | Bounded parameter expansion / search | Research/ops tooling |
| `cognitive/`, `feedback/`, `journal/` | Sidecar memory / feedback / journal | Explicitly DORMANT or non-spine consumers (F-012 class) |
| `monitoring/`, `analytics/`, `events/` | Telemetry and analysis | Supporting; not decision authority |
| `retrieval/`, `search/`, `llm_research/` | Retrieval / LLM research helpers | Experimental / research |
| `data_ingestion/`, `uat/`, `validation_access/` | Ingest + UAT + validation access | Ops / test surfaces |
| `logs/`, `ui/`, `utils/` | Logging helpers, UI remnants, shared utils | Supporting; some UI under archive |

### The dependency shape, at the top level

`docs/architecture/code-map.generated.md`'s L0 package-dependency graph (auto-regenerated by
`scripts/analysis/gen_code_map.py`) records edges like: `agent → config_layer`, `agent →
control_plane`, `agent → core`, `agent → governance`, `agent → runtime` (the agent depends on
almost everything it can act on, never the reverse); and `bitnet → engines`, `bitnet → features`,
`bitnet → utils` (BitNet is a downstream consumer of the engine/feature layer, not upstream of it —
this matters when reading [Chapter 10](10-four-scoring-engines.md)'s account of the Zone Gate
engine). The full 35-package graph is larger than is useful to reproduce here; treat this chapter's
excerpt as an orientation and the generated file as the source of truth, since it's regenerated
directly from imports rather than hand-maintained.

### Two companion generated docs worth knowing about

- `docs/architecture/module-roles.generated.md` — a one-line role per `src/` module, sourced from
  each module's own docstring. Useful as a fast "what does this file do" lookup when a chapter's
  "Authoritative sources" list points you at an unfamiliar path.
- `docs/reference/architecture.md` — a more traditional onboarding doc (tech stack with versions,
  directory structure, data-flow diagrams for the backtest/live/governance/agent paths, design
  patterns, external integrations, `.env`/config overview, execution entry points). This book does
  not reproduce that doc's content — treat it as the reference companion to this chapter's narrative
  framing.

## Classification

| Concept | Status |
|---|---|
| `src/` 36-package structure | Production (the whole tree ships) |
| `research/` (416 files) | Mixed — see [Ch.19](19-research-programs.md)/[Ch.20](20-research-platform.md) |
| The 9 subpackages marked `DORMANT` above | Legacy |
| Generated architecture docs (`code-map`, `module-roles`) | Production tooling, regenerate-don't-hand-edit |

## Authoritative sources

- `docs/reference/architecture.md` — tech stack, directory tree, data-flow diagrams, design
  patterns, config overview, entry points (headers verified this session; full content not
  reproduced here by design — see [Ch.03](03-how-this-book-fits.md)'s anti-duplication policy).
- `docs/architecture/code-map.generated.md` — the authoritative import graph (regenerate via
  `python scripts/analysis/gen_code_map.py`).
- `docs/architecture/module-roles.generated.md` — per-module one-line roles.
- `docs/topics/readme.md` — the `DORMANT` subsystem table.

## Unresolved questions

- The 22 subpackages in the "not yet individually chaptered" row above are real, verified to exist,
  but this pass didn't have room to give each its own chapter. Tracked in [A2](A2-unresolved-questions.md).
- `docs/reference/architecture.md`'s full body (design patterns, external integrations, entry
  points) was header-verified but not read in full this session — a future pass should confirm this
  chapter's summary against the full text.

---
**Previous:** [Chapter 03 — How This Book Fits](03-how-this-book-fits.md) · **Next:** [Chapter 05 — Data Ingestion and the No-Lookahead Discipline](05-data-ingestion-no-lookahead.md)
**Related:** [Chapter 02 — The Invariants and the Happy Flow](02-invariants-and-happy-flow.md)
**Memory:** `docs/memory/architecture-memory.md` (deep companion for full cross-package detail).
