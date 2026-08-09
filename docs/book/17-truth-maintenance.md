# Chapter 17 — Truth Maintenance: Findings, Closure, and Authority

**Part VI — Governance**
Status of this chapter: Written

## Why this chapter exists

This chapter explains the machinery behind a vocabulary this book has already used in nearly every
chapter — "AUDITED," "CLOSED," confidence levels, `F-0xx` finding IDs. Rather than define these
piecemeal, this is their one canonical home: how the repository decides what it believes, how
confident it is, and how it prevents a claim from quietly rotting into a false one.

## What problem it solves

A repository this size, worked on across years by multiple humans and multiple LLMs, faces a
specific failure mode: the same fact stated three different ways in three different docs, one of
which is now wrong, with no way to tell which. This chapter covers the doctrine built specifically
to prevent that — "silent truth divergence."

## What you need to already know

[Chapter 3](03-how-this-book-fits.md) — this chapter fills in the classification vocabulary that
chapter promised to explain in full.

## The idea

### The seven rules

The Repository Truth Maintenance Doctrine (`CLAUDE.md` §6.2) states seven rules, worth knowing as a
set because they compound: (1) find the doc that already owns a topic before creating a new one; (2)
classify every claim as `ALIGNED`, `DOC_DRIFT` (code wins, fix the doc), `CODE_DRIFT` (doc wins, fix
the code), or `AMBIGUOUS`; (3) never silently resolve an `AMBIGUOUS` conflict — surface it and ask;
(4) never delete disproven history — mark it `SUPERSEDED`/`INVALIDATED_BY` and keep the row; (5)
minimize doc count; (6) synchronize related artifacts rather than editing in isolation; (7) state
truth per-branch, never globally. [Chapter 7](07-feature-pipeline.md)'s 38-vs-39-dim finding is a
live, worked example of rule 2 in action — this book classified it and flagged it rather than
silently patching it, per rule 3's caution and this chapter's own scope discipline.

### Findings: the unit of validated belief

`docs/current-findings.md` is where a validated or overturned conclusion gets recorded, the same
turn it's discovered. Every finding carries a confidence level — `Certain`, `Likely`, or `Possible`
— and cites its evidence. Findings are never deleted, only marked `SUPERSEDED` or `RETIRED` with the
row kept intact, so the repository's history of what it *used* to believe stays legible even after
that belief changes. This book's own chapters cite specific findings (F-005, F-028, F-036, F-038,
F-039, F-041B, F-044, F-048, F-057, F-060, F-062, and others) exactly this way — as evidence, with
the confidence and scope the finding itself declares, never inflated.

### Epistemic Integrity — catching overclaims before they're registered

Before any finding is registered, a six-question pre-registration check runs: what artifact
supports this (file:line required)? Could insufficient power explain the observation? Am I upgrading
sign noise into meaning? Is this statistical or economic (a distinct authority tier)? Is the parent
claim stronger than its children? Would I phrase this differently after seeing raw counts? If any
answer exposes uncertainty, the finding's confidence gets downgraded or its status set to
`HYPOTHESIS` rather than accepted as-is. When this check catches a real overclaim, the required
phrasing is explicit and disarming rather than defensive: *"Caught me overclaiming; I owe you a
correction."* A pre-registration correction under this ritual is treated as evidence the discipline
worked, not as a failure — [Chapter 10](10-four-scoring-engines.md)'s Gaussian-audit ablation and
this book's own 38-vs-39-dim flag in [Chapter 7](07-feature-pipeline.md) are both examples of the
same instinct: report the uncertainty rather than round it away.

**Correction is fixing the source, not just the chat.** If a false claim is retracted, the same turn
also has to fix every recorded instance of it — the finding's `Reversal:` field, the doc, the memory
file — marked `CORRECTED: <old> -> <new>`, never silently deleted.

### Closure & Authority: what "CLOSED" and "AUDITED" actually mean

`docs/governance/closure_authority_index.json` tracks closure status per subsystem, governed by one
non-negotiable invariant: **closure is boundary-scoped and non-transitive.** A `CLOSED` upstream
subsystem does not make anything downstream of it `CLOSED` — only the specific artifact that
declares closure for a *specific, named boundary* counts. Three distinctions worth memorizing,
because conflating them is the exact mistake this index exists to prevent:

- `AUDITED ≠ CLOSED` — reviewed and characterized is not the same as end-to-end proven.
- `LINEAGE CLOSED ≠ ECONOMICALLY VALIDATED` — knowing a model loads the artifact it claims to is not
  the same as that artifact being worth anything.
- `UPSTREAM CLOSED ≠ DOWNSTREAM CLOSED` — see the non-transitivity invariant above.

Concretely, in this book's own vocabulary (Chapter 3): CRT is `CLOSED` for its mechanism boundary
only ([Chapter 8](08-crt-state-machine.md)); Gaussian, Zone Gate, RR, BitNet, and TradeNet are all
`AUDITED` ([Chapter 10](10-four-scoring-engines.md), [Chapter 11](11-fusion.md)) — reviewed
end-to-end, with clear, documented findings, but not certified as economically proven. A `CLOSED` or
`AUDITED` surface reopens only under specific conditions: a governed dependency inside its declared
boundary changes, a closure invariant fails, new contradictory evidence appears, or the artifact's
own stated revalidation condition fires — never just because someone feels like revisiting it.

## Classification

| Concept | Status |
|---|---|
| Truth Maintenance Doctrine (7 rules) | Production doctrine, actively enforced (test-guarded) |
| Findings registry (`current-findings.md`) | Production, living document |
| Epistemic Integrity ritual (E-001) | Production doctrine |
| Closure & Authority Index | Production, machine-readable + test-guarded |

## Authoritative sources

- `CLAUDE.md` §6.2 (Truth Maintenance, the seven rules, the Documentation Drift Protocol, the
  Findings Mandate) and §6.5 (the Authority Ladder, cross-referenced from [Chapter 16](16-config-first-and-promotion.md)).
- `docs/current-findings.md` — the living findings registry.
- `docs/governance/EPISTEMIC_INTEGRITY.md` — the full six-question ritual.
- `docs/governance/closure_authority_index.json` — the machine-readable closure registry.
- `docs/governance/DOCUMENTATION_DRIFT_PROTOCOL.md` — the full drift-classification process.
- `tests/test_current_findings.py`, `tests/governance/test_epistemic_invariants.py`,
  `tests/test_closure_authority_index.py` — the enforcement floors.

## Unresolved questions

None — this doctrine is unusually self-documenting; its own charter is the primary source and this
chapter is a faithful compression of it.

---
**Previous:** [Chapter 16 — Config-First Doctrine and the Promotion Path](16-config-first-and-promotion.md) · **Next:** [Chapter 18 — A Field Guide to docs/governance/](18-field-guide-governance.md)
**Related:** [Chapter 03 — How This Book Fits](03-how-this-book-fits.md) (the classification vocabulary this chapter grounds)
**Memory:** `docs/memory/governance-memory.md`.
