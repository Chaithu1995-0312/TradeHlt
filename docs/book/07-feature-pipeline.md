# Chapter 07 — The Feature Pipeline and the Canonical Vector

**Part II — Market Understanding**
Status of this chapter: Written

## Why this chapter exists

The four scoring engines in Part IV don't see a candle — they see a fixed-length numeric vector.
This chapter covers where that vector comes from, what's in it, and — because this is where the
book caught a live piece of documentation drift while researching it, later fixed at the source —
exactly how many dimensions it actually has today.

## What problem it solves

Explains the single most-consumed data contract in the codebase: `CANONICAL_FEATURES`. Every engine,
BitNet, and most of the research pipeline binds to this vector's shape.

## What you need to already know

[Chapter 6](06-market-ontology.md) — the feature math this pipeline runs is derived from the
ontology's `primitives`/`feature_compositions`/`derived_metrics`, not invented locally.

## The idea

### What the pipeline does

`src/features/feature_pipeline.py`'s `FeaturePipeline.run()` takes an enriched candle stream and
produces `(enriched_df, vectors)` — a dataframe plus the fixed-length numeric vectors that engines
actually consume. The vector's *shape* — which fields, in which order, at what dimensionality — is
defined once, in `src/features/feature_schema.py`, as `CANONICAL_FEATURES`. Nothing downstream is
supposed to reconstruct that shape independently; `core/engine_runner.py` imports it directly, as
do `engines/zone_gate_engine.py`, `engines/heuristic_gaussian_engine.py`, and `crt_engine_v2.py`.

### A doc-drift this book caught, flagged, and — on a follow-up pass — fixed at the source

`docs/reference/schemas.md` §4 used to document a **38-dimension, schema v3.0** feature tuple —
`CANONICAL_FEATURE_DIM = 38`, with a single `macd_hist` field and a `wick_size` field. The code that
actually runs today, `src/features/feature_schema.py`, is at **39 dimensions, schema v4.0**
(`CANONICAL_FEATURE_DIM: int = 39`): `macd_hist` was split into `macd_hist_raw` and `macd_hist_z`
(indices 18–19), and `wick_size` was renamed to `candle_range` (index 28). A `SCHEMA_V3_ALIASES`
mapping exists solely so old v3 records can still be *read*; it is not what new code produces. The
pipeline module's own docstring calls this out explicitly, warning readers to quote the code
constant rather than a number, because the docstring itself had briefly carried a stale "38" through
the v2→v3→v4 migrations.

This was a textbook `DOC_DRIFT` case per `CLAUDE.md` §6.2 (code wins, doc needs fixing) — the fix
itself (F-062, 2026-07-31) had already shipped on the *code* side; `docs/reference/schemas.md`'s
table just hadn't been updated to match. This book's first pass deliberately flagged it without
touching the reference doc (keeping scope to the book itself); **on a follow-up pass (2026-08-07),
`docs/reference/schemas.md` §4 was corrected directly** to the verified 39-dim/v4.0 tuple, with the
`macd_hist_raw`/`macd_hist_z` split and `candle_range` rename spelled out and `SCHEMA_V3_ALIASES`
included for backward-compat context. Per `CLAUDE.md`'s Documentation Drift Protocol, fixing the
source is the completion condition — this paragraph itself is the audit-trail entry for that fix.

**The rule this still leaves you with:** when you need the current dimensionality or field order,
prefer `src/features/feature_schema.py`'s `CANONICAL_FEATURES` constant as the fastest-moving source
of truth — `schemas.md` is now correct as of this fix, but the constant is what actually governs at
runtime and will always be first to change.

### Who consumes the vector

`core/engine_runner.py` is the hub: it builds the 39-dim vector once per candle and hands it to all
four engines uniformly. This is what makes "all four engines or nothing"
([Chapter 2](02-invariants-and-happy-flow.md)'s invariant #2) mechanically enforceable — every
engine is looking at the exact same input surface, so a missing engine is a missing *scorer*, never
a missing *input*.

## Classification

| Concept | Status |
|---|---|
| `feature_pipeline.py` / `FeaturePipeline.run()` | Production |
| `CANONICAL_FEATURES` @ 39-dim, schema v4.0 (`feature_schema.py`) | Production, current |
| `docs/reference/schemas.md` §4 | **Fixed** (2026-08-07) — now documents 39-dim/v4.0, matching the code |
| `SCHEMA_V3_ALIASES` | Production, read-compatibility only — not what new code emits |

## Authoritative sources

- `src/features/feature_pipeline.py` — the pipeline entry point (`FeaturePipeline.run()`).
- `src/features/feature_schema.py` — **the single source of truth** for `CANONICAL_FEATURES` and
  `CANONICAL_FEATURE_DIM`.
- `docs/reference/schemas.md` §4 — the reference doc, corrected 2026-08-07 to match the code.
- `docs/current-findings.md` — F-062 (the code-side rename that created this v3/v4 gap).
- `docs/topics/feature-schema.md` — the always-synced topic doc for this concept.

## Unresolved questions

None — `docs/reference/schemas.md` §4 was corrected to 39-dim/v4.0 on 2026-08-07; this chapter's
own doc-drift flag from the book's first pass is resolved.

---
**Encyclopedia:** [E1b — Features & Registry](encyclopedia/E1b-features-registry.md) · machine twin `encyclopedia/encyclopedia_rows.jsonl` (phase=E1b)

**Previous:** [Chapter 06 — The Market Ontology](06-market-ontology.md) · **Next:** [Chapter 08 — The CRT State Machine](08-crt-state-machine.md)
**Related:** [Chapter 10 — The Four Scoring Engines](10-four-scoring-engines.md) (the vector's consumers)
**Memory:** `docs/memory/feature-memory.md`.
