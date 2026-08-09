# Chapter 06 — The Market Ontology: Canonical Semantic Authority

**Part II — Market Understanding**
Status of this chapter: Written

## Why this chapter exists

Before a candle can be scored, every quantity computed from it — a wick length, a displacement
strength, a zone boundary — needs one, and only one, agreed-upon meaning across the whole codebase.
This chapter covers the artifact that owns that meaning: `configs/formulas/market_ontology.yaml`.
Understanding it first is what makes [Chapter 7](07-feature-pipeline.md)'s feature vector, and
every engine chapter after it, legible rather than a wall of unexplained formulas.

## What problem it solves

Historically, this repository suffered from *definitional drift* — the same-sounding quantity
(`wick_size`, `body_ratio`) computed two different ways in two different files, silently. The
ontology exists to make that structurally impossible going forward: one canonical node per concept,
with every consumer required to bind to it rather than re-derive it locally.

## What you need to already know

[Chapter 5](05-data-ingestion-no-lookahead.md) — the ontology's `base_inputs` are exactly the OHLCV
fields that survive ingestion.

## The idea

### What the ontology actually is

`market_ontology.yaml` (version `1.4` as of this writing, ~2,600 lines) is the repository's
declared "**permanent semantic authority**." It defines every market concept as a typed node:
`primitives` (raw geometric building blocks), `feature_compositions`, `derived_metrics`,
`rolling_indicators`, `temporal_context`, `structural_states`, `indicator_identities`,
`execution_behaviours`, plus `invariants` and — importantly — `canonical_unknowns`, an explicit
place to register a discovered-but-not-yet-understood market behavior rather than let it live only
as a code comment or a TODO.

Every node carries a fixed field set: id, canonical name, aliases, a *knowledge_status* on a
refinement ladder, its formula, its dependencies, and who produces/consumes it. The refinement
ladder itself is worth internalizing, because it's the vocabulary this book borrows for describing
how mature any given piece of market knowledge is:

```
UNKNOWN → OBSERVED → CHARACTERIZED → MATHEMATICALLY_DEFINED → FORMULA_DERIVED → VALIDATED
        → PRODUCTION_CERTIFIED → STABLE
```

A node only reaches `PRODUCTION_CERTIFIED` by demonstrating measured economic value — see the
Authority Ladder in [Chapter 17](17-truth-maintenance.md). Reaching a mathematically clean formula
is necessary but never sufficient for that top tier.

### Why "authority" here means something specific

The ontology's authority is "literal supersession" for *meaning* — when a semantic question arises,
this file is where the answer originates, and code, config, research, and even historical findings
are expected to synchronize to it, not the other way around. But that authority is bounded by two
physical constraints, and both matter for anyone editing it:

1. **Frozen runtime keys.** The `primitives`, `feature_compositions`, and `derived_metrics` sections
   are read at *import time* by `crt_engine_v2.py` (via `fm_resolve.bind_phase2_crt_callables()`).
   They can only grow additively — removing or renaming a key there is a breaking change to running
   code, not a documentation edit.
2. **Behavior changes still need governance.** "Ontology first" governs where a semantic change
   *originates*, not an automatic license to mutate runtime behavior. Any change that actually
   alters production output still has to clear the parity-proof and promotion gate from
   [Chapter 16](16-config-first-and-promotion.md) — the ontology can't bypass governance, it feeds it.

### Downstream reach

Every consumer that computes market meaning is expected to bind to this file rather than re-derive
it: `crt_engine_v2.py` at import time (frozen sections), the feature registry / formula registry
facade that [Chapter 7](07-feature-pipeline.md) depends on, and — per the ontology's own evolution
contract — effectively everything else in the pipeline traces its semantic meaning back here. This
is why it's Chapter 6, not buried in an appendix: it's upstream of every later Part's vocabulary.

## Classification

| Concept | Status |
|---|---|
| Ontology as the semantic authority for meaning | Production, actively governed (CLAUDE.md §6.6) |
| Frozen runtime keys (`primitives`/`feature_compositions`/`derived_metrics`) | Production, additive-only |
| `canonical_unknowns` section | Explicit, honest placeholder for open questions — not a gap in the doctrine, a designed feature of it |

## Authoritative sources

- `configs/formulas/market_ontology.yaml` — the ontology itself (2,600+ lines, version 1.4, 2026-07-24).
- `docs/governance/MARKET_ONTOLOGY_EVOLUTION_CONTRACT.md` — the full evolution contract this
  chapter summarizes.
- `CLAUDE.md` §6.6 — the Canonical Market Ontology Evolution Contract (the two mechanical
  constraints, the refinement ladder, the Automatic Semantic Discovery ritual).
- `src/features/registry/` (formula registry facade), `src/config_layer/crt_engine_v2.py` (import-time binding).
- `docs/current-findings.md` F-047 — the ontology's authoritative status, source-verified.

## Unresolved questions

None for this pass — the ontology's own evolution contract is unusually explicit about its own
scope and limits, which made this chapter straightforward to write faithfully.

---
**Previous:** [Chapter 05 — Data Ingestion and the No-Lookahead Discipline](05-data-ingestion-no-lookahead.md) · **Next:** [Chapter 07 — The Feature Pipeline and the Canonical Vector](07-feature-pipeline.md)
**Related:** [Chapter 17 — Truth Maintenance](17-truth-maintenance.md) (the Authority Ladder that governs when a node earns production certification)
**Memory:** `docs/memory/feature-memory.md`.
