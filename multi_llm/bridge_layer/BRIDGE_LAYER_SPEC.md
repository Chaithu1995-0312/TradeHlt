# Bridge Layer Specification — Tradelatest

_Generated: 2026-09-24 01:18 IST. Repository is sole authority. Measurement-system catalog — no setups, no directional teaching._

## Ontology chain

```
OHLCV ingestion
  → Feature Ontology
  → State Ontology
  → Decision Ontology
  → Measurement Ontology
```

| Layer | Authority (repo paths) | `layer_dependency_graph` node |
|---|---|---|
| **OHLCV ingestion** | `src/data_ingestion/ohlcv_schema.py`<br>`src/data_ingestion/corpus_store.py`<br>`src/data_ingestion/corpus_gate.py` | `data_ingestion` |
| **Feature Ontology** | `src/features/feature_schema.py`<br>`src/features/feature_pipeline.py`<br>`userinvestigation/CANONICAL_FEATURES.html`<br>`src/features/smc/*` | `features` |
| **State Ontology** | `src/features/crt_state_resolver.py`<br>`src/config_layer/crt_engine_v2.py`<br>`src/config_layer/state_identity.py`<br>`configs/formulas/market_crt_states.yaml` | `config_layer` |
| **Decision Ontology** | `active_models.yaml`<br>`src/core/decision_engine.py`<br>`src/core/engine_runner.py`<br>`src/core/gate_intelligence.py` | `core / engines` |
| **Measurement Ontology** | `multi_llm/parameter_usage_audit/MC-OPP-DETECT-01.json`<br>`multi_llm/parameter_usage_audit/MC-JOINT-01.json`<br>`src/research/measurement/trade_lifecycle_engine.py`<br>`src/research/measurement/forward_walk.py` | `research` |

Grounding graphs: `multi_llm/layer_dependency_graph.jsonl`, `multi_llm/story_dependency_graph.jsonl`.

### Chain notes (evidence)

1. **OHLCV** — `data_ingestion.ohlcv_schema.REQUIRED_OHLCV_COLUMNS`; corpus admission stamps `dataset_identity` for MC-OPP-DETECT-01.
2. **Features** — `feature_schema.CANONICAL_FEATURES` (48, schema v6.0) produced by `FeaturePipeline.run`; SMC package fills indices 39–47.
3. **States** — Execution funnel from `active_models.yaml` / `_crt_state_generated.CRTState`; research predicates in `market_crt_states.yaml` via `CRTStateResolver`; live execution authority remains `CRTEngine` (`crt_engine_v2.py`). Parent C1/C2/C3 is a disjoint sub-graph (`parent_crt.ParentCRTTrack`).
4. **Decision** — `active_models.yaml` + `core.decision_engine` / `engine_runner` / fusion engines per `docs/architecture/module-roles.generated.md`.
5. **Measurement** — MC-OPP-DETECT-01 (detection) → MC-JOINT-01 + `trade_lifecycle_engine.measure` (`Y_scanner`, `Y_oracle`, `Y_joint`, `authority_outcome`).

## Concept catalog

Seven fields per concept. `STATUS` = BOUND | PARTIAL | UNBOUND.

### `OHLCV` — **BOUND**

- **1. Observable definition:** Mandatory broker bar contract: columns {timestamp, open, high, low, close, volume}. Presence, integrity, and reviewed clock provenance enforced before feature work (data_ingestion.ohlcv_schema.REQUIRED_OHLCV_COLUMNS / require_ohlcv_columns / validate_ohlcv_frame).
- **2. Feature representation:** `{"canonical_indices": {"open": 0, "high": 1, "low": 2, "close": 3, "volume": 4}, "schema_version": "6.0", "dim": 48}`
- **3. State representation:** None as CRT enum; raw bar is pre-state. CRTEngine.process_candle consumes Candle from OHLCV.
- **4. Authority module:** `{"path": "src/data_ingestion/ohlcv_schema.py", "symbols": ["REQUIRED_OHLCV_COLUMNS", "require_ohlcv_columns", "validate_ohlcv_frame"]}`
- **5. Storage representation:** `["Admitted corpus via data_ingestion.corpus_store (Parquet read-cache over broker OHLCV)", "MC-OPP-DETECT-01 dataset_identity.{csv_sha256, dataset_id} stamps opportunity rows"]`
- **6. Evidence artifact:** `["src/data_ingestion/ohlcv_schema.py", "docs/architecture/module-roles.generated.md", "multi_llm/parameter_usage_audit/MC-OPP-DETECT-01.json"]`
- **7. Directly observable vs derived:** OBSERVABLE
- **Citations:** `src/data_ingestion/ohlcv_schema.py`, `src/features/feature_schema.py`, `docs/architecture/code-map.generated.md`

