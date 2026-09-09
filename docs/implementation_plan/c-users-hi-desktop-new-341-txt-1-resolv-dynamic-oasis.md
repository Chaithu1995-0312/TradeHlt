# CRT Semantic Authority — constructor-neutral identity (PR-1)

## Context

`docs/implementation_plan/crt-state-identity-ontology-2026-09.md` (Grok, Draft, user decisions
2026-09-02 locked) solves **one authority for the CRT noun**. Your reading of it is that its real
direction is not "Resolver or Engine?" but **CRT exists independently of both** — Engine, Resolver,
and any future constructor become interchangeable implementations of one CRT semantic authority,
and the binding question is *what semantic metadata must every CRT state expose?*

The design as written cannot express that. Its `StateDefinition` is **engine-shaped**:
`handler: process_range`, `dispatch: state_eq`, `htf_protected`, `records_entry_index`,
`records_entry_timestamp`, `ends_expansion_telemetry_on_enter`, `creates_shadow_on_htf_reset`,
`reset_telemetry: displacement_age`, `ttl_kind`. Those are facts about `crt_engine_v2`'s
implementation, not about what a CRT state *is*. Authored into identity, identity becomes "the
engine, in YAML": the resolver could never satisfy it and a third constructor is born
non-conformant. That is the one thing this plan changes.

Two directives from you are carried through:

1. **Resolver = Runtime is the long-term direction.** The layer is designed so a constructor can be
   swapped, and the resolver is registered as a real constructor with a measured capability gap —
   not as a permanent diagnostic (design KD-8 is reframed, see below).
2. **88.16% parity ≠ same construction, and 88.16% is acceptable.** F-069 is not reversed and is not
   treated as a defect to close. It becomes what it actually is: evidence that two constructors of
   one identity differ — which is *why* identity must be constructor-neutral.

**Load-bearing fact you should have before driving toward Resolver = Runtime:** parity is not the
blocker. `_continuous_gates_pass` fail-closes `EXECUTION` when `raw.get('score'/'risk_score'/
'crt_score')` is `None`, and none of those three keys exist in `CANONICAL_FEATURES`
([crt_state_resolver.py:1302](src/features/crt_state_resolver.py:1302),
[crt_semantic_parity_report.md:100](reports/crt_semantic_parity_report.md:100)). The resolver emits
**0 EXECUTION / 0 RESOLUTION on any real vector, by construction**, and has no entry/SL/TP geometry
at all. Accepting the parity gap does not touch either. This plan records that as a typed, machine-
checked capability gap rather than prose, so the path to runtime is measurable.

Authority: none granted. No G001, no promotion, no live rail, no CRT re-closure, no finding flip,
`market_reality_v1.yaml:crt_state.enabled` stays `false`. Hash-neutral (no `params` edit).

---

## The architecture

```
CRT Identity        constructor-neutral semantics — existence, order, topology,
                    classification, occupancy semantics, capability declarations
      ↓
CRT Model           loaded, frozen, queryable (PR-2)
      ↓
CRT Constructors    engine | resolver | future — each a namespaced binding block
      ↓
CRT Occupancy       per-bar state series, comparable across constructors
```

`RANGE`, `SWEEP`, `DISPLACEMENT`, `EXPANSION`, `RETEST`, … belong to **CRT Identity**, not to any
constructor. The repo already has the word for the bottom edge: `CRTConstructionTrace`
([crt_construction_trace.py](src/runtime/crt_construction_trace.py)) already emits both
constructions per bar and joins them.

### Answer to "what semantic metadata must every CRT state expose?" — three tiers

**Tier 1 — semantic core** (`identity.states.<NAME>`). True regardless of who constructs it; every
constructor must agree. Nothing here names a Python symbol or a construction step.

| Field | Why it is neutral |
|---|---|
| `id` / `name` / `sem_id` | identity handle (`CRT-S-*` local to this file; no `CRT-S-*` in the ontology namespace) |
| `timeframe_role` · `subgraph` | `parent_timeframe`\|`execution_timeframe`; F-075 disjointness, refuses the RANGE/RANGE_C1 collapse |
| `occupancy_class` | `ground`\|`event`\|`memory`\|`trade`\|`archive` — what kind of occupancy this is |
| `is_ground` · `requires_memory` · `is_cycle_reset` · `is_one_bar_archive` · `self_loop_legal` | shape of the occupancy, not how it is reached |
| `can_emit_signal` · `can_emit_bias` | **capability declaration** — what an occupancy of this state *authorizes*. This is precisely what a constructor must be able to honor, so it belongs to identity, not to the engine |
| `description` · `notes` · `epistemic` · `lifecycle` · `knowledge_status` | meaning + evolution ladder (`PRODUCTION_CERTIFIED`/`STABLE` forbidden — no G001 here) |

