# L-003 / JSE Architecture Review + FALSIFY Evidence Pack

**Status:** REVIEW_SAVED (docs/governance/research only)  
**version:** `ARCH-REVIEW.v1`  
**run_id:** `arch_review_falsify_pack_20260908_023341`  
**Generated (IST):** 2026-09-08 02:33:41 IST · **UTC:** 2026-09-07T21:03:41Z  
**Branch pin:** `feature/trace-parquet-duckdb-query` @ `d7c25f6e55616261b8b229b000875abd3bd315eb`

Machine-readable pack: `docs/research/reports/l003_jse_falsify_evidence_pack-2026-09-08.json`  
Schemas: `docs/research/reports/schemas/` + `docs/research/reports/SCHEMAS_README.md`

> **Freeze note:** The L-003 package remains **`L003_PACKAGE_FROZEN`** (`L-003-FREEZE.v1`, run_id `l003_package_freeze_20260907_201945`). This document is a **review report + episode/registry extension**. It does **not** reopen L-003 doctrine. Light errata only: wording downgrade path-defined → **path-geometry-associated** in episode docs; Population Registry stub; MeasurementObject mathematical-type fields.

---

## 1. Executive summary

### Identity separation win

The strongest architectural win is identity: **`Y_scanner ≠ Y_oracle`** (HOMONYM). Shared terminal tokens ∈ `OutcomeLabel = {SL_HIT, TP_HIT, TIMEOUT}` are **value-domain only**; same token does not imply same event. MeasurementObjects `Y_scanner`, `Y_oracle`, `Y_joint` are **REGISTERED_IDENTITY** (L-003L/M + MOR) — ontology correction of *what is measured*, not an edge claim.

### FALSIFY stack (what was actually falsified)

| ID | H0 (short) | Result |
|---|---|---|
| **L-003G** | Entry-time anatomy fields → `STATE_SL_TP` membership | **FALSIFIED** (LOIO mean AUC ≈ **0.516**) — **strongest empirical result** |
| **JSE-001** | `engine_state_asof` → `STATE_SL_TP` (BNB) | **FALSIFIED** (AUC ≈ **0.500**) — *not* “CRT falsified” |
| **JSE-002** | `engine_state_asof` → path geometry (BNB) | **FALSIFIED** (macro AUC ≈ **0.50–0.51**) |
| **JSE-003** | `engine_context_history` → path geometry (BNB) | **FALSIFIED** (best macro ≈ **0.515**; binary ≈ **0.522**) |

Observation hierarchy (updated):

> **Entry weak (L-003G) · engine_state_asof weak (JSE-001/002) · engine_context_history weak (JSE-003) · Path geometry strong as Y_joint descriptor (L-003C–E) — as association, not as “path-defined population”**

### User review grades (preserved)

| Axis | Grade |
|---|---|
| Identity | **A** |
| Ontology | **A-** |
| Measurement | **B+** |
| Population | **B** |
| Predictive | **B-** |
| Trading-process | **C+** |

---

## 2. Full user review (clean paraphrase + key equations)

### What the review affirmed

1. **Identity A** — separating scanner/oracle/joint as distinct MeasurementObjects is correct and should stay frozen.
2. **Ontology A-** — four-layer split (ExitProcess / MeasurementProcess / ObservedVariable / Population) and coordinate≠population discipline are right; remaining noun/math gaps keep it from a clean A.
3. **Measurement B+** — L-003G and JSE-001/2/3 are real falsification-oriented measurements with honest scope limits.
4. **Population B** — set notation is present in episode prose, but Ω is still underspecified as a *registered* object; need a Population Registry.
5. **Predictive B-** — predictive work correctly falsified weak predictors; it has not yet produced a supported positive predictive story for `STATE_SL_TP`.
6. **Trading-process C+** — trail/exit-ordering associations (L-003H/I) exist, but process-level explanation of how `STATE_SL_TP` paths are *generated* is still thin.

### Key asks (embedded)

