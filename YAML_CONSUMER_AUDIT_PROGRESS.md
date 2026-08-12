# YAML Consumer Audit — Progress Summary

**Date**: 2026-07-17  
**Status**: Phases 1-2 Complete, Phase 3+ In Progress  

---

## Phases Completed ✅

### Phase 1: File Verification
- ✅ Located `active_models.yaml` (57 KB, 855 lines) at repository root
- ✅ Located `market_ontology.yaml` (30 KB, 509 lines) in configs/formulas/
- ✅ Verified both are valid YAML
- ✅ Documented top-level structure for each

**Deliverable**: `YAML_CONSUMER_AUDIT_PHASE1.md`

---

### Phase 2: Direct Consumers (Loader Functions)
- ✅ Found **active_models.yaml** loader: `state_contract_loader._load_yaml()` → `load_and_validate_state_contracts()`
- ✅ Found **market_ontology.yaml** loader: `features.registry._loader.load_ontology()`
- ✅ Traced immediate consumers (1 hop):
  - `state_contract_loader` → `crt_engine_v2` (CRTEngine init)
  - `fm_resolve._ontology_index()` → `resolve_fm()` → `crt_engine_v2`
  - `composition_registry` (feature compositions)
  - `derived_registry` (derived metrics)
  - `features.registry.validate_registry()` (validation)

**Deliverable**: `YAML_CONSUMER_AUDIT_PHASE2.md`

---

## Phases In Progress 🔄

### Phase 3: Runtime Reachability
**Status**: Identified 12 modules that reference loader entry points:
```
Production path:
  - src/config_layer/crt_engine_v2.py
  - src/config_layer/production_config.py
  - src/core/engine_runner.py (implied)
  - src/runtime/backtest_v2.py
  - src/runtime/live_engine_hook.py (implied)

Research/Validation path:
  - src/research/measurement/forward_walk.py
  - src/runtime/crt_baseline_trace.py
  - src/runtime/crt_fail_reason_counters.py

Governance/Validation path:
  - src/governance/promotion_manager.py
  - src/config_layer/state_topology.py

Core infrastructure:
  - src/features/fm_resolve.py (loader itself)
  - src/features/formula_registry.py
  - src/features/registry/__init__.py
  - src/config_layer/state_contract_loader.py (loader itself)
```

**Next**: Trace call chains to identify actual execution paths (production spine vs research vs test)

---

## Phases Pending ⏳

### Phase 4: Consumer Classification
- Classify each module as: Production / Research / Test / Dead
- Distinguish runtime (every candle) vs init-time (startup)

### Phase 5-7: Build Deliverable Matrices & Graphs
- Consumer matrix (module × property grid)
- Runtime dependency graphs (ASCII art)
- Dead consumer list

### Phase 8-9: Blast Radius & Mismatch Analysis
- What reloads if either YAML changes?
- What recomputes?
- What documentation claims vs code shows?

### Phase 10-11: Final Deliverables
- Summary report with confidence scores

---

## Critical Findings So Far

1. **Active Models YAML has single entry point**: All consumption funnels through `load_and_validate_state_contracts()` in `state_contract_loader.py`

2. **Market Ontology has multiple parallel consumers**:
   - `fm_resolve._ontology_index()` for FM binding
   - `composition_registry` for feature compositions
   - `derived_registry` for derived metrics
   - `validate_registry()` for validation
   - All lazy-loaded

3. **No raw yaml.load() calls found**: Both YAMLs only loaded through wrapper functions (good for auditing)

4. **Lazy loading pattern**: Both YAMLs loaded on-demand, not at import time

5. **12 downstream modules identified** (need to classify which are production vs research)

---

## Next Critical Steps

1. **Complete Phase 3**: Verify runtime reachability of each module
   - Which modules are on production spine?
   - Which are research-only?
   - Which are test-only?

2. **Trace to entry points**:
   - How does `crt_engine_v2` get initialized? (via `EngineRunner`, `live_engine_hook`, `backtest_v2`)
   - How does `validate_registry()` get called? (via promotion_manager, config_validator)

3. **Identify dead consumers**: Any loaders that are defined but never called?

4. **Blast radius**: What breaks if either YAML is modified?

---

## Confidence Scores (Preliminary)

| Finding | Confidence | Status |
|---------|-----------|--------|
| **Direct loaders identified** | 10/10 | Verified with line numbers |
| **Load timing (lazy)** | 10/10 | Code-confirmed |
| **12 downstream modules** | 9/10 | Grep-found, need verification |
| **Production entry points** | 7/10 | Inferred, not yet traced |
| **Test/research separation** | 6/10 | Assumed, needs classification |
| **Complete consumer matrix** | 3/10 | Not yet compiled |
| **Dead code detection** | 2/10 | Not yet searched |

---

## Recommended Execution Path

**For immediate high-value findings:**
1. Complete runtime reachability trace (Phase 3) → tells us production vs research
2. Build consumer matrix (Phase 6) → single source of truth
3. Blast radius analysis (Phase 9) → tells us impact of changes

**For comprehensive audit:**
- All 11 phases as planned