### `range` — **BOUND**

- **1. Observable definition:** Three repo bindings kept separate: (1) CRT ground state RANGE (configs/formulas/market_crt_states.yaml + CRTState.RANGE); (2) M15 structural liquidity range / active_range — h_ref=max(high), l_ref=min(low) over child window (config_layer.m15_structural_range.from_child_window / RangeDetector.detect_m15_structural_range); (3) vector feature candle_range = high-low (CANONICAL index 28). Parent reference candle state is RANGE_C1 (disjoint sub-graph).
- **2. Feature representation:** `{"candle_range": {"index": 28, "formula": "high - low"}}`
- **3. State representation:** `{"execution": "RANGE", "parent": "RANGE_C1", "engine_object": "M15StructuralLiquidityRange {h_ref, l_ref, equilibrium, clock_id}"}`
- **4. Authority module:** `{"path": "src/config_layer/crt_engine_v2.py", "symbols": ["RangeDetector.detect_m15_structural_range", "RangeDetector.detect_htf_range"], "also": ["src/config_layer/m15_structural_range.py::from_child_window", "src/features/crt_state_resolver.py", "src/config_layer/parent_crt.py::ParentCRTTrack._become_c1"]}`
- **5. Storage representation:** `["Feature column candle_range in pipeline / clean_labels vectors", "Engine active_range fields; results/layer_trace/*_layer_trace.jsonl joins"]`
- **6. Evidence artifact:** `["src/config_layer/m15_structural_range.py", "configs/formulas/market_crt_states.yaml", "src/features/feature_schema.py", "active_models.yaml"]`
- **7. Directly observable vs derived:** MIXED: candle_range=OBSERVABLE; structural active_range and CRT RANGE=DERIVED
- **Citations:** `src/config_layer/crt_engine_v2.py::RangeDetector`, `src/config_layer/m15_structural_range.py`, `src/features/feature_schema.py`, `configs/formulas/market_crt_states.yaml`

### `liquidity` — **BOUND**

- **1. Observable definition:** Resting reference levels/pools via distance and pressure, plus the M15 structural liquidity range used as the CRT sweep envelope. Features: liquidity_distance (ATR-normalised distance to nearest liquidity level), liquidity_pressure_score ([0,1]). EQH/EQL/PDH/PDL are resting-liquidity levels. No standalone boolean feature named only liquidity.
- **2. Feature representation:** `{"liquidity_distance": {"index": 36}, "liquidity_pressure_score": {"index": 37}, "liquidity_sweep": {"index": 21, "role": "event on liquidity levels"}, "related_levels": ["eqh_distance", "eql_distance", "pdh_distance", "pdl_distance"]}`
- **3. State representation:** No CRT enum LIQUIDITY. Envelope: M15_STRUCTURAL_LIQUIDITY_RANGE (SEM-011).
- **4. Authority module:** `{"path": "src/features/feature_pipeline.py", "symbols": ["FeaturePipeline.compute_structure_liquidity", "FeaturePipeline.compute_liquidity_distance"], "also": ["src/config_layer/m15_structural_range.py", "src/features/smc/levels.py"]}`
- **5. Storage representation:** `["Canonical vector slots 36-37", "clean_labels / opportunities features.* (MC-OPP-DETECT-01 may_drift_prefixes)"]`
- **6. Evidence artifact:** `["src/features/feature_schema.py", "userinvestigation/CANONICAL_FEATURES.html", "docs/architecture/module-roles.generated.md"]`
- **7. Directly observable vs derived:** DERIVED
- **Citations:** `src/features/feature_schema.py`, `src/features/feature_pipeline.py`, `src/config_layer/m15_structural_range.py`

### `sweep` — **BOUND**