1. **`Y_scanner` / `Y_oracle` need mathematical maps `Ω → Label`**, not only producer refs.
2. **Freeze** Label space `L`, Joint state space `S = L × L`, Population `Ω`, and `Y_joint : Ω → S`.
3. **L-003G is the strongest result** — keep it central in the FALSIFY pack.
4. Downgrade wording **“path-defined” → “path-geometry-associated”** (association with path geometry ≠ definition-by-path).
5. **Need Population Registry** (stub at minimum).
6. **Next episode:** path-generation process for `STATE_SL_TP` population — **observe before predict**.

### Key equations (quoted / locked for this review)

```text
L  := OutcomeLabel = {SL_HIT, TP_HIT, TIMEOUT}     # value domain only
S  := L × L                                           # |S|=9 = Omega_joint / Ic_joint
Y_scanner : Ω → L
Y_oracle  : Ω → L
Y_joint   : Ω → S
Y_joint(x) := (Y_scanner(x), Y_oracle(x))

JointStateCoordinate  s ∈ S
JointStatePopulation  { x ∈ Ω : Y_joint(x) = s }

STATE_SL_TP_anatomy := { x ∈ Ω_anatomy_opportunity : Y_joint(x) = STATE_SL_TP }
```

Producer refs remain necessary but **not sufficient**:

```text
Y_scanner emitted by opportunity_scanner._simulate(...)   # producer
Y_oracle  emitted by forward_walk(exit_model="intrabar_fixed")
# PLUS mathematical type Ω → L / Ω → S on the registry entry
```

---

## 3. Ontology freeze status (objects separated)

Already frozen under L-003L/M + FREEZE (unchanged by this report):

| Object | Status |
|---|---|
| `OutcomeLabel` / `L` | value_domain_only |
| `Y_scanner`, `Y_oracle`, `Y_joint` | REGISTERED_IDENTITY |
| `S = L × L` (`Omega_joint`) | STATE_SPACE_FROZEN (9 StateIDs, coordinate-only `STATE_*`) |
| Four layers | ExitProcess / MeasurementProcess / ObservedVariable / Population |
| Coordinate ≠ Population | Leak-2 closed in freeze |
| Attribution / edge | still blocked |

**This pass adds (extensions, not doctrine reopen):**

- Mathematical `formula_map` / `mathematical_type` on MOR Y_* entries
- Population Registry stub (`Ω_anatomy_opportunity`, `Ω_bnb_anatomy`, `STATE_SL_TP_anatomy`)
- Episode wording errata: path-geometry-associated
- Shareable FALSIFY schemas + evidence pack

---

## 4. Remaining noun / math gaps

