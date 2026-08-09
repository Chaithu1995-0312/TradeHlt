# Phase-2 Design — FM Resolution Through FORMULA_REGISTRY

| Field | Value |
|---|---|
| Status | **IMPLEMENTED** (Option A — 2026-07-11); see `config_authority_matrix.md` §12 |
| Date (UTC) | 2026-07-11 |
| Prerequisite | Phase-1 state contracts certified (`config_authority_matrix.md` §11.4b) |
| Non-goals | Model dispatch · formula changes · threshold moves · automatic `required_fm` execution · fourth YAML |
| Implementation | `src/features/fm_resolve.py` + 4 CRT call sites + `tests/test_fm_resolution_phase2.py` |
| Plan export | `docs/implementation_plan/phase1-state-contract-review-phase2-fm-resolution.md` |

---

## Central question

How can loaded state contracts resolve existing FM identities through `FORMULA_REGISTRY` **without** making `active_models.yaml` a second execution authority?

**Answer (recommended):** contracts authorize/assert dependency **identity**; Python call sites remain the only place that *requests* computation; registry remains the only place that *binds* FM → callable. WHO never runs formulas.

---

## 1. Authority boundaries (frozen for Phase-2)

| Layer | File / component | Owns | Must not own |
|---|---|---|---|
| **WHAT** | `configs/formulas/market_ontology.yaml` | FM id, formula meaning, lifecycle | thresholds, state graph, dispatch |
| **WHAT-exec** | `FORMULA_REGISTRY` / `compute_composition` / `compute_derived` | FM id → callable | control flow |
| **WHO** | `active_models.yaml` `state_contracts` | required_fm / config_key *names* / eligible_models | execution order, formula text, numbers |
| **HOW** | production config / `CRTConfig` | numeric values, flags, paths | FM math |
| **Control flow** | `crt_engine_v2.py` StateMachine | transitions, when to compute | alternate formula definitions |

Forbidden graph:

```text
active_models.required_fm  ──iterate──► auto-execute FORMULA_REGISTRY
```

Allowed graphs:

```text
Python explicit call site  ──► resolve FM id ──► FORMULA_REGISTRY callable
                              ▲
                              └── contract asserts FM ∈ required_fm[current_state] (optional assert)
```

---

## 2. Executable FM call-site census (CRT spine)

Traced from `src/config_layer/crt_engine_v2.py` (current working tree after CH-002/F-050 + Phase-1).

### 2.1 FM-002 `candle_range` (hist. `wick_size`)

| Field | Value |
|---|---|
| Ontology | `primitives.candle_range` · impl `candle_math.candle_range` · lifecycle consumable |
| Registry | `FORMULA_REGISTRY["candle_math.candle_range"]` |
| CRT sites | `Candle.wick_size` property `:111-113` → `_cm.candle_range(high, low)` |
| Consumers | SWEEP size gate (`wick_size` vs `atr_multiplier_min * ATR`); FM-028 inputs; score_breakout ATR multiple |
| States | SWEEP, EXPANSION (via FM-028), scoring |
| Mode | computed on property access; not cached as FM-002 key |
| Config | `atr_multiplier_min` (HOW) |
| Tests | `tests/test_candle_math.py` parity; state contracts require FM-002 on SWEEP |

### 2.2 FM-010 `body_ratio`

| Field | Value |
|---|---|
| Ontology | `feature_compositions.body_ratio` · num/den body_size/candle_range · **no single FORMULA_REGISTRY impl key** · lifecycle consumable |
| Registry path | `compute_composition("body_ratio", o,h,l,c)` or `_cm.body_ratio` (parity-bound primitive composition) |
| CRT sites | `Candle.body_ratio` `:116-118` → `_cm.body_ratio`; TTL would_trade `:2578` → `_cm.body_ratio`; gates via property |
| Consumers | SWEEP→DISPLACEMENT gate; EXPANSION TTL label; soft-conf f_body; cache at RETEST |
| States | SWEEP, EXPANSION, RETEST |
| Mode | property recompute; cached on RETEST as `body_ratio` |
| Config | `body_ratio_min`, `confirmation_body_min` |
| Note | Composition FM — Phase-2 resolver must support composition path, not only FORMULA_REGISTRY flat map |

### 2.3 FM-027 `displacement_retrace`

