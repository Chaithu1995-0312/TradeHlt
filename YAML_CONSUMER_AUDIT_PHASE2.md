# YAML Consumer Audit — Phase 2: Direct Consumers

**Date**: 2026-07-17  
**Status**: Phase 2 Complete  

## Direct Consumers Found

### active_models.yaml

**Direct Loader**: `state_contract_loader.load_and_validate_state_contracts()`
- **File**: `src/config_layer/state_contract_loader.py:189-303`
- **Load Function**: `_load_yaml()` at line 54
- **Evidence**: 
  ```python
  # Line 203
  doc = _load_yaml(am_path)
  # Uses yaml.safe_load() at line 63
  data = yaml.safe_load(path.read_text(encoding="utf-8"))
  ```
- **Load Timing**: Lazy-loaded on first call to `load_and_validate_state_contracts()`
- **Return Type**: Dictionary → parsed into `StateContractBundle`
- **Primary Consumer**: Parses `crt.runtime.state_contracts`, `crt.runtime.valid_transitions`

**Consumers of Loader Result**:
- `crt_engine_v2.py`: Line 2631 imports `load_and_validate_state_contracts`
  - Uses state contracts to validate CRT state machine at runtime
  - Called during CRTEngine initialization

---

### market_ontology.yaml

**Direct Loader**: `features.registry._loader.load_ontology()`
- **File**: `src/features/registry/_loader.py:11-15`
- **Evidence**:
  ```python
  def load_ontology(path: Path | None = None) -> dict:
      import yaml  # lazy
      p = path or _ONTOLOGY_PATH
      return yaml.safe_load(p.read_text(encoding="utf-8"))
  ```
- **Load Timing**: Lazy-loaded on first access
- **Return Type**: Dictionary (raw YAML)

**Immediate Consumers of `load_ontology()`**:
1. `fm_resolve._ontology_index()` (line 59)
   - Builds FM id → metadata index from ontology sections
   - Used by `resolve_fm()` to bind FM ids to implementations

2. `composition_registry.build_composition_registry()` (line 28)
   - Uses ontology to register feature compositions

3. `derived_registry.build_derived_registry()` (line 36)
   - Uses ontology to register derived metrics

4. `features/registry/__init__.py validate_registry()` (line 62, 118)
   - Validates entire ontology structure and consistency

---

## Indirect Consumers (Immediate — 1 hop from loader)

### active_models.yaml Chain

```
active_models.yaml
  ↓ (via _load_yaml)
state_contract_loader.load_and_validate_state_contracts()
  ↓ (returns StateContractBundle)
crt_engine_v2.CRTEngine.__init__()
  ├─ Parses state_contracts
  ├─ Validates against VALID_TRANSITIONS (Python enum)
  └─ Binds FM ids via fm_resolve.resolve_fm()
```

---

### market_ontology.yaml Chain

```
market_ontology.yaml
  ↓ (via load_ontology)
fm_resolve._ontology_index()
  ├─ Features by FM-0NN id
  ├─ Implementation links (via FORMULA_REGISTRY)
  └─ Lifecycle metadata
  ↓
fm_resolve.resolve_fm() — resolves FM-0NN → callable
  ↓ (used by)
crt_engine_v2.bind_phase2_crt_callables()
  └─ Binds CRT FM requirements to implementations

AND

market_ontology.yaml
  ↓ (via load_ontology)
composition_registry.build_composition_registry()
  └─ Registers feature_compositions section
  
market_ontology.yaml
  ↓ (via load_ontology)
derived_registry.build_derived_registry()
  └─ Registers derived_metrics section

market_ontology.yaml
  ↓ (via load_ontology)
features.registry.validate_registry()
  └─ Validates parity between ontology + implementations
```

---

## Loading Mechanism Summary

| YAML | Load Function | Location | Timing | Cache |
|------|---------------|----------|--------|-------|
| **active_models.yaml** | `_load_yaml()` | state_contract_loader.py:54 | On first call to `load_and_validate_state_contracts()` | Yes, process-wide `_CACHE` |
| **market_ontology.yaml** | `load_ontology()` | features/registry/_loader.py:11 | On first access | Lazy, no explicit cache (LRU on resolve_fm) |

---

## Key Findings

1. **No direct yaml.load() in application code**: Both YAMLs are loaded through wrapper functions, not via raw yaml.load() calls elsewhere.

2. **Two separate loading paths**:
   - `active_models.yaml` → single entry point via `state_contract_loader`
   - `market_ontology.yaml` → single entry point via `features.registry._loader`, consumed by three registry builders

3. **Lazy loading**: Both YAMLs are loaded on-demand, not at module import time.

4. **Cache patterns**:
   - `active_models`: Process-wide cache in `state_contract_loader._CACHE`
   - `market_ontology`: No explicit process cache; relies on `@lru_cache` on dependent functions

5. **No references found yet in**:
   - Test code (need Phase 3)
   - Research code (need Phase 3)
   - Documentation-only references (need Phase 10)

---

## Search Patterns Used

✅ `market_ontology\.yaml` — found references  
✅ `active_models\.yaml` — found references  
✅ `load.*market_ontology` — no functions with this exact name  
✅ `load.*active_models` — no functions with this exact name  
✅ `_load_yaml` — found (internal to state_contract_loader)  
✅ `load_ontology` — found (internal to registry._loader)  

---

## Next Phase

→ Phase 3: Trace indirect consumers and determine runtime reachability (who calls the loaders?)
→ Phase 4: Classify each consumer (direct/indirect/runtime/research/test/dead)
