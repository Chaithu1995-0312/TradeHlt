# Reasoning Capability Registry — Doctrine (M1 pilot)

> **What this is.** The doctrine for a new, additive ontology layer that groups existing models'
> outputs by *what reasoning question they answer*, extracted bottom-up from evidence of what
> models already do — never invented ahead of an implementation. Machine-readable twin:
> `configs/formulas/market_ontology.yaml` → `reasoning_capabilities` section. Model↔capability
> mapping: [`capability_model_map.json`](capability_model_map.json). Test floor:
> `tests/test_reasoning_capabilities.py`.
>
> **Created:** 2026-07-29 · **Status: M1 PILOT — one capability (RC-001) registered.**
> Milestone 2+ is contingent on this pilot's method holding and is **not authorized** by this
> document. **Authority: NONE** (CLAUDE.md §6.5 rung 1 — information only). This layer never
> promotes a model, never enables a flag, never changes a fusion weight.
>
> **Companions:** [`MODEL_INTENT_AUTHORITY_REGISTER.md`](MODEL_INTENT_AUTHORITY_REGISTER.md)
> (MIAR — remains authoritative on per-model intent/boundaries; this layer extends it, never
> overrides it) · [`model-design-intent.md`](../architecture/model-design-intent.md) Part VII
> (the source evidence this pilot formalizes) ·
> [`MARKET_ONTOLOGY_EVOLUTION_CONTRACT.md`](MARKET_ONTOLOGY_EVOLUTION_CONTRACT.md) (the schema
> discipline this layer inherits verbatim)

---

## 0. Why this exists, and why it is bottom-up

The user's proposal was to reverse `Models → Documentation` into
`Semantics → Cognition → Implementations → Documentation` — define the complete space of
market-reasoning capabilities first, partition it orthogonally, prove dependencies, *then* map
implementations onto it.

Two research passes (2026-07-29) found **zero prior artifact** of this vision anywhere in the
repo's own record, and found that every adjacent structure — the market ontology, MIAR's 7-stage
taxonomy, `model-design-intent.md`'s redundancy audit — was built **models-first**: catalog what
exists, then organize it. Building the literal top-down form (a *complete* space, defined before
any implementation) would collide with two standing doctrines: `target-strategy-architecture.md`
§12 anti-goal #1 (rejects a "fully semantic-executable OS"), and CLAUDE.md §6.5 +
`intelligence-compounding.md`'s evidence-earns-complexity discipline ("should emerge from
necessity").

**Ruling: bottom-up extraction.** Same end state — a capability semantics that can eventually
generate registries — reached by extracting capabilities from the evidence of 21 real, tested
models rather than inventing them a-priori. This never claims a-priori completeness, so it
collides with neither doctrine, and can start immediately because the raw material already
exists: `model-design-intent.md` Part VII already found five clusters of redundant measurement
(familiarity, regime, structure, trap/breakout, meta-fusion) — a capability is a formalization of
one such cluster, not a new invention.

## 1. Two existing mechanisms this reuses

**`market_question_matrix` is already a proto-capability registry.** In `miar_registry.json` — a
flat list of canonical market questions, each with **exactly one owner**, enforced by
`tests/test_miar_registry.py::test_market_question_matrix_single_owner`. A "market question" *is*
a reasoning capability in all but name — at the **per-model** grain. What it lacks is a **coarser**
grain: a way to say "these two per-model questions are the same underlying reasoning axis viewed
at different scales." That coarser grain is what `reasoning_capabilities` adds. It does not
replace the matrix; every existing row stays exactly as committed.

**The ontology has a declared, unpopulated extension slot.** `market_ontology.yaml`
`spec_schema.semantic_registry.sections` lists non-frozen sibling sections validated by
`validate_semantic_registry()` and **never read on the runtime binding path**. `reasoning_capabilities`
is one such section (added 2026-07-29), alongside the still-empty `model_contracts`,
`regimes`, `risk_behaviours`, `state_transitions`. A capability node is a semantic node like any
other — same `knowledge_status_ladder`, same `semantic_node_required_fields`, same epistemic
discipline. Nothing new was invented at the mechanism level; only a new `ReasoningCapability`
category and section name were added to already-existing machinery.

## 2. What a capability node asserts, and what it must never assert

A `reasoning_capabilities` node records: *these N models, evidenced across M lineage
findings, appear to answer variants of one reasoning question.* It is registered at
`knowledge_status: OBSERVED` — a measured pattern, mechanism not proven — never higher, until a
`resolution_metric` is actually run.

