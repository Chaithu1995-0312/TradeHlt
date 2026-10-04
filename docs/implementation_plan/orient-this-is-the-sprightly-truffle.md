# CRT Resolver Layer — File Trace, Design Review, and the `constructor_id` Field

> Semantic-authority lane. Read-only understanding + one designed field.
> **No measurement, no results, no G001, no production change.**

---

## Context

The 2026-09-03 constructor-neutral revision (PR-1, shipped) declares Engine and Resolver as
peer **constructors** of one CRT identity, with occupancy as their comparable output. An
inbound multi-LLM proposal suggested "just run the resolver on XAUUSD and look at dwell"
before designing further.

Reproducing that proposal against source showed the observation is not missing — it has been
made at least twice, with **incompatible answers**, and the layer that is supposed to hold
such answers cannot tell the two apart. So the useful deliverable is not a run. It is:

1. a **file trace** of the resolver flow, so the layer is legible as a whole;
2. a **design review** naming what each file is authoritative for and where the seams are;
3. a designed **`constructor_id`** field (user decision) that makes two constructions of the
   same identity distinguishable — flagged, because it touches a FROZEN contract.

**Grounding facts established this session (all source-verified):**

- `logs/bar_structure/XAUUSD_bar_structure.jsonl` carries **no canonical feature vector**
  (LIVE record: OHLCV + `atr_abs` + engine CRT internals + 48 SMC fields). It is *engine
  occupancy*, not resolver input.
- Resolver occupancy already exists: `reports/crt_state_fresh_run_xauusd.md` (2026-08-05,
  47,197 bars) — `RANGE 39,308 / SWEEP 6,213 / EXPANSION 1,125 / DISPLACEMENT 240 /
  SHADOW_PENDING 254 / RETEST 57 / EXECUTION 0 / RESOLUTION 0 / EXPIRED 0`.
- A second resolver series exists: F-086 `crt_state_resolved` —
  `RANGE 21,745 / SWEEP 15,186 / EXPANSION 7,092`. **17,563-bar RANGE divergence, mechanism
  UNATTRIBUTED.**
- `PRODUCER_IDS = frozenset({"engine", "resolver"})` is already frozen
  ([`src/identity/tokens.py:17`](src/identity/tokens.py:17)), and across all 8 certified
  corpora (197,564 L3 occupancy rows) **100% are `producer_id: "engine"`**. The resolver
  slot is declared, admissible, and empty.

---

## Part A — File trace of the resolver flow

### A1. The construction path (corpus → occupancy)