| Field | Value |
|---|---|
| Ontology | `derived_metrics.displacement_retrace` · impl `derived_math.displacement_retrace` · lifecycle registered |
| Registry | `FORMULA_REGISTRY["derived_math.displacement_retrace"]` |
| CRT sites | `try_expansion_to_retest` cache build `:1385-1389` → `_dm.displacement_retrace(...)` |
| Consumers | `cached_features`; BitNet map key `retest_depth`; soft-conf path via cache |
| States | EXPANSION→RETEST emission; RETEST consume |
| Mode | computed once at retest confirm; cached |
| Config | (inputs from state candles; retest depth gates use *different* CRT-local depth) |

### 2.4 FM-028 `displacement_atr_ratio`

| Field | Value |
|---|---|
| Ontology | `derived_metrics.displacement_atr_ratio` · impl `derived_math.displacement_atr_ratio` · lifecycle registered |
| Registry | `FORMULA_REGISTRY["derived_math.displacement_atr_ratio"]` |
| CRT sites | retest overextension guard `:1360`; cache `:1390-1393` |
| Consumers | gate vs `max_displacement_strength`; cache; BitNet map `disp_strength` |
| States | EXPANSION (gate + emit); RETEST (cache) |
| Mode | computed at retest attempt; cached on success |
| Config | `max_displacement_strength` |

### 2.5 CRT-local (not Phase-2 FM targets)

| Quantity | Why local |
|---|---|
| ATR mean TR | no FM id |
| Range H/L/EQ | no FM id |
| RiskScore 0.35/0.25/0.20/0.20 | hardcoded scoring, not FM |
| soft-conf f_mom / f_disp | not registry FM |
| `min_depth = 0.1 * ATR` | hardcoded gate |
| sweep taxonomy wicks | diagnostic |

### 2.6 EngineRunner CRT scorer (out of Phase-2 SM slice)

`engines/crt_engine.py` → `scoring_engine.compute_scores` uses **pipeline** feature names (`retest_depth`, `disp_strength`) — **not** the CRT state machine. Phase-2 must not conflate the two surfaces.

---

## 3. Architecture options

### Option A — Contract-aware resolution assertions (recommended Phase-2 slice)

```text
existing call site (_cm / _dm)
    → resolve declared FM id for that site (static map in code, or annotation)
    → FORMULA_REGISTRY / compute_composition lookup
    → assert callable is identity-equal (or byte-equal on sample) to current direct import
    → optional: assert FM ∈ state_contracts[current_state].required_fm when state known
    → execute existing path (or execute registry callable if proven identical)
```

| Dimension | Assessment |
|---|---|
| Observation | Call sites already use registry-bound modules; contracts already list required FMs |
| Inference | Lowest migration: proves identity without changing control flow |
| Authority risk | **Low** — WHO only asserts; WHAT still owns math |
| Parity risk | **Low** if assert-then-execute same callable |
| Overhead | Negligible (startup + optional debug asserts) |
| Why fail? | Composition FM-010 has no flat FORMULA_REGISTRY key — needs composition resolver branch |
| Invalidators | Multiple callables for one FM; numerical drift vs `_cm` |

### Option B — Explicit FeatureResolver

```text
CRT call site
    → FeatureResolver.resolve(fm_id, **inputs)
    → contract authorize (state declares FM) [optional hard/soft]
    → FORMULA_REGISTRY / composition
    → return float
```

| Dimension | Assessment |
|---|---|
| Observation | Cleaner long-term API; single choke point |
| Inference | Good **second** step after A proves registry identity |
| Authority risk | Medium if resolver starts “inferring” which FMs to run |
| Parity risk | Medium (input packing / arity differences) |
| Why fail? | Hidden eager caches; wrong inputs; call-order changes |
| Rule | Caller **must** pass explicit FM id + inputs; never “run all required_fm” |

### Option C — Automatic state feature execution

```text
current state → for fm in required_fm: resolve+execute → bag of features
```

| Dimension | Assessment |
|---|---|
| Observation | Matches “dynamic loading” rhetoric but not CRT structure |
| Inference | **High risk** — YAML becomes execution schedule |
| Failure modes | Eager eval; missing inputs for some FMs mid-state; double compute vs cache; order dependence; WHO becomes HOW |
| Recommendation | **Reject** for Phase-2 |

---

## 4. Evaluation summary

| Option | Authority duplication | Parity | Complexity | Recommend |
|---|---|---|---|---|
| A | Low | Best | Smallest | **Yes — Phase-2** |
| B | Low–Med | Good if careful | Medium | Phase-2.1 after A green |
| C | High | Worst | High | **No** |

### Cross-cutting risks (all options)

