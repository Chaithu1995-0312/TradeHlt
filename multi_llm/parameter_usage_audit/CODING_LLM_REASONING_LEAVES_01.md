# CODING_LLM_REASONING_LEAVES_01

Parallel semantic leaves (keyword + formula) for funnel, feature map, and design schema.
Machine: `multi_llm/parameter_usage_audit/CODING_LLM_REASONING_LEAVES_01.json`

Pinned run: `run_20260916_225925_XAUUSD` / canonical `run_20260916_172925` / config `v2_htfcrt_2026_08` W=16

## How a coding LLM should use this

1. Pick the **lane** (funnel | feature_map | design_schema).
2. Bind claims to a **leaf_id** / **keyword** — do not invent a fourth funnel order.
3. Treat **formula** as the invariant; numbers under `run1_ref` are instance evidence.
4. HTF patch locks live in `DC-HTF-AUTHORITY-01_PARALLEL_LEAVES.json` — crosslink only.
5. Never promote mechanism counts to patch authorization (`L-HTF-CFGATE`).

## A — Funnel workflow

| leaf_id | keyword | status | formula |
|---|---|---|---|
| `L-FN-PATH` | `FUNNEL_STATE_PATH` | CORRECTED | `PATH := RANGE → SWEEP → DISPLACEMENT → EXPANSION → RETEST → EXECUTION (+ SHADOW_PENDING side-path into EXPANSION); ¬(...` |
| `L-FN-EDGE` | `FUNNEL_EDGE_COUNT` | MEASURED | `EDGE(a,b) := \|{L3 notes : transition=a→b ∧ a≠b}\|; TRANSITION_COUNTER.has_matrix = false; matrix_source = L3.note` |
| `L-FN-BN` | `FUNNEL_BOTTLENECK` | MEASURED | `BN_i := 1 - EDGE(s_i,s_{i+1}) / entries(s_i); primary_BN := [SWEEP→DISP −78%, DISP→EXP −64%, EXP→RETEST −84%, RETEST→...` |
| `L-FN-DEATH` | `FUNNEL_CANDIDATE_DEATH` | MEASURED | `DEATH(r) := \|{c ∈ CANDIDATE_LIFECYCLE : death_reason=r}\|; Σ DEATH = 1798; DEATH(RESET_HTF)=1442 (80.2%); DEATH(RESE...` |
| `L-FN-SCORE` | `FUNNEL_SCORE_GATE` | MEASURED | `PASS_SCORE := score ≥ 0.3; DECISION_DISTANCE: unique_pass=23, unique_fail=1 (CAND-17925); EXECUTION=4 ≪ 23 ⇒ post_sco...` |
| `L-FN-FILTER` | `FUNNEL_POSTSCORE_FILTER` | MEASURED | `FILTER ∈ {off_session:OFF_SESSION:15, parent_bias_LONG:2, parent_bias_SHORT:2, CONFIRMATION_FAILED:1}; RETEST→RANGE ≈ 20` |

### `L-FN-PATH` · `FUNNEL_STATE_PATH`

- **LLM hint:** Use this as the only legal state order when labeling bottlenecks or writing transition tests.
- **Formula:** `PATH := RANGE → SWEEP → DISPLACEMENT → EXPANSION → RETEST → EXECUTION (+ SHADOW_PENDING side-path into EXPANSION); ¬(EXPANSION → DISPLACEMENT)`
- **Run1:** L3 note transition=* ; corrected vs earlier mis-ordered funnel

### `L-FN-EDGE` · `FUNNEL_EDGE_COUNT`

- **LLM hint:** Count non-self L3 transitions; do not use TRANSITION_COUNTER as a from→to matrix.
- **Formula:** `EDGE(a,b) := |{L3 notes : transition=a→b ∧ a≠b}|; TRANSITION_COUNTER.has_matrix = false; matrix_source = L3.note`
- **Run1:** `{"RANGE\u2192SWEEP": 1792, "SWEEP\u2192DISPLACEMENT": 399, "DISPLACEMENT\u2192EXPANSION": 142, "EXPANSION\u2192RETEST": 24, "RETEST\u2192EXECUTION": 4, "SWEEP\u2192RANGE": 1372}`

### `L-FN-BN` · `FUNNEL_BOTTLENECK`

- **LLM hint:** Bottleneck = drop on PATH edge, not bar-occupancy alone.
- **Formula:** `BN_i := 1 - EDGE(s_i,s_{i+1}) / entries(s_i); primary_BN := [SWEEP→DISP −78%, DISP→EXP −64%, EXP→RETEST −84%, RETEST→EXEC −83%]`