- **1. Observable definition:** Engine: RangeDetector.detect_sweep — pierce active_range boundary then close back inside (swept_high/swept_low); founds CRTState.SWEEP via try_range_to_sweep. Features: liquidity_sweep in {+1,-1,0} from (high>ref_high & close<=ref_high)/(low<ref_low & close>=ref_low); sweep_detected=(liquidity_sweep!=0); double_sweep; candles_since_sweep. Resolver SWEEP.when may be bypassed for founding when thresholds.sweep_geometry=htf_range.
- **2. Feature representation:** `{"sweep_detected": {"index": 20}, "liquidity_sweep": {"index": 21}, "double_sweep": {"index": 6}, "candles_since_sweep": {"index": 35}}`
- **3. State representation:** `{"execution": "SWEEP", "memory": "SHADOW_PENDING", "parent_analogue": "MANIPULATION_C2"}`
- **4. Authority module:** `{"path": "src/config_layer/crt_engine_v2.py", "symbols": ["RangeDetector.detect_sweep", "StateMachine.try_range_to_sweep"], "also": ["src/features/feature_pipeline.py::compute_structure_liquidity", "src/features/crt_state_resolver.py"]}`
- **5. Storage representation:** `["Feature columns sweep_detected, liquidity_sweep, double_sweep, candles_since_sweep", "SweepEvent on engine state; layer_trace / CRT traces"]`
- **6. Evidence artifact:** `["src/config_layer/crt_engine_v2.py::RangeDetector.detect_sweep", "configs/formulas/market_crt_states.yaml", "userinvestigation/CANONICAL_FEATURES.html"]`
- **7. Directly observable vs derived:** DERIVED (requires active_range or swing refs)
- **Citations:** `src/config_layer/crt_engine_v2.py`, `src/features/feature_pipeline.py`, `configs/formulas/market_crt_states.yaml`, `src/features/feature_schema.py`

### `displacement` — **BOUND**

- **1. Observable definition:** CRT funnel SWEEP->DISPLACEMENT only (try_sweep_to_displacement): ATR body size, body_ratio, candle_range gates plus directional impulse away from swept side. Feature: disp_strength = clip(body_size/(atr*close), ...) at index 33. Parent analogue impulse = DISTRIBUTION_C3.
- **2. Feature representation:** `{"disp_strength": {"index": 33}, "supporting": ["body_ratio", "candle_range", "atr", "change_of_character"]}`
- **3. State representation:** `{"execution": "DISPLACEMENT", "downstream": "EXPANSION", "memory_flag": "pending_displacement_active"}`
- **4. Authority module:** `{"path": "src/config_layer/crt_engine_v2.py", "symbols": ["StateMachine.try_sweep_to_displacement", "StateMachine.try_displacement_to_expansion"], "also": ["src/features/crt_state_resolver.py", "src/features/feature_pipeline.py"]}`
- **5. Storage representation:** `["Feature column disp_strength", "Engine displacement_candle / direction", "CRT state timelines"]`
- **6. Evidence artifact:** `["configs/formulas/market_crt_states.yaml", "active_models.yaml", "src/features/feature_schema.py"]`
- **7. Directly observable vs derived:** MIXED: disp_strength local OBSERVABLE; CRT DISPLACEMENT state DERIVED
- **Citations:** `src/config_layer/crt_engine_v2.py`, `src/features/crt_state_resolver.py`, `src/features/feature_schema.py`

### `FVG` — **BOUND**

- **1. Observable definition:** features.smc.fvg: 3-candle imbalance — bullish when bars[i-1].high < bars[i+1].low; bearish when bars[i-1].low > bars[i+1].high. Active = most recent unfilled zone; fvg_distance = signed ATR-normalised tanh-bounded distance to near edge (0.0 if none).
- **2. Feature representation:** `{"fvg_distance": {"index": 40}}`
- **3. State representation:** No CRT enum. Zone object in features.smc._geometry.
- **4. Authority module:** `{"path": "src/features/smc/fvg.py", "symbols": ["find_active_fvg", "fvg_distance", "_find_fvg_events"]}`
- **5. Storage representation:** `["Canonical vector index 40", "bar_structure_snapshot ZONE_FAMILIES includes fvg"]`
- **6. Evidence artifact:** `["src/features/smc/fvg.py", "src/features/feature_schema.py", "src/features/feature_pipeline.py"]`
- **7. Directly observable vs derived:** OBSERVABLE (OHLCV local 3-bar window)
- **Citations:** `src/features/smc/fvg.py`, `src/features/feature_schema.py`

### `order block` — **BOUND**

