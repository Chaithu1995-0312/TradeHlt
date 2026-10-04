# CRT Market States vs `market_ontology.yaml`

**Mode:** observational / read-only (no production code or config changes)  
**Date:** 2026-07-11  
**Question:** Are CRT market states declared in the ontology, and does CRT read those declarations?  
**Source plan:** session investigation plan (approved; export requested)

---

## Context

User recollection: market states such as SWEEP, DISPLACEMENT, EXPANSION, RETEST were configured in the market ontology so ontology/config would be the WHAT-layer authority.

This report traces **current source only**. Name overlap does not imply runtime authority.

---

## Executive finding

**CRT market states are not declared in `market_ontology.yaml` and CRT never loads that YAML.**

| Layer | Role for market states |
|-------|------------------------|
| Executable state identity + transitions | Hardcoded: `CRTState` + `VALID_TRANSITIONS` + `StateMachine` in `src/config_layer/crt_engine_v2.py` |
| Behavioral thresholds | Production config → `CRTConfig` |
| Descriptive WHO map | `active_models.yaml` `crt.runtime` — **not** read by CRT at runtime |
| Feature-math WHAT | `market_ontology.yaml` — FM-* only; **state machines explicitly out of scope** |

---

## 1. What `market_ontology.yaml` actually contains

**Path:** `configs/formulas/market_ontology.yaml` (294 lines, version 1.1)

**Top-level keys only:**

| Key | Purpose |
|-----|---------|
| `version`, `authority` | schema meta |
| `base_inputs` | OHLCV + leaves (atr, ema_*, disp_open/close, retest_close, …) |
| `primitives` | FM-001… candle geometry |
| `feature_compositions` | body_ratio etc. |
| `derived_metrics` | retest_depth, displacement_retrace, … |

**No keys:** `states`, `market_states`, `crt_states`, `state_machine`, `VALID_TRANSITIONS`, or any of `RANGE` / `SHADOW_PENDING` / `SWEEP` / `DISPLACEMENT` / `EXPANSION` / `RETEST` / `EXECUTION` / `RESOLUTION` / `EXPIRED` as state declarations.

**Explicit design freeze** (lines 26–28):

> rolling indicators … and **stateful detection (sweep/BOS/CHOCH/pivot state machines) are ALGORITHMS, not this layer** — adding them is a separate architectural review (boundary freeze).

**Authority model in header** (lines 9–16): ontology **declares feature meaning**; `FORMULA_REGISTRY` is compute authority; formulas never `eval`'d. This is the **feature-math WHAT layer**, not CRT lifecycle states.

**`configs/formulas/`** contains only this one YAML file.

---

## 2. Master table (all nine CRT states)