### `L-FN-DEATH` · `FUNNEL_CANDIDATE_DEATH`

- **LLM hint:** Death reasons from CANDIDATE_LIFECYCLE only; RESET_HTF ≠ SWEEP→RANGE edge count.
- **Formula:** `DEATH(r) := |{c ∈ CANDIDATE_LIFECYCLE : death_reason=r}|; Σ DEATH = 1798; DEATH(RESET_HTF)=1442 (80.2%); DEATH(RESET_HTF) ≠ EDGE(SWEEP,RANGE)`

### `L-FN-SCORE` · `FUNNEL_SCORE_GATE`

- **LLM hint:** Score threshold 0.3 is not the main RETEST→EXEC kill; session/bias filters are.
- **Formula:** `PASS_SCORE := score ≥ 0.3; DECISION_DISTANCE: unique_pass=23, unique_fail=1 (CAND-17925); EXECUTION=4 ≪ 23 ⇒ post_score_filters dominate`

### `L-FN-FILTER` · `FUNNEL_POSTSCORE_FILTER`

- **LLM hint:** After score pass, FILTER_REJECTED reasons cut RETEST→RANGE.
- **Formula:** `FILTER ∈ {off_session:OFF_SESSION:15, parent_bias_LONG:2, parent_bias_SHORT:2, CONFIRMATION_FAILED:1}; RETEST→RANGE ≈ 20`

## B — Feature map

| leaf_id | keyword | status | formula |
|---|---|---|---|
| `L-FT-GROUP` | `FEATURE_TRADE_COLUMN_GROUPS` | SCHEMA_PINNED | `COLS_90 := identity∪geometry∪price∪trend∪vol∪momentum∪structure∪regime∪distances∪live∪cached∪bitnet∪meta; identity ⊇ ...` |
| `L-FT-LIVE` | `FEATURE_LIVE_VS_CACHED` | OPEN_AUTHORITY | `live_x := value at entry from live metrics path; cached_x := value from CRT cache / prior snapshot; x := feature_pipe...` |
| `L-FT-BITNET` | `FEATURE_BITNET_STUB` | MEASURED | `IF engine.state.bitnet_main_score is None THEN bitnet_score_at_entry=0.0 ∧ bitnet_decision_at_entry=""; stub ≠ model_...` |
| `L-FT-DRIFT` | `FEATURE_DRIFT_MIN_SAMPLES` | MEASURED | `DRIFT_OK ⇔ \|buffer\| ≥ 30; buffer holds {retest_depth, body_ratio, disp_strength}; site = features/feature_monitor.p...` |
| `L-FT-L1` | `FEATURE_L1_BUILD_RECORD` | MEASURED | `L1 := 1 row (module=features.feature_pipeline, status=PASS, bar_idx=-1, artifact_path=None, output_hash=None); ≠ per-...` |
| `L-FT-SNAP` | `FEATURE_SNAPSHOTS_EMITTER` | LOCATED | `SNAP_PATH := logs/feature_snapshots.jsonl; SNAP ∈ Run1_artifacts = false; emitter ≈ core/engine_runner (optional)` |
| `L-FT-JOIN` | `FEATURE_INDEX_JOIN` | MEASURED | `join_ts := opened_at = events.timestamp = layer.bar_ts; bar_idx = trades.candle_idx - 1 = events.candle_index + 62` |

### `L-FT-GROUP` · `FEATURE_TRADE_COLUMN_GROUPS`

- **LLM hint:** 90 trade columns; group before using as model inputs. Identity ≠ features.
- **Formula:** `COLS_90 := identity∪geometry∪price∪trend∪vol∪momentum∪structure∪regime∪distances∪live∪cached∪bitnet∪meta; identity ⊇ {trade_id, run_id}; features ⊆ COLS_90 \ identity`
- **Groups:** `{"price_ohlcv": "cols ~29-34", "trend": "ema_*/trend_*/momentum_score", "volatility": "atr, volatility_ratio", "momentum": "rsi_14, macd_*", "structure": "sweep_*, break_of_structure, body_ratio, ...", "regime": "volatility_regime, retest_depth, liquidity_pressure", "distances": "order_block/fvg/breaker/pdh/pdl/...", "live": "live_atr, live_ema_*", "cached": "cached_retest_depth, cached_body_ratio, ...", "bitnet": "bitnet_score_at_entry, bitnet_decision_at_entry"}`

