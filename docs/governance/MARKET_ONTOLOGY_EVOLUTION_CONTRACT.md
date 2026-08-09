# Canonical Market Ontology Evolution Contract

> **Adopted 2026-07-25** (user directive). The long-form of CLAUDE.md §6.6. The machine-readable
> authority lives in `configs/formulas/market_ontology.yaml` (`spec_schema.semantic_registry`);
> this doc is the human-language charter. Enforced by `tests/test_semantic_registry.py` via
> `features.registry.validate_semantic_registry`.

## Purpose

The market ontology is the **permanent semantic authority** of the repository. It defines every
market concept — feature, formula, derived mathematics, state, transition, pattern, regime,
context, structure, zone, geometry, liquidity/volatility/execution/risk behaviour, model
input/output, validation rule, invariant. Every implementation, model, config, report, and
research artifact derives its **meaning** from the ontology. No market behaviour may exist outside
it: discovered-but-undefined behaviour becomes an explicit `UNKNOWN_*` node, never a TODO or a
buried comment.

## Authority (user decision: LITERAL SUPERSESSION)

The ontology is authority **#1**, first-mover. For **meaning/semantics**, runtime, models, and the
historical §4.0 / §6.5 precedence derive from it: a semantic change originates in the ontology and
everything else synchronizes.

### Two mechanical constraints (physical — keep supremacy coherent, NOT doctrine-overridable)

1. **Frozen runtime keys stay flat + additive.** `primitives` / `feature_compositions` /
   `derived_metrics` are read by `crt_engine_v2` at import (`fm_resolve.bind_phase2_crt_callables`).
   The ontology may change first, but frozen-key edits are additive-only or the engine hard-crashes
   on import. New node types live in the **non-frozen** sibling sections
   (`spec_schema.semantic_registry.sections`), invisible to `_ITERATED_SECTIONS`, the runtime
   binding, and `validate_registry`.
2. **Behaviour cascades are governed.** An ontology change that would alter **production behaviour**
   still cascades through parity-proof + the promotion gate before it reaches runtime. "Ontology
   first" governs the **origin and requirement** of a change — it must originate in and be recorded
   by the ontology — not an automatic unvalidated runtime mutation (this preserves the
   anti-split-brain guarantee of §4.0 and the earned-authority ladder of §6.5).

## Node schema

Every node in a semantic section carries the full `semantic_node_required_fields` set (id,
canonical_name, aliases, semantic_category, knowledge_status, description, observed_behaviour,
mathematical_definition, units, formula, dependencies, required_inputs, produced_outputs,
producers, consumers, transitions, validation_rules, confidence, evidence, origin, status, version,
owner, traceability, notes). A field's **value** may be `UNKNOWN` / `[]` until discovered — the key
must be **present**. **Never fabricate** a value the evidence does not support. `id` is unique
across the whole ontology (FM-0NN frozen ids and SEM-/UNK- semantic ids share one namespace).

## Refinement ladder (knowledge axis, distinct from `lifecycle`)

`UNKNOWN → OBSERVED → CHARACTERIZED → MATHEMATICALLY_DEFINED → FORMULA_DERIVED → VALIDATED →
PRODUCTION_CERTIFIED → STABLE`

A node **refines in place** up this ladder; its identity never changes and **no duplicate node** is
created. `UNKNOWN` is a valid, permanent citizen — it participates in dependency graphs, validation,
and traceability until resolved. `PRODUCTION_CERTIFIED` is earned only by measured G001 (§6.5) —
evidence alone never grants production authority.

## Epistemic discipline — separate the levels (mandatory for UNKNOWN)

The single most important rule: **a node must never mix measured facts, validated knowledge, and
hypotheses into one statement.** Hypotheses harden into "facts" by repetition otherwise. A
research-stage node carries an `epistemic:` block keeping the levels distinct:

| Component                  | Purpose                                    | May change?             |
| -------------------------- | ------------------------------------------ | ----------------------- |
| `observation`†             | measured facts                             | rarely                  |
| `known_invariants`         | facts already validated                    | only with new evidence  |
| `unknown_mechanism`        | the single unanswered question             | yes                     |
| `candidate_hypotheses`     | explicitly-untested guesses (NOT truth)    | yes                     |
| `resolution_metric`        | how the question will be answered          | can evolve if improved  |
| `falsification_conditions` | what evidence would DISPROVE the hypotheses | can evolve              |

† `observation` is the node's existing `observed_behaviour`; `evidence` is the node's `evidence`
field. The `epistemic` block holds the remaining five keys.

The block is **mandatory when `knowledge_status == UNKNOWN`** and **encouraged for OBSERVED /
CHARACTERIZED**; whenever present (any status) it is validated. `falsification_conditions` is the
newest discipline — good research documents not only how a theory is supported but how it could be
proven wrong. State invariants factually: prefer *"current evidence indicates X is not explained by
the previously identified defect Y"* over *"X is not an artifact"* — ruling out one known defect
does not rule out an unrelated, not-yet-identified one.

## Automatic Semantic Discovery ritual (every investigation)

While investigating, actively search for: undefined behaviours, duplicate/equivalent semantics,
hidden transformations, implicit assumptions, missing formulas/transitions/consumers/producers/
invariants/lifecycle rules. **Each discovery becomes a canonical ontology node** the same turn —
seeded at the honest `knowledge_status` with `evidence` + `origin` filled, and a contamination
caveat in `notes` when the source is a single run / shadow path / possibly-contaminated upstream.
Do not force a new behaviour into an existing node because it "looks similar"; if evidence is
insufficient, create a new node (or an `UNKNOWN_*`) and refine it as evidence accumulates.

## Cross-layer synchronization order

`ontology → formula registry → feature registry → feature schema → feature pipeline → models →
configuration → validation → documentation`. The ontology changes first; behaviour-affecting
cascades remain governed (constraint 2).

## Enforcement

`features.registry.validate_semantic_registry(ontology)` (sibling to `validate_registry`, reads its
vocabularies from `spec_schema.semantic_registry` — ontology-first) checks: required fields present;
id present + globally unique; version int; category ∈ vocabulary; knowledge_status ∈ ladder;
evidence + origin non-empty above UNKNOWN; `canonical_unknowns` nodes stay UNKNOWN/OBSERVED; list
fields `[]` not null. Floor: `tests/test_semantic_registry.py`. The frozen path (`validate_registry`)
is unaffected — additive by construction.

## Seed nodes (2026-07-25, this session)

`SEM-001 EXPANSION_DWELL_DIVERGENCE` (OBSERVED), `SEM-002 HTF_PROTECTION` (CHARACTERIZED),
`SEM-003 STATE_OCCUPANCY_VS_DWELL_SPAN` (MATHEMATICALLY_DEFINED, invariant), `UNK-001` (the UNKNOWN
root mechanism of the resolver EXPANSION under-dwell). `FM-002 candle_range` (aliases `wick_size`,
`resolved_renamed_v4`) is the in-tree STABLE ladder exemplar. All grant no production authority.

## Long-term objective

The ontology becomes a complete mathematical + semantic **digital twin** of the trading system —
every behaviour, feature, state, transition, execution rule, model, report, and validation
representable as ontology objects with full mathematical identity, semantic lineage, implementation
traceability, and runtime verification. No part of the system may rely on undocumented semantics or
implicit assumptions. (Guardrail: build incrementally from evidence — §6.5 "no premature
framework"; a node earns complexity only when a real behaviour demands it.)
