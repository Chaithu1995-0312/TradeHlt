# Semantic OS v2 — Meaning Plane (Ontology v2)

> **Status:** FROZEN v2.0.0 architecture (user + architecture-review accepted 2026-10-02); v2.0.1
> clarifications in §12; slice 2 (Trading) decisions in §13. PROPOSED
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
objective and objective-based targets · ~~Trading and Decision/Execution concept contracts~~ (done: slice 2 §13, slice 3 §14) ·
grounding `--kind CONCEPT/REPRESENTATION` · L3 v2.0.0 · ontology scope v2.

## 12. Amendments

Clarifications only (v2.0.1, 2026-10-02, from the slice-1 independent audit). They state what the
frozen text left implicit; no concept, invariant or decision above changes meaning (I-19).

| Id | Section | Clarification |
|---|---|---|
| A-1 | §5 | For MKT-P01 the `instance_key` is (anchor = bar of the first stage after AWAITING_SWEEP, side = none, parent = `run_id`). This is the "run_id + first non-AWAITING bar" key of the slice-1 brief, expressed in §5 terms. |
| A-2 | §6 | Optional record fields, not validated in slice 1: `lifecycle.proposed_states` (states named but PROPOSED, never emitted), `lifecycle.entry_events` / `exit_events` (stage records; tokens may name a concept id or a lifecycle step such as `founding` or `termination`), `parameterization.<p>.applies_to` (the founding values a parameter applies to), `parameterization.<p>.default_ref` (the config key that usually supplies the value — documentation only; a missing identity-bearing value is still an error, never a default). |
| A-3 | §6 | A parameter `domain` written `CONCEPT.param` takes its domain from that concept's parameter. |
| A-4 | §5, §7 | A REP parameter value written `section.key` binds the parameter to settings. It is valid only if the key resolves in the active config to an in-domain value; each resolved value is its own parameterization (I-17). |
| A-5 | §8 | `terminal_reason_map.yaml` declares both the authority and the class vocabulary; at equal match length an `exact` entry beats a `prefix` entry. |
| A-6 | §6, §11 | Consumer derivation (I-14, and I-18's "0 consumers") has no slice-1 mechanism; it arrives with grounding `--kind CONCEPT/REPRESENTATION`. Slice 1 enforces only "0 representations". |
| A-7 | §6 | Optional `aliases` list on a concept record: earlier canonical names kept for history (MKT-E09 `retest_entry` → `retest_touch`). An alias is never a second concept. |
| A-8 | §6 | Optional `roles` mapping on a THESIS record names the concepts it binds (I-11). Optional `decide_in` + `decision` on a divergence name a deferred decision and the slice that must settle it. |
| A-9 | §13 | Slice-2 review (2026-10-02). A role's availability is separate from its firing's: TRS-03 is knowable on the MKT-E04 bar, MKT-E10 on the breach bar. One displacement move, from the sweep reference price to the MKT-E04 close, serves both invalidation and extension (user); the engine's body-based inclusive retrace is a TRS-03 divergence. A component cost depends on the walk's actual exit, so it is available on the exit bar. A net outcome's identity names `cost_source`. `forward_walk_oco` leaves the TRS-08 walk domain (user). TRS-06 cites `ExecutionEngine._derive_trade_intent`, not `CRTEngine`. |

## 13. Slice 2 — Trading layer (user decisions 2026-10-02)

Concept contracts TRS-01…08 (thesis, objective, invalidation, entry, stop, target, cost, outcome).

| Id | Decision |
|---|---|
| D2-1 | A thesis is born on the MKT-E04 displacement bar, not on the sweep. A sweep without displacement is an episode, not a failed thesis. |
| D2-2 | Invalidation (ends the thesis) and stop (ends the position) are separate and both required (I-11). Whether an invalidation while the position is open closes the position is **deferred to slice 3** as a recorded divergence with `decide_in: slice_3`; the validator fails once slice-3 records exist and it is still open. **Settled in slice 3 (D3-1).** |
| D2-3 | Objectives and targets are roles (I-10). `fixed_r` targets are plan-derived (Trading layer); `structural_tp2` places a TARGET role on a MKT-L01 level. Multipliers are in R. |
| D2-4 | TRS-04 contract value is `resting_order`; `approval_bar_legacy` is a legacy value with an I-6 divergence (F-110). |
| D2-5 | An outcome's identity carries its walk, its basis (gross / net) and, for net, its cost model (I-15). |
| D2-6 | The exit schedule (partial fractions, stop management after TP1), fills, position lifecycle and approval are Decision/Execution — slice 3. |
| D2-7 | Trade intent (`liq_sweep`, `pullback`, `breakout`, `reversal`) is an identity-bearing parameter of TRS-06 target 1, not a concept. |
| D2-8 | Slice 2 is implemented by Grok and reviewed by Claude; no separate audit (user). |

## 14. Slice 3 — Decision/Execution layer (user decisions 2026-10-02)

Concept contracts DEX-01…09: position_size, portfolio_admission, fill, approval, position,
exit_schedule, exit_rule, carry, position_result. Order of one position: plan → size → admission →
fill → approval (before the fill under `approval_bar_legacy`, after it under `resting_order`) →
position under its schedule and rules → carry → result.

| Id | Decision |
|---|---|
| D3-1 | **D2-2 settled as a policy, not a rule.** DEX-07 `on_invalidation ∈ {hold, close_on_invalidation, close_on_origin}` is identity-bearing. The TRS-03 invalidation is always recorded on the thesis, whatever the value. The active engine is `close_on_origin` (SEM-021, `after_resting_fills`). No value carries an economic claim. The TRS-03 divergence now reads `decided_in: slice_3`. |
| D3-2 | Scope: the core seven concepts plus overnight carry (DEX-08) and portfolio admission (DEX-02). |
| D3-3 | A night is a broker-server rollover: each later broker date with bars, up to the exit bar's date. The triple-swap weekday comes from the swap calibration; if swap or that weekday is unmeasured and a night is crossed, carry is None, never 0. |
| D3-4 | A plan over a portfolio cap is FILTERED (`portfolio_cap`), never trimmed. A filter or a position close ends only that plan or position; the thesis keeps its own lifecycle. |
| D3-5 | Caps: `max_concurrent_positions` and `max_open_risk` (a fraction of equity). One thesis may found several positions, and they may overlap. |
| D3-6 | Risk is a fraction everywhere in the contract; percent-valued settings are recorded divergences (F-111). `PortfolioAllocator` is not called: it trims risk and sizes from confidence, a different meaning (recorded on DEX-02). |
| D3-7 | DEX-09 `walk ∈ {bar_replay, broker_fills}` keeps backtest and live results apart (F-010, F-103). A `bar_replay` result under `hold` with no TTL must equal `multi_tp_walk` with the same exit schedule. |
| D3-8 | Slice 3 is implemented by Claude, by user decision (2026-10-02, "You implement"), as a one-slice exception to O-5 like slice 1's fixes. Same brief, same rules. |

Amendment A-10 (§6): an optional `decided_in` + `resolution` on a divergence records a settled
deferral; only `decide_in` counts as open (V-16).
