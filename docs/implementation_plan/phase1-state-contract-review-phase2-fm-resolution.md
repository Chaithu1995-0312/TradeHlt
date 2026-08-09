# Plan: Phase-1 State-Contract Review → Phase-2 Readiness

| Field | Value |
|---|---|
| Status | **APPROVED + PHASE-2 + PHASE-TOPOLOGY IMPLEMENTED** (2026-07-11) — plan exported; FM Option A (§12); Phase-Topology WHO-loaded graph drives SM (§13) |
| Date (UTC) | 2026-07-11 |
| Branch | `feature/truth-registry-v2` |
| Related design | [`docs/governance/phase_2_fm_resolution_design.md`](../governance/phase_2_fm_resolution_design.md) |
| Phase-1 certification | [`docs/governance/config_authority_matrix.md`](../governance/config_authority_matrix.md) §11 |
| Non-goals | Fourth YAML · dynamic executable topology · model dispatch · formula/threshold moves |

---

## Context

Conversation chain (three questions kept separate):

1. **CRT IN→OUT tracing** (raw candles → state machine → trade) — not 38-feature audit.
2. **Ontology authority** — `market_ontology.yaml` is feature math only; CRT states live in Python + descriptive YAML.
3. **Dynamic YAML loading without a fourth file** — reuse the three authorities with clear ownership.

**Phase 1 was subsequently implemented and certified (2026-07-11).** This plan reviews that implementation against the target architecture and sequences the next safe step.

---

## Phase-1 review verdict

**Overall: PASS — ownership boundaries preserved; behavior-neutral; fail-closed validation is real.**

| Intent (conversation) | Implementation | Status |
|---|---|---|
| No fourth YAML | Splice under `active_models.yaml` `crt.runtime.state_contracts` | ✅ |
| Typed runtime objects | `StateContract` + `StateContractBundle` (frozen + MappingProxyType) | ✅ |
| Validation only — no control-flow change | Loader at `CRTEngine.__init__`; `get_state_contract()` inspect-only | ✅ |
| No formula / threshold ownership in WHO | Only `required_fm`, `config_keys`, `eligible_models` (strings/IDs) | ✅ |
| Cross-validate FM vs ontology | `_resolve_fm` → market ontology + FORMULA_REGISTRY / compositions | ✅ |
| Cross-validate config keys vs HOW | Each key must be a `CRTConfig` field | ✅ |
| No `eval` / expression injection | Rejects `=`, operators, spaces; negative tests | ✅ |
| No model dispatch | `eligible_models` identity-checked only (`bitnet` on RETEST) | ✅ |
| Parity | Dual process_candle fingerprint + BNB/XAU isolated PRE/POST ledgers | ✅ certified |

---

## What Phase 1 actually loads and creates

### Source schema (`active_models.yaml` → `crt.runtime`)

```text
state_contract_schema_version: "1.0"
state_contracts:
  <STATE>:
    required_fm: [FM-…]        # WHAT refs only
    config_keys: [field…]      # HOW key names only
    eligible_models: [id…]     # WHO model ids; no dispatch
```

Census-derived contents:

| State | required_fm | eligible_models |
|---|---|---|
| RANGE | [] | [] |
| SHADOW_PENDING | [] | [] |
| SWEEP | FM-002, FM-010 | [] |
| DISPLACEMENT | [] | [] |
| EXPANSION | FM-010, FM-028 | [] |
| RETEST | FM-010, FM-027, FM-028 | bitnet |
| EXECUTION / RESOLUTION / EXPIRED | [] | [] |

Also fixed `cached_features_at_retest` names → FM-027/028/010 emission names (CH-002 alignment).

### Typed objects

| Type | Path | Role |
|---|---|---|
| `StateContract` | `src/config_layer/state_contract.py` | One state: ids only |
| `StateContractBundle` | same | contracts + transitions + source_path |
| `load_and_validate_state_contracts()` | `src/config_layer/state_contract_loader.py` | Fail-closed pipeline |
| `CRTEngine.state_contracts` | `crt_engine_v2.py` ~2186 | Loaded once at construct |
| `CRTEngine.get_state_contract()` | same | Inspection API |

### Fail-closed invariants (loader + tests)

1. Schema version must be `"1.0"`.
2. Contract keys == `CRTState` names (no missing/extra states).
3. `valid_transitions` == code `VALID_TRANSITIONS` (**parity mirror**, not executable graph swap).
4. Every `required_fm` exists in ontology; impl callable (or composition num/den); lifecycle ∈ {registered, parity_verified, consumable}.
5. Every `config_keys` entry is a `CRTConfig` field.
6. Every `eligible_models` entry is a top-level model block in `active_models.yaml`.
7. Unknown fields, numeric literals, formula-looking strings → reject.
8. **No** parallel `STATE_REQUIRED_FM` constants in Python.

Tests: `tests/test_state_contracts.py` (~32 cases) + certification note in `docs/governance/config_authority_matrix.md` §11.4b.

