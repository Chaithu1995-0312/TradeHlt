# Ontology Runtime Reachability Audit

> **Date:** 2026-07-25
> **Source:** `configs/formulas/market_ontology.yaml` (2304 lines, 63 entities)
> **Purpose:** Trace which ontology content is actually read at runtime vs. which is documentation-only.
> **Classification:** Analysis — describes current state, does not change behaviour.

---

## 1. The Ontology Sections and Their Contents

| Section | Count | Scope |
|---|---|---|
| `base_inputs` | 13 | OHLCV + structural reference leaves |
| `primitives` (FM-001..005) | 5 | Mathematical identities over OHLC |
| `feature_compositions` (FM-010..013) | 4 | Ratios of two primitives |
| `derived_metrics` (FM-020..031) | 12 | Deterministic normalized quantities |
| `rolling_indicators` (FM-040..067) | 16 | Windowed indicators (pipeline-computed) |
| `temporal_context` (FM-051..052) | 2 | Calendar projections from timestamps |
| `structural_states` (FM-054..069) | 10 | Event/classification flags (pipeline-computed) |
| `indicator_identities` | 2 | Historical descriptive records (superseded) |
| `migration_candidates` | 2 | Superseded by FM-030/FM-031 |
| Semantic Registry (`execution_behaviours`, `invariants`, `canonical_unknowns`) | 4 | SEM-001..003, UNK-001 |
| **Total** | **63** | **Complete ontology inventory** |

---

## 2. FORMULA_REGISTRY Contents (17 callables)

`FORMULA_REGISTRY = {**PRIMITIVES, **DERIVED}` — built in `src/features/registry/__init__.py:26`.

### PRIMITIVES (5 callables)

| Ontology Name | FM-ID | Python Callable | `impl` key |
|---|---|---|---|
| `body_size` | FM-001 | `candle_math.body_size` | `candle_math.body_size` |
| `candle_range` | FM-002 | `candle_math.candle_range` | `candle_math.candle_range` |
| `upper_wick` | FM-003 | `candle_math.upper_wick` | `candle_math.upper_wick` |
| `lower_wick` | FM-004 | `candle_math.lower_wick` | `candle_math.lower_wick` |
| `total_wick` | FM-005 | `candle_math.total_wick` | `candle_math.total_wick` |

### DERIVED (12 callables)

| Ontology Name | FM-ID | Python Callable | `impl` key |
|---|---|---|---|
| `disp_strength` | FM-020 | `derived_math.disp_strength` | `derived_math.disp_strength` |
| `retest_depth` | FM-021 | `derived_math.retest_depth` | `derived_math.retest_depth` |
| `ema_spread` | FM-022 | `derived_math.ema_spread` | `derived_math.ema_spread` |
| `momentum_score` | FM-023 | `derived_math.momentum_score` | `derived_math.momentum_score` |
| `volatility_ratio` | FM-024 | `derived_math.volatility_ratio` | `derived_math.volatility_ratio` |
| `liquidity_distance` | FM-025 | `derived_math.liquidity_distance` | `derived_math.liquidity_distance` |
| `liquidity_pressure_score` | FM-026 | `derived_math.liquidity_pressure_score` | `derived_math.liquidity_pressure_score` |
| `displacement_retrace` | FM-027 | `derived_math.displacement_retrace` | `derived_math.displacement_retrace` |
| `displacement_atr_ratio` | FM-028 | `derived_math.displacement_atr_ratio` | `derived_math.displacement_atr_ratio` |
| `disp_strength_atr_rescale` | FM-029 | `derived_math.disp_strength_atr_rescale` | `derived_math.disp_strength_atr_rescale` |
| `ema_spread_atr` | FM-030 | `derived_math.ema_spread_atr` | `derived_math.ema_spread_atr` |
| `momentum_score_atr` | FM-031 | `derived_math.momentum_score_atr` | `derived_math.momentum_score_atr` |

---

## 3. Features in Ontology but NOT in FORMULA_REGISTRY (32 entities)

### Feature Compositions (4) — separate `compute_composition()` path

