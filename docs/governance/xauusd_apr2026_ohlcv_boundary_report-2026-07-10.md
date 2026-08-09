# XAUUSD April-2026 OHLCV → Derived Mathematics Boundary Report

| Field | Value |
|---|---|
| Trace id | `XAUUSD-APR2026-OHLCV-BOUNDARY-2026-07-10` |
| Binding | frozen candidate `4d73f5ce…` / `data/mt5/XAUUSD_M15.csv` |
| Slice | April 2026 (1929 rows; first bar 2026-04-01T01:45:00) |

**There is not a single boundary.** Fan-out creates **multiple simultaneous first-derivation boundaries** depending on which consumer path is taken.

---

## Boundary inventory

### B-01 — candle_math geometry (scalar)

| Field | Value |
|---|---|
| boundary_id | `B-01_CANDLE_MATH` |
| upstream_stage | Candle OHLC fields (from CandleLoader or raw row) |
| downstream_stage | `features.candle_math` (`body_size`, `candle_range`, `body_ratio`, wicks) |
| source_fields_preserved | open, high, low, close (inputs only; not stored) |
| source_fields_dropped | volume (not consumed by candle_math) |
| source_fields_mutated | none (pure functions) |
| derived_fields_created | body_size, candle_range, upper_wick, lower_wick, total_wick, body_ratio |
| semantic_contract | immutable geometry identities; parity-tested vs FeaturePipeline vectorized forms |
| enforcement | `tests/test_candle_math.py`; formula registry / ontology |
| tests/probes | parity battery |
| status | **PROVEN** (STATIC_AND_EXECUTED — April sample body_ratio=0.629049…) |

### B-02 — FeaturePipeline batch enrichment

| Field | Value |
|---|---|
| boundary_id | `B-02_FEATURE_PIPELINE` |
| upstream_stage | OHLCV DataFrame (`pd.read_csv` dual-load or equivalent) |
| downstream_stage | `FeaturePipeline.run()` → enriched frame + 38-dim vectors |
| source_fields_preserved | timestamp, open, high, low, close, volume **remain columns** in enriched output |
| source_fields_dropped | 78 rows dropped in finalize (warmup NaNs) over full corpus |
| source_fields_mutated | **volume may be substituted** with high-low proxy when all volume zero (T-003 class; crypto path — XAU had nonzero volume in health logs) |
| derived_fields_created | candle_body, wicks, MAs, RSI, ATR, BB, volume_ratio, disp_strength, retest_depth, … + CANONICAL_FEATURES (38) |
| semantic_contract | 38-dim BitNet/feature schema; `center=True` swing noted in module docs |
| enforcement | feature_schema + schema_validator; FeatureMonitor drift log |
| tests/probes | feature pipeline tests; April retain 1929 rows / 38 features present |
| status | **PROVEN** (STATIC_AND_EXECUTED) |

**This is the primary “OHLCV becomes feature state” boundary for fusion/BitNet paths.**

### B-03 — CRT state machine

| Field | Value |
|---|---|
| boundary_id | `B-03_CRT_STATE_MACHINE` |
| upstream_stage | `Candle` stream (+ HTF id / active range from spine) |
| downstream_stage | `CRTEngine.process_candle` → state, events, cached_features |
| source_fields_preserved | candle OHLC used each bar |
| source_fields_dropped | N/A (state is additive) |
| source_fields_mutated | none of source bars; **internal range/sweep structures** are derived |
| derived_fields_created | CRTState, sweep/displacement structures, cached FM metrics |
| semantic_contract | VALID_TRANSITIONS / event taxonomy |
| enforcement | crt tests; spine BacktestRunner |
| tests/probes | isolated call **BLOCKED** without `active_range`; spine wiring STATIC PROVEN |
| status | **UNPROVEN as executed on April slice** / **PROVEN statically as consumer** |

### B-04 — Secondlow event geometry

| Field | Value |
|---|---|
| boundary_id | `B-04_SECONDLOW_EVENTS` |
| upstream_stage | full OHLCV series via `load_ohlcv` (pandas) |
| downstream_stage | independent purge events |
| source_fields_preserved | series used for geometry |
| source_fields_dropped | non-event bars |
| source_fields_mutated | none |
| derived_fields_created | purge_time, event descriptors |
| semantic_contract | secondlow_v1 detector rules |
| enforcement | regression tests on frozen candidate (60/36 partitions) |
| status | **PROVEN** (STATIC_AND_EXECUTED) |

### B-05 — Resample HTF aggregate

| Field | Value |
|---|---|
| boundary_id | `B-05_RESAMPLE_HTF` |
| upstream_stage | M15 Candle list |
| downstream_stage | `research.resample` → HTF OHLCV CSV |
| source_fields_preserved | OHLCV semantics at coarser bar |
| source_fields_mutated | OHLC recomputed by aggregation; volume summed/defined by resampler |
| derived_fields_created | new HTF rows |
| semantic_contract | calendar left-label (PROVEN for resample path per OHLCV contract) |
| status | **PROVEN** statically; **LATENT** for this XAU April run (not executed) |

### B-06 — forward_walk labels/exits

| Field | Value |
|---|---|
| boundary_id | `B-06_FORWARD_WALK` |
| upstream_stage | entry candle + future candle path |
| downstream_stage | outcome R / hit labels |
| source_fields_preserved | path prices used |
| derived_fields_created | exit reason, R multiple, time-to-outcome |
| status | **PROVEN** statically (HypothesisRunner); not executed on April XAU slice |

---

## Source-field mutation summary

| Mutation class | Where | April XAU evidence |
|---|---|---|
| None (pure validate) | L1/L2 | PROVEN |
| Volume proxy substitution | FeaturePipeline T-003 | Mechanism present; XAU volume not all-zero in health summary |
| Row drop (warmup) | FeaturePipeline.finalize | 78 rows / full corpus |
| Path rewrite | Phase-1 guard | PROVEN (root → mt5) |
| Aggregation OHLC | resample | STATIC only |

---

## Multi-boundary conclusion

```text
FIRST_DERIVATION_BOUNDARIES =
  B-01 candle_math
  B-02 FeaturePipeline
  B-03 CRTEngine (spine-dependent)
  B-04 secondlow detector
  B-05 resample (latent this run)
  B-06 forward_walk (latent this run)
```

OHLCV does **not** end at a single stage. Source fields often **coexist** with derived columns (B-02) until a consumer drops them (event extractors, feature vectors, metrics).
