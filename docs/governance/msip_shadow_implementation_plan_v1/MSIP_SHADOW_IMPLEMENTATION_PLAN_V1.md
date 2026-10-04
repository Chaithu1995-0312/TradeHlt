# MSIP Shadow Implementation Plan V1

**Plan version:** 1.1.0  
**Task class:** OBSERVATION_ONLY  
**Implementation authorized:** **False**  
**G-IMPL-01:** NOT_PASSED — READY only after separate explicit owner authorization  
**G-PLAN-01 review:** PASS — see `G_PLAN_01_REVIEW_V1.json`  
**Machine authority:** `MSIP_SHADOW_IMPLEMENTATION_PLAN_V1.json`

## Prerequisite (CONFIRMED)

- `DECISION_C = ACCEPTED`
- `MSIP_SHADOW_DESIGN_CONTRACT_V1 = ACCEPTED`
- `G-DESIGN-01 = PASSED`
- `OWNER_STAMP_STATUS = CONFIRMED`

## Architecture binding

```text
GOVERNED WHAT → CONTINUOUS SHADOW INTERPRETATION → MARKET STATE OBSERVATION
→ PROVENANCE + COMPARISON + DISAGREEMENT EVIDENCE

CURRENT CRT remains authoritative opportunity lifecycle
```

This plan maps the accepted design contract to modules, interfaces, insertion points, tests, and rollback — **without coding**.

---

## 1. Module boundaries (proposed; create only after G-IMPL-01 OPEN)

| Path | Role | Boundary |
|------|------|----------|
| `src/msip/` | NEW package root for shadow market-state | no CRT mutator imports; no `EngineState` writes |
| `src/msip/market_state_vector.py` | immutable value object + schema validation | pin `MARKET_STATE_VECTOR_SCHEMA_V1` |
| `src/msip/interpretation_config.py` | strict `msip_shadow` load | fail-closed when enabled |
| `src/msip/shadow_emitter.py` | features → vector + provenance | continuous twins for HOW labels |
| `src/msip/disagreement.py` | optional CRT comparison (read-only) | observational only |
| `src/msip/isolation.py` | import-guard helpers for tests | forbidden-module list |
| `scripts/analysis/run_msip_shadow.py` | batch CLI on frozen corpus | writes under `results/msip_shadow/` only |
| `tests/test_msip_shadow_*.py` | contract suite | see §9 |

**Forbidden at impl:** `StateMachine.try_*` mutation; assign `EngineState`; open trades / emit CRT events as shadow side effects; write `configs/production` or `ACTIVE_VERSION`.

---

## 2. Interfaces

- `build_market_state(bar_features, config, provenance_ctx, crt_obs=None) -> MarketStateVector` — pure
- `emit_jsonl(path, vector) -> None` — append-only under shadow output root
- `observe_crt_state(snapshot) -> CrtPhaseObservation` — pure, read-only; not required for non-observation dimensions
- `load_msip_shadow_config(prod_cfg) -> MsipShadowConfig | Disabled` — fail-closed

---

## 3. Runtime insertion point

**Batch research path**

1. Load frozen OHLCV corpus (Phase-1 XAUUSD binding when instrument=XAUUSD)
2. Run/load FeaturePipeline finalized feature table (authoritative WHAT)
3. Optionally co-run `CRTEngine.process_candle` for observation snapshot only (separate object graph)
4. Per bar with feature row: `build_market_state` → `emit_jsonl`
5. Optionally emit disagreement records
6. Write run manifest

**Live path (if later):** after feature vector available; before/after CRT for observation only; shadow must not gate CRT; CRT must not await shadow.

**Not insertion points:** inside `StateMachine.try_*`; UltronRisk approve as veto; TRADE_OPENED journal as authority rewrite.

---

## 4. Authoritative input sourcing

| Class | Source |
|-------|--------|
| **WHAT** | FeaturePipeline columns; `formula_registry` / market ontology FM ids; `CANONICAL_FEATURES` + schema/order hashes in provenance |
| **HOW** | `msip_shadow` config section only; instrument/TF overrides = label bands / enables only |
| **FORBIDDEN until parity** | CRT-local ATR/EMA; CRT `Candle.body_ratio` / `wick_size` as MSIP `source_features` |
| **CRT observation** | optional post-`process_candle` state name/index; never identity dependency |

---

## 5. Schema / version ownership

- `MARKET_STATE_VECTOR_SCHEMA_V1` — design authority under `msip_shadow_design_v1/`; code validator pins `schema_version`
- `msip_shadow` config — HOW ownership; `config_id` / sha256 on every bar provenance
- Feature schema — `src/features/feature_schema.py` remains WHAT order authority
- `CRTConfig` — **untouched** by this plan

---

## 6. Provenance emission

Contract: `SHADOW_PROVENANCE_CONTRACT_V1`.