| FM-ID | Name | Resolution |
|---|---|---|
| FM-010 | `body_ratio` | numerator `body_size` / denominator `candle_range` via `PRIMITIVE_SHORTNAME` |
| FM-011 | `upper_wick_ratio` | numerator `upper_wick` / denominator `candle_range` |
| FM-012 | `lower_wick_ratio` | numerator `lower_wick` / denominator `candle_range` |
| FM-013 | `body_to_total_wick_ratio` | numerator `body_size` / denominator `total_wick` |

### Rolling Indicators (16) — pipeline-computed, no scalar form

| FM-ID | Name | Reason for exclusion |
|---|---|---|
| FM-040 | `true_range` | Uses `prev_close` — windowed (lookback=1) |
| FM-041 | `atr` | SMA of true_range over 14 bars |
| FM-042 | `rsi_14` | SMA gain/loss averaging over 14 bars |
| FM-043 | `ema_fast` | EWMA of close over span 9 |
| FM-044 | `ema_slow` | EWMA of close over span 21 |
| FM-045 | `swing_high` | Centered pivot over width 2k+1, k-bar delay |
| FM-046 | `swing_low` | Centered pivot over width 2k+1, k-bar delay |
| FM-047 | `macd_line` | EWM(12) - EWM(26) of close |
| FM-048 | `macd_signal` | EWM(9) of macd_line |
| FM-049 | `macd_hist_raw` | macd_line - macd_signal |
| FM-053 | `macd_hist_z` | Rolling z-score over window 50 |
| FM-050 | `volatility_regime` | Tercile rank over trailing percentile window |
| FM-062 | `volume_ratio` | volume / SMA(volume, 20) |
| FM-063 | `volume_spike` | Adaptive trailing percentile threshold |
| FM-066 | `last_swing_high_price` | Stateful forward-fill of pivot high |
| FM-067 | `last_swing_low_price` | Stateful forward-fill of pivot low |

### Temporal Context (2) — calendar projections, no scalar market-math form

| FM-ID | Name | Reason for exclusion |
|---|---|---|
| FM-051 | `hour_of_day` | `timestamp.dt.hour` — not a price computation |
| FM-052 | `session` | Window model over hour buckets |

### Structural States (10) — event/classification flags, pipeline-computed

| FM-ID | Name | Formula summary |
|---|---|---|
| FM-054 | `trend_bias` | `sign(ema_fast - ema_slow)` {-1,0,+1} |
| FM-055 | `higher_high` | `high > prev(last_swing_high_price)` {0,1} |
| FM-056 | `lower_low` | `low < prev(last_swing_low_price)` {0,1} |
| FM-057 | `break_of_structure` | Close-based directional break {-1,0,+1} |
| FM-058 | `liquidity_sweep` | Stop-run detection {-1,0,+1} |
| FM-059 | `sweep_detected` | `liquidity_sweep != 0` {0,1} |
| FM-060 | `double_sweep` | Both sweep directions within trailing window {0,1} |
| FM-061 | `retest_flag` | Recent sweep + price within ATR band of EMA |
| FM-068 | `rsi_state` | Ternary RSI interpretation {-1,0,+1} |
| FM-069 | `displacement_flag` | Body-dominated candle marker {0,1} |

**Total not in FORMULA_REGISTRY: 32**

---

## 4. Runtime Reading Points

### 4.1 Hot Path (called on every bar)

```
crt_engine_v2.py:34    → _FM_CRT = bind_phase2_crt_callables()   # called ONCE at import
crt_engine_v2.py:92    → _FM_CRT["FM-002"](high, low)            → candle_range
crt_engine_v2.py:97    → _FM_CRT["FM-010"](open, high, low, close) → body_ratio
crt_engine_v2.py:1548  → _FM_CRT["FM-028"](candle_range, atr)   → displacement_atr_ratio
crt_engine_v2.py:1596  → _FM_CRT["FM-027"](retest_close, ...)   → displacement_retrace
crt_engine_v2.py:1601  → _FM_CRT["FM-028"](candle_range, atr)   → displacement_atr_ratio (again)
```

**Ontology fields read:** `impl` (from primitives, derived_metrics); `numerator`/`denominator` (from feature_compositions)