- **1. Observable definition:** features.smc.order_block: last opposite-color origin candle before a causal swing break (close beyond confirmed swing). Zone = origin [low, high]. Mitigated on later overlap. order_block_distance = signed ATR distance to nearest unmitigated OB near edge.
- **2. Feature representation:** `{"order_block_distance": {"index": 39}}`
- **3. State representation:** No CRT enum. Zone + break_events shared with breaker/mitigation.
- **4. Authority module:** `{"path": "src/features/smc/order_block.py", "symbols": ["find_active_order_block", "order_block_distance", "_find_break_events"]}`
- **5. Storage representation:** `["Canonical vector index 39", "ZONE_FAMILIES order_block"]`
- **6. Evidence artifact:** `["src/features/smc/order_block.py", "src/features/feature_schema.py", "docs/CODEBASE_SEMANTIC_NAMES.md"]`
- **7. Directly observable vs derived:** DERIVED (needs confirmed swings / break events)
- **Citations:** `src/features/smc/order_block.py`, `src/features/feature_schema.py`

### `breaker` — **BOUND**

- **1. Observable definition:** features.smc.breaker: order block fully violated (later close beyond far edge) then polarity flip; active until retest/mitigation of flipped zone. breaker_distance = signed ATR distance to nearest un-retested breaker.
- **2. Feature representation:** `{"breaker_distance": {"index": 41}}`
- **3. State representation:** No CRT enum. Flipped Zone.
- **4. Authority module:** `{"path": "src/features/smc/breaker.py", "symbols": ["find_active_breaker", "breaker_distance"]}`
- **5. Storage representation:** `["Canonical vector index 41", "ZONE_FAMILIES breaker"]`
- **6. Evidence artifact:** `["src/features/smc/breaker.py", "src/features/feature_schema.py", "tests/test_smc_break_event_memo.py"]`
- **7. Directly observable vs derived:** DERIVED (requires prior OB violation)
- **Citations:** `src/features/smc/breaker.py`, `src/features/feature_schema.py`

### `HTF context` — **BOUND**

- **1. Observable definition:** Not a single CANONICAL feature. Composition of: (1) HTFBuilder reset CLOCK id on M15 structural range; (2) ResetLogic.should_reset on clock_id change (protects EXPANSION/RETEST); (3) ParentCandleBuilder calendar-true parents feeding ParentCRTTrack; (4) optional htf_state.HTFState posture {UNKNOWN, EXPANSION, ACCUMULATION, DISTRIBUTION, REVERSAL} — explicitly NOT CRTState. Parent bias enters CRTEngine.process_candle via parent_state only.
- **2. Feature representation:** `{"canonical_feature_named_htf_context": null, "related": ["session", "hour_of_day", "pdh_distance", "pdl_distance"]}`
- **3. State representation:** `{"reset": "ResetLogic -> FORCE RANGE (except protected states)", "parent_crt": ["RANGE_C1", "MANIPULATION_C2", "DISTRIBUTION_C3"], "htf_state_posture": ["UNKNOWN", "EXPANSION", "ACCUMULATION", "DISTRIBUTION", "REVERSAL"]}`
- **4. Authority module:** `{"path": "src/config_layer/crt_engine_v2.py", "symbols": ["ResetLogic.should_reset"], "also": ["src/config_layer/parent_crt.py::ParentCRTTrack", "src/features/parent_candle.py::ParentCandleBuilder", "src/config_layer/htf_state.py::HTFState", "src/runtime/parent_crt_feed.py"]}`
- **5. Storage representation:** `["active_range.clock_id / htf_candle_id", "parent_state on process_candle path", "layer_trace plane joins"]`
- **6. Evidence artifact:** `["src/config_layer/crt_engine_v2.py::ResetLogic", "src/config_layer/parent_crt.py", "src/config_layer/htf_state.py", "src/config_layer/state_identity.py", "active_models.yaml"]`
- **7. Directly observable vs derived:** DERIVED
- **Citations:** `src/config_layer/crt_engine_v2.py`, `src/config_layer/parent_crt.py`, `src/config_layer/htf_state.py`, `src/config_layer/m15_structural_range.py`
- **Notes:** SURPRISE: htf_state.DISTRIBUTION != CRTState.DISTRIBUTION_C3 (F-077).

### `manipulation` — **BOUND**