### `L-FT-LIVE` · `FEATURE_LIVE_VS_CACHED`

- **LLM hint:** Do not equate live_* with non-live or cached_* without an authority rule.
- **Formula:** `live_x := value at entry from live metrics path; cached_x := value from CRT cache / prior snapshot; x := feature_pipeline batch value; authority_for_decision := declared_config_key (fail-closed if missing)`

### `L-FT-BITNET` · `FEATURE_BITNET_STUB`

- **LLM hint:** On this run BitNet columns are schema stubs, not evaluated scores.
- **Formula:** `IF engine.state.bitnet_main_score is None THEN bitnet_score_at_entry=0.0 ∧ bitnet_decision_at_entry=""; stub ≠ model_reject`

### `L-FT-DRIFT` · `FEATURE_DRIFT_MIN_SAMPLES`

- **LLM hint:** insufficient_data (need 30) means monitor buffer samples, not 30 trades.
- **Formula:** `DRIFT_OK ⇔ |buffer| ≥ 30; buffer holds {retest_depth, body_ratio, disp_strength}; site = features/feature_monitor.py; wire = runtime/backtest_v2.py → distribution.feature_drift`

### `L-FT-L1` · `FEATURE_L1_BUILD_RECORD`

- **LLM hint:** L1 is a single observation record; no per-bar feature artifact pointer on this run.
- **Formula:** `L1 := 1 row (module=features.feature_pipeline, status=PASS, bar_idx=-1, artifact_path=None, output_hash=None); ≠ per-bar feature store`

### `L-FT-SNAP` · `FEATURE_SNAPSHOTS_EMITTER`

- **LLM hint:** logs/feature_snapshots.jsonl is a global optional emitter, not a Run1 folder artifact.
- **Formula:** `SNAP_PATH := logs/feature_snapshots.jsonl; SNAP ∈ Run1_artifacts = false; emitter ≈ core/engine_runner (optional)`

### `L-FT-JOIN` · `FEATURE_INDEX_JOIN`

- **LLM hint:** When joining features to layer_trace / events / trades, use L-HTF-IDX offsets.
- **Formula:** `join_ts := opened_at = events.timestamp = layer.bar_ts; bar_idx = trades.candle_idx - 1 = events.candle_index + 62`

## C — Design schema

| leaf_id | keyword | status | formula |
|---|---|---|---|
| `L-DS-DETECT` | `SCHEMA_MC_OPP_DETECT_01` | FROZEN | `DETECT := MT5 OHLCV → opportunity; immutable = {trade_id, dataset_identity}; nest = dataset_identity → trace_id → ana...` |
| `L-DS-JOINT` | `SCHEMA_MC_JOINT_01` | FROZEN | `STATES_6 := {BOTH_SL, BOTH_TP, BOTH_TIMEOUT, JOINT_STATE_SL_TP, JOINT_STATE_TP_SL, JOINT_STATE_SL_TIMEOUT}; authority...` |
| `L-DS-LIFE` | `SCHEMA_TRADE_LIFECYCLE_V0` | SHIPPED | `measure(entry,sl,tp,side,bars) → {Y_scanner, Y_oracle, Y_joint, authority_outcome, rr_*, duration_*, exit_mechanism_*...` |
| `L-DS-HTF` | `SCHEMA_DC_HTF_AUTHORITY_01` | REOPENED_PATCH_PARKED | `clock_id ⊨ lifecycle_cadence; h_ref,l_ref ⊨ sweep_structure; should_reset_today ⊨ clock_flip ∨ retrace ∨ extension; s...` |
| `L-DS-IDNEST` | `SCHEMA_IDENTITY_NEST` | FROZEN | `dataset_identity → trace_id → analysis_id → run_id → trade_id; trade_id mint = sha1(instrument\|ts\|direction\|entry:...` |
| `L-DS-SPLIT` | `SCHEMA_DETECT_VS_MEASURE` | FROZEN | `DETECT_AUTH = MT5 OHLCV; MEASURE_AUTH = path / y_R_net; DETECT ∩ MEASURE = trade_id,trace_id forwarded; ¬(scanner_lab...` |
| `L-DS-FAILCLOSED` | `SCHEMA_FAILCLOSED_CONFIG` | SHIPPED | `Tier1 = {body_ratio_min, atr_multiplier_min, expansion_atr_min_distance, retest_depth_max}; missing_key ⇒ fail_closed...` |

### `L-DS-DETECT` · `SCHEMA_MC_OPP_DETECT_01`

