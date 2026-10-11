# Training/live parity and runtime-authority audit (read-only)

Scope: implementation and dependency audit. No fix was applied; `src/`, `configs/`, existing models and research artifacts are unchanged. Every observation below is reproduced by `python scripts/analysis/parity_audit_probes.py --out results/parity_audit/probes.json` (raw output in `probes.json`, probe ids P1 to P9).

## 0. Corrections to my earlier statements
1. **Parity report overstated agreement.** `results/training_live_parity/REPORT.md` said 32 of 35 features were identical on the live ingestion path. My comparison coerced non-numeric values to NaN and skipped them, which hid that `session` leaves the hook as a **string** ("asia", "london", "new_york") while the pipeline emits integers 0/1/2 (P8). So only 31 of 35 are numerically identical and `session` breaks type. The three formula differences stand.
2. **`v1` was not a dangling entry.** I said the active registry entry `v1` had no model file. `models/v1.json` exists: a 254-byte stub (`schema: gaussian_params_v1`, mu 0.0, sigma 1.0). It is the file `HeuristicGaussianEngine` falls back to. When I promoted `xau_m15_causal_n9_20261011` I replaced a working stub as the active entry (see F9). Rollback is a single file copy (section 6, decision D1); I have not done it.

## 1. Dependency map (file and symbol)
**Schema authority**
- `src/features/feature_schema.py`: `CANONICAL_FEATURES` (35, ordered), `CANONICAL_FEATURE_DIM`, `SCHEMA_HASH` (l.102, md5 of concatenated names), `SchemaObject.checksum` (l.137, md5 of `json.dumps(features, sort_keys=True)`), `SCHEMA_VERSION = "1.0"` (l.171), `GAUSSIAN_SCHEMA`/`TRADENET_SCHEMA` (version "2.0"), `schema_for_model`, `validate_vector`, `SESSION_MAP`, `TREND_MAP`.
- `src/features/dataset_builder.py`: `CANONICAL_FEATURE_ORDER`, `GAUSSIAN_FEATURE_SCHEMA`, `extract_feature_vector`. `src/features/schema_validator.py::validate_vector` duplicates `feature_schema.validate_vector` with a different exception type.
- External mirrors: `model_export_format.json` (input_dim 35, `schema_version` "v5"), `tools/cpp/cpp_runner.cpp` (header comment says it mirrors the order; not executed here).

**Producers of feature values**
- Canonical batch: `FeaturePipeline.run()` (`src/features/feature_pipeline.py`), used by `BacktestRunner`, and by `rr_dataset_builder._build_canonical_features_df` (over trade rows).
- Live ingestion: `runtime/live_engine_hook.py::_build_ohlcv_and_auxiliary` (recomputes `body_size`, `wick_size`, `body_ratio`; stringifies `session`; defaults every other field to 0.0) then `core/feature_store.py::FeatureStore.process` (recomputes `double_sweep` from a 10-entry history, defaults `volume_ratio`).
- Unused: `features/bitnet_feature_builder.py::build_bitnet_features` (no callers) with the same anatomy formulas as the hook. `scripts/backtest/manual_backtest.py` and `config_layer/crt_engine_v2.py::Candle` carry their own copies of the pipeline formulas.
- **`trade_data` producer: none.** Only `live_engine_hook.py` and `engines/live_engine.py` mention it (P4).

**Consumers**
- `core/engine_runner.py` (l.263 to 281 selects the Gaussian engine by `gaussian_impl`; production config value `"heuristic"`; l.558 reads `body_ratio` from the hook-built input).
- `engines/ml_gaussian_engine.py::MLGaussianEngine` (active registry entry, `trainer.load_gaussian_model`, `extract_feature_vector`; fail-open to score 0.5).
- `engines/heuristic_gaussian_engine.py::GaussianRegistry` (second, independent registry reader: uses only `mu`/`sigma` of the active entry; fallback list `['v1','import_fix_v1']`).
- `engines/live_engine.py::LiveEngine.process` (advisory alert engine, imports non-existent functions, F1).
- `agent/modes/pipeline_mode.py::_live_dry_run` (imports non-existent `LiveEngineHook`, F2).
- `runtime/baseline_capture.py` (records `SCHEMA_HASH`, active Gaussian version).