- **1. Observable definition:** Parent-timeframe only: CRTState.MANIPULATION_C2 — C2 parent candle that sweeps C1 ParentRange boundary and closes back inside. ParentCRTTrack._detect_parent_sweep (swept_high/swept_low). Bias not set until DISTRIBUTION_C3. Execution M15 machine has no MANIPULATION state.
- **2. Feature representation:** `{"canonical_feature": null}`
- **3. State representation:** MANIPULATION_C2 (PARENT_TIMEFRAME_STATES; disjoint from execution graph)
- **4. Authority module:** `{"path": "src/config_layer/parent_crt.py", "symbols": ["ParentCRTTrack.on_parent_close", "_detect_parent_sweep", "ParentSweepEvent"]}`
- **5. Storage representation:** `["ParentCRTTrack.state / sweep event", "runtime.parent_crt_feed stream"]`
- **6. Evidence artifact:** `["src/config_layer/parent_crt.py", "src/config_layer/state_identity.py", "active_models.yaml", "src/config_layer/_crt_state_generated.py"]`
- **7. Directly observable vs derived:** DERIVED
- **Citations:** `src/config_layer/parent_crt.py`, `src/config_layer/state_identity.py`, `active_models.yaml`

### `distribution` — **BOUND**

- **1. Observable definition:** Primary: CRTState.DISTRIBUTION_C3 — C3 parent impulse away from swept side after MANIPULATION_C2 (directional_impulse). Only then ParentCRTTrack.bias becomes LONG/SHORT. Second binding: htf_state.HTFState.DISTRIBUTION — orthogonal posture (large-in-range); not DISTRIBUTION_C3.
- **2. Feature representation:** `{"canonical_feature": null}`
- **3. State representation:** `{"parent_crt": "DISTRIBUTION_C3", "htf_state_posture": "HTFState.DISTRIBUTION (orthogonal)"}`
- **4. Authority module:** `{"path": "src/config_layer/parent_crt.py", "symbols": ["ParentCRTTrack._directional_impulse_confirmed"], "also": ["src/config_layer/htf_state.py::HTFState"]}`
- **5. Storage representation:** `["ParentCRTTrack.state + bias", "htf_state posture fields if enabled"]`
- **6. Evidence artifact:** `["src/config_layer/parent_crt.py", "src/config_layer/htf_state.py", "src/config_layer/state_identity.py", "active_models.yaml"]`
- **7. Directly observable vs derived:** DERIVED
- **Citations:** `src/config_layer/parent_crt.py`, `src/config_layer/htf_state.py`, `src/config_layer/state_identity.py`
- **Notes:** Dual meaning — consumers must name which DISTRIBUTION.

### `CHoCH` — **BOUND**

- **1. Observable definition:** change_of_character: signed {-1,0,+1} = break_of_structure when it disagrees with trend_bias; else 0. features.smc.choch.change_of_character — algebraic combo only (no standalone CHOCH state-machine). Resolver LINK-001 may require BullishCHoCH/BearishCHoCH during DISPLACEMENT dwell.
- **2. Feature representation:** `{"change_of_character": {"index": 47}}`
- **3. State representation:** `{"feature_states": ["NoCHoCH", "BullishCHoCH", "BearishCHoCH"], "crt_enum": null}`
- **4. Authority module:** `{"path": "src/features/smc/choch.py", "symbols": ["change_of_character"]}`
- **5. Storage representation:** `["Canonical vector index 47"]`
- **6. Evidence artifact:** `["src/features/smc/choch.py", "src/features/feature_schema.py", "configs/formulas/market_crt_states.yaml"]`
- **7. Directly observable vs derived:** DERIVED (needs break_of_structure + trend_bias)
- **Citations:** `src/features/smc/choch.py`, `src/features/feature_schema.py`, `configs/formulas/market_crt_states.yaml`

### `EQH` — **BOUND**

- **1. Observable definition:** features.smc.levels: equal-highs cluster — 2+ confirmed swing highs within tolerance_atr*atr; eqh_distance = signed ATR distance from close to nearest EQH cluster (0.0 if none).
- **2. Feature representation:** `{"eqh_distance": {"index": 45}}`
- **3. State representation:** No CRT enum.
- **4. Authority module:** `{"path": "src/features/smc/levels.py", "symbols": ["eqh_eql_distance", "_nearest_equal_cluster"]}`
- **5. Storage representation:** `["Canonical vector index 45"]`
- **6. Evidence artifact:** `["src/features/smc/levels.py", "src/features/feature_schema.py"]`
- **7. Directly observable vs derived:** DERIVED
- **Citations:** `src/features/smc/levels.py`, `src/features/feature_schema.py`

### `EQL` — **BOUND**

