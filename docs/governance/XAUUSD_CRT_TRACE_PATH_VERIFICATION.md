# XAUUSD CRT TRACE — Executable Path Verification

**Status:** VERIFIED (executable path resolved)  
**Date (UTC):** 2026-07-14  
**Task:** XAUUSD CRT baseline 4-hour (16×M15) executable trace  
**Behavior:** Observation only — no CRT redesign / no MSIP / no formula change  

---

## A. CORPUS

| Field | Value |
|---|---|
| **physical path** | `data/mt5/XAUUSD_M15.csv` (executable Phase-1 frozen candidate) |
| **row count** | 47275 data rows |
| **SHA-256** | `4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56` |
| **timestamp column** | `timestamp` (string `YYYY-MM-DD HH:MM:SS`, naive wall clock) |
| **OHLCV mapping** | `timestamp,open,high,low,close,volume` (lowercase) |
| **timeframe** | M15 |
| **range** | `2024-05-22 01:00:00` → `2026-05-21 23:45:00` |
| **authority (executable)** | `src/data_ingestion/xauusd_phase1_candidate.py` + `docs/governance/xauusd_m15_phase1_frozen_candidate.json`; status `FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION`; fail-closed via `guard_xauusd_csv_path` |
| **byte match** | Verified on disk against module constant `PHASE1_SHA256` |

**Note / contradiction:** `data/XAUUSD_M15.csv` (root, 50169 rows, sha `486cf361…`) is **not** the executable Phase-1 binding. Any request path matching XAUUSD M15 is rewritten to the mt5 candidate by `guard_xauusd_csv_path`. See CONTRADICTION C-XAU-001.

---

## B. FEATURE PATH

| Field | Value |
|---|---|
| **entrypoint** | `features.feature_pipeline.FeaturePipeline(raw_df).run()` |
| **call site (replay)** | `BacktestRunner.__init__` (`src/runtime/backtest_v2.py` ~1648–1675) when `csv_path` set and `skip_features=False` |
| **finalized outputs** | `enriched_df` (OHLCV + feature columns) + `feature_vectors` (N×38 float array) |
| **lookup** | `feature_ts_to_idx: timestamp_str → row index` (post-`finalize` dropna alignment) |
| **CANONICAL_FEATURES authority** | `src/features/feature_schema.py` |
| **canonical feature count** | **38** (`CANONICAL_FEATURE_DIM`) |
| **SCHEMA_HASH** | `1ba02abbafdd0786831181677de547c1` |
| **FEATURE_ORDER_HASH** | `235553310100a340` |
| **warmup / finalize** | Pipeline internal rolling warmup → `finalize()` drops rows with NaN features; CRT candle stream still includes pre-finalize bars |

**Critical executable fact:** the 38-vector is **attached to trades at TRADE_OPENED** via timestamp lookup. It is **not** passed into `CRTEngine.process_candle`. CRT builds its own ATR/EMA/body_ratio/cached FM-027/028 from OHLC + local state.

---

## C. CRT CONSTRUCTION PATH

| Field | Value |
|---|---|
| **class** | `config_layer.crt_engine_v2.CRTEngine` |
| **constructor call site** | `BacktestRunner.run` ~L1810: `CRTEngine(self.crt_cfg, sweep_tracer=self._sweep_tracer)` |
| **CRTConfig source** | `self.crt_cfg` from `BacktestConfig.crt_config` or `ConfigBuilder.build(instrument)` |
| **prod load path** | CLI/helpers use `load_prod_config` / `BacktestConfig.from_prod_config` merging `params` + `crt_engine` from production JSON |
| **active config file** | `configs/production/ACTIVE_VERSION` → `v2_multi_2026_04` → `configs/production/v2_multi_2026_04.json` |
| **WHO layer** | `active_models.yaml` → `crt.runtime.state_contracts` / `valid_transitions` (parity with `state_topology.VALID_TRANSITIONS`) |
| **env effects** | `BACKTEST_ENGINE_GATE` affects **EngineRunner gate after TRADE_OPENED**, not CRT SM transitions; exit model from config |
| **runtime mutation** | `engine.set_spread(...)` per bar if spread simulation on; HTF remaining counters on state |

---

## D. BAR EXECUTION PATH

| Field | Value |
|---|---|
| **candle source** | `CandleLoader(csv_path, instrument).stream()` |
| **per-bar CRT method** | `CRTEngine.process_candle(candle, htf.current_htf_id) -> dict` (~L2388) |
| **caller** | `BacktestRunner.run` loop ~L1982 |
| **order vs FeaturePipeline** | Pipeline runs **once at init** over full CSV; CRT runs **streaming** bar-by-bar |
| **state persistence** | Single `CRTEngine` instance for full run; `EngineState` mutated in place |
| **reset boundary** | `StateMachine.reset_to_range`; gap detector; HTF/retrace/extension resets via `reset_lg.should_reset` |
| **init boundary** | After `warmup_candles`, `engine.initialise_range(htf.seed_candles(), ...)` |
| **cached features** | Populated at RETEST confirmation inside `try_expansion_to_retest` (FM-027/028 + body_ratio) |

**Trace execution model (required):** normal CRT construction → full prefix `process_candle` with trace **disabled** → enable trace for 16 target bars → disable → stop. No mini-replay, no fabricated `state_before`.

---

## E. CRT OUTPUT PATH