| # | File | Role in this flow |
|---|---|---|
| 1 | `data/mt5/XAUUSD_M15.csv` | L0 corpus. 47,275 raw M15 bars. |
| 2 | [`src/features/feature_pipeline.py`](src/features/feature_pipeline.py) | Builds the canonical vector **and** the non-vector intermediates the resolver needs: `rsi_state` (:596), `displacement_flag` (:1009), `retest_flag` (:1030). Drops 78 warmup bars → 47,197. |
| 3 | [`src/features/feature_schema.py`](src/features/feature_schema.py) | `CANONICAL_FEATURES` — the vector contract. **Does not contain `score` / `risk_score` / `crt_score`** (this is GAP-RESOLVER-001's root). |
| 4 | [`src/features/feature_states.py`](src/features/feature_states.py) | `FeatureStateEncoder.classify()` — continuous → discrete feature states. Binning authority = `market_ontology.yaml`. |
| 5 | [`configs/formulas/market_ontology.yaml`](configs/formulas/market_ontology.yaml) | §6.6 semantic authority for feature identity/binning. Upstream of every resolver predicate. |
| 6 | [`configs/formulas/market_crt_states.yaml`](configs/formulas/market_crt_states.yaml) | **The resolver's own construction authority.** `feature_states` (15), `states` (9, each `name/description/requires_memory/when/notes`), `valid_transitions` (12), `thresholds` (19 incl. `sweep_geometry`, `range_atr_period`, `score_threshold: 0.45`, and a nested `lifecycle` block). |
| 7 | [`configs/formulas/crt_resolver_links.yaml`](configs/formulas/crt_resolver_links.yaml) | Variant registry: `links` = LINK-001/002/003, `variants` = `base`, `max_live_variants: 8`. Rewrites which `when:` clauses survive. |
| 8 | [`src/features/crt_state_resolver.py`](src/features/crt_state_resolver.py) | The constructor. 1,849 lines. |
| 9 | `resolver.resolve()` / `resolve_batch()` | Per-bar state name → the occupancy series. |

### A2. Inside the resolver (the parts that decide occupancy)

| Concern | Location |
|---|---|
| Construction surface | [`:226-276`](src/features/crt_state_resolver.py:226) `__init__(config_path, ontology, *, variant, links, links_config_path, allow_missing_when_features)` |
| Variant resolution | [`:965-1000`](src/features/crt_state_resolver.py:965) `_resolve_enabled_links` — **default is every link OFF**; `variant` and `links` mutually exclusive by design |
| Clause filtering | [`:1002-1016`](src/features/crt_state_resolver.py:1002) `_apply_link_filter` rewrites each state's `when` in place |
| Supply contract | [`:1018-1096`](src/features/crt_state_resolver.py:1018) `_compute_required_when_features` / `_resolve_waivers` / `_missing_supply_message` — exists because an absent non-vector feature used to make a state silently never fire |
| Per-bar entry | [`:413-450`](src/features/crt_state_resolver.py:413) `resolve(features, timestamp, *, htf_id, force_reset, reset_reason, engine_reset, engine_state_to)` |
| Batch entry | [`:626-644`](src/features/crt_state_resolver.py:626) `resolve_batch` — sequential, memory carried |
| **Injection kwargs** | `engine_reset` / `engine_state_to` — "research-shadow only"; they put the *engine's* answer inside the resolver's decision |
| Continuous gates | [`:1268-1313`](src/features/crt_state_resolver.py:1268) `_continuous_gates_pass` — **fail-open by default**, with EXECUTION as the one fail-closed exception ([`:1305-1311`](src/features/crt_state_resolver.py:1305)) |
| Per-state entry funnels | `_sweep_entry_allowed` (:1315), `_displacement_entry_allowed` (:1406), `_expansion_entry_allowed` (:1480) |
| Lifecycle / resets | `_apply_lifecycle_resets` (:669), `_check_session_gap` (:729), `_advance_htf` (:746), `_force_range_reset` (:778), `_tick_shadow_ttl` (:832) |
| HTF phase-lock | [`:1791-1835`](src/features/crt_state_resolver.py:1791) `build_htf_id_timeline` — its docstring states that omitting it inflates SWEEP↔RANGE off-diagonal cells via warmup/index phase drift |

### A3. Callers (13 in `src/` + `scripts/`)

| File | What it does with the resolver |
|---|---|
| [`scripts/research/run_crt_state_on_mt5_xauusd.py`](scripts/research/run_crt_state_on_mt5_xauusd.py) | **Path A, already run.** Default `CRTStateResolver()`, phase-locked, supplies `CANONICAL ∩ columns` + `retest_flag` + `displacement_flag` (:100-104, :128). Produced the 39,308 series. |
| [`scripts/research/build_bar_matrix.py`](scripts/research/build_bar_matrix.py) | F-086's producer. `create_resolver()`, phase-locked, supplies **every** enriched column via `to_dict("records")` (:160) incl. `rsi_state` (`_NON_VECTOR_STATE_INPUTS`, :76), `resolve_batch` (:209). Produced the 21,745 series. |
| [`src/runtime/crt_construction_trace.py`](src/runtime/crt_construction_trace.py) | Engine⊕resolver per-bar join. Calls `resolve()` **after** `process_candle` (:317). Config section exists **only** in `v4_dual_construction_2026_09.json`; `ACTIVE_VERSION` is `v2_htfcrt_2026_08`; defaults `enabled: false`; **no trace JSONL exists on disk**. |
| [`src/runtime/backtest_v2.py`](src/runtime/backtest_v2.py) | Hosts the trace emitter. |
| `scripts/research/crt_parity_{report,sweep,classifier}.py`, `crt_state_confusion_matrix.py`, `validate_crt_state_resolver.py`, `crt_range_rebuild_probe.py`, `crt_resolver_economic_comparison.py` | F-069 program surface. |
| `scripts/analysis/crt_threshold_authority_census.py`, `scripts/governance/build_g001_consumer_attribution.py`, `scripts/maintenance/gen_crt_state_identity.py` | Governance readers. |
| Tests | `tests/governance/test_crt_predicate_supply_contract.py`, `test_crt_resolver_links.py`, `tests/test_crt_state_resolver_{gate_parity,sweep_geometry,displacement_gate,b1h_polish}.py`, `tests/Grok/test_C_parity.py` |

### A4. The identity + storage layer the occupancy would land in

| File | Role |
|---|---|
| [`configs/formulas/crt_state_identity.yaml`](configs/formulas/crt_state_identity.yaml) | PR-1. `identity.{schema,version,authority,generated_artifact,generator,state_list(12),parent_timeframe_states(3),valid_transitions(12),states(12×18 fields),constructors{engine,resolver}}`. |
| [`src/config_layer/crt_identity_schema.py`](src/config_layer/crt_identity_schema.py) | Validator + neutrality lint. `_TIER1_FIELDS` (18, closed, :70), `_ENGINE_BINDING_FIELDS` (:77), `_RESOLVER_BINDING_{REQUIRED,OPTIONAL}` (:85-87), `_FORBIDDEN_IN_TIER1` (:92), bidirectional `blocking_gaps ⇔ runtime_eligible` (:368-376), projection-allowance rules (:379-399). |
| [`src/identity/tokens.py`](src/identity/tokens.py) | `PRODUCER_IDS = {"engine","resolver"}` (:17), `L0_PK` (:41), `L3_OCC_EXTRA = (producer_id, topology_id, track_id, state)` (:45). |
| [`src/identity/store.py`](src/identity/store.py) | PK assembly (:31): `L0_PK + (producer_id, topology_id, track_id)`. |
| [`src/identity/certify.py`](src/identity/certify.py) | Writer. `topology_id = sha256(VALID_TRANSITIONS)` (:238-240); `producer_id` hardcoded `"engine"` (:316, :350). |
| [`src/identity/check.py`](src/identity/check.py) | Identity Check; validates `producer_id` against the closed set (:183) and `topology_id` against the stored topology snapshot (:205). |
| `results/identity_cert/*/records/L3_OCCUPANCY.jsonl` | 8 corpora, 197,564 rows, **100% `engine`**. |

---

## Part B — Design review of this layer

**B1. The resolver is a second, independently-parameterized state machine — not a lookup.**
It carries its own memory (`CRTStateMemory`), TTLs, HTF clock, session-gap resets, sticky-dwell
ages, and per-state entry funnels. "Declarative" describes where its thresholds live, not how
much machinery it runs. This is why F-069's residual is 96.1% *Category C — divergent
construction*, and why its determination was **structurally config-unreachable**.

**B2. Its authority boundary is clean; its identity boundary is not.**
`market_crt_states.yaml` is unambiguously the resolver's construction authority, and
`crt_state_identity.yaml` is unambiguously the semantic authority above it — the generator
refuses at file level to point at the resolver's own YAML
([`gen_crt_state_identity.py:8-17`](scripts/maintenance/gen_crt_state_identity.py:8)). That
separation holds. What does **not** exist anywhere is a name for *which parameterization of
the resolver produced a given occupancy series*.

**B3. The parameterization surface is large and entirely un-named.**
Construction-time: `config_path` content (19 thresholds incl. `sweep_geometry` ∈
{`htf_range`,`pipeline_swing`} and the nested `lifecycle` block), `links_config_path`,
`variant` / `links` (default: **all off**), `ontology`, `allow_missing_when_features`.
Call-time: the **supply set** the caller passes, the `htf_id` source, `force_reset`, and the
two injection kwargs. Every one of these moves occupancy. None is recorded on the output.

**B4. The two existing series are the demonstration, not an anomaly.**
Same module, same corpus, same default construction, both phase-locked, neither injecting —
and RANGE differs by 17,563 bars. Two candidate mechanisms, **neither verified**: the supply
sets differ (`CANONICAL ∩ columns` + 2 extras vs. every enriched column incl. `rsi_state`),
and commit `03c3dbf` (F-069 program) touched **both** `crt_state_resolver.py` and
`market_crt_states.yaml` between the two dates. Attribution requires a re-run, not a diff.
Recorded here as UNATTRIBUTED (F-100 discipline).

**B5. The storage layer anticipated constructors but under-identifies them.**
`producer_id` is in the L3 primary key, and `"resolver"` is already admissible. But the
other constructor-shaped PK field, `topology_id`, hashes `VALID_TRANSITIONS` — the identity
**graph**, which both constructors share by construction. So writing both series above as
`producer_id: "resolver"` gives them an **identical primary key**: same instrument,
timeframe, bar, corpus hash, producer, topology, track. One silently displaces or
"preserves" against the other. This is the F-056 / F-079 / F-083 / F-085 silent-gap class —
a skipped distinction indistinguishable from an absent one — sitting inside a CLOSED,
FROZEN v1.0.0 contract.

**B6. Tier 3 is already the right shape for this.**
`blocking_gaps ⇔ runtime_eligible` is enforced bidirectionally in code, and both resolver
gaps carry `independent_of_f069: true`. The capability ledger works. What it lacks is a
subject: it says what *"the resolver"* can do, while the repo contains at least two.

---

## Part C — The `constructor_id` field (designed, not built)

**Purpose.** Make "which construction of this identity produced this occupancy" a first-class,
machine-checked identity, so two resolver series are distinguishable rather than colliding.

### C1. Shape

Add to `identity.constructors.<C>` a declared, closed **parameterization manifest**, and
derive `constructor_id = sha256(canonical_json(manifest))` — the same discipline
`topology_id` already uses, one level lower.

```yaml
identity:
  constructors:
    resolver:
      # ... source / description / projection_allowances / capabilities / states ...
      parameterization:                 # NEW — closed field set, all required
        construction:
          states_config: configs/formulas/market_crt_states.yaml
          states_config_sha256: "<hash of file bytes>"
          links_config: configs/formulas/crt_resolver_links.yaml
          links_config_sha256: "<hash of file bytes>"
          variant: base                 # or null
          enabled_links: []             # resolved set, sorted; default all-off
          ontology_sha256: "<hash>"
          waived_when_features: []      # sorted
        invocation:                     # call-time contract — the half that split the series
          supply_set: canonical_plus_non_vector   # closed vocabulary
          supply_keys_sha256: "<hash of the sorted key list actually passed>"
          htf_source: phase_locked_timeline       # closed vocabulary
          injection: none                         # closed: none | engine_state | engine_reset | both
```

**The `invocation` half is load-bearing and is the part a naive design would omit.** A
`constructor_id` hashing only construction params would give the 39,308 and 21,745 series the
*same* id — the exact failure this field exists to prevent.

### C2. Where it binds

| Surface | Change |
|---|---|
| [`crt_identity_schema.py`](src/config_layer/crt_identity_schema.py) | New `_PARAMETERIZATION_FIELDS` closed set + `_validate_parameterization`, wired into `_validate_engine_constructor` / `_validate_resolver_constructor`. Add `parameterization` to the constructor `_require_keys` set. Closed vocabularies for `supply_set` / `htf_source` / `injection` (mirrors `_DISPATCH` / `_TTL_KIND` style). Reject unknown keys, as Tier 1/2 already do. |
| [`src/identity/tokens.py`](src/identity/tokens.py) | `L3_OCC_EXTRA` / `L3_EVT_EXTRA` gain `constructor_id`. |
| [`src/identity/store.py:31`](src/identity/store.py:31) | PK gains `constructor_id`. **← the frozen-contract change** |
| [`src/identity/check.py`](src/identity/check.py) | Validate `constructor_id` against a stored parameterization snapshot, exactly as `topology_id` is validated against the topology snapshot (:205). |
| [`src/identity/certify.py`](src/identity/certify.py) | Stop hardcoding `producer_id: "engine"` at :316/:350 — take producer + constructor_id from the caller; write the parameterization snapshot alongside `{"topology": topo_bytes}`. |

### C3. ⚠️ FROZEN-CONTRACT FLAG — requires its own authorization

Adding `constructor_id` to the L3 primary key is **not** an additive change:

- `PHYSICAL_STORAGE_ARCHITECTURE.md` and `STORAGE_PRESERVATION_CONTRACT.md` are **CLOSED /
  FROZEN v1.0.0, user-accepted 2026-08-23**. Their reopen policy admits "governed code/config/
  artifact dependencies inside the declared boundary change" — this qualifies, and it is a
  reopen, not a patch.
- **197,564 existing rows across 8 certified corpora re-identify.** Every one currently has
  no `constructor_id`; adding the field to the PK changes their identity. A legacy sentinel
  (e.g. `constructor_id: "legacy-engine-uncharacterized"`) preserves them without fabricating
  a parameterization they never recorded — but that is a governance decision, not a default.
- `RECOMPUTE != RECOVER` (invariant 8) applies directly: re-certifying the 8 corpora to mint
  real engine `constructor_id`s is a *recompute*, and does not recover the original
  provenance.

**Recommended sequencing:** land the YAML + schema half first (Tier-2 `parameterization` +
`constructor_id` derivation + lint), which is purely additive to `crt_state_identity.yaml`
and touches nothing frozen. Treat the `src/identity/` PK change as a **separate, separately
authorized** turn under `REPOSITORY_CONSTRUCTION_PROTOCOL.md`.

### C4. Explicitly out of scope

No occupancy run. No resolver rows written. No attribution of the 39,308 vs 21,745
divergence. No PR-2 `CRTModel`. No re-litigation of F-069. No G001, no promotion, no
`enabled: false` change.

---

## Verification

For the Part-C.2 schema half (the only part proposed for implementation now):

1. `python -c "from config_layer.crt_identity_schema import validate_crt_identity_file; validate_crt_identity_file()"` → returns without raising.
2. `pytest tests/test_crt_state_identity.py -q` → green, including the existing
   `blocking_gaps ⇔ runtime_eligible` and neutrality-lint negative tests.
3. **New negative tests, mirroring the existing lint style:** (a) a `parameterization` block
   missing `invocation` fails closed; (b) an out-of-vocabulary `injection` value fails closed;
   (c) moving `parameterization` into `identity.states.<NAME>` is rejected by
   `_FORBIDDEN_IN_TIER1` (add it to that set — it is a constructor concern, never semantic core);
   (d) two constructors declaring byte-identical manifests derive the same `constructor_id`,
   and changing one `supply_keys_sha256` changes it.
4. `pytest tests/test_identity_store.py tests/governance/ -q` → unchanged (the store is not
   touched in this half).
5. Confirm no runtime drift: `configs/production/ACTIVE_VERSION` still `v2_htfcrt_2026_08`,
   `market_reality_v1.yaml:crt_state.enabled` still `false`, no config hash change
   (`crt_state_identity.yaml` is not a `params` block).