- **1. Observable definition:** Symmetric to EQH on swing lows; eql_distance at CANONICAL index 46 (features.smc.levels.eqh_eql_distance).
- **2. Feature representation:** `{"eql_distance": {"index": 46}}`
- **3. State representation:** No CRT enum.
- **4. Authority module:** `{"path": "src/features/smc/levels.py", "symbols": ["eqh_eql_distance"]}`
- **5. Storage representation:** `["Canonical vector index 46"]`
- **6. Evidence artifact:** `["src/features/smc/levels.py", "src/features/feature_schema.py"]`
- **7. Directly observable vs derived:** DERIVED
- **Citations:** `src/features/smc/levels.py`, `src/features/feature_schema.py`

### `PDH` — **BOUND**

- **1. Observable definition:** Previous-day high = most recently CLOSED D1 parent candle high from ParentCandleBuilder('D1').parent_history; pdh_distance = signed ATR distance from close.
- **2. Feature representation:** `{"pdh_distance": {"index": 43}}`
- **3. State representation:** No CRT enum; depends on D1 parent close stream.
- **4. Authority module:** `{"path": "src/features/smc/levels.py", "symbols": ["pdh_pdl_distance"], "also": ["src/features/parent_candle.py::ParentCandleBuilder"]}`
- **5. Storage representation:** `["Canonical vector index 43"]`
- **6. Evidence artifact:** `["src/features/smc/levels.py", "src/features/feature_schema.py", "src/features/feature_pipeline.py"]`
- **7. Directly observable vs derived:** DERIVED (needs D1 parent_history)
- **Citations:** `src/features/smc/levels.py`, `src/features/parent_candle.py`, `src/features/feature_schema.py`

### `PDL` — **BOUND**

- **1. Observable definition:** Previous-day low from same D1 parent_history[-1].low; pdl_distance at CANONICAL index 44.
- **2. Feature representation:** `{"pdl_distance": {"index": 44}}`
- **3. State representation:** No CRT enum.
- **4. Authority module:** `{"path": "src/features/smc/levels.py", "symbols": ["pdh_pdl_distance"]}`
- **5. Storage representation:** `["Canonical vector index 44"]`
- **6. Evidence artifact:** `["src/features/smc/levels.py", "src/features/feature_schema.py"]`
- **7. Directly observable vs derived:** DERIVED
- **Citations:** `src/features/smc/levels.py`, `src/features/feature_schema.py`

## Status rollup

| BOUND | PARTIAL | UNBOUND |
|---:|---:|---:|
| 16 | 0 | 0 |

UNBOUND concepts: _(none)_.

## Authority surprises

- htf_state.HTFState.DISTRIBUTION is orthogonal to CRTState.DISTRIBUTION_C3 (src/config_layer/htf_state.py F-077).
- active_models.yaml documents crt fusion score (engines.crt_engine.compute) as distinct from CRTState machine in crt_engine_v2.
- CANONICAL_FEATURES is derived from configs/formulas/market_ontology.yaml at import; HTML catalog mirrors vector slots.
- Parent MANIPULATION_C2/DISTRIBUTION_C3 share no transition edges with execution SWEEP/DISPLACEMENT (state_identity partition).
- MC-OPP-DETECT-01 marks logs/XAUUSD/xauusd_phase1_20260723/opportunities.parquet noncompliant (missing identity nest).

## CRT / feature quick index (no teaching)

| Concept | Feature id(s) | State enum(s) |
|---|---|---|
| OHLCV | open..volume [0–4] | — |
| range | candle_range [28] | RANGE, RANGE_C1 |
| liquidity | liquidity_distance [36], liquidity_pressure_score [37] | (envelope M15-SLR) |
| sweep | sweep_detected [20], liquidity_sweep [21], double_sweep [6], candles_since_sweep [35] | SWEEP, SHADOW_PENDING |
| displacement | disp_strength [33] | DISPLACEMENT → EXPANSION |
| FVG | fvg_distance [40] | — |
| order block | order_block_distance [39] | — |
| breaker | breaker_distance [41] | — |
| HTF context | (none dedicated; session/hour/pdh/pdl related) | ResetLogic + parent C1/C2/C3 + HTFState |
| manipulation | — | MANIPULATION_C2 |
| distribution | — | DISTRIBUTION_C3 *(≠ HTFState.DISTRIBUTION)* |
| CHoCH | change_of_character [47] | feature-states NoCHoCH/BullishCHoCH/BearishCHoCH |
| EQH / EQL | eqh_distance [45], eql_distance [46] | — |
| PDH / PDL | pdh_distance [43], pdl_distance [44] | — |

