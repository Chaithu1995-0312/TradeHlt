# Encyclopedia E1b — Feature Pipeline & Registry (deep map)

**Phase:** E1b  
**Status:** DONE (file-level map of `src/features/` — 28 modules)  
**Date:** 2026-08-07  
**Parent:** [Chapter 24](../24-repository-encyclopedia.md) · [E1 spine](E1-spine-implementation.md) · [Encyclopedia index](README.md)  
**Architecture narrative:** [Chapter 06](../06-market-ontology.md) · [Chapter 07](../07-feature-pipeline.md)

## Scope

| Surface | Count | Role |
|---|---:|---|
| `src/features/*.py` (top-level) | 23 | Pipeline, schema, semantic layers, builders, monitors |
| `src/features/registry/` | 5 | **Authoritative feature-math implementation** (no `eval`) |
| **Total** | **28** | Group A feature surface (was DIR_ORIENTED under E1 only) |

**Authority model (immutable):**

```text
configs/formulas/market_ontology.yaml   → DECLARES meaning (WHAT)
src/features/registry/* + candle_math/derived_math → IMPLEMENTS math (HOW)
src/features/feature_pipeline.py        → EMITS 39-dim vector (v4.0)
src/features/feature_schema.py          → NAMES / pins CANONICAL_FEATURES
```

Never re-derive formula math in engines/scripts — use registry / `derived_math` / pipeline (F-047, ownership lint).

**Book status:** `feature_pipeline.py` + `feature_schema.py` **CITED** in Ch.07; all other modules were package-oriented until this E1b map.

---

## Layer map (semantic pipeline)

| Layer | Module(s) | Role |
|---|---|---|
| L0 OHLC identity | `candle_math.py`, `registry/primitive_registry.py` | Immutable geometry (body, wick, range, ratios) |
| L1 derived scalars | `derived_math.py`, `registry/derived_registry.py` | ATR-relative / normalized metrics (FM-0NN) |
| L1 compositions | `registry/composition_registry.py` | Named ratios over primitives |
| Registry facade | `formula_registry.py`, `registry/__init__.py`, `registry/_loader.py` | FORMULA_REGISTRY + ontology load |
| FM resolve | `fm_resolve.py` | FM-id → callable (fail-closed) |
| Identity | `feature_identity.py` | feature_id collision / governed identities |
| Batch pipeline | `feature_pipeline.py` | Production 39-dim vector builder |
| Schema pin | `feature_schema.py`, `schema_validator.py` | CANONICAL_FEATURES / dim / fail-fast validate |
| Online builders | `feature_builder.py`, `crt_feature_builder.py` | Tick/row → input_data / CRT→canonical dict |
| Structure / PIT | `causal_structure.py` | FC1-A delayed-confirmed swings (no lookahead) |
| Session / clock | `session_classifier.py`, `broker_clock.py` | Session ownership; MT5 UTC correction (F-066) |
| Semantic L2 | `feature_states.py` | Feature values → declared states |
| Semantic L4 | `market_context.py` | States → market context |
| Semantic L5 | `market_shape.py` | Context → recurring shapes |
| Semantic L5 CRT | `crt_state_resolver.py` | Feature states → CRT 9-state resolve (parity with engine) |
| Semantic L7 | `model_evidence.py` | Model testimony per bar |
| Contracts | `gaussian_schema_contract.py` | Gaussian NB schema under v4 migration |
| Dataset prep | `dataset_builder.py`, `dataset_validator.py` | Train/log feature extract + validate |
| Drift | `feature_monitor.py` | Rolling distribution / Z-drift on trades |
| Package | `__init__.py` | Exports |

---

## 1. Math authority (immutable primitives + registry)

### `src/features/candle_math.py`
- **Group:** A · **Relevance:** LIVE · **Book:** DIR_ORIENTED (E1b deep)
- **Purpose:** Single immutable source for candle geometry identities (body/wick/range/ratios). Mechanism not policy (F-046 class).
- **Relationships:** Used by pipeline, CRT, registry primitives; parity-tested.
- **Chapter:** Ch.06–07; F-046.

### `src/features/derived_math.py`
- **Group:** A · **Relevance:** LIVE
- **Purpose:** Scalar implementations of deterministic normalized metrics (disp_strength/retest/… FM forms). Sibling of candle_math.
- **Relationships:** `registry/derived_registry.py` maps ontology impl names here (no eval).
- **Chapter:** Ch.06–07; F-047/F-050/F-063.

### `src/features/registry/primitive_registry.py`
- **Group:** A · **Relevance:** LIVE
- **Purpose:** Maps ontology primitive impl names → `candle_math` callables.
- **Chapter:** Ch.06.

### `src/features/registry/composition_registry.py`
- **Group:** A · **Relevance:** LIVE
- **Purpose:** Trading-interpretation ratios (named callables over primitives).
- **Chapter:** Ch.06.

