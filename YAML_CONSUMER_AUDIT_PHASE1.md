# YAML Consumer Audit — Phase 1: File Verification

**Date**: 2026-07-17  
**Status**: Phase 1 Complete  

## File Audit Report

### active_models.yaml

**Path**: `./active_models.yaml` (root directory)  
**Size**: 57,445 bytes (~57 KB)  
**Lines**: 855  
**Format**: Valid YAML (v2.1 schema)  

**Top-level Structure**:
```yaml
meta:
  schema_version: 2.1
  migration: ...
  machine_readable_sources: ...
  
# Model entries by category:
- crt: (CRT engine specs)
- gaussian: (Gaussian scorer specs)
- bitnet: (BitNet config)
- zone_gate: (Zone gate specs)
- rr_model: (RR engine specs)
- strategy_modules: (Strategy specs)
- engine_runner: (Orchestration specs)
- ...
```

**Purpose**: Machine-readable model registry containing:
- Intent layers (architectural design)
- Runtime layers (what executes today)
- Evidence layers (research findings)
- Operational status (active/dormant/experimental)

---

### market_ontology.yaml

**Path**: `./configs/formulas/market_ontology.yaml`  
**Size**: 29,556 bytes (~30 KB)  
**Lines**: 509  
**Format**: Valid YAML  

**Top-level Structure**:
```yaml
# Comments + authority model + layer separation rules

primitives:
  - candle_range
  - body
  - wick_size
  - ... (OHLC-derived identities)

feature_compositions:
  - body_ratio (body / candle_range)
  - ... (configurable ratios)

derived_metrics:
  - atr
  - momentum_score
  - ... (normalized quantities)

rolling_indicators:
  - atr_rolling (FM-040)
  - rsi (FM-041)
  - ... (windowed indicators)

feature_families:
  - candle_structure
  - momentum
  - volatility
  - ... (grouped by trading interpretation)

formula_registry:
  FM-001: { name: "ema_fast", formula: "...", ... }
  FM-002: { name: "ema_slow", formula: "...", ... }
  ... (38 canonical features)
```

**Purpose**: Market structure definitions, feature formulas, layer registry:
- Separates primitives (immutable math) from compositions (policy)
- Defines 38-dimensional canonical feature schema
- Maps semantic names to implementation identities
- Authority for what each feature mathematically means

---

## File Locations Summary

| File | Path | Size | Lines | Primary Consumers |
|------|------|------|-------|------------------|
| **active_models.yaml** | `./active_models.yaml` | 57 KB | 855 | Claude session initialization, engine_runner config, CRT state machine |
| **market_ontology.yaml** | `./configs/formulas/market_ontology.yaml` | 30 KB | 509 | Feature pipeline, formula registry, feature schema validation |

---

## Additional Copies (Archived/Test)

- `./msip_1_verification_package/02_feature_authority/market_ontology.yaml` (test/verification package)
- `./msip_1_verification_package/04_crt_runtime/active_models.yaml` (test/verification package)

**Note**: These are likely test/verification artifacts. Primary focus: root and configs/formulas/ versions.

---

## Next Phase

→ Phase 2: Find direct consumers via grep search patterns