### Explicit non-effects (still true)

- Does **not** replace `_cm` / `_dm` call sites (Phase-1; Phase-2 routes identity-preserving resolve at 4 sites).
- Does **not** auto-execute `required_fm`.
- Does **not** dispatch Gaussian / ZoneGate / RR / BitNet / TradeNet.
- Does **not** change transition branch conditions.
- `use_bitnet` remains HOW (`CRTConfig` / production JSON).

---

## Ownership boundary check (target table vs reality)

| Concern | Authority (target) | Phase-1 reality | Gap? |
|---|---|---|---|
| Feature formulas | `market_ontology.yaml` | FM ids resolved against ontology; no formula text in contracts | ✅ |
| State identities | `active_models.yaml` | Declared + parity-checked vs `CRTState` | ⚠️ Dual: code enum still owns execution |
| Legal transitions | `active_models.yaml` (aspirational) | YAML **mirrored** and validated; **Python `VALID_TRANSITIONS` still executes** | ⚠️ Intended for Phase-1; topology load deferred |
| Detector/guard IDs | `active_models.yaml` | **Not present** in `state_contracts` | Deferred (conversation Phase 3) |
| Required FM IDs | `active_models.yaml` | Loaded + cross-validated | ✅ validation; not runtime assert-at-call-site yet |
| Required config keys | production config values + key names in WHO | Key names validated vs `CRTConfig` | ✅ validation; values still HOW |
| Runtime thresholds | production config | Untouched | ✅ |
| Executable SM | Python | Untouched | ✅ |

**Conclusion:** Phase 1 matches the “validation-only typed contracts” design. It does **not** yet make YAML the executable state topology authority — correctly deferred.

---

## Residual risks / DOC_DRIFT (do not mix into Phase-2 code)

### R1 — Duplicate descriptive authority still in `active_models.yaml`

Under `crt.runtime.detection.*` and related blocks:

- Numeric `defaults:` (e.g. `body_ratio_min: 0.70`)
- Prose `logic` / `gate_*` formula strings

These are **not** loaded by the state-contract pipeline, but they remain a drift surface (WHO re-stating HOW + WHAT). Phase-6 cleanup (strip or mark non-authoritative) remains open. Do **not** treat them as runtime truth.

### R2 — Doctrine table lag

`config_authority_matrix.md` §0 still says WHO `Runtime load?` **No**. Phase 1 **does** load `state_contracts` (+ transition parity) at CRT construct. Update should say something like:

> Partial: `state_contracts` + graph parity load at CRTEngine init; narrative/detection blocks still session-only.

### R3 — Dual transition authority

`tests/test_crt_state_invariants.py` and Phase-1 loader both enforce YAML ↔ code parity. Executable graph remains Python. Conversation “Phase 2 = dynamic topology” would invert that — **high blast radius**; only after parity instrumentation is solid.

### R4 — Phase numbering mismatch (conversation vs repo)

| Conversation phase | Repo artifact |
|---|---|
| Phase 1: typed contracts validation | **DONE** (`§11` matrix + loader) |
| Phase 2: dynamic state identity + transition graph | **Not designed as next** → re-label **Phase-Topology** (later) |
| Phase 3: detector/guard IDs | Not started |
| Phase 4–5: FM / config deps | **Partially absorbed into Phase 1 validation** |
| Repo `phase_2_fm_resolution_design.md` | **FM resolution Option A** (assert call-site ↔ registry) — **this is repo Phase-2** |

**Recommendation:** Adopt the **repo’s Phase-2 design** (FM resolution assertions) as the next code step. Treat conversation “dynamic topology” as a **later phase** (Phase-Topology), because:

- Topology swap changes control flow surface area.
- FM Option A is behavior-preserving, uses already-loaded contracts, and proves WHAT↔call-site identity without granting WHO execution authority.
- Auto-running `required_fm` as a schedule is **explicitly rejected** (Option C).

---

## Recommended approach (next work)

### Do now (review close-out — docs)

1. Export this plan to `docs/implementation_plan/` (**this file**).
2. Fix matrix §0 “Runtime load?” DOC_DRIFT (surgical) when implementing Phase-2.
3. Keep conversation phases and repo Phase-2 design **cross-linked** so future sessions don’t re-merge questions.

### Implement next: **Phase 2 = FM resolution Option A** (from existing design)

**Authority rule frozen:**

```text
Python call site  → resolve FM id → FORMULA_REGISTRY / composition
                      ▲
                      └── optional assert: FM ∈ state_contracts[state].required_fm
```

**Forbidden:**

```text
for fm in required_fm: auto-execute   # YAML becomes schedule
eval(yaml formula)
```

#### Files to touch

