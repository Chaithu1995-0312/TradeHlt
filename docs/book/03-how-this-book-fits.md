# Chapter 03 — How This Book Fits the Repository's Knowledge

**Part I — Foundations**
Status of this chapter: Written

## Why this chapter exists

This repository already has more documentation than most codebases have code: ~900 files under
`docs/`, a 300+-file governance ledger, a memory hierarchy, a topics index, findings registries. A
reader could reasonably ask "why does this need a *book* on top of all that?" This chapter answers
that directly, and — because the book borrows vocabulary from those existing systems — defines the
classification labels ("Production", "Experimental", "Research", ...) used in every chapter from
here on, mapped honestly onto the repo's own status vocabulary rather than invented fresh.

## What problem it solves

Without this chapter, a reader bounces between `CLAUDE.md`, `docs/knowledge-map.md`,
`docs/topics/readme.md`, and `docs/memory/README.md` to figure out which of several overlapping
"index" documents to trust for what. This chapter is that decision, made once.

## What you need to already know

[Chapter 1](01-why-tradelatest-exists.md) and [Chapter 2](02-invariants-and-happy-flow.md) — the
substance this book organizes.

## The idea

### The repository already has record systems — this book is a new one, not a replacement

`docs/knowledge-map.md` names nine existing "record systems," each authoritative for a different
question: the SESSION LOG (`assistant_project.md`, "what actually happened, dated"), Plans
(`docs/plans/`, "what was designed"), Analysis (`docs/analysis/`, "point-in-time studies — evidence,
not current truth"), Findings (`docs/current-findings.md`, "current validated conclusions"),
Research families, Codebase structure maps, Topics, a Timeline (the date-join across the others),
and Research substrates (frozen per-instrument datasets). None of these are *sequential* — each
answers one kind of question well, but none walks a reader start-to-finish through the ideas.

**This book is a tenth: the sequencing layer.** It doesn't replace any of the above — it points into
them, in order, the way a textbook points into a language's reference manual without reproducing it.
Concretely: this book cites the SESSION LOG and findings for *what happened and what's proven*,
`docs/topics/` for *the grounded per-concept picture* (code ↔ tests ↔ entry points), and
`docs/memory/` for *the reading order into source* when you're about to edit a subsystem. If you're
about to change code, `docs/memory/` is still the more direct next stop — see below.

### The memory hierarchy still governs when you're about to edit code

`CLAUDE.md` §0 fixes a hierarchy: `CLAUDE.md` → the matching `docs/memory/*-memory.md` companion →
deep companions (`docs/architecture/`, `docs/reference/`) → **source code (always wins)**. This book
sits *alongside* that hierarchy, not above it: reading a book chapter is how you learn what a
subsystem is and why it exists; loading the matching memory doc is still the step you take
immediately before editing that subsystem's code. The six memory docs and the `src/` trees they
route to:

| Memory doc | Routes to | Nearest book chapter |
|---|---|---|
| `agent-memory.md` | `src/agent/` | [Ch.21](21-ai-automation-agent.md) |
| `runtime-memory.md` | `src/runtime/` | [Ch.02](02-invariants-and-happy-flow.md), [Ch.05](05-data-ingestion-no-lookahead.md) |
| `feature-memory.md` | `src/features/` | [Ch.07](07-feature-pipeline.md) |
| `engine-memory.md` | `src/engines/` | [Ch.10](10-four-scoring-engines.md) |
| `governance-memory.md` | `src/governance/`, `config_validator.py` | [Ch.16](16-config-first-and-promotion.md) |
| `architecture-memory.md` | multi-package, full spine | [Ch.02](02-invariants-and-happy-flow.md), [Ch.04](04-architecture-at-a-glance.md) |

### Topics vs. this book

`docs/topics/` (26 files) and this book overlap in subject but not in shape. A topic doc is a
single, continuously-updated concept dossier — code anchor, entry points, tests, status, one file,
kept in sync with code on *every* touching turn (`CLAUDE.md` §6.4). A book chapter is a fixed point
in a narrative sequence — it teaches the concept in the order a new reader needs to encounter it,
and links to the topic doc for the always-current, code-synced detail. Where both exist for the
same concept (e.g. CRT, Fusion+Decision, Execution Planning, Ultron, the Agent), **the topic doc is
the fresher, code-verified source**; this book's chapter is the narrative on-ramp to it.

### The classification vocabulary this book uses

Per the book's own brief, every concept is classified as one of: **Production, Experimental,
Research, Legacy, Deprecated, Partial, Unknown**. The repository doesn't use these exact seven
words — it has its own, more granular status vocabulary, built up across different subsystems. This
book maps onto that vocabulary rather than inventing a parallel one:

| Book label | Repo-native equivalent(s) it draws on |
|---|---|
| **Production** | Wired into the live decision spine; `docs/topics/` status `living`; Closure & Authority Index `CLOSED` (fully proven boundary) |
| **Experimental** | `docs/governance/` closure status `AUDITED` (reviewed, not certified) or `COMPLETE` (a sub-step, not the whole domain); config-gated but not the active default |
| **Research** | Lives under `src/research/`, `docs/research-readiness/`; findings with confidence `Likely`/`Possible`; Authority Ladder tier "information exists" or "economic usefulness exists" but not "authority earned" (§6.5) |
| **Legacy** | `docs/topics/` status `DORMANT` — real code, off the live path, sidecar/inert/orphaned |
| **Deprecated** | Explicitly superseded per a finding's `SUPERSEDED`/`INVALIDATED_BY` marker (CLAUDE.md §6.2 rule 4 — the row is kept, never deleted) |
| **Partial** | Built but unwired (e.g. TradeNet v2, F-005) or `docs/topics/` status `stub` |
| **Unknown** | No finding, topic, or closure artifact covers it — flagged in each chapter's Unresolved Questions, never guessed |

A chapter's "Classification" section always uses this table's left column, so the label means the
same thing everywhere in the book even though the underlying evidence format differs by subsystem.

## Classification

Not applicable — this chapter defines classification rather than applying it.

## Authoritative sources

- `docs/knowledge-map.md` — the nine existing record systems and how they connect (read in full for
  this chapter).
- `docs/memory/README.md` — the memory hierarchy and task→doc routing table.
- `docs/topics/readme.md` — the topic index, its status vocabulary (`living`/`stub`/`DORMANT`), and
  its explicit relationship to the idea-governance "Bricks" framework (kept parallel, not merged, by
  a 2026-06-01 decision).
- `CLAUDE.md` §0 (Architecture Memory Policy), §2 (Companion Documentation table).
- `docs/governance/closure_authority_index.json` and its `CLOSED`/`AUDITED`/`COMPLETE`/`OPEN`
  vocabulary (see [Chapter 17](17-truth-maintenance.md) for the full explanation of that index).

## Unresolved questions

None — this is a navigational chapter over existing, verified index documents.

---
**Previous:** [Chapter 02 — The Invariants and the Happy Flow](02-invariants-and-happy-flow.md) · **Next:** [Chapter 04 — Architecture at a Glance](04-architecture-at-a-glance.md)
**Related:** [Chapter 17 — Truth Maintenance](17-truth-maintenance.md) (the closure/authority vocabulary in full)
**Memory:** `docs/memory/README.md` (this chapter's primary subject).
