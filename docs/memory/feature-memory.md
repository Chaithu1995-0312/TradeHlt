# Feature Memory (navigation)

> **Last generation:** 2026-08-07  
> **Code-first:** `src/features/**` + `configs/formulas/market_ontology.yaml` on conflict (ontology owns meaning; code owns emission).

## Purpose

Index the canonical feature surface: schema identity, pipeline emission, geometric/derived math, formula registry, and drift monitoring.

## Responsibilities

- Define `CANONICAL_FEATURES` order/dimension and schema hashes.  
- Build feature frames/vectors from OHLCV (config-driven periods).  
- Own candle geometry (`candle_math`) and scalar derived metrics (`derived_math`).  
- Registry/ontology-backed formulas (no new local formula math).  
- Optional session clock basis, CRT state resolver, dataset build/validate, feature drift monitor.

## Runtime role

**Feature engineering** — upstream of all scoring engines and the decision spine. Batch or stream depending on harness.

## Entry points

| Entry | Symbol / path |
|---|---|
| Schema identity | `src/features/feature_schema.py` · `CANONICAL_FEATURES` |
| Pipeline | `src/features/feature_pipeline.py` · `FeaturePipeline` |
| Geometry | `src/features/candle_math.py` |
| Derived scalars | `src/features/derived_math.py` |
| Formula facade | `src/features/formula_registry.py` + `src/features/registry/` |
| Ontology (meaning) | `configs/formulas/market_ontology.yaml` |
| Monitor | `src/features/feature_monitor.py` |
| Session clock | `src/features/broker_clock.py` |

## Exit points

| Exit | Consumer |
|---|---|
| Feature vectors / enriched frames | `EngineRunner`, CRT engine, models, BitNet (if enabled) |
| Schema hashes | Baseline capture, training guards |
| Drift stats | Backtest metrics / logs |
| Dataset artifacts | Training / RR builders |

## Important contracts

1. **Schema hash is load-bearing** — name/order/dim changes invalidate baselines/models.  
2. **Ontology first** for feature meaning; implementations must not re-derive unregistered math.  
3. Rolling indicator **periods** are config-driven (`feature_pipeline` section); geometric primitives are structural.  
4. `normalization_basis` / `session_timestamp_basis` are config-gated (defaults byte-identical legacy).  
5. Pipeline consumers in live vs backtest may differ (e.g. live_engine_hook feature map) — verify the call path.

## Reading order

1. This file.  
2. `src/features/feature_schema.py` (identity).  
3. `src/features/feature_pipeline.py` (emission).  
4. Ontology + `formula_registry` if math/ownership.  
5. Topic: `docs/topics/feature-schema.md`.  
6. Closure artifacts under `docs/governance/` when certification/lineage matters.

## Related documents

| Doc | Role |
|---|---|
| [`../topics/feature-schema.md`](../topics/feature-schema.md) | Topic index |
| [`../reference/schemas.md`](../reference/schemas.md) | Schema shapes |
| [`../governance/MARKET_ONTOLOGY_EVOLUTION_CONTRACT.md`](../governance/MARKET_ONTOLOGY_EVOLUTION_CONTRACT.md) | Ontology evolution |
| [`engine-memory.md`](engine-memory.md) | Downstream consumers |
| [`architecture-memory.md`](architecture-memory.md) | Layer placement |

## Known coverage

| Scope | Status |
|---|---|
| `src/features/` (~28 files) | ~43% name visibility in deep map (pipeline/schema heavy) |
| Full FM-* DAG certification | Governance artifacts — not duplicated here |
| Registry package internals | Read `src/features/registry/` as needed |

## Last generation timestamp

2026-08-07