| Market state | Ontology declaration | Ontology formula/condition | Loader | CRT runtime consumer | Actual executable owner | Config dependencies | Status |
| ------------ | -------------------- | -------------------------- | ------ | -------------------- | ----------------------- | ------------------- | ------ |
| RANGE | **NO** in market_ontology | n/a | n/a | `CRTState.RANGE`, `detect_htf_range`, reset targets | **CRT Python** `crt_engine_v2.py` | HTF window size via backtest `htf_candles_per_range`; range = maxH/minL code | **CRT_ONLY** — not in ontology |
| SHADOW_PENDING | **NO** | n/a | n/a | `try_range_to_shadow_pending`, TTL countdown | **CRT Python** + config TTL | `pending_displacement_ttl_candles` | **CRT_ONLY** |
| SWEEP | **NO** (prose/notes only) | n/a | n/a | `detect_sweep`, `try_range_to_sweep` | **CRT Python** (geometry hardcoded) | none for detection rule itself | **CRT_ONLY** |
| DISPLACEMENT | **NO** as state; related **feature** FM-028 under `derived_metrics` | feature formula only | feature loader only | `try_sweep_to_displacement` | **CRT Python gates** + **shared math** `body_ratio` + **prod config** thresholds | `atr_min_displacement`, `body_ratio_min`, `atr_multiplier_min`, `max_sweep_age_candles` | **CRT_ONLY state**; feature formulas PARTIALLY shared |
| EXPANSION | **NO** | n/a | n/a | `try_displacement_to_expansion` | **CRT Python** + config | `expansion_atr_min_distance` | **CRT_ONLY** |
| RETEST | **NO** as state; related features FM-021/027 under derived_metrics | feature formulas only | feature path only | `try_expansion_to_retest` | **CRT Python** + config + **derived_math** FM-027/028 at cache | `retest_depth_max`, `retest_atr_depth_fraction`, `max_displacement_strength` | **CRT_ONLY state**; cache emission PARTIALLY shared math |
| EXECUTION | **NO** | n/a | n/a | `try_retest_to_execution` after soft-conf approve | **CRT Python** + config scoring | soft-conf / tier / session / spread keys | **CRT_ONLY** |
| RESOLUTION | **NO** | n/a | n/a | `try_execution_to_resolution` | **CRT Python** | exit_model (intrabar vs close) | **CRT_ONLY** |
| EXPIRED | **NO** | n/a | n/a | EXPANSION TTL branch → `EXPIRED` → reset | **CRT Python** + config | `max_expansion_age_candles`, `max_expansion_age_hours` | **CRT_ONLY** |

### Per-state checklist (questions 1–7)

For **every** state above:

1. **Declared in `market_ontology.yaml`?** **No.**
2. YAML path / file:line / semantic / formulas / binding: **N/A** (absent).
3. **Hardcoded in Python?** **Yes** — `class CRTState(Enum)` in `src/config_layer/crt_engine_v2.py` (~65–76); legal edges in `VALID_TRANSITIONS` (~1076–1086); guards in `StateMachine.try_*` and `CRTEngine.process_candle`.
4. **Does CRT load ontology at startup/runtime?** **No.** `crt_engine_v2.py` has **zero** references to `market_ontology`, `load_ontology`, or `FORMULA_REGISTRY`. Imports: `candle_math`, `derived_math`, taxonomy, bitnet, etc. only.
5. **Transport chain for states:** breaks immediately — no declaration → no loader consumption for states → no CRT consumer of ontology states.
6. **`DECLARED_BUT_NOT_CONSUMED`?** Applies to **feature FM-*** entries when audited against non-registry re-derivation sites; **does not apply to market states** because they are **NOT DECLARED** in the ontology.
7. **Executable transition conditions** come from:
   - **market ontology:** never for state transitions
   - **production config (`CRTConfig`):** thresholds only
   - **CRT Python:** detection predicates + `VALID_TRANSITIONS` enforcement
   - **shared math modules:** `body_ratio`, FM-027/028, etc. **inside** gates — not state identity
   - **combination:** typical gate = Python structure + config threshold + optional shared math scalar

---

## 3. Ontology loader chain (proven)

```text
configs/formulas/market_ontology.yaml
        ↓
features.registry._loader.load_ontology()   # yaml.safe_load; used by formula registry / governance tools
        ↓
parsed dict: {primitives, feature_compositions, derived_metrics, base_inputs, …}
        ↓
FORMULA_REGISTRY (named callables in src/features/registry/*)
        ↓
Consumers: feature lineage tests, feature_math_lint, feature_surface_query, parity tests
        ✗  NO edge to CRTEngine / StateMachine / CRTState
```

### Where the chain breaks for market states

```text
market_ontology.yaml
        ✗  NO market-state section (by design freeze L26–28)
        ✗  CRT never calls load_ontology
        ✗  CRT never reads FORMULA_REGISTRY for transitions
```

### Partial related chain (feature math only, not states)

```text
market_ontology.yaml  (declares FM-010 body_ratio, FM-027, FM-028, …)
        ↓
impl: candle_math.* / derived_math.*   (registry binds names → callables)
        ↓
CRTEngine imports candle_math as _cm, derived_math as _dm  DIRECTLY
        ↓
used inside displacement/retest gates and cached_features emission
```