**A capability node must never:**
- Assert a-priori completeness of the reasoning space (§0's whole rationale).
- Assert orthogonality between capabilities without evidence — overlap is *reported*
  (`overlap_declared` + rationale), never silently resolved and never forbidden.
- Grant any model authority, change any fusion weight, or alter any `explicit_non_goals` /
  `authority_boundary` already declared in MIAR. MIAR wins on model intent (its own §0 hierarchy);
  this layer only adds a coarser lens over MIAR's existing questions.
- Let a hypothesis become a fact by repetition. Where the evidence is a redundancy *pattern*
  observed once (Part VII, `Authority: NONE`), the node's `epistemic.unknown_mechanism` must state
  the real open question, and `candidate_hypotheses` must include the null hypothesis — that the
  models share only vocabulary, not a common formal target.

## 3. M1 pilot register

One capability, extracted from the best-evidenced cluster in Part VII:

| id | name | producers | overlap | knowledge_status |
|---|---|---|---|---|
| `RC-001` | `statistical_structural_familiarity` | Gaussian heuristic, Gaussian ML (shadow), Zone Gate similarity kernel, CRT internal distance-decay | Declared — see `capability_model_map.json` | `OBSERVED` |

Full node: `market_ontology.yaml` → `reasoning_capabilities.statistical_structural_familiarity`.
Model mapping: `capability_model_map.json` → `RC-001` (maps the two MIAR-registered models,
`gaussian` and `zone_gate`; CRT's internal mechanism is cited as evidence inside the node but CRT
itself is **not** mapped — see the map's `no_capability_reason.crt` for why conflating a primary
capability with an embedded secondary mechanism would repeat the exact models-first error this
exercise exists to correct).

## 4. M1.4 — Direction-reversal proof: deriving a matrix row from RC-001

The committed, unaltered `market_question_matrix` rows this capability relates to:

```json
{"question": "How statistically conformant is this state to previously observed states?",
 "owner": "gaussian", "secondary_consumers": ["decision_fusion"]}
{"question": "Is this inside a valid structural zone?",
 "owner": "zone_gate", "secondary_consumers": ["decision_fusion"]}
```

Both are pre-existing, individually valid, single-owned, and **unaltered by this pilot**.

**Attempted derivation.** If `RC-001` is projected down to a single `market_question_matrix`-shaped
row — one question, one owner, matching the matrix's existing schema — the candidate row is:

```json
{"question": "How familiar/typical is this state relative to previously observed or reference states?",
 "owner": "???"}
```

**Result: the derivation cannot complete without violating the matrix's own invariant.**
`RC-001` has **two** MIAR-registered producers (`gaussian`, `zone_gate`), not one.
`test_market_question_matrix_single_owner` requires exactly one owner per question. Picking either
model as "the" owner would misrepresent the evidence (both independently compute a
familiarity-shaped quantity today) — exactly the kind of arbitrary, models-first ownership
assignment this exercise exists to avoid, not reproduce under a new name.

**This is the finding, not a defect to fix.** It demonstrates two things at once:
1. **Generation-from-semantics is directionally real** — the derivation is mechanical, not
   hand-waved (see `test_reasoning_capabilities.py::test_capability_ids_consistent_with_ontology`
   and the map's `overlap_declared` field, which encodes exactly this multi-owner fact).
2. **The matrix and the capability layer operate at genuinely different grains**, and neither
   should be forced into the other's shape. `market_question_matrix` is correct and complete *at
   the per-model grain* — both existing rows stay exactly as committed. `reasoning_capabilities`
   is a **separate, coarser, companion registry**, not a generator that overwrites the matrix.
   Any future attempt to auto-generate `market_question_matrix` rows from capabilities must
   either (a) extend the matrix's schema to permit multi-owner rows explicitly, or (b) accept that
   the matrix stays per-model and the capability layer stays a distinct, coarser index — a design
   decision for Milestone 2+, not resolved here.

## 5. Milestone 2+ (not authorized here)

Contingent on this pilot's mechanism holding under scrutiny: repeat extraction for the four
remaining Part VII clusters (regime — four vocabularies; structure — three languages;
trap/breakout; meta-fusion — HMF/TradeNetMeta); build a capability-level dependency DAG (distinct
from `build_lineage_graph`'s feature DAG and `feature_dag_layers.py`'s L0–L6 code DAG, neither of
which model anything above features); resolve the matrix-vs-capability grain question raised in
§4. **Completeness of the space is a horizon, never a claim** — this register grows only as
evidence arrives, exactly like the ontology's own `canonical_unknowns` citizens.

## 6. Maintenance

- A new capability requires: producers cited with file paths, evidence citing real findings (not
  narrative alone), an honest `epistemic` block including the null hypothesis, and a
  `capability_model_map.json` entry with `overlap_declared` set truthfully.
- Extending `MIAR`'s `entries` or `sidecar_entries` list is unaffected by this layer — the two
  registries are independent; `tests/test_miar_registry.py`'s 17/4 counts are not touched by
  anything here.
- Every claim in §4 is mechanically checked, not just asserted in prose — see
  `tests/test_reasoning_capabilities.py`.