**Tier 2 — constructor bindings** (`identity.constructors.<c>.states.<NAME>`). How one named
constructor reaches and handles that state. All of the design's engine fields move here verbatim —
same names, same values, different home.

- `engine`: `dispatch`, `handler`, `htf_protected`, `htf_protect_via_active_trade`,
  `creates_shadow_on_htf_reset`, `records_entry_index`, `records_entry_timestamp`,
  `ends_expansion_telemetry_on_enter`, `reset_telemetry`, `reset_target`, `ttl_applies`, `ttl_kind`
- `resolver`: `defined` (9 of 12), `predicate_source: configs/formulas/market_crt_states.yaml`,
  `sticky`, `reachable`, `unreachable_reason` (EXECUTION/RESOLUTION → the score-feature gate, cited)

**Tier 3 — constructor capability contract** (`identity.constructors.<c>.capabilities`). This is the
Resolver = Runtime ledger, in the file, mechanically checked:

```yaml
produces_occupancy: true
produces_memory: true
covers_states: [...]           # ⊆ state_list
reaches_signal_state: bool     # can it ever occupy a can_emit_signal state?
produces_trade_geometry: bool  # entry / SL / TP
runtime_eligible: bool
blocking_gaps: []              # non-empty ⇒ runtime_eligible MUST be false
```

Engine: all true, `blocking_gaps: []`. Resolver: `reaches_signal_state: false`,
`produces_trade_geometry: false`, `runtime_eligible: false`, with two named gaps citing source.
The gap list is the roadmap; the test makes it impossible to declare the resolver runtime-eligible
by prose alone.

### The third graph becomes a typed delta, not a rival

Identity owns **one** `valid_transitions` (the engine graph — no `SHADOW_PENDING → EXPANSION`).
Each constructor may declare `projection_allowances`: typed, ratcheted deltas of the one graph.
The resolver's extra edge moves from "an untyped rival graph in another file" to
`constructors.resolver.projection_allowances[0]`, with its existing per-bar-exit-state
justification. Mirrors the stale-pin ratchet already in
[test_crt_states_yaml_transition_parity.py](tests/test_crt_states_yaml_transition_parity.py) —
that floor keeps running unchanged and stays the genuinely independent cross-file guard.

### What this does not change

The generator stays mechanical and untouched by Tier 2/3: it reads only
`identity.{state_list,valid_transitions,parent_timeframe_states}` — the `constructors:` block is
invisible to it. So PR-3 (source migration) remains exactly as the design specifies.

---

## Deliverables (PR-1 — declaration only, no runtime, no engine change)

### 1. Revise the design document
[docs/implementation_plan/crt-state-identity-ontology-2026-09.md](docs/implementation_plan/crt-state-identity-ontology-2026-09.md)

- **Overview / Architecture / mermaid**: insert the Identity → Model → Constructors → Occupancy
  layer; Engine and Resolver both become constructors of one authority.
- **§1 Closed vocabularies / §3 StateDefinition / §4 12-state example / §9 JSON Schema**: re-partition
  into the three tiers. Field *names and values* are preserved; only their home moves.
- **§7 CRTModel**: queries split — `model.definition(state)` (neutral) vs
  `model.binding("engine", state)` (constructor). Add `model.capabilities(c)` and
  `model.constructors()`.
- **Alternatives**: add **(I) constructor-neutral identity — CHOSEN**; keep A–H, mark (C) as
  superseded on its "dual identity" half.
- **KD-8 reframed**: resolver is a *registered constructor, not currently runtime-eligible*, with
  named gaps — not "diagnostic only, forever". Record explicitly that this reverses the draft's
  framing on user direction (2026-09-03), that F-069 itself is **not** reversed, and that no
  authority moves. Preserve the old text as `SUPERSEDED` (§6.2 rule 4).
- **KD-9 refined**: the 17-site map is a `constructors.engine` binding table; PR-4/PR-5 read
  `model.binding("engine", s).*`.
- **New KD-18** metadata partition (Tier 1/2/3) · **KD-19** projection allowances as typed deltas ·
  **KD-20** capability contract + `blocking_gaps ⇒ not runtime_eligible`.