CRT does **not** go ontology → loader → CRT. It **bypasses** the ontology loader and imports the **same Python modules** the registry points at. That is **implementation sharing**, not **ontology executable authority** over states.

---

## 4. Where states *are* written (non-ontology)

### A. Executable authority — `crt_engine_v2.py`

- `CRTState` enum (9 members)
- `VALID_TRANSITIONS` dict
- `StateMachine._transition` + `try_*` guards
- `CRTEngine.process_candle` orchestration
- Thresholds: `CRTConfig` filled by `ConfigBuilder` / production JSON

### B. Descriptive WHO registry — `active_models.yaml` (`crt.runtime`)

- `state_list`, `valid_transitions`, `detection.*`, `lifecycle.*`
- Points at `file_line` in CRT code
- **Not imported by CRT runtime** (`src/` only hits `active_models` via governance/hypothesis paths, not engine)
- Defaults in YAML can **drift** from live config (see §7)

### C. Docs

- `docs/architecture/event-taxonomy.md` documents enum + transitions as code citations
- CLAUDE.md / findings tables describe 9-state machine

**None of B/C are runtime transport into CRT.**

---

## 5. Executable flow (proven by current code)

```text
raw OHLCV (CandleLoader → Candle)
    → CRT Python: ATR buffer, RangeDetector, detect_sweep, StateMachine.try_*
    → shared math modules (candle_math / derived_math) for selected scalars
    → production config thresholds (CRTConfig / params / crt_engine sections)
    → VALID_TRANSITIONS + state mutation (CRTState)
    → action dict / TRADE_OPENED / RESET / …
```

**Not:**

```text
market_ontology.yaml → state machine execution
```

---

## 6. Ontology role classification

| Surface | Classification |
|---------|----------------|
| `market_ontology.yaml` **for CRT market states** | **RUNTIME DEAD** for states — **not declared**; design explicitly excludes state machines |
| `market_ontology.yaml` **for feature FM math** | **VALIDATED DECLARATIVE AUTHORITY** (WHAT) + registry as compute authority; parity/lint enforce |
| Ontology → CRT **state** path | **RUNTIME DEAD** / chain absent |
| Ontology → CRT **body_ratio / FM-027/028** | **PARTIALLY WIRED**: same impl modules; CRT does not load YAML; does not go through `FORMULA_REGISTRY` API |
| `active_models.yaml` CRT states | **DOCUMENTATION/GOVERNANCE ONLY** (WHO intent/runtime description); tests may pin shape; **not executable** |
| `CRTState` / `VALID_TRANSITIONS` / `try_*` | **EXECUTABLE AUTHORITY** for market-state flow |
| Production JSON / `CRTConfig` | **EXECUTABLE AUTHORITY** for **thresholds** (HOW), not state identity |

**Overall for “is ontology the WHAT-layer authority for market states?”**  
→ **No. Ontology is WHAT for feature mathematics only. Market states are STRUCTURAL code (frozen in CRT Python).**

---

## 7. Formula / semantics drift

| Drift type | Evidence |
|------------|----------|
| Ontology state missing in CRT | N/A — ontology has no states |
| **CRT state missing in ontology** | **All 9 CRT states** absent from market_ontology |
| Formula mismatch (feature layer) | Ontology/pipeline FM-021 `retest_depth` (EMA/ATR) ≠ CRT retest **gate** (range-boundary depth) ≠ FM-027 `displacement_retrace` (cross-candle); names historically collided (F-050/CH-002) |
| Threshold ownership mismatch | Live thresholds: production/`CRTConfig`. Ontology has **no** state thresholds. `active_models.yaml` `defaults` can disagree with live config (e.g. docs still show `body_ratio_min: 0.70`, `retest_depth_max: 0.25`, `expansion_atr_min_distance: 0.20` while runtime XAUUSD build previously resolved `0.6` / `0.35` / `0.08`) — descriptive drift, not ontology |
| Implementation binding not consumed | Ontology `impl:` bindings consumed by **registry/governance**, not by CRT loader |
| Duplicate semantic ownership | **State names** described in active_models + docs + code; **execution only in code**. Feature names partially in ontology + CRT cache keys |
| Hardcoded CRT bypassing ontology | **By design for algorithms:** entire state machine is code; ontology freeze forbids putting sweep SM in WHAT layer |

