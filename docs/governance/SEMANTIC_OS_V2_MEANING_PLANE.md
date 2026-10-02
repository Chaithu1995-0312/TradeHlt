# Semantic OS v2 — Meaning Plane (Ontology v2)

> **Status:** FROZEN v2.0.0 architecture (user + architecture-review accepted 2026-10-02). PROPOSED
> concepts stay open by design (I-18). Implementation is sliced; slice 1 = Geometry + Market.
> **Authority:** meaning authority (CLAUDE.md §6.6). Grants **no** runtime authority (§6.5).
> **Charter it extends:** [`SEMANTIC_OS_CONTRACT.md`](SEMANTIC_OS_CONTRACT.md) (system plane, advisory).
> **Machine artifacts:** [`concept_contracts.yaml`](../../configs/formulas/concept_contracts.yaml) ·
> [`representation_registry/`](../../configs/formulas/representation_registry/) ·
> [`terminal_reason_map.yaml`](../../configs/formulas/terminal_reason_map.yaml)

## 1. Purpose

Every observation, inference, decision and result has exactly one declared meaning, one identity,
one authority, and a traceable path from representation to meaning. **Code is evidence, not
authority** for meaning: where code and a concept contract disagree, the difference is recorded as a
divergence and resolved later by an authorised change — never silently, never by editing history.

## 2. Planes

| Plane | Contents | Authority |
|---|---|---|
| System (exists) | CN concepts, BD boundaries, CT behaviour contracts, journeys, file identities (`docs/governance/semantic_os/`) | Advisory |
| **Meaning (this doc)** | Market ontology → concept contracts → REP registry → implementation | Meaning authority (§6.6) |
| Evidence (exists) | Findings, MPA provenance, research family registry, JSONL claim catalog (`CC-*`) | Evidence only |
| Grounding (exists; to extend) | `query_semantic_os.py --ground`, later `--kind CONCEPT/REPRESENTATION` | Claim gate (§6.7) |

"Contract" alone means a system-plane `CT-*` contract. Meaning-plane records are **concept contracts**.

## 3. Layers and types

A layer may reference only its own or lower layers (I-12).