- **LLM hint:** Detection authority — opportunity birth. Do not confuse with measurement money authority.
- **Formula:** `DETECT := MT5 OHLCV → opportunity; immutable = {trade_id, dataset_identity}; nest = dataset_identity → trace_id → analysis_id → run_id → trade_id; schema_change ⇒ User approval`
- **Artifact:** `MC-OPP-DETECT-01`

### `L-DS-JOINT` · `SCHEMA_MC_JOINT_01`

- **LLM hint:** Measurement authority — Y_scanner/Y_oracle/Y_joint; money = path only.
- **Formula:** `STATES_6 := {BOTH_SL, BOTH_TP, BOTH_TIMEOUT, JOINT_STATE_SL_TP, JOINT_STATE_TP_SL, JOINT_STATE_SL_TIMEOUT}; authority_outcome := path_outcome + y_R_net; mismatch ∈ STATES_6 ≠ error`
- **Artifact:** `MC-JOINT-01`

### `L-DS-LIFE` · `SCHEMA_TRADE_LIFECYCLE_V0`

- **LLM hint:** Emit-only engine; wraps trail simulate + forward_walk(intrabar_fixed); no new exit semantics.
- **Formula:** `measure(entry,sl,tp,side,bars) → {Y_scanner, Y_oracle, Y_joint, authority_outcome, rr_*, duration_*, exit_mechanism_*}; specimen ⇒ JOINT_STATE_SL_TP`
- **Artifact:** `trade_lifecycle_engine v0`

### `L-DS-HTF` · `SCHEMA_DC_HTF_AUTHORITY_01`

- **LLM hint:** clock_id = cadence; h_ref/l_ref = structure; ResetLogic = lifecycle. Patch PARKED.
- **Formula:** `clock_id ⊨ lifecycle_cadence; h_ref,l_ref ⊨ sweep_structure; should_reset_today ⊨ clock_flip ∨ retrace ∨ extension; structural_break_patch = PARKED; APPLY ⇔ locks ∧ counterfactual_gate`
- **Artifact:** `DC-HTF-AUTHORITY-01`

### `L-DS-IDNEST` · `SCHEMA_IDENTITY_NEST`

- **LLM hint:** Never mint a new campaign id in measurement; forward trade_id+trace_id.
- **Formula:** `dataset_identity → trace_id → analysis_id → run_id → trade_id; trade_id mint = sha1(instrument|ts|direction|entry:.8f|sl:.8f)[:16]; unit_id = legacy alias`

### `L-DS-SPLIT` · `SCHEMA_DETECT_VS_MEASURE`

- **LLM hint:** Detection produces candidates; measurement labels them. Separate authorities.
- **Formula:** `DETECT_AUTH = MT5 OHLCV; MEASURE_AUTH = path / y_R_net; DETECT ∩ MEASURE = trade_id,trace_id forwarded; ¬(scanner_label ⇒ money_truth)`

### `L-DS-FAILCLOSED` · `SCHEMA_FAILCLOSED_CONFIG`

- **LLM hint:** Tier-1 CRTConfig keys required; no silent .get defaults.
- **Formula:** `Tier1 = {body_ratio_min, atr_multiplier_min, expansion_atr_min_distance, retest_depth_max}; missing_key ⇒ fail_closed; shipped fail-closed A = 09ffcb1`

## D — HTF lock crosslinks (do not duplicate)

- `L-HTF-DIR` `HTF_BREAK_DIRECTIONALITY` → `DC-HTF-AUTHORITY-01_PARALLEL_LEAVES.json`
- `L-HTF-PROT` `HTF_BREAK_PROTECT_PARITY` → `DC-HTF-AUTHORITY-01_PARALLEL_LEAVES.json`
- `L-HTF-ORD` `HTF_BREAK_CHECK_ORDER` → `DC-HTF-AUTHORITY-01_PARALLEL_LEAVES.json`
- `L-HTF-CFGATE` `HTF_COUNTERFACTUAL_GATE` → `DC-HTF-AUTHORITY-01_PARALLEL_LEAVES.json`



## N1/N2 cleanup (2026-09-22)
- **L-FN-FILTER**: `reason_None:1` (not CONFIRMATION_FAILED); Σ=20. CONFIRMATION_FAILED (CAND-17925) may exist as event but L3 RETEST→RANGE reason is unlabeled.
- **L-FN-EDGE**: `run1_ref` now lists all **17** L3 transition pairs (was 6 edge-only).