**Training**
- Path P5: `scripts/training/phase5_calibration.py` (`*_trades.csv` entry snapshots, `extract_feature_vector`), wrote the `gaussian_p5_*`/`tradenet_p5_*` files.
- Path TP: `training/train_pipeline.py::run_gaussian_update` -> `validate_logs` -> `rr_dataset_builder.build_dataset` (pipeline over trade rows) -> `trainer.train_gaussian` -> `core/model_registry.register_gaussian`/`promote_gaussian`.
- Path mine: `scripts/training/gaussian_from_backtest.py` (P5-style snapshots; experimental).
- Registry writer: `core/model_registry.GaussianModelRegistry` (separate from the heuristic reader).

**Tests present**: `test_schema_contracts.py` (35 features, `SCHEMA_HASH` stable, session encoding), `test_trainer.py` (mismatched schema raises), `test_train_pipeline.py`, `test_gaussian_active_artifact.py`. **Absent**: any test importing `runtime.live_engine_hook` or `LiveEngine`, hook-vs-pipeline parity, `MLGaussianEngine` fallback on live-shaped input, TradeNet loader checks.

## 2. Observed failures (evidence: probe id)
| ID | Severity | Observation |
|---|---|---|
| F1 | High | `engines/live_engine.py::LiveEngine.process` imports `build_feature_vector` and `validate_feature_vector` from `features.dataset_builder`; neither exists (P4). Every call returns BLOCK `feature_error`; no inference runs. |
| F2 | Medium | `pipeline_mode._live_dry_run` imports `LiveEngineHook`; the class is `HookedLiveEngine` (P4). The tool always returns an error. |
| F3 | High | No producer of `trade_data` exists in the repo (P4). The hook relies on an external caller and fills missing fields with 0.0 (e.g. `volatility_regime` 0 means "low" in training). |
| F4 | High | **Decision-affecting formula split.** For O100 H104 L98 C102 the pipeline, `Candle` and `manual_backtest` give `wick_size` 6.0 and `body_ratio` 0.333 (body over high-low). The hook and the unused builder give `wick_size` 4.0 and `body_ratio` 0.5 (body over range minus body) (P5). `EngineRunner` reads that `body_ratio` for displacement thresholds (`body_ratio_min` 0.65 to 0.70), so live decisions would not match backtest. |
| F5 | Medium | `double_sweep`: pipeline window of 5 bars, `FeatureStore` history of 10 entries. Sequence +1, six quiet bars, −1: pipeline 0, FeatureStore 1 (P6). |
| F6 | High | `session`: three encodings. Pipeline integers (Asia 0, London 1, NY 2 by hour), `feature_schema.SESSION_MAP` (London 0, NY 1, Asian 2, Overlap 3), hook strings (P7). `extract_feature_vector` does `float(session)`, so a hook-built dict raises `ValueError`; `MLGaussianEngine` silently returns the neutral 0.5 fallback (P8). |
| F7 | High | All 12 Gaussian files (32 or 33 features) are rejected by `trainer.load_gaussian_model`; none records its timeframe; only the 9-trade experimental artifact loads (P2). All 5 TradeNet checkpoints have 32 or 33 inputs against 35 (P3). `trainer.load_model` has no schema check and uses `torch.load` without `weights_only`; not executable here (no torch). |
| F8 | Medium | Two incompatible hashes (`SCHEMA_HASH` vs `SchemaObject.checksum`), three version labels ("1.0", "2.0", "v5"), two `validate_vector` functions. Neither hash encodes formulas, windows or missing-value rules (P1). |
| F9 | Medium | My registry promotion changed the active entry from the `v1` stub to an experimental 9-trade model. The heuristic reader still resolves mu 0.0 and sigma 1.0 (unchanged numerically, since the entry has no mu/sigma and defaults apply), and production uses `gaussian_impl: heuristic`, so production decisions are unaffected today. Setting `GAUSSIAN_IMPL=ml` would load the experimental model (P9). |
| F10 | Medium | Two training paths build features differently (P5 entry snapshots on contiguous candles; TP runs the pipeline over trade rows, and the 214-bar volatility warm-up drops most rows from short trade lists). |
| F11 | Low | The hook gives `candles_since_retest` an int cast and `body_size` a recomputation; both match the pipeline for valid candles. Not a defect today, listed so the future contract covers them. |