- **PR plan**: PR-1..PR-7 renumbered only where the constructor split changes them (PR-4/PR-5 read
  bindings; PR-6 becomes "register the resolver's binding + allowances", not "nest under
  `resolver:`").

### 2. `configs/formulas/crt_state_identity.yaml` (new)
Document root **exactly** `{ identity: <schema> }` (locked user decision 1; the missing-`identity`
fail-close is the firewall against the generator being pointed at the resolver file). All 12 states.
Engine bindings transcribed from measured behaviour at the sites listed below; resolver bindings
transcribed from [market_crt_states.yaml](configs/formulas/market_crt_states.yaml) `states:` +
[crt_semantic_parity_report.md](reports/crt_semantic_parity_report.md). Nothing invented.

Engine binding source sites (already measured, do not re-derive):
`crt_engine_v2.py` `:1036` `:1038` `:1043` (entry index / timestamp / expansion-telemetry-end),
`:1859` `:1880` (reset telemetry — `displacement_age` vs `candidate_age`, mutually exclusive),
`:1894` (shadow create), `:2580` (HTF-protect set), `:2960` `:3066` `:3126` `:3163` `:3168` `:3257`
(6 occupancy branches); `parent_crt.py` `:108` `:123` `:133` `:142`. Total 17.

### 3. `src/config_layer/crt_identity_schema.py` (new — validator only)
`validate_crt_identity(doc) -> None`, raising `CRTIdentityError`. No loader wiring, no `CRTModel`,
**not** called from `CRTEngine.__init__` (design KD-16 — an unused hold must not take down
production). Reuse the fail-closed idiom and `_load_yaml` pattern from
[state_contract_loader.py:54](src/config_layer/state_contract_loader.py:54); do **not** add a second
loader family and do **not** route through `features.registry.load_ontology` (null-is-a-trap) or the
fail-open Semantic OS loader (design KD-11).

### 4. `tests/test_crt_state_identity.py` (new floor)
- schema / closed vocab / partition / parent↔execution disjoint-edge enumeration
- **neutrality lint** — no Tier-2 field name may appear under `identity.states.*` (this is what
  mechanically prevents identity drifting back into being engine-shaped)
- `state_list` ≡ generated `CRTState` names **and order**; `valid_transitions` edge-set ≡
  `VALID_TRANSITIONS`; `parent_timeframe_states` ≡ `PARENT_TIMEFRAME_STATES`
  ([_crt_state_generated.py](src/config_layer/_crt_state_generated.py))
- identity ≡ `active_models.yaml:crt.runtime` (still the generation source until PR-3)
- forbidden anywhere under `identity.states.*`: `when` `condition` `formula` `eval` `code`
  `thresholds` `required_fm` `config_keys` `eligible_models`
- identifier-only injection guard (`description`/`notes`/`epistemic` exempt — `(F-074)` must pass;
  `handler: "abs(close-open)"` must fail)
- resolver `covers_states` ⊆ `state_list` (9 ⊆ 12); resolver cannot invent a 13th state
- `SHADOW_PENDING → EXPANSION` **absent** from `identity.valid_transitions`, present exactly once
  as a resolver projection allowance; stale-allowance ratchet
- `blocking_gaps` non-empty ⇒ `runtime_eligible: false`; exactly one constructor is runtime-eligible
- `knowledge_status` excludes `PRODUCTION_CERTIFIED` / `STABLE`; `handler` ∈ planned allowlist or null

### 5. `configs/formulas/market_ontology.yaml`
`semantic_registry.sections += crt_states` — **section name only, zero nodes** (locked user decision
3). No `CRT-S-*` in the ontology namespace, no invented `SEM-*`, frozen keys untouched.

### 6. Governance close-out
`📝 SESSION LOG ENTRY` → `assistant_project.md` (§6/§7.4). Doc-drift decisions for FileIdentity
`crt.state_topology`, CN-004, BD-006 and the `crt_construction_trace.py` "declarative MEANING layer"
docstring are **classified and recorded, not applied** — they stay PR-7, after PR-3 makes the cited
owner true. No finding is added or flipped in PR-1 (nothing was measured).

---

## Verification

```bash
cd /d/Tradelatest && python -m pytest tests/test_crt_state_identity.py tests/test_crt_state_invariants.py tests/test_crt_state_generated_parity.py tests/test_crt_states_yaml_transition_parity.py tests/test_crt_states_yaml_state_names.py tests/test_state_contracts.py tests/test_semantic_registry.py -q
```

```bash
cd /d/Tradelatest && python scripts/maintenance/gen_crt_state_identity.py --check
```

Expected: all green; `--check` OK **unchanged** (PR-1 does not touch the generator or its source).

Behaviour gate — `PRODUCTION_BEHAVIOR_CHANGED = NO`, proven structurally rather than by a backtest:
no file under `src/` outside the new validator module is edited, no production config is touched, no
`params` block changes (config hash unchanged), and `_crt_state_generated.py` is byte-identical. If
any of those four is false, the change has left PR-1 scope.

Negative check to run explicitly (the neutrality lint is the point of this PR): move `htf_protected`
from `constructors.engine` into `identity.states.EXPANSION` and confirm the floor **fails**.