### `src/features/registry/derived_registry.py`
- **Group:** A · **Relevance:** LIVE
- **Purpose:** Maps derived FM impl names → `derived_math` callables + signature dispatch.
- **Chapter:** Ch.06.

### `src/features/registry/_loader.py`
- **Group:** A · **Relevance:** LIVE
- **Purpose:** Leaf ontology YAML loader (lazy PyYAML); avoids import cycles.
- **Relationships:** Reads `configs/formulas/market_ontology.yaml`.
- **Chapter:** Ch.06.

### `src/features/registry/__init__.py`
- **Group:** A · **Relevance:** LIVE
- **Purpose:** Authoritative aggregated feature-math registry API (FORMULA_REGISTRY, validation helpers).
- **Chapter:** Ch.06–07; F-047.

### `src/features/formula_registry.py`
- **Group:** A · **Relevance:** LIVE
- **Purpose:** Back-compat facade re-exporting the registry package (do not re-implement math here).
- **Chapter:** Ch.06.

### `src/features/fm_resolve.py`
- **Group:** A · **Relevance:** LIVE
- **Purpose:** Phase-2 FM resolution: FM-id → callable via ontology + FORMULA_REGISTRY (Option A).
- **Entry points:** Certification tooling, consumers needing FM-id dispatch.
- **Chapter:** Ch.06; E3 feature_dag tools.

### `src/features/feature_identity.py`
- **Group:** A · **Relevance:** LIVE
- **Purpose:** Fail-closed feature_id lookup; governs duplicate/collision families (phase-1 identity registry docs).
- **Chapter:** Ch.07 governance adjacent.

---

## 2. Production vector emission & schema

### `src/features/feature_pipeline.py`
- **Group:** A · **Relevance:** LIVE · **Book:** CITED (Ch.07)
- **Purpose:** Production-grade M15 OHLCV → deterministic vector of length `CANONICAL_FEATURE_DIM` (39, v4.0). Config-driven indicator periods (`feature_pipeline` section).
- **Relationships:** Backtest + live feature build; BitNet/Zone/CRT consumers of vector slots.
- **Chapter:** Ch.07; F-061/F-066 config gates (`normalization_basis`, `session_timestamp_basis`).

### `src/features/feature_schema.py`
- **Group:** A · **Relevance:** LIVE · **Book:** CITED (Ch.07)
- **Purpose:** Canonical feature names, dim, schema objects, hash pins. Source of truth for 39-dim order.
- **Note:** Reference docs may lag (38 vs 39) — code wins.
- **Chapter:** Ch.07; F-062.

### `src/features/schema_validator.py`
- **Group:** A · **Relevance:** LIVE
- **Purpose:** Strict fail-fast validator for the canonical feature contract.
- **Entry points:** Dataset/train preflight; tests.
- **Chapter:** Ch.07.

### `src/features/gaussian_schema_contract.py`
- **Group:** A · **Relevance:** LIVE-contract
- **Purpose:** Gaussian NB feature-schema contract under SCHEMA-V4-VECTOR-MIGRATION (dim renames).
- **Chapter:** Ch.10 Gaussian; F-062 class.

---

## 3. Online / CRT builders

### `src/features/feature_builder.py`
- **Group:** A · **Relevance:** LIVE
- **Purpose:** Constructs canonical `input_data` dict from raw tick/row; enforces mandatory OHLCV.
- **Relationships:** Live/engine paths needing lightweight build vs full batch pipeline.
- **Chapter:** Ch.07 adjacent.

### `src/features/crt_feature_builder.py`
- **Group:** A · **Relevance:** LIVE / PARTIAL
- **Purpose:** CRT trade/candle/state → dict with **exactly** all CANONICAL_FEATURES. Historical body_ratio outlier path audited (F-046 — prefer candle_math).
- **Chapter:** Ch.07–08.

### `src/features/causal_structure.py`
- **Group:** A · **Relevance:** LIVE
- **Purpose:** FC1-A delayed-confirmed structure publication helpers (PIT-safe swings). Batch authority via pipeline structure/liquidity columns.
- **Chapter:** Ch.07; F-051 class.

---

## 4. Session & broker clock

### `src/features/session_classifier.py`
- **Group:** A · **Relevance:** LIVE
- **Purpose:** **Single owner** of “what session is this?” — deliberately separates feature session labels vs CRT filter windows (F-066 doctrine).
- **Chapter:** Ch.07; F-017/F-066.

### `src/features/broker_clock.py`
- **Group:** A · **Relevance:** LIVE (config-gated)
- **Purpose:** Convert MT5 broker-server timestamps to true UTC when `session_timestamp_basis=utc_corrected`. Default `broker_local` is byte-identical legacy.
- **Relationships:** `mt5_candle_fetcher` labeling; feature_pipeline session path.
- **Chapter:** Ch.07; F-066.