| Surface | Location |
|---|---|
| **return value** | `process_candle` → `action` dict (`action`, `state`, `candle`, …) |
| **state mutation** | `StateMachine._transition` / `reset_to_range` |
| **events** | `EventLogger.record(...)` on engine (`self.ev_log`) |
| **trades** | `state.active_trade` + executor; backtest journals on `TRADE_OPENED` in action |
| **diversions/resets** | `RESET`, `SWEEP_EXPIRED`, `FILTER_REJECTED`, soft-conf rejects, gap reset |
| **telemetry** | `TelemetryCollector`; optional `SweepTraceLogger` |

---

## F. EXISTING OBSERVABILITY (reusable)

| Hook | Reuse? |
|---|---|
| `EventLogger` records | Yes — snapshot events emitted this bar |
| `state.transition_log` | Yes — transition history |
| `SweepTraceLogger` | Partial — sweep only |
| `TelemetryCollector` | Partial — not full guard operands |
| Feature ts→vector map | Yes — canonical 38 values by timestamp |

**Missing for this task:** per-guard operand/threshold/result in evaluation order; effective CRTConfig provenance snapshot; explicit state_before/after pack; CRT input provenance classes.

---

## G. MISSING OBSERVABILITY → INSTRUMENTATION DECISION

| FIELD | WHY REQUIRED | OBSERVATION POINT | METHOD | BEHAVIOR PRESERVATION | TEST |
|---|---|---|---|---|---|
| `state_before` / `state_after` | Causal reconstruction | enter/exit `process_candle` | Optional observer callback | No-op when `baseline_trace is None` or disabled | ON/OFF parity |
| `guards_evaluated[]` | Decision path | each condition in `try_*` + key process_candle branches | `_trace_guard(...)` only if hooks active | Attribute check only when off | short-circuit test |
| CRT inputs + provenance | Prove non-use of full 38-vector | same points as operands | Record source_class at observation | Read-only | provenance test |
| effective config | Policy reconstruction | once per run + keys read | Snapshot `dataclasses.asdict(CRTConfig)` | No mutation | hash stable |
| canonical 38 | Market representation | FeaturePipeline vectors by ts | Lookup only | No recompute | 38-count invariant |
| outputs | Consequence | `action` + `ev_log` delta | Diff event log length/content | Read-only | output capture test |

---

## H. INSTRUMENTATION DECISION SUMMARY

1. Add optional `CRTBaselineTraceHooks` (`src/runtime/crt_baseline_trace.py`).
2. Wire `CRTEngine.baseline_trace` / `StateMachine.trace_hooks` — **default None**.
3. Additive `_trace_guard` calls at existing decision points (no re-evaluation, no rule engine extraction).
4. Standalone runner `scripts/analysis/xauusd_crt_baseline_trace.py` uses production corpus + same CRT construction + FeaturePipeline; does **not** enable EngineRunner gate (CRT spine isolation; env `BACKTEST_ENGINE_GATE` irrelevant when not using full BacktestRunner journal path).
5. Neutrality tests: trace off ≡ no hooks; trace on/off same state/action sequence.

---

## Path verdict

```text
EXECUTABLE_PATH_VERIFIED = YES
CORPUS_AUTHORITY = PHASE1_FROZEN data/XAUUSD_M15.csv (hash matched)
FEATURE_SCHEMA_AUTHORITY = feature_schema.py (38 / SCHEMA_HASH / FEATURE_ORDER_HASH)
CRT_CONSTRUCTION_PATH_VERIFIED = YES (CRTEngine + CRTConfig from prod)
FEATURE_VS_CRT_COUPLING = DECOUPLED (38-vector not consumed by process_candle guards)
```

Proceed to optional instrumentation + 16-bar capture.

---

## CONTRADICTIONS

### C-XAU-001 — Root CSV vs executable Phase-1 candidate

| Field | Value |
|---|---|
| **CLAIM** | Some census/docs treat `data/XAUUSD_M15.csv` (50169 rows, sha `486cf361…`) as XAUUSD M15 primary |
| **EXECUTABLE EVIDENCE** | `guard_xauusd_csv_path` → `xauusd_phase1_candidate.PHASE1_PHYSICAL_PATH = data/mt5/XAUUSD_M15.csv` (47275 rows, sha `4d73f5ce…`) |
| **FILES** | `src/data_ingestion/xauusd_phase1_candidate.py`, `docs/governance/xauusd_m15_phase1_frozen_candidate.json`, `runtime/backtest_v2.guard_xauusd_csv_path` |
| **AFFECTED BOUNDARY** | Corpus selection for XAUUSD M15 replay |
| **REOPEN CONDITION FIRE?** | NO (does not reopen CRT CLOSED) |
| **IMPACT ON TRACE** | Trace uses executable Phase-1 mt5 candidate only |
| **RECOMMENDED NEXT ACTION** | Align CAD prose / research pins with Phase-1 binding (doc hygiene) |

### C-CRT-FEAT-001 — 38-vector decoupled from CRT guards

| Field | Value |
|---|---|
| **CLAIM** | Implied “candle → 38 features → CRT inputs” linear stack |
| **EXECUTABLE EVIDENCE** | `process_candle(candle, htf_id)` uses OHLC + local ATR/EMA/body_ratio; 38-vector attached only at TRADE_OPENED journal path |
| **FILES** | `crt_engine_v2.py:process_candle`, `backtest_v2.py` feature lookup at TRADE_OPENED |
| **AFFECTED BOUNDARY** | Feature↔CRT coupling (not CRT CLOSED reopen) |
| **REOPEN CONDITION FIRE?** | NO |
| **IMPACT ON TRACE** | Trace captures both surfaces separately with provenance classes |
| **RECOMMENDED NEXT ACTION** | Keep dual capture; do not invent CRT consumption of unused dims |