| Gap | Severity | Mitigation in this pack |
|---|---|---|
| Y_* specified mainly via producer refs | High (user ask #1) | MOR patched with `Ω → OutcomeLabel` / `Ω → S` |
| Ω ambiguity (which rows? which instruments?) | High (user ask #2/#5) | Population Registry stub |
| “path-defined” overclaim after L-003G | Medium (user ask #4) | Episode wording → path-geometry-associated |
| Missing Population Registry | Medium | `POPULATION_REGISTRY.md` + JSON stub |
| Predictive stack is mostly negative results | Expected at B- | Next episode observes path-generation before new predictors |
| Trading-process explanation thin | Expected at C+ | PATH_GENERATION_FOR_STATE_SL_TP |

---

## 5. FALSIFY Evidence Pack

Each record below matches `falsify_record.schema.json` and the JSON pack.

### 5.1 L-003G — entry → Y_joint / STATE_SL_TP

| Field | Content |
|---|---|
| **H0** | Entry-time anatomy fields available before trade completion predict membership in `{x: Y_joint(x)=STATE_SL_TP}`. |
| **MeasurementObject** | Predictor family: entry-time anatomy fields. Target: `Y_joint` → coordinate `STATE_SL_TP`. Maps: `Y_joint : Ω → S`. |
| **Population** | `Ω_anatomy_opportunity` (BNB/BTC/ETH/SOL); n=559,768; base rate 31.5257%. |
| **Join** | Anatomy trade_dataset four-instrument join; CRT/HTF/manipulation unavailable. |
| **Metric** | Primary: LOIO mean AUC. Band: AUC≈0.5–0.55 + null lifts ⇒ FALSIFY. |
| **Result** | **FALSIFIED_on_available_entry_fields**. LOIO mean AUC=**0.5162**; mean top-decile lift=**1.0534**; within mean AUC=0.5146. |
| **Scope limits** | Available entry inventory only; abs prices excluded from LOIO MV; does not falsify unmeasured entry worlds. |
| **Artifacts** | `docs/governance/ANALYTICS_JOINT_STATE_ENTRY_PREDICTABILITY_L003G.md` · `docs/governance/analytics_joint_state_entry_predictability_l003g-2026-09-07.json` |
| **What NOT claimed** | Trail explanation; attribution; edge; path-generation process; “path-defined” as definition. |

**Review stance:** L-003G is the **strongest falsification result** in the package.

### 5.2 JSE-001 — engine_state_asof → STATE_SL_TP (BNB)

| Field | Content |
|---|---|
| **H0** | `engine_state_asof` explains `{x: Y_joint(x)=STATE_SL_TP}` on BNB anatomy↔events join. |
| **MeasurementObject** | Predictor: `engine_state_asof` (**≠ CRT Context**). Target: `Y_joint` / `STATE_SL_TP`. |
| **Population** | `Ω_bnb_anatomy`; n=139,942; coverage 1.000. |
| **Join** | `trade_dataset_BNBUSDT.csv` as-of joined to `run_20260603_122112_BNBUSDT/BNBUSDT_events.jsonl` (RESET→RANGE). |
| **Metric** | Chrono 70/30 AUC (STATE_SL_TP ovr). |
| **Result** | **FALSIFIED** for this join surface. AUC_SL_TP=**0.5004** (≈ chance). |
| **Scope limits** | BNB-only; one events run; categorical `state_to` only; not Parent/HTF/manipulation. |
| **Artifacts** | `docs/research/JOINT_STATE_EXPLAINABILITY.md` · `docs/research/jse001_crt_context_bnbusdt-2026-09-07.json` · `results/research/jse001_crt_context_bnbusdt/` |
| **What NOT claimed** | “CRT falsified”; edge; attribution; which outcome is right. |

### 5.3 JSE-002 — engine_state_asof → path geometry (BNB)

| Field | Content |
|---|---|
| **H0** | `engine_state_asof` predicts path-geometry descriptors (peak/MFE/T_MAE buckets; optional exit-ordering). |
| **MeasurementObject** | Predictor: `engine_state_asof`. Targets: L-003C–E-style path geometry (+ optional `scanner_exit_precedes_oracle_tp`). |
| **Population** | `Ω_bnb_anatomy`; coverage 1.000. |
| **Join** | Same as JSE-001. |
| **Metric** | Macro AUC ovr on multiclass buckets; binary AUCs; Δ vs JSE-001. |
| **Result** | **FALSIFY_PATH_AND_YJOINT**. peak macro=**0.5045**; mfe=**0.5033**; t_mae=**0.4978**; best binary=**0.5102**. Not +0.02 better than Y_joint null. |
| **Scope limits** | BNB-only; one events run; `state_to` only. |
| **Artifacts** | `docs/research/JOINT_STATE_EXPLAINABILITY.md` · `docs/research/jse002_engine_state_path_geometry_bnbusdt-2026-09-07.json` · `results/research/jse002_engine_state_path_geometry_bnbusdt/` |
| **What NOT claimed** | CRT falsified; weakening of L-003C–E association of path geometry *with* Y_joint (different arrow). |

### 5.4 JSE-003 — engine_context_history → path geometry (BNB)

| Field | Content |
|---|---|
| **H0** | `engine_context_history` predicts path geometry better than chance / better than as-of `state_to`. |
| **MeasurementObject** | Predictor family: `engine_context_history` (**not** CRT Context). |
| **Population** | `Ω_bnb_anatomy`; coverage 1.000. |
| **Join** | Same events timeline as JSE-001/002; ~48 history features. |
| **Metric** | History-set macro AUC; SUPPORT_ASSOCIATION threshold AUC≥0.58 + chrono stability (not met). |
| **Result** | **FALSIFIED**. peak history macro=**0.5146** (Δ+0.010 vs asof); best binary=**0.5217**. |
| **Scope limits** | BNB-only; one events run; not causal; not CRT. |
| **Artifacts** | `docs/research/JOINT_STATE_EXPLAINABILITY.md` · `docs/research/jse003_engine_context_history_path_geometry-2026-09-07.json` · `results/research/jse003_engine_context_history_path_geometry/` |
| **What NOT claimed** | CRT claim; causality; edge; L-003 doctrine reopen. |

---

## 6. Associated (not falsified) evidence

| ID | Role | Lean / note | Artifacts |
|---|---|---|---|
| **L-003B** | Identity | HOMONYM `Y_scanner ≠ Y_oracle` | `ANALYTICS_OUTCOME_POPULATION_COMPARISON_L003B.md` + JSON |
| **L-003F** | Census | Joint-state masses; `STATE_SL_TP` ~31.5% | `ANALYTICS_JOINT_OUTCOME_STATES_L003F.md` + JSON |
| **L-003C/D/E** | Path geometry association | Associates with joint membership — **path-geometry-associated**, not path-defined | disagreement / path mechanics / adverse timing MD+JSON |
| **L-003H** | Exit ordering | Supports trail-early-exit *pattern* in `STATE_SL_TP` (association) | `ANALYTICS_TRAIL_EXIT_TRANSITIONS_L003H.md` + JSON |
| **L-003I** | Baseline direction | Trail not sufficient; lean retained; no causality | `ANALYTICS_TRAIL_BASELINE_INVERSION_L003I.md` + JSON |

---

## 7. Schemas appendix

Shareable schemas (see `docs/research/reports/SCHEMAS_README.md`):

| Schema | Path |
|---|---|
| MeasurementObject | `docs/research/reports/schemas/measurement_object.schema.json` |
| Joint state space | `docs/research/reports/schemas/joint_state_space.schema.json` |
| Population | `docs/research/reports/schemas/population.schema.json` |
| Falsify record | `docs/research/reports/schemas/falsify_record.schema.json` |
| Registry shape refs | `docs/research/reports/schemas/registry_shape_references.json` |

Binding rule: FALSIFY records cite MOR `object_id`s, Population Registry ids, and L-003L StateIDs; Y_* entries must carry `formula_map` (`Ω → L` / `Ω → S`) in addition to producer refs.

---

## 8. Recommended next episode

### `PATH_GENERATION_FOR_STATE_SL_TP`

**Stance:** observe before predict.

**Population:** `STATE_SL_TP_anatomy = { x ∈ Ω_anatomy_opportunity : Y_joint(x) = STATE_SL_TP }`

**Objective:** observe the **path-generation process** that produces units in this population (path geometry evolution, exit-ordering events, trail activation timing) as a *process description*, not as a new weak predictor hunt.

**Non-goals:** edge claims; “which outcome is right”; CRT ontology claims without declared MeasurementObjects; reopening L-003 doctrine.

---

## 9. Index of evidence artifact paths

### FALSIFY core

| Finding | Human | Machine |
|---|---|---|
| L-003G | `docs/governance/ANALYTICS_JOINT_STATE_ENTRY_PREDICTABILITY_L003G.md` | `docs/governance/analytics_joint_state_entry_predictability_l003g-2026-09-07.json` |
| JSE-001 | `docs/research/JOINT_STATE_EXPLAINABILITY.md` (§ JSE-001) | `docs/research/jse001_crt_context_bnbusdt-2026-09-07.json` |
| JSE-002 | `docs/research/JOINT_STATE_EXPLAINABILITY.md` (§ JSE-002) | `docs/research/jse002_engine_state_path_geometry_bnbusdt-2026-09-07.json` |
| JSE-003 | `docs/research/JOINT_STATE_EXPLAINABILITY.md` (§ JSE-003) | `docs/research/jse003_engine_context_history_path_geometry-2026-09-07.json` |

### Associated

| Finding | Human | Machine |
|---|---|---|
| L-003B | `docs/governance/ANALYTICS_OUTCOME_POPULATION_COMPARISON_L003B.md` | `docs/governance/analytics_outcome_population_comparison_l003b-2026-09-07.json` |
| L-003F | `docs/governance/ANALYTICS_JOINT_OUTCOME_STATES_L003F.md` | `docs/governance/analytics_joint_outcome_states_l003f-2026-09-07.json` |
| L-003H | `docs/governance/ANALYTICS_TRAIL_EXIT_TRANSITIONS_L003H.md` | `docs/governance/analytics_trail_exit_transitions_l003h-2026-09-07.json` |
| L-003I | `docs/governance/ANALYTICS_TRAIL_BASELINE_INVERSION_L003I.md` | `docs/governance/analytics_trail_baseline_inversion_l003i-2026-09-07.json` |
| L-003C | `docs/governance/ANALYTICS_OUTCOME_DISAGREEMENT_POPULATION_L003C.md` | `docs/governance/analytics_outcome_disagreement_population_l003c-2026-09-07.json` |
| L-003D | `docs/governance/ANALYTICS_OUTCOME_PATH_MECHANICS_L003D.md` | `docs/governance/analytics_outcome_path_mechanics_l003d-2026-09-07.json` |
| L-003E | `docs/governance/ANALYTICS_OUTCOME_ADVERSE_TIMING_L003E.md` | `docs/governance/analytics_outcome_adverse_timing_l003e-2026-09-07.json` |

### Freeze / registry / episode

| Artifact | Path |
|---|---|
| Package freeze | `docs/governance/ANALYTICS_L003_PACKAGE_FREEZE.md` · `analytics_l003_package_freeze-2026-09-07.json` |
| State space L-003L | `docs/governance/ANALYTICS_JOINT_STATE_SPACE_L003L.md` · JSON |
| Noun parity L-003M | `docs/governance/ANALYTICS_NOUN_PARITY_L003M.md` · JSON |
| MOR | `docs/governance/MEASUREMENT_OBJECT_REGISTRY.md` · `measurement_object_registry.json` |
| Population Registry (new stub) | `docs/governance/POPULATION_REGISTRY.md` · `population_registry.json` |
| JSE episode | `docs/research/JOINT_STATE_EXPLAINABILITY.md` · `joint_state_explainability_pin.json` |
| This report | `docs/research/reports/L003_JSE_ARCHITECTURE_REVIEW_AND_FALSIFY_EVIDENCE.md` |
| This pack | `docs/research/reports/l003_jse_falsify_evidence_pack-2026-09-08.json` |

### Results dirs (JSE)

- `results/research/jse001_crt_context_bnbusdt/`
- `results/research/jse002_engine_state_path_geometry_bnbusdt/`
- `results/research/jse003_engine_context_history_path_geometry/`

---

## 10. Errata log (this run)

1. Episode doc `JOINT_STATE_EXPLAINABILITY.md`: “path-defined” → **path-geometry-associated** where it overclaimed definition.
2. MOR: Y_scanner / Y_oracle / Y_joint gain `mathematical_type` + `formula_map` (`Ω → L` / `Ω → S`) alongside producers.
3. Population Registry stub registered.
4. Historical L-003G lean_text still contains the string “path-defined” as a frozen measurement artifact; **interpretive** wording for new episode/report prose is path-geometry-associated (association with L-003C–E descriptors, not a definition of the population by path).