---

## 8. Memory reconciliation

If market states were “configured in the ontology” in a past session, that either:

1. Was **intended but never landed** in `market_ontology.yaml`, or  
2. Was implemented instead in **`active_models.yaml` `crt.runtime`** (descriptive WHO) and/or **production thresholds**, or  
3. Referred to **feature formulas** (body_ratio, displacement_*) used **inside** CRT gates — not the state enum itself.

Current source is consistent with **no ontology state authority**.

---

## 9. As-is architecture diagram

```text
market_ontology.yaml          active_models.yaml (crt.runtime)
  [feature FM-* only]           [descriptive state_list + detection prose]
        ↓                                 ✗ no runtime load by CRT
load_ontology / FORMULA_REGISTRY
        ↓
governance / feature tools
        ✗

production JSON ──→ CRTConfig thresholds ──┐
candle_math / derived_math (direct import) ─┼→ CRTEngine / StateMachine / CRTState
hardcoded VALID_TRANSITIONS + try_* ────────┘
```

---

## 10. Verification performed (read-only)

- Read `configs/formulas/market_ontology.yaml` structure and freeze note  
- Loaded `CRTState` / `VALID_TRANSITIONS` from `crt_engine_v2`  
- Confirmed zero ontology/registry imports in `crt_engine_v2.py`  
- Confirmed `load_ontology` only for feature registry/governance tooling  
- Confirmed `active_models.yaml` crt.runtime describes all 9 states but is not CRT-loaded  
- Confirmed `configs/formulas/` has only the one ontology file  

---

## 11. Final verdict

```text
MARKET_STATES_DECLARED_IN_ONTOLOGY = NO (0/9; state machines explicitly out of ontology scope)
CRT_READS_MARKET_ONTOLOGY = NO
ONTOLOGY_TO_CRT_RUNTIME_CHAIN = BROKEN_AT_DECLARATION (no state section; CRT never calls load_ontology)
ONTOLOGY_EXECUTABLE_AUTHORITY = RUNTIME_DEAD_FOR_STATES; FEATURE_MATH_IS_VALIDATED_DECLARATIVE_WHAT (registry executes; CRT imports shared math modules directly = PARTIALLY_WIRED for FM scalars only)
CRT_STATE_EXECUTABLE_OWNER = CRT Python (CRTState + VALID_TRANSITIONS + StateMachine.try_* + process_candle); thresholds from production CRTConfig
DUPLICATE_SEMANTIC_OWNERSHIP = YES (descriptive: active_models.yaml + docs; executable: crt_engine_v2.py only)
ONTOLOGY_CRT_DRIFT = ALL_NINE_STATES_MISSING_FROM_ONTOLOGY; feature-name/threshold prose in active_models may lag live CRTConfig; FM-021 vs CRT retest gate are different quantities
HIGHEST_IMPACT_FINDING = Ontology is not and was designed not to be CRT market-state authority; belief that market states are ontology-driven is DOC_DRIFT / memory drift — executable authority remains hardcoded CRT state machine + config thresholds
UNRESOLVED_GAPS = Whether a future governed “state ontology” should be added (architectural review required per ontology L26–28); whether active_models defaults should be mechanically synced to CRTConfig (governance hygiene, not ontology)
REPORT_PATH = reports/CRT_MARKET_STATES_ONTOLOGY_TRACE.md
```

---

*End of observational report. No production formulas, configs, or models were modified for this export.*