**Resolution chain:**
1. `fm_resolve._ontology_index()` loads ontology YAML and indexes `id` → metadata
2. `resolve_fm(fm_id)` looks up `impl` name, resolves through `FORMULA_REGISTRY` or `compute_composition()`
3. `bind_phase2_crt_callables()` asserts registry identity (FM-002===candle_math.candle_range, etc.)
4. Result cached in module-level `_FM_CRT` dict — no further ontology reads on subsequent bars

### 4.2 Shadow Path (research only — FeatureStateEncoder)

```
FeatureStateEncoder.__init__() → load_ontology()
  → iterates ALL 6 iterated sections
  → reads "states" blocks (value → semantic state name)
  → reads "taxonomy.category" (Market Context dimension)
  → reads "lineage.vector_key" (to map to canonical index)
```

Used by `CRTStateResolver` → NOT on the trading decision path.

### 4.3 Test/Script Path

| Function | What it reads | Where called |
|---|---|---|
| `validate_registry()` | id, impl, lifecycle, formula, computation_class, numerator, denominator, depends_on, states, taxonomy, semantics, lineage | Test suite |
| `validate_semantic_registry()` | All semantic registry nodes (execution_behaviours, invariants, canonical_unknowns) | Test suite |
| `build_lineage_graph()` | depends_on from all entries + base_inputs | Analysis scripts |
| `resolve_fm(fm_id)` | impl, lifecycle, numerator, denominator | Tests, manual resolution |
| `compute_derived(name, **inputs)` | derived_metrics[name].impl | Tests |

---

## 5. Ontology Fields Never Read at Runtime

| Field | Used where? | Status |
|---|---|---|
| `formula` (YAML string) | Documentation | Never eval'd |
| `semantics.description` | Human-readable | Documentation only |
| `semantics.why_it_exists` | Human-readable | Documentation only |
| `semantics.interpretation` | Human-readable | Documentation only |
| `taxonomy.knowledge_class` | Classification metadata | Documentation only (except category read by FeatureStateEncoder) |
| `lineage.derivation_depth` | Descriptive integer | Documentation only |
| `lineage.consumed_by` | Documentation | Documentation only |
| `lineage.produced_by` | Documentation | Documentation only |
| `config_keys` | Config binding | Pipeline code owns these, not ontology |
| `clip` | Bounds description | Documentation only |
| `bounded` | Domain description | Documentation only |
| `aliases` | Historical record | Documentation only |
| `note` / `notes` | Prose commentary | Documentation only |
| `indicator_identities.*` | Historical descriptive | Superseded by rolling_indicators |
| `migration_candidates.*` | Historical proposed | Superseded by FM-030/FM-031 |
| `semantic_registry.*` | Knowledge nodes | Validated by tests only |
| `spec_schema.*` | Schema contract | Schema documentation only |

---

## 6. Summary

| Metric | Count |
|---|---|
| Ontology entities (total) | 63 |
| In FORMULA_REGISTRY (executable scalar callables) | 17 |
| Of which on hot path (called every bar) | 4 (FM-002, FM-010, FM-027, FM-028) |
| Of which reachable via `resolve_fm`/`compute_derived` only | 13 |
| Not in FORMULA_REGISTRY (pipeline-computed, no scalar form) | 32 |
| Composition path (via PRIMITIVE_SHORTNAME) | 4 |
| Rolling indicators | 16 |
| Temporal context | 2 |
| Structural states | 10 |
| Semantic registry nodes (tests only) | 4 |
| Indicator identities / migration candidates (historical) | 4 |
| Ontology fields read on hot path | 3 (`impl`, `numerator`, `denominator`) |
| Ontology fields read on shadow path | 3 (`states`, `taxonomy.category`, `lineage.vector_key`) |
| Ontology fields never read at runtime | ~25+ (all `formula`, `semantics`, `lineage.consumed_by`, etc.) |

### Key Architectural Insight

The ontology serves two distinct purposes:

1. **Executable surface (~40 YAML lines):** `impl`, `numerator`, `denominator` → resolve to Python callables on the CRT engine import path
2. **Knowledge specification (~2260 lines):** `formula` strings, `semantics`, `lineage`, `states`, `taxonomy` → documentation and test validation only

The ontology's `formula` strings are **never eval'd at runtime**. They exist for human/LLM readers to understand what each feature means. The actual computation is governed by `FORMULA_REGISTRY` (for scalar features) and the pipeline code (for rolling/structural/temporal features).