| Layer | Types | Must never represent |
|---|---|---|
| GEOMETRY | PRIMITIVE (GP-01…07) | Meaning |
| MARKET | LEVEL, ZONE, EVENT, CONDITION, EPISODE, EPISODE_STAGE | Roles, policy, position state |
| TRADING | THESIS, OBJECTIVE (role), INVALIDATION (role+rule), ENTRY, STOP (role), TARGET (role), COST, OUTCOME | Market facts; fills |
| DECISION / EXECUTION | SIGNAL, DECISION, EXECUTION_SPEC, EXECUTION (position lifecycle, fills) | Market meaning |
| cross-cutting | MEASUREMENT (lives in its subject's layer), REPRESENTATION, CONCEPT CONTRACT | — |

**Market rule.** Market concepts are determined by observable market and time inputs only. Data
availability, producer construction and policy decisions never masquerade as market events.

**Three role distinctions.** (1) A LEVEL is not its role: the same `h_ref` is the OBJECTIVE of a LONG
thesis and the INVALIDATION of a SHORT one (`htf_state.resolve_objective`). (2) A market event
(50% retrace) ≠ a thesis invalidation (FAILED) ≠ a position stop (displacement extreme ± buffer) —
the engine already suppresses all resets once a position is open (`crt_engine_v2.py:2874-2877`).
(3) An EPISODE_STAGE ≠ a position lifecycle state.

## 4. Geometry primitives

| Id | Name | UPPER rule (LOWER mirrors) | Equality |
|---|---|---|---|
| GP-01 | PIERCE | `high > L` | not a pierce |
| GP-02 | BEYOND | `close > L` | not beyond |
| GP-03 | REACH | `close >= L` | reached |
| GP-04 | PIERCE_AND_REJECT | `high > L and close < L` (SP-001) | close == L is neither GP-02 nor GP-04 |
| GP-05 | OVERLAP | `low <= zone_high and high >= zone_low` | edges inclusive |
| GP-06 | DIRECTIONAL_IMPULSE | SP-002 / F-074 | — |
| GP-07 | IN_BAND | **PROPOSED** — SP-003 deferred on OQ7 | — |

Prices compare at instrument precision with no hidden epsilon; a tolerance is a declared
identity-bearing parameter. Gap bars are evaluated as given (no interpolated trade-through).

## 5. Identity contract

```
SEMANTIC        = (concept_id, kind, reference, timeframe, clock, availability_rule)
PARAMETERIZATION= identity-bearing parameter values            -> parameterization_id
SETTINGS        = config_hash / config_version                 (lineage only)
REPRESENTATION  = SEMANTIC + parameterization_id + producer_id + encoding + schema_version
INSTANCE        = SEMANTIC + parameterization_id + instance_key(anchor, side, parent)
```

| Change | Result |
|---|---|
| settings change, no identity-bearing value changes | settings lineage only |
| identity-bearing value changes (e.g. W 5→10, tie rule) — even if only one value is configured | new `parameterization_id` |
| two values coexist at runtime | two REPRESENTATION identities |
| different producer | new REPRESENTATION identity; producers are never equal (L3 §7.2) |
| different encoding / schema | new REPRESENTATION identity |

`reference` is a founding rule or an anchor object (range equilibrium ≠ 50% displacement retracement).
`parameterization_id` uses the same canonical-JSON sha256 as `crt_identity_schema.derive_constructor_id`.
This is the frozen L3 contract's own vocabulary: parameterization = identity, settings = lineage.

## 6. Concept contracts

One record per concept id in `concept_contracts.yaml`: definition, layer, kind, status, identity,
parameterization (each parameter declares `identity_bearing`; `legacy_values` only with a recorded
divergence), inputs, rule, units, lifecycle, absence, authority{evidence, sources, lineage},
divergences, version. Representations and consumers are **not** stored there: the REP registry is
the single source for representation → concept, and consumers are derived from code (I-14).

- **ACCEPTED** = contractually definable from an identified REPO source or an explicit USER_DECISION.
  It does **not** mean empirically validated, economically useful, or universal trading knowledge.
- **PROPOSED** = zero representations, zero consumers (I-18).

## 7. Representation registry

Sharded by producer under `configs/formulas/representation_registry/`. Every representation resolves
to exactly one concept id with parameterization, encoding, absence rule and schema version. Every
canonical slot / enum member appears exactly once: as a representation, an L0 raw observation, a
deprecated representation, or in a shrink-only `unmapped` ratchet.

## 8. Terminal authority

Every episode termination carries `terminal_authority ∈ {MARKET, OBSERVATION, PRODUCER, DECISION,
EXECUTION}`, a `terminal_class` and a `reason_code`, and keeps the legacy reason verbatim.
`terminal_reason_map.yaml` maps the engine's existing reason strings at read time.

Measured on the active-config XAUUSD trace (`run_20260930_163142`, 2,887 RESET events, 0 unmapped):
MARKET/EXPIRED 2,467 · MARKET/FAILED 166 · MARKET/SPENT 109 · OBSERVATION 121 · DECISION/FILTERED 20 ·
EXECUTION/POSITION_CLOSED 4. The engine's CRT series is therefore policy- and observation-shaped (I-3a).

## 9. Invariants

| # | Invariant |
|---|---|
| I-1 | An EVENT never becomes a persistent CONDITION (or the reverse) without a new identity |
| I-2 | A representation cannot redefine its concept: name, value and contract agree |
| I-3 | A decision never redefines a market observation; it may terminate an episode, recorded only as `DECISION` |
| I-3a | A series shaped by non-market terminations declares that shaping |
| I-4 | Every MEASUREMENT declares unit, normalisation basis and missing rule |
| I-5 | Historical representations are immutable; access via versioned aliases (`RECOMPUTE != RECOVER`) |
| I-6 | `available_at` ≤ the bar of any use; a fill is observable after its decision |
| I-7 | Absence is explicitly distinguishable from every valid value |
| I-8 | One concept, one predicate composition; implementations differ only by declared parameters |
| I-9 | One label, one rule — or the divergence is recorded |
| I-10 | A role never overwrites the status of its level |
| I-11 | Every tradable episode declares both thesis invalidation and position stop |
| I-12 | Layers reference only lower layers |
| I-13 | Unreachable semantics are marked, never asserted |
| I-14 | Producers and consumers are mechanically verified |
| I-15 | An outcome names its walk and cost model |
| I-16 | Clock-dependent concepts declare their clock |
| I-17 | Settings never enter semantic identity; identity-bearing value changes produce a new `parameterization_id` |
| I-18 | No canonical meaning by familiar name; PROPOSED concepts have 0 representations and 0 consumers |
| I-19 | Frozen governance contracts change only through their own amendment mechanism |

## 10. Decisions record

| Id | Decision |
|---|---|
| D-1 | `MKT-C07 break_against_momentum` = FM-083's documented meaning; `MKT-E03 choch` PROPOSED (B: opposite last structure break; C: ends a swing sequence) |
| D-2 | I-3 as worded above (decisions may terminate, never masquerade) |
| D-3 | Parameterization vs settings (§5) |
| D-4 | L3 CRT-state identity reopens as **v2.0.0** under its own change id (new topology without EXECUTION/RESOLUTION on the market track; `episode_id`) — deferred |
| D-5 | Ontology scope v2 takes BOS/CHoCH/pivot semantics; `market_ontology.yaml:40` exclusion becomes SUPERSEDED — separate change id, deferred |
| D-6 | Artifact topology: ontology → concept contracts → REP registry → implementation |
| D-7 | I-7 as worded above |
| O-1 | No parity oracle on existing code (user, 2026-10-02): acceptance is contract compliance; existing modules are called, never edited, by the meaning-plane package |
| O-4 | TTL expiry → PRODUCER |
| O-5 | Claude authors registries, this spec and the handoff brief; coding LLMs implement; Claude reviews against contracts (user, 2026-10-02; CLAUDE.md §13.8 update pending user decision) |

## 11. Deferred / PROPOSED

`MKT-E03 choch` · `MKT-C02 structural_trend` · `GP-07 in_band` / `MKT-Z06 retest_band` (OQ7) · zone
state FILLED · `MKT-E02` consumption `once_per_level` · parent-track C1/C2/C3 stage mapping · M15
objective and objective-based targets · Trading and Decision/Execution concept contracts (slice 2) ·
grounding `--kind CONCEPT/REPRESENTATION` · L3 v2.0.0 · ontology scope v2.