---

## 5. Semantic stack (states → context → shape → CRT resolve → model evidence)

### `src/features/feature_states.py`
- **Group:** A · **Relevance:** LIVE-semantic
- **Purpose:** Layer 2 — feature VALUES → declared semantic STATES (`market_crt_states` / ontology feature_states).
- **Chapter:** Ch.06–08 semantic pipeline.

### `src/features/market_context.py`
- **Group:** A · **Relevance:** LIVE-semantic
- **Purpose:** Layer 4 — combine states into full market context (“what is happening”).
- **Chapter:** Ch.06.

### `src/features/market_shape.py`
- **Group:** A · **Relevance:** LIVE-semantic
- **Purpose:** Layer 5 — assign recurring shape identity (`configs/formulas/market_shapes.yaml` class).
- **Chapter:** Ch.06 / Ch.09 adjacent.

### `src/features/crt_state_resolver.py`
- **Group:** A · **Relevance:** LIVE-semantic / RESEARCH-parity
- **Purpose:** Resolve 9 CRT states from declared feature states (declarative path). Semantic parity with `crt_engine_v2` is incomplete by construction (F-069) — not a drop-in replacement for the engine.
- **Chapter:** Ch.08; F-069.

### `src/features/model_evidence.py`
- **Group:** A · **Relevance:** LIVE-semantic
- **Purpose:** Layer 7 — record what each model says about the bar (testimony), not what the market is.
- **Chapter:** Ch.06 semantic stack.

---

## 6. Dataset, validation, drift

### `src/features/dataset_builder.py`
- **Group:** A · **Relevance:** TRAIN/RESEARCH
- **Purpose:** Extract feature vectors / BitNet slices from fusion logs for training datasets.
- **Chapter:** Ch.07; training E4/E6.

### `src/features/dataset_validator.py`
- **Group:** A · **Relevance:** TRAIN/RESEARCH
- **Purpose:** Validate fusion trade logs before dataset build or model training (entropy, balance, min-n).
- **Chapter:** Ch.16 training quality gates.

### `src/features/feature_monitor.py`
- **Group:** A · **Relevance:** LIVE-ops
- **Purpose:** Rolling feature distribution + drift (Z-scores); wired on TRADE_OPENED in backtest (CLAUDE Phase 2).
- **Chapter:** Ch.07; FeatureMonitor in backtest_v2.

### `src/features/__init__.py`
- **Group:** A · **Relevance:** LIVE
- **Purpose:** Package exports / marker.

---

## Config keys (feature surface)

| Config area | Examples | Effect |
|---|---|---|
| `feature_pipeline` | `rsi_period`, `atr_period`, `ema_*`, `macd_*`, `normalization_basis`, `session_timestamp_basis` | Periods + F-061/F-066 gates |
| Ontology YAML | `configs/formulas/market_ontology.yaml` | FM identities / lifecycle |
| Shapes YAML | `configs/formulas/market_shapes.yaml` | Shape declarations |
| CRT states YAML | market_crt_states (semantic) | State predicates for resolver |

---

## Tests & lint (pointers)

| Surface | Role |
|---|---|
| `tests/test_feature_pipeline.py`, `tests/test_candle_math.py` | Pipeline / geometry |
| `scripts/analysis/feature_math_lint.py` | Ownership lint — no new local formula math |
| E3 `feature_dag_*`, `feature_surface_query` | Certification / query API |
| `tests/test_schema_contracts.py` | Schema pins |

---

## Danger flags

| Flag | Meaning |
|---|---|
| **NO_LOCAL_FORMULA_MATH** | New quantities register in ontology → registry first |
| **PIT_SENSITIVE** | Swings/structure must stay causal (F-051) |
| **DIM_PIN** | Schema hash load-bearing — dim change invalidates baselines |
| **RESOLVER_≠_ENGINE** | `crt_state_resolver` not byte-identical to crt_engine_v2 (F-069) |
| **DOC_DRIFT** | *(historical flag; `schemas.md` §4 was corrected to 39-dim/v4.0 on 2026-08-07 — see [Ch.07](../07-feature-pipeline.md))* |

---

## E1b exit criterion

| Criterion | Status |
|---|---|
| All 28 `src/features/**/*.py` files have purpose rows | **Met** |
| Registry authority chain documented | **Met** |
| Semantic layers L2/L4/L5/L7 + CRT resolver placed | **Met** |
| Linked to Ch.06–07 and F-ids | **Met** |

---
**Related:** [Ch.06](../06-market-ontology.md) · [Ch.07](../07-feature-pipeline.md) · [E1](E1-spine-implementation.md) · [E3 feature DAG](E3-governance-tooling.md) · Machine twin: `encyclopedia_rows.jsonl`
