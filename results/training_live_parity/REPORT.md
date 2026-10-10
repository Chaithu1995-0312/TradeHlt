# Training/live parity report (read-only)

Nothing was retrained, rebuilt, activated or reconfigured. Probe: `scripts/analysis/training_live_parity.py` (in memory); raw output `parity.json`. `volatility_regime` = Candidate A; swings = `causal_v2`.

## 1. Producers and consumers
| Item | Producer | Consumer | Notes |
|---|---|---|---|
| Batch features | `FeaturePipeline.run()` -> `(df, vectors)`; drops warm-up rows | `BacktestRunner`, `*_trades.csv` entry snapshot | contiguous candle history |
| Training path P5 (wrote `gaussian_p5_*`, `tradenet_p5_*`) | `scripts/training/phase5_calibration.py`: `*_trades.csv` -> `extract_feature_vector(trade_row)` | `GaussianNBModel`, TradeNet | entry-bar snapshot of batch features. Source dirs `results/portfolio_p*` are **not in this checkout** |
| Training path TP (`train_pipeline.run_gaussian_update`) | `validate_logs` -> `rr_dataset_builder.build_dataset` | Gaussian registry | runs `FeaturePipeline` over **trade records as if they were candles**, positional alignment |
| Live features | **No in-repo producer of `trade_data`** | `HookedLiveEngine.process` -> `_build_ohlcv_and_auxiliary` -> `FeatureStore` -> `EngineRunner` | features passed through with `_safe_float(...,0.0)` defaults |
| Live Gaussian inference | `LiveEngine.process` | advisory alerts | imports `build_feature_vector`/`validate_feature_vector` from `features.dataset_builder`; **neither exists** -> `feature_error` BLOCK, inference never runs |
| `live_hook.dry_run` tool | `pipeline_mode.py` | agent | imports nonexistent `LiveEngineHook` (class is `HookedLiveEngine`) |

## 2. Model inventory (all 17 artifacts)
- 12 Gaussian JSON: 11 have 32 features, 1 (`...20260406T005252`) has 33; current schema has 35. Missing: `volume`, `volume_ratio`, `double_sweep` (32) / `volume_ratio`, `double_sweep` (33). Order of common features matches.
- **`trainer.load_gaussian_model` rejects all 12** (hard schema check, verified by calling it).
- 5 TradeNet `.pth` (inspected via zip member sizes only, no unpickling): first layer weight = 32x32 (4 files) and 32x33 (latest) vs `TRADENET_SCHEMA.n_features` = 35. All 5 incompatible with the 35-dim schema.
- Training timeframe is **not recorded** in any model file or registry entry; training-sample counts 350 (8 Gaussian) and 84,822 (4). Timeframe: unresolved.
- `model_export_format.json` already declares input_dim 35 / 35 names (C++ side matches the current schema, not the models).
- The populations affected are therefore: 12 Gaussian + 5 TradeNet, and every consumer of the schema (live hook, C++ runner, BitNet per-instrument dirs not inspected).

## 3. Feature parity at identical timestamps
Idealised upstream (`trade_data` = batch row), XAUUSD M15 2025-07, 2100 raw bars -> 1886 rows after warm-up, 0 FeatureStore failures. 32 of 35 features identical. Differences:
| Feature | Rows differing | Cause |
|---|---|---|
| `wick_size` | 99.9% | hook recomputes `(H-L)-body`; pipeline uses `H-L` |
| `body_ratio` | 99.9% (max diff 431) | hook `body/wick_excl_body`; pipeline `body/(H-L)` |
| `double_sweep` | 13.8% | FeatureStore rolling window 10; pipeline window 5 |
This is the *best case*: real live parity also depends on whoever builds `trade_data` (unresolved).

## 4. History, warm-up, missing values
- Batch: first 214 bars for `volatility_regime` are NaN and dropped; live has no warm-up gate and no history store for these features: absent/NaN input becomes **0.0**, which is a valid class in batch (volatility_regime 0 = low). The 2-bar swing confirmation delay and 200-bar reference exist only if the upstream replicates them; nothing in the hook checks.
- Training path TP: warm-up now bites trade lists. Rows surviving `FeaturePipeline` on a synthetic trade-row frame: 50 -> 0, 120 -> 0, 250 -> 36, 350 -> 136, 600 -> 386 (`build_dataset` raises below 20).
- Session encoding: `feature_schema.SESSION_MAP` (london 0/ny 1/asia 2/overlap 3) disagrees with pipeline (hour<8 0, <16 1, else 2).

## 5. Identity: schema vs feature definition (separate)
- Schema identity: `SCHEMA_HASH` = md5 of names only; `SchemaObject.checksum`/model `schema_checksum` = md5 of `json.dumps(feature_schema, sort_keys=True)`. Two algorithms, not comparable.
- Feature-definition identity: **does not exist**. No artifact records swing mode, volatility window/ranking, session encoding, window sizes (double_sweep 5 vs 10), or body_ratio formula. A model trained with `centred_v1` swings and the old volatility label has the same schema hash as one trained with the new definitions.

## 6. Unresolved dependencies
1. Who produces live `trade_data` (and with which feature code).
2. Missing `build_feature_vector` / `validate_feature_vector`; nonexistent `LiveEngineHook`.
3. Training timeframe and data for the 12+5 models; `results/portfolio_p*` absent.
4. Which of the two training paths (P5 vs TP) is canonical.
5. Whether ATR-based features should share a horizon (separate contract question).
6. BitNet per-instrument dirs and `cpp_runner.cpp` runtime not traced.

## 7. Implications for the blocked steps (no action taken)
Contract freeze needs: one definition source for `wick_size`, `body_ratio`, `double_sweep`, `session`; a definition hash that includes those parameters; a decision on the canonical training path and live feature producer. Retraining before that would reproduce the mismatch.