## 3. Required changes (not applied) and acceptance tests
| Change | Owner | Acceptance test |
|---|---|---|
| R1 One feature-definition contract (`feature_contract.json`): ordered names plus, per feature, formula id, parameters, lookback, missing-value policy, implementation version; `contract_hash` = sha256 of canonical JSON | `features/feature_schema.py` | Hash changes when any formula, window or policy changes; unchanged when comments change. Existing `SCHEMA_HASH` kept as a legacy alias or replaced with an explicit migration note. |
| R2 Models and registry entries store `contract_hash` and `schema_hash`; loaders compare both | `trainer.save_*`/`load_*`, `model_registry`, `heuristic GaussianRegistry` | Loading an artifact with a different contract hash, feature count or order raises; missing hash raises (old files become ineligible without deletion). |
| R3 One implementation of the anatomy, session and `double_sweep` features, imported by pipeline, hook and builder | `FeaturePipeline` helpers | Property test: hook-built row equals pipeline row at the same timestamp for all 35 features, including types. |
| R4 `session` encoding single-sourced and numeric at every boundary | `SESSION_MAP` vs pipeline | `extract_feature_vector(live_frame)` succeeds; `SESSION_MAP` matches the pipeline mapping or is removed. |
| R5 Fix or retire `LiveEngine` imports and `live_hook.dry_run` | `engines/live_engine.py`, `pipeline_mode.py` | Importing `LiveEngine` and calling `process` on a valid frame returns a non-error result; dry-run tool returns schema identity and feature parity result. Requires approval (touches `src/`). |
| R6 A `trade_data` producer, designed after tracing the intended data flow | new, under `src/inout` or `src/runtime` | Deterministic dry run: same input twice gives identical features; missing or incompatible input fails closed (no 0.0 fill, no 0.5 fallback). No order placement. |
| R7 Fail-closed behaviour for model use in live paths | `MLGaussianEngine`, `EngineRunner` | Missing or incompatible model produces an explicit error status the caller must handle, not a neutral score. |
| R8 Pin the training path used for production models and record provenance in the artifact | `train_pipeline`, `phase5_calibration` | Artifact contains dataset hash, timeframe, date range, contract hash; registry refuses entries without them. |

## 4. Minimal remediation sequence
1. **D1 (decision):** keep or roll back the experimental registry promotion. Rollback: copy `models/gaussian_registry.pre_xau_m15_causal_n9_20261011.json` over `models/gaussian_registry.json`.
2. R1 and R2 (contract plus loader checks): pure additions with tests, then mark old artifacts ineligible by derived status.
3. R3 and R4 (one formula source) with the parity property test; decide the authoritative `body_ratio` definition (the backtest and CRT engine use body over range; the live hook currently differs).
4. R5 and R6 only after approval and a traced data-flow design; read-only dry run first.
5. R7 and R8, then a leakage-controlled dataset and retrain.

## 5. What this audit did not establish
Whether the C++ runner and the BitNet per-instrument directories consume the same order (only a header comment and the 35-name `model_export_format.json` were checked); TradeNet loading (no torch installed, only checkpoint tensor shapes inspected); which external process, if any, calls the hook in the author's deployment.

## 6. Decisions needed from you
- **D1** roll back the registry promotion (recommended, to restore the pre-change state) or keep it flagged experimental.
- **D2** approve changes under `src/` for R1 to R4 (additive, tested) as the first implementation step.
- **D3** which body_ratio definition is authoritative for live decisions.