- **Two-surface CRT:** SM FM cache ≠ EngineRunner feature vector — do not unify blindly.
- **FM-010 composition** needs explicit composition path.
- **Cached lifecycle:** RETEST cache must remain single-write at transition.
- **Neutral market-state future:** keep contracts state-id keyed so a future neutral state layer can host its own contracts without rewriting math.
- **Opportunity cost:** Phase-3 model dispatch is a separate architecture decision (CRTState vs neutral) — do not couple.

---

## 5. Recommendation

```text
PHASE_2_RECOMMENDED_ARCHITECTURE = Option A (contract-aware resolution assertions)
  then optional Option B (explicit FeatureResolver) only after A proves
  registry callable ≡ current direct path on golden vectors.

PHASE_2_REJECTED_ARCHITECTURES = Option C (automatic required_fm execution)
```

**Reason:** A is the smallest semantic migration that still uses loaded contracts + FORMULA_REGISTRY without granting WHO execution authority. C creates a fourth *de facto* execution plane.

---

## 6. Smallest Phase-2 implementation slice (design only)

### Files (expected)

| Path | Change |
|---|---|
| `src/features/fm_resolve.py` (new) | `resolve_fm_callable(fm_id) -> Callable` + composition handling; **no** auto-run-all |
| `src/config_layer/crt_engine_v2.py` | At existing FM sites: resolve + assert identity with `_cm`/`_dm` (or call resolved callable if identical) |
| `tests/test_fm_resolution_phase2.py` (new) | golden float parity; contract membership asserts; negative unknown FM |
| `docs/governance/config_authority_matrix.md` | §12 results after implement |

### Call sites in slice (only these)

1. `Candle.body_ratio` / FM-010  
2. `Candle.wick_size` / FM-002  
3. `try_expansion_to_retest` FM-027 emit  
4. `try_expansion_to_retest` FM-028 guard + emit  

### Failure behavior

- Unknown FM / unbound impl → **fail closed** at construction or first use (tests).  
- Contract missing FM for a site that asserts membership → fail in **test/debug** builds; production default may start as log-only then ratchet (decide at implement).  
- Numerical mismatch vs prior direct path → **STOP** (parity fail).

### Observability

- Optional DEBUG log: `fm_id`, callable qualname, state_id.  
- No new hot-path telemetry required for A.

### Tests

- Positive: FM-002/010/027/028 registry resolution + CRT property parity vectors.  
- Negative: unknown FM; deprecated lifecycle; composition missing num/den.  
- Behavioral: BNBUSDT (+ XAUUSD if available) ledger hash equality PRE/POST Phase-2.

### Rollback

- Single-module resolver + call-site assert wrappers; remove wrappers reverts to current direct imports.  
- No production config keys.

### Must not change

formulas · thresholds · transitions · candidates · model dispatch · trade execution · HOW semantics

---

## 7. Phase-2 stop conditions

STOP implementation if:

1. FM identity cannot map 1:1 to current callable semantics.  
2. One FM id maps to multiple behaviorally distinct implementations.  
3. Existing CRT call sites cannot reconcile with FORMULA_REGISTRY / composition API.  
4. Registry resolution changes numeric outputs.  
5. Resolver introduces eager computation of `required_fm` lists.  
6. Resolver changes cache lifecycle (extra writes/reads).  
7. Resolver changes call ordering with observable effects.  
8. `active_models.yaml` becomes executable formula authority.  
9. Behavior parity fails.  
10. Phase-2 requires model dispatch changes.

---

## 8. Relationship to Phase-1 contracts

| Phase-1 | Phase-2 |
|---|---|
| Declares `required_fm` | Uses declaration to **assert** call-site FM membership |
| Does not execute FM | Still does not auto-execute from list |
| Loader validates FM exists | Runtime uses same registry binding for execution path identity |

`required_fm` remains a **dependency declaration**, not a schedule.

---

## 9. Epistemic notes

**What we know**

- Phase-1 contracts + FM-002/010/027/028 census are executable.  
- Direct `_cm`/`_dm` imports are already the registry callables for primitives/derived.  
- FM-010 is composition-path special.

**What we think**

- Option A will be byte-identical with low effort.  
- Option B is desirable later for readability, not required for authority hygiene.

**What we don’t know**

- Whether production should hard-fail on contract membership violations day-1 or ratchet from soft→hard.  
- Whether EngineRunner CRT scorer should ever share SM FM cache (out of Phase-2 scope).

**Most likely failure mode**

Treating Option B as “iterate required_fm” (slipping into C).

**Highest-leverage next step**

Implement Option A only for the four call sites above; certify ledger parity; then decide soft vs hard contract membership asserts.

---

*End of Phase-2 design. No implementation authorized by this document alone.*