Required: schema_version, config_id, config_sha256, feature_schema_hash, feature_order_hash, dimension_sources, HOW label provenance when INTERPRETED_STATE_LABEL_HOW present, continuous_twins_present when labels present.

Incomplete bar → **PARTIAL** — never silent complete.

---

## 7. Shadow isolation

- Flags: `affects_crt=false`, `affects_execution=false`, `affects_events=false`
- Import policy: no CRT mutation imports on shadow emit write path
- CRT co-run instance separate; shadow cannot hold a writable mutator reference

---

## 8. Deterministic execution

- Same corpus sha + config sha + schema version + commit → byte-identical JSONL (DET-01)
- No wall-clock in identity fields (bar timestamps only)
- Stable JSON key ordering

---

## 9. Test strategy

| File | Covers |
|------|--------|
| `tests/test_msip_shadow_schema_validation.py` | schema_version, required fields, field authority classes |
| `tests/test_msip_shadow_what_how_separation.py` | HOW labels need config id + continuous twins |
| `tests/test_msip_shadow_neutrality_vs_crt.py` | CRT action/state identical shadow on vs off |
| `tests/test_msip_shadow_determinism.py` | two-run JSONL equality |
| `tests/test_msip_shadow_crt_phase_not_identity.py` | `crt_state` not required dep of other dims |
| `tests/test_msip_shadow_isolation_imports.py` | static/import guard: no `try_*` from emitter |
| `tests/test_msip_shadow_failure_modes.py` | missing features, PARTIAL, disabled section |

---

## 10. Telemetry

- `results/msip_shadow/{run_id}/market_state.jsonl`
- `results/msip_shadow/{run_id}/run_manifest.json`
- `results/msip_shadow/{run_id}/disagreement.jsonl` (optional)
- No writes to CRT event streams as shadow side effects

---

## 11. Failure handling

| Case | Behavior |
|------|----------|
| config section missing | shadow disabled if optional; if `enabled:true` missing keys → fail-closed at load |
| feature missing | dimension null + PARTIAL; do not invent |
| HOW label without twins | INVALID_HOW / drop label; continuous WHAT still emitted |
| CRT obs unavailable | `crt_phase_observation.observed=false`; other dims unaffected |
| emit I/O failure | log + fail run; never alter CRT objects |
| **never** | wrap CRT in shadow try/except that changes CRT control flow |

---

## 12. Rollout sequence

0. Owner confirmed Decision C + design contract — **DONE**
1. G-PLAN-01 review PASS — **DONE** (this package)
2. Owner stamps plan **ACCEPTED** (separate; not done by review alone)
3. Owner separately authorizes **G-IMPL-01 OPEN** if desired
4. Only then create `src/msip` + tests
5. Shadow run on Phase-1 XAUUSD (or declared subset) under OBSERVATION_ONLY
6. CRT_LOCAL_MATH_PARITY_AUDIT_V1 measurement
7. G-SHADOW-01 evaluation
8. G-MIG-01 remains **CLOSED**

---

## 13. Rollback / removal path

- Disable: `msip_shadow.enabled=false` or omit section
- Code removal: delete/disable `src/msip` + scripts; CRT path unchanged
- Artifacts: historical shadow JSONL retained as evidence; not golden CRT outputs
- CRT rollback not required

---

## 14. Objective criteria to open G-IMPL-01

**All required:**

- `DECISION_C = ACCEPTED`
- `MSIP_SHADOW_DESIGN_CONTRACT_V1 = ACCEPTED`
- `DESIGN_CONTRACT_CONSISTENCY_REVIEW_V1 = PASS`
- `G-PLAN-01 = PASSED`
- `MSIP_SHADOW_IMPLEMENTATION_PLAN_V1 = ACCEPTED` (owner stamp)
- `IMPLEMENTATION_AUTHORIZED` remains separate; default NO until owner sets G-IMPL-01 OPEN
- Plan still declares shadow-only isolation and non-goals
- No CRTConfig threshold program attached to this impl phase

**Not sufficient alone:** G-PLAN-01 PASS without owner plan acceptance; plan acceptance without explicit G-IMPL-01 OPEN.

**When open allows:** create `src/msip`, listed tests, `run_msip_shadow.py`, optional experimental `msip_shadow` config (non-production first).

**When open still forbids:** CRT consumer migration; concurrent candidates; CRTConfig threshold retune as part of MSIP; production behavior change claims.

---

## Non-goals

- production code in this plan artifact
- opening G-IMPL-01 by this document alone
- CRTConfig threshold changes
- concurrent candidates
- EngineRunner binding
- economic optimization
- historical CRT trade-hash golden equality

## Hard stop

This document is a **plan**. G-PLAN-01 PASS does not open production coding. Plan acceptance and G-IMPL-01 OPEN remain separate owner decisions.