| Path | Change |
|---|---|
| `src/features/fm_resolve.py` (**new**) | `resolve_fm_callable(fm_id) -> Callable` + composition branch for FM-010 |
| `src/config_layer/crt_engine_v2.py` | At 4 census sites only: resolve + identity assert vs current `_cm`/`_dm` (or call resolved callable if proven identical) |
| `tests/test_fm_resolution_phase2.py` (**new**) | Golden float parity; membership asserts; unknown-FM fail-closed |
| `docs/governance/config_authority_matrix.md` | §12 results after implement |
| `docs/governance/phase_2_fm_resolution_design.md` | Status → IMPLEMENTED when done |

#### Call sites in slice (only)

1. `Candle.wick_size` / FM-002  
2. `Candle.body_ratio` / FM-010 (composition path)  
3. `try_expansion_to_retest` FM-027 emit  
4. `try_expansion_to_retest` FM-028 guard + emit  

#### Reuse existing utilities

- `features.registry.FORMULA_REGISTRY`, `load_ontology`, `compute_composition` / `compute_derived`
- `state_contract_loader._resolve_fm` patterns (or factor shared resolve into `fm_resolve` and call from both loader + CRT — avoid duplicating resolution logic)
- `tests/test_candle_math.py` / derived_math parity vectors as golden baselines
- Phase-1 loader cache for contract membership asserts

#### Parity gate (mandatory)

```text
process_candle dual-run fingerprint unchanged
BNB + XAU static-scorer ledger sha equality PRE/POST
No production config / ACTIVE_VERSION change (hash-neutral)
```

#### STOP conditions (from design §7)

- One FM → multiple distinct callables; numeric drift; eager `required_fm` execution; cache lifecycle change; WHO becomes formula authority.

### Explicitly defer (do not combine)

| Item | Why |
|---|---|
| Dynamic executable `VALID_TRANSITIONS` from YAML | Control-flow rewrite; dual authority flip |
| Detector/guard ID registries | Separate closed Python map; later phase |
| Strip `detection.defaults` / logic strings from am | Phase-6 cleanup; no behavior gain yet |
| Model dispatch from `eligible_models` | Authority ladder; BitNet still HOW-gated |
| Fourth YAML / `market_state_registry.yaml` | Rejected |

---

## Critical files (read before implementing Phase 2)

| File | Why |
|---|---|
| `src/config_layer/state_contract.py` | Contract types / injection guards |
| `src/config_layer/state_contract_loader.py` | Existing FM resolution (factor or wrap) |
| `src/config_layer/crt_engine_v2.py` | Call sites ~111–118, ~1360–1393, engine init ~2186 |
| `src/features/registry/` + `formula_registry.py` | WHAT bindings |
| `configs/formulas/market_ontology.yaml` | FM identity authority |
| `active_models.yaml` `state_contracts` | WHO dependency declarations |
| `docs/governance/phase_2_fm_resolution_design.md` | Approved architecture |
| `docs/governance/config_authority_matrix.md` §11–§11.6 | Phase-1 certification baseline |
| `tests/test_state_contracts.py` | Regression floor for WHO load |

---

## Verification

### Phase-1 review (read-only confirm anytime)

```text
pytest tests/test_state_contracts.py tests/test_crt_state_invariants.py -q
# expect: all green; load_and_validate_state_contracts() succeeds
```

### Phase-2 implementation gate

```text
pytest tests/test_fm_resolution_phase2.py tests/test_state_contracts.py tests/test_candle_math.py -q
# dual process_candle fingerprint
# optional: backtest_v2 BNB + XAU --scorer static → sha-equal trades/summary to Phase-1 cert hashes in matrix §11.4b
```

### Construction protocol (when coding)

- Classify vs `change_contracts.json` (architecture / feature binding; no HOW numbers).
- Manifest + `construction_protocol.py validate-completion` if governed surfaces change.
- SESSION LOG + doc sync (matrix §12) same turn.

---

## Success criteria for this review task

1. Phase-1 ownership boundaries documented as **preserved**.  
2. Residual risks (R1–R4) listed without conflating CRT-trace / ontology / dynamic-load questions.  
3. Next code step = **FM resolution Option A**, not topology rewrite or fourth YAML.  
4. Dynamic topology + guard registries remain **later**, parity-gated phases.

---

## Epistemic close (aligned with conversation)

| | |
|---|---|
| **Know** | CRT runs on raw candles + Python SM + config thresholds; Phase-1 contracts load WHO deps fail-closed without changing behavior. |
| **Think** | Three-file authority is sufficient; Option A is the highest-leverage next step. |
| **Don’t know** | Soft vs hard fail on call-site contract membership day-1; full consumer readiness for stripping descriptive defaults. |
| **Likely failure** | Merging topology + FM + guard + cleanup into one patch. |
| **Next** | Implement Phase-2 Option A per design doc after plan approval. |

---

## Approval record

| Item | Value |
|---|---|
| Approved by | User |
| Date | 2026-07-11 |
| Comment | Approved; export plan into repo markdown |
| Export path | `docs/implementation_plan/phase1-state-contract-review-phase2-fm-resolution.md` |
| Approved next code step | Phase-2 FM resolution Option A (not topology rewrite) |
