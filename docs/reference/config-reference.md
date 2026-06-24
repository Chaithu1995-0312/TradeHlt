# CONFIG_REFERENCE.md

> Complete reference for `configs/production/v1_multi_2026_03.json`.
> This file is the **single source of truth** for every runtime tunable. No
> Python module is allowed to define a default that shadows a value here.
>
> **Runtime-status notes** (as of 2026-06-07 12:52 UTC+5:30) have been added to
> several sections below. These notes describe whether each config section has a
> confirmed runtime consumer in the current codebase, without making decisions
> about what to change.

---

## Top-Level Metadata

| Key              | Example / Type                    | Purpose                                                            |
| ---------------- | --------------------------------- | ------------------------------------------------------------------ |
| `version`        | `"v1_multi_2026_03"` / str        | Registry key. Pattern: `v{N}_{label}_{YYYY_MM}`.                   |
| `config_id`      | `"cfg_initial_2026_03_24"` / str  | Human-readable config id (carried through audit logs).             |
| `schema_version` | `"1.3"` / str                     | Shape version. Bumped when top-level sections are added/removed.   |
| `created_at`     | ISO-8601 / str                    | Creation timestamp.                                                |
| `promoted_at`    | ISO-8601 / str                    | Timestamp of the `PROMOTED` event in `promotion_log.jsonl`.        |
| `notes`          | str                               | Free-form notes (e.g., validation remediation).                    |

---

## `params` — CRT Tunables

Feeds `_params_to_crt_config()` → `CRTConfig`. The only section a tuner is allowed to mutate freely.

| Key                           | Type  | Default |
| ----------------------------- | ----- | ------- |
| `retest_depth_max`            | float | `0.3`   |
| `retest_atr_depth_fraction`   | float | `0.5`   |
| `body_ratio_min`              | float | `0.65`  |
| `atr_multiplier_min`          | float | `1.5`   |
| `expansion_atr_min_distance`  | float | `0.2`   |

✅ **Runtime status**: Confirmed consumed by `src/config_layer/crt_engine_v2.py` via `CRTConfig`.

---

## `engine_runner` — Orchestrator Flags

Consumed by `src/core/engine_runner.py`.

| Key                        | Type     | Default / Example                                           |
| -------------------------- | -------- | ----------------------------------------------------------- |
| `model_path`               | str      | `"results/model_export_format.json"`                        |
| `min_atr`                  | float    | `0.0003`                                                    |
| `allowed_sessions`         | list[str]| `["london","new_york","overlap"]`                           |
| `bitnet_zone_threshold`    | float    | `0.25`                                                      |
| `zone_registry_path`       | str      | `"models/zone_registry.json"`                               |
| `zone_gate_execution_mode` | str      | `"normal"` (normal \| shadow)                               |
| `zone_mode`                | str      | `"hard"` (hard \| soft)                                     |
| `debug_mode`               | bool     | `false`                                                     |
| `gaussian_impl`            | str      | `"heuristic"` (heuristic \| ml)                             |
| `convergence_window`       | int      | `500`                                                       |
| `fusion_compare_evaluate`  | bool     | `true`                                                      |
| `fusion_use_evaluate`      | bool     | `false`  — feature flag for new fusion path                 |
| `rr_fusion`                | dict     | `{enabled: false, model_path: "models/rr_model.json", threshold: 0.5}` |
| `dual_engine`              | dict     | See below                                                   |

✅ **Runtime status**: Confirmed consumed by `src/core/engine_runner.py`. Notable: `fusion_use_evaluate=false` means the `FusionEngine.evaluate()` path is never invoked in production; `fusion_compare_evaluate=true` calls it only for shadow logging.

### `engine_runner.dual_engine`

| Key                           | Type  | Default |
| ----------------------------- | ----- | ------- |
| `trend_strength_threshold`    | float | `0.15`  |
| `momentum_threshold`          | float | `0.30`  |
| `range_volatility_threshold`  | float | `0.80`  |
| `breakout_min_score`          | float | `0.30`  |
| `trap_min_score`              | float | `0.32`  |
| `neutral_min_score`           | float | `0.32`  |
| `fusion_min_score`            | float | `0.25`  |

✅ **Runtime status**: Confirmed consumed by `src/core/engine_runner.py` Step 6 (regime gate).

---

## `fusion_engine` — Weighted Combination

Consumed by `src/core/fusion_engine.py`.

| Key                          | Type  | Default | Purpose                                                  |
| ---------------------------- | ----- | ------- | -------------------------------------------------------- |
| `weight_crt`                 | float | `0.30`  | CRT engine weight                                        |
| `weight_gaussian`            | float | `0.25`  | Gaussian engine weight                                   |
| `weight_zone_gate`           | float | `0.25`  | Zone-gate engine weight                                  |
| `weight_rr`                  | float | `0.20`  | RR engine weight                                         |
| `conflict_resolution_policy` | str   | `"conservative"` | Resolution when engines disagree                   |
| `gaussian_weight`            | float | `0.60`  | Internal fusion sub-weight (heuristic+ml blend)          |
| `neural_weight`              | float | `0.40`  | Internal fusion sub-weight (neural path)                 |
| `llm_weight`                 | float | `0.20`  | LLM tie-breaker weight                                   |
| `llm_lower_band`             | float | `0.45`  | LLM fires only when Gaussian score ∈ [lower, upper]      |
| `llm_upper_band`             | float | `0.65`  | Upper bound of LLM tie-breaker band                      |
| `enable_llm`                 | bool  | `true`  | Master kill switch for LLM tie-breaker                   |
| `tier_full`                  | float | `0.75`  | Full-position confidence tier                            |
| `tier_half`                  | float | `0.60`  | Half-position confidence tier                            |
| `tier_quarter`               | float | `0.50`  | Quarter-position confidence tier                         |

✅ **Runtime status**: Confirmed consumed by `src/core/fusion_engine.py`. See also `regime_fusion_weights` note under `inout` section.

---

## `decision_engine` — Final ACCEPT/REJECT

| Key                          | Type  | Default |
| ---------------------------- | ----- | ------- |
| `score_threshold`            | float | `0.45`  |
| `p_win_threshold`            | float | `0.40`  |
| `rr_threshold`               | float | `1.20`  |
| `weak_component_threshold`   | float | `0.55`  |
| `weak_link_weight`           | float | `0.30`  |

⚠️ **Runtime status** *(as of 2026-06-07 12:52 UTC+5:30)*: `score_threshold` is documented as a gating threshold but `src/core/decision_engine.py` may not enforce it as a hard gate in all paths. The key exists in config and is read, but its effective role in decision logic should be verified against the actual code path.

---

## `execution_planner` — Intent-Driven Entry/SL/TP/TTL

Consumed by `src/config_layer/execution_planner.py` (`ExecutionPlannerV1_2`).

| Key                           | Type  | Default    |
| ----------------------------- | ----- | ---------- |
| `min_rr_ratio`                | float | `1.5`      |
| `atr_mult_breakout_tp`        | float | `2.0`      |
| `atr_mult_pullback_tp`        | float | `1.5`      |
| `atr_mult_reversal_tp`        | float | `1.0`      |
| `atr_mult_sweep_tp`           | float | `1.2`      |
| `ttl_breakout_sec`            | int   | `180`      |
| `ttl_pullback_sec`            | int   | `300`      |
| `ttl_reversal_sec`            | int   | `120`      |
| `ttl_liq_sweep_sec`           | int   | `240`      |
| `ttl_unknown_sec`             | int   | `180`      |
| `default_sl_atr_mult`         | float | `1.0`      |
| `risk_percent`                | float | `0.5`      |
| `lookback_candles_sl`         | int   | `5`        |
| `liquidity_lookback`          | int   | `20`       |
| `liquidity_volume_threshold`  | float | `1.5`      |
| `liquidity_touch_count`       | int   | `2`        |
| `reject_unknown_intent`       | bool  | `true`     |
| `precision_default`           | int   | `8`        |
| `default_account_balance`     | float | `10000.0`  |
| `precision_overrides`         | dict  | `{XAUUSD:2, BTCUSDT:2, ETHUSDT:2, BTCUSD:2, ETHUSD:2}` |

⚠️ **Runtime status** *(as of 2026-06-07 12:52 UTC+5:30)*: `ExecutionPlannerV1_2` reads TTL keys (`ttl_*_sec`), `risk_percent`, `precision_default`, `precision_overrides`, and `default_account_balance`. However, `min_rr_ratio`, `default_sl_atr_mult`, `lookback_candles_sl`, and `liquidity_*` keys are **not read by ExecutionPlanner** — these SL/RR/liquidity values are delegated to `gate_intelligence.compute_crt_levels()`. The active config `v2_multi_2026_04.json` may be missing some of these keys entirely, causing hardcoded fallback values to be used. Verify the actual consumer before relying on changes to these keys.

---

## `ultron_risk_gate` — Position & Kill-Switch

Consumed by `src/core/ultron_risk_gate.py`.

| Key                       | Type  | Default |
| ------------------------- | ----- | ------- |
| `disabled`                | bool  | `false` |
| `max_risk_per_trade_pct`  | float | `1.0`   |
| `max_portfolio_risk_pct`  | float | `5.0`   |
| `max_trades_per_day`      | int   | `10`    |
| `max_daily_loss_pct`      | float | `3.0`   |
| `min_rr_ratio`            | float | `1.5`   |

✅ **Runtime status**: Confirmed consumed by `src/core/ultron_risk_gate.py`. Note: the kill-switch persist path is hardcoded as `logs/kill_switch_state.json` in the same file, not read from config.

---

## `crt_engine` — State Machine

Consumed by `src/config_layer/crt_engine_v2.py`.

| Key                         | Type           | Default                                                             |
| --------------------------- | -------------- | ------------------------------------------------------------------- |
| `score_decay_lambda`        | float          | `0.05`                                                              |
| `max_spread_pct`            | float          | `0.05`                                                              |
| `atr_period`                | int            | `14`                                                                |
| `atr_buffer_multiplier`     | float          | `3`                                                                 |
| `max_sweep_age_candles`     | int            | `20`                                                                |
| `atr_min_displacement`      | float          | `1.2`                                                               |
| `confirmation_body_min`     | float          | `0.6`                                                               |
| `sl_atr_buffer`             | float          | `0.2`                                                               |
| `tp1_atr_multiplier`        | float          | `1.0`                                                               |
| `tp2_atr_multiplier`        | float          | `2.0`                                                               |
| `bitnet_main_threshold`     | float          | `0.55`                                                              |
| `news_blackout_minutes`     | int            | `15`                                                                |
| `retrace_reset_pct`         | float          | `0.50`                                                              |
| `conf_alpha`                | float          | `0.70`                                                              |
| `conf_beta`                 | float          | `0.30`                                                              |
| `conf_weights`              | list[float]    | `[0.35, 0.35, 0.15, 0.15]`                                          |
| `conf_floor`                | float          | `0.20`                                                              |
| `weak_link_weight`          | float          | `0.30`                                                              |
| `ema_fast`                  | int            | `2`                                                                 |
| `ema_slow`                  | int            | `5`                                                                 |
| `tier_1_threshold`          | float          | `0.75`                                                              |
| `tier_2_threshold`          | float          | `0.30`                                                              |
| `soft_conf_max_candles`     | int            | `3`                                                                 |
| `sizing_bands`              | list[[float,float]] | `[[0.75, 0.010], [0.55, 0.005]]`                               |
| `session_windows`           | dict           | `{LONDON:["07:00","10:00"], NEWYORK:["13:00","16:00"], ASIA:["00:00","03:00"]}` |

✅ **Runtime status**: Confirmed consumed by `src/config_layer/crt_engine_v2.py` via `CRTConfig`.

---

## `gaussian_scorer` — Calibration Constants

Consumed by `src/config_layer/crt_gaussian_scorer.py`.

| Key              | Type  | Default |
| ---------------- | ----- | ------- |
| `retest_mu`      | float | `0.237` |
| `retest_s2`      | float | `0.040` |
| `body_mu`        | float | `0.847` |
| `body_s2`        | float | `0.021` |
| `disp_mu`        | float | `2.177` |
| `disp_s2`        | float | `1.196` |
| `sigmoid_k`      | float | `4.5`   |
| `sigmoid_x0`     | float | `0.50`  |
| `execute_p`      | float | `0.50`  |
| `decay_lambda`   | float | `0.0`   |

✅ **Runtime status**: Confirmed consumed by `src/config_layer/crt_gaussian_scorer.py`.

---

## `rr_model` — Risk-Reward Fusion

Consumed by `src/config_layer/rr/rr_fusion.py`.

| Key                           | Type  | Default                                         |
| ----------------------------- | ----- | ----------------------------------------------- |
| `ridge_alpha`                 | float | `10.0`                                          |
| `gnb_var_smoothing`           | float | `1e-9`                                          |
| `drift_threshold`             | float | `1.5`                                           |
| `mahal_clip`                  | float | `500.0`                                         |
| `confidence_bypass_threshold` | float | `0.3`                                           |
| `min_samples`                 | int   | `20`                                            |
| `dataset_min_samples`         | int   | `20`                                            |
| `score_weights`               | dict  | `{gaussian: 0.5, ml: 0.3, confidence: 0.2}`     |
| `model_path`                  | str   | `"models/rr_model.json"`                        |
| `dataset_path`                | str   | `"models/rr_dataset.json"`                      |

✅ **Runtime status**: Confirmed consumed by `src/config_layer/rr/rr_fusion.py`.

---

## `llama_gate` — Local LLM Server

Consumed by `src/config_layer/llm_inference_client.py`.

| Key                    | Type  | Default                                  | Purpose                                               |
| ---------------------- | ----- | ---------------------------------------- | ----------------------------------------------------- |
| `server_url`           | str   | `"http://127.0.0.1:8080/completion"`     | Local llama.cpp HTTP endpoint                         |
| `request_timeout`      | float | `2.0` (seconds)                          | Per-call timeout                                      |
| `probe_timeout`        | float | `1.0`                                    | Liveness probe timeout                                |
| `fail_count_disable`   | int   | `10`                                     | Open circuit breaker after N consecutive failures     |
| `score_n_predict`      | int   | `4`                                      | Tokens predicted per score call                       |
| `score_temperature`    | float | `0.0`                                    | Deterministic scoring                                 |
| `insight_max_tokens`   | int   | `300`                                    | Max tokens for `llm_insight()` narratives             |
| `insight_temperature`  | float | `0.3`                                    | Narrative temperature (slightly creative)             |

✅ **Runtime status**: Confirmed consumed by `src/config_layer/llm_inference_client.py`.

---

## `config_validator` — Pre-Promotion Gates

Consumed by `src/config_layer/config_validator.py`.

| Key                           | Type  | Default / Meaning                                       |
| ----------------------------- | ----- | ------------------------------------------------------- |
| `min_trades_per_instrument`   | int   | `10` — HARD gate                                        |
| `max_drawdown_pct`            | float | `0.35` — HARD gate (fraction, not percent)              |
| `min_win_rate`                | float | `0.35` — SOFT warning                                   |
| `min_expectancy`              | float | `-0.5` — SOFT warning (R-multiples)                     |
| `score_threshold`             | float | `0.15` — HARD gate (min fitness)                        |
| `max_score_std_dev`           | float | `0.30` — SOFT warning (cross-instrument consistency)    |
| `trade_count_target`          | int   | `50`                                                    |
| `warmup_candles`              | int   | `30`                                                    |
| `fitness_weights`             | dict  | `{expectancy_rr: 0.5, win_rate: 0.2, trade_count_norm: 0.2, drawdown: 0.1}` |

✅ **Runtime status**: Confirmed consumed by `src/config_layer/config_validator.py`. The `fitness_weights` key names here (`expectancy_rr`, `trade_count_norm`, `drawdown`) match what `config_validator.py` lines 132–136 actually reads. See note in `docs/SCHEMAS.md` about prior key-name drift.

---

## `goal` — Economic-Objective Targets (Goal Layer)

Consumed by `src/config_layer/goal_schema.py` (`GoalSpec.from_prod_config`) → compared by
`src/config_layer/goal_validator.py`. The single machine-readable statement of business
success (goal id **G001**). **Advisory-first:** every backtest emits a `goal_report`
(measure-only telemetry); a config that fails the goal is only HARD-blocked at promotion when
`enforce: true`. See [`docs/topics/goal-layer.md`](../topics/goal-layer.md) and
[`docs/architecture/goal.md`](../architecture/goal.md) §1.1.

| Key                  | Type   | Default / Meaning                                                       |
| -------------------- | ------ | ----------------------------------------------------------------------- |
| `goal_id`            | str    | `"G001"` — label for this objective (mandatory)                         |
| `enforce`            | bool   | `false` — DORMANT. `true` folds goal FAILs into promotion hard-failures |
| `trades_per_month`   | object | `{min:20, target:40, max:80}` — frequency band                          |
| `avg_rr`             | object | `{min:2.0}` — currently reports SKIP (no faithful aggregate metric)     |
| `win_rate`           | object | `{min:0.35}`                                                            |
| `max_drawdown_pct`   | object | `{max:0.10}` — fraction, not percent                                    |
| `risk_per_trade`     | object | `{target:0.005}` — informational                                        |
| `expectancy_r`       | object | `{min:0.20}` — realized E[R], R-multiples                               |
| `timeframe`          | object | `{execution:"M15", structure:"H1"}`                                     |
| `instruments`        | list   | `["BTCUSDT","ETHUSDT","BNBUSDT"]`                                        |
| `constraints`        | object | `{reaction_only, human_execution, no_prediction}` — all `true`          |

**Editing:** the goal section is **hash-neutral** — `config_hash` covers only `params`, so
editing `goal` does not require a rehash (do NOT touch `params`). A *missing* section is
fail-soft (advisory disabled, F-018); a *present-but-malformed* section fails-fast.

✅ **Runtime status**: Advisory telemetry confirmed via `BacktestMetrics.distribution["goal_report"]`; enforcement path present but DORMANT (`enforce=false`).

---

## `governance` — Shadow Promotion

Consumed by `src/governance/shadow_promotion_gate.py`.

| Key                  | Type  | Default                                  |
| -------------------- | ----- | ---------------------------------------- |
| `min_shadow_trades`  | int   | `30` — must be positive integer          |
| `shadow_data_csv`    | str   | `"data/AUDUSD_M15.csv"`                  |
| `shadow_output_csv`  | str   | `"results/shadow_trades.csv"`            |

✅ **Runtime status**: Confirmed consumed by `src/governance/shadow_promotion_gate.py`. Note: `promotion_margin` is not in this section — it is hardcoded as `PROMOTION_MARGIN=0.02` in `src/core/model_registry.py`.

---

## `validation_summary` — Last Approval Metrics

Written by `PromotionManager._execute_promotion()` on every successful promote.

```json
{
  "config_id":           "prod_validation_v1_multi_2026_03",
  "final_score":         0.3224,
  "mean_score":          0.3224,
  "consistency_penalty": 0.0,
  "total_trades":        42,
  "max_drawdown":        0.095,
  "instruments":         ["AUDUSD"],
  "per_instrument":      {"AUDUSD": {...}},
  "warnings":            ["AUDUSD: low trade count (42) — sample may be marginal."],
  "updated_at":          "2026-04-10T18:27:25.290581Z"
}
```

✅ **Runtime status**: Written by `PromotionManager`, read by governance audit tools.

---

## `backtest` — BacktestRunner Defaults

| Key                        | Type  | Default    |
| -------------------------- | ----- | ---------- |
| `htf_candles_per_range`    | int   | `4`        |
| `warmup_candles`           | int   | `30`       |
| `slippage_enabled`         | bool  | `true`     |
| `slippage_atr_fraction`    | float | `0.10`     |
| `slippage_seed`            | int   | `42`       |
| `simulated_spread_pct`     | float | `0.0002`   |
| `initial_capital`          | float | `100000.0` |
| `risk_pct_per_trade`       | float | `0.01`     |
| `use_compounding`          | bool  | `true`     |
| `gap_reset_enabled`        | bool  | `true`     |
| `gap_reset_minutes`        | int   | `120`      |
| `event_flush_every`        | int   | `100`      |

✅ **Runtime status**: Confirmed consumed by `src/runtime/backtest_v2.py` via `BacktestConfig.from_prod_config()`.

---

## `feature_monitor` — Drift Detector

| Key             | Type  | Default | Purpose                                   |
| --------------- | ----- | ------- | ----------------------------------------- |
| `window_size`   | int   | `500`   | Rolling stats window                      |
| `hard_drift_z`  | float | `3.0`   | Z-score above which WARNING is logged     |
| `soft_drift_z`  | float | `2.5`   | Z-score above which DEBUG is logged       |

✅ **Runtime status**: Confirmed consumed by `src/features/feature_monitor.py`.

⚠️ **Note** *(as of 2026-06-07 12:52 UTC+5:30)*: The config also contains keys `drift_regime_pause_enabled` and `drift_cooldown_candles` which are **not listed in this reference** and whose runtime consumer status is unconfirmed. These may be read by `feature_monitor.py` or may be unused.

---

## `tuner` — Auto-Tuner

| Key                    | Type  | Default                                                              |
| ---------------------- | ----- | -------------------------------------------------------------------- |
| `trade_count_floor`    | int   | `3`                                                                  |
| `trade_count_target`   | int   | `50`                                                                 |
| `consistency_alpha`    | float | `0.1`                                                                |
| `fitness_weights`      | dict  | `{expectancy_rr: 0.5, win_rate: 0.2, trade_count_norm: 0.2, drawdown: 0.1}` |
| `llm_gate`             | dict  | `{base_score_trigger: 0.1, hard_reject_threshold: 0.2, blend_weights: [0.7, 0.3]}` |
| `phase2_min_iter`      | int   | `20`                                                                 |

✅ **Runtime status**: Confirmed consumed by `scripts/training/auto_tuner_multi.py`.

---

## `training` — Training Pipeline

| Key                      | Type | Default |
| ------------------------ | ---- | ------- |
| `min_records_to_train`   | int  | `200`   |
| `min_records_recommend`  | int  | `500`   |

✅ **Runtime status**: Confirmed consumed by `src/training/train_pipeline.py`.

---

## `portfolio` — Multi-Instrument Allocator

| Key                     | Type  | Default                 |
| ----------------------- | ----- | ----------------------- |
| `initial_capital`       | float | `100000.0`              |
| `risk_pct`              | float | `0.01`                  |
| `slippage_atr_fraction` | float | `0.08`                  |
| `warmup_candles`        | int   | `100`                   |
| `output_dir`            | str   | `"results/portfolio"`   |

✅ **Runtime status**: Confirmed consumed by `src/portfolio/portfolio_validation.py`.

---

## `agent` — AI Automation Agent

Consumed across `src/agent/*`. Key subsections include BitNet 3B model path, REPL flags, and `copilot_auto_narrate=false`. See `docs/AGENT_REFERENCE.md` for the full tool/intent inventory.

✅ **Runtime status**: Confirmed consumed by `src/agent/*` modules.

---

## `inout` — Live Execution Runtime

Consumed by `src/inout/*`. The largest nested block in the config.

### `inout.scanner`

| Key                           | Type      | Purpose                            |
| ----------------------------- | --------- | ---------------------------------- |
| `allowed_symbols`             | list[str] | Symbols eligible for scanning      |
| `scan_timeframes`             | list[str] | Timeframes scanned                 |
| `candle_expansion_atr_mult`   | float     | Expansion threshold in ATR units   |
| `volume_spike_mult`           | float     | Volume spike detection multiplier  |
| `volume_lookback`             | int       | Lookback window for volume stats   |
| `min_atr_threshold`           | float     | Minimum ATR to scan                |
| `structure_lookback`          | int       | Lookback for market structure      |
| `require_all_conditions`      | bool      | AND vs OR gating                   |
| `min_composite_score`         | float     | Minimum composite score to emit    |
| `cooldown_seconds`            | int       | Anti-spam cooldown                 |

### `inout.exit`

TP ladder + probability-driven exits. Keys: `tp1_fraction`, `tp2_fraction`, `runner_fraction`, `tp1_rr`, `tp2_rr`, `sl_structure_lookback`, `sl_atr_buffer_mult`, `runner_trail_atr_mult`, `p75_factor`, `min_confidence_for_prob_exit`, `min_prob_samples`, `tp2_abandon_prob`, `runner_extend_prob_threshold`, `runner_tight_prob_threshold`, `tp1_near_threshold`, `high_atr_pct_skip`.

### `inout.time`

| Key              | Type | Purpose                  |
| ---------------- | ---- | ------------------------ |
| `min_time_min`   | int  | Minimum hold time        |
| `default_time_min` | int| Default hold time        |
| `max_time_min`   | int  | Hard exit after N minutes|

### `inout.risk`

| Key                       | Type  | Purpose                         |
| ------------------------- | ----- | ------------------------------- |
| `max_concurrent_trades`   | int   | Max open positions              |
| `max_total_exposure_pct`  | float | Max combined exposure           |
| `risk_per_trade_pct`      | float | Per-trade risk                  |
| `dedup_window_seconds`    | int   | Dedup duplicate signals         |

### `inout.probability`

Probability-engine blending: `approach`, `model_dir`, `blend_weight`, `tp1_min_prob`, `tp2_min_prob`, `min_confidence`, `prob_blend_alpha`, `auto_retrain_n`, `min_train_records`.

### `inout.db`

SQLite-like trade store for live mode: `path`, `wal_mode`, `timeout`.

### `inout.logging`

| Key              | Type | Example                       |
| ---------------- | ---- | ----------------------------- |
| `audit_log_path` | str  | live trade audit JSONL path   |
| `log_level`      | str  | `"INFO"` / `"DEBUG"`          |

⚠️ **Runtime status** *(as of 2026-06-07 12:52 UTC+5:30)*: The `inout` config block is consumed by `src/inout/*` which was **archived on 2026-05-02** (moved to `archive/inout_legacy/`). No code path in current `src/` reads these keys. They exist in the production config but have no active runtime consumer in the current spine.

---

## `capital_management` — Capital Protection Thresholds

| Key                          | Type  | Default    |
| ---------------------------- | ----- | ---------- |
| `total_capital_inr`          | float | `1000000.0`|
| `max_risk_per_trade_pct`     | float | `1.0`      |
| `kill_switch_daily_loss_inr` | float | `50000.0`  |
| `monthly_drawdown_limit_pct` | float | `15.0`     |

⚠️ **Runtime status** *(as of 2026-06-07 12:52 UTC+5:30)*: **No confirmed consumer.** The capital-protection layer in the runtime spine is `ultron_risk_gate` (see above), which reads its own separate keys. No code path in `src/core/ultron_risk_gate.py`, `src/core/engine_runner.py`, or any engine reads from the `capital_management` section. A trader editing these keys will see zero effect on runtime behavior. To wire this section, a coding agent would add `capital_management` as a config source in `UltronRiskGate.evaluate()`.

---

## `data_ingestion` — Data Source Configuration

| Key              | Type  | Default                                           |
| ---------------- | ----- | ------------------------------------------------- |
| `db_url`         | str   | `"postgresql://localhost/tradelatest"`             |
| `mt5_enabled`    | bool  | `false`                                           |
| `csv_data_dir`   | str   | `"data/"`                                         |

⚠️ **Runtime status** *(as of 2026-06-07 12:52 UTC+5:30)*: **No confirmed consumer.** The codebase has no database — all state is file-backed (per `CLAUDE.md §1`, `ARCHITECTURE.md §1`). The signal flow reads from CSV files, not Postgres. This section references a PostgreSQL database that does not exist in the architecture. The `mt5_enabled: false` key suggests a legacy MT5 integration feature that was never connected.

---

## `gate_intelligence` — Multi-Weight Signal Gate

| Key                          | Type  | Default |
| ---------------------------- | ----- | ------- |
| `gate_weight_intent`         | float | `0.30`  |
| `gate_weight_vol`            | float | `0.25`  |
| `gate_weight_liquidity`      | float | `0.25`  |
| `gate_weight_structure`      | float | `0.20`  |
| `gate_approval_threshold`    | float | `0.55`  |

⚠️ **Runtime status** *(as of 2026-06-07 12:52 UTC+5:30)*: **No confirmed consumer in the CRT spine.** The spine (SIGNAL_FLOW.md Steps 3–6) flows through EngineRunner → FusionEngine → DecisionEngine → ExecutionPlanner → UltronRiskGate. None of these modules read `gate_intelligence` keys. The `gate_intelligence.compute_crt_levels()` function IS called by ExecutionPlanner, but it does not use these weight/approval-threshold keys. These keys appear to be an unimplemented design for a pre-fusion signal gate.

---

## `sl_tp_comparison` — SL/TP Method Analyser

| Key                      | Type  | Default |
| ------------------------ | ----- | ------- |
| `legacy_sl_atr_mult`     | float | `1.0`   |
| `legacy_tp_atr_mult_*`   | float | varies  |
| `primary_metric`         | str   | `"profit_factor"` |
| `output_path`            | str   | `"results/sl_tp_comparison/"` |

⚠️ **Runtime status** *(as of 2026-06-07 12:52 UTC+5:30)*: **No consumer in the live or backtest trade path.** This section is used ONLY by `analytics/sl_tp_comparator.py` for post-hoc analysis. The config's own `_comment` field says: "Used ONLY by SLTPComparator, never in live path". It is a pure analytical tool section that does not affect trading decisions.

---

## `phase5_calibration` — Training-Only Quality Gates

| Key                  | Type  | Default |
| -------------------- | ----- | ------- |
| `val_ratio`          | float | `0.30`  |
| `min_val_samples`    | int   | `30`    |
| `min_corr`           | float | `0.10`  |
| `max_cal_error`      | float | `0.25`  |
| `cv_corr_std_max`    | float | `0.05`  |
| `cv_n_folds`         | int   | `3`     |
| `require_cv_stable`  | bool  | `true`  |

⚠️ **Runtime status** *(as of 2026-06-07 12:52 UTC+5:30)*: This is a **training-pipeline-only** section (consumed by `src/training/phase5_calibration.py`), not a runtime trading parameter. It lives in the production config alongside runtime sections but only takes effect during model training, not during live or backtest trading.

---

## `training_trigger` — Auto-Retrain Thresholds

| Key                     | Type  | Default |
| ----------------------- | ----- | ------- |
| `min_new_samples`       | int   | `100`   |
| `drift_window_hours`    | int   | `24`    |
| `drift_event_threshold` | int   | `5`     |
| `cooldown_hours`        | int   | `72`    |
| `integrity_log`         | str   | `""`    |
| `drift_event_kinds`     | list  | `[]`    |

⚠️ **Runtime status** *(as of 2026-06-07 12:52 UTC+5:30)*: **No confirmed consumer.** The auto-training pipeline (`scripts/training/auto_tuner_multi.py`) is invoked manually via CLI, not triggered by these thresholds. There is no auto-trigger daemon in the documented CLI entry points (`ARCHITECTURE.md §7`). These keys may be intended for a future auto-retrain service that has not been implemented.

---

## `signal_belief` — Temporal Conviction Accumulator

*(Not present in the active v2_multi_2026_04.json — documented here for reference.)*

| Key                | Type  | Default |
| ------------------ | ----- | ------- |
| `enabled`          | bool  | `false` |
| `high_conviction`  | float | `0.8`   |
| `min_confirmations`| int   | `2`     |

⚠️ **Runtime status** *(as of 2026-06-07 12:52 UTC+5:30)*: **Section absent from active config.** `src/core/engine_runner.py` line 425 reads `config.get("signal_belief", {})`, which returns an empty dict when the key is missing. The belief gate (temporal conviction accumulator at lines 819–839) is therefore **never active**. The code exists and the gate logic is implemented, but the enabling config section has never been added to the production config.

---

## `cognitive_layer` — Cognitive Bus

*(Not present in the active v2_multi_2026_04.json — documented here for reference.)*

| Key       | Type  | Default |
| --------- | ----- | ------- |
| `enabled` | bool  | `false` |

⚠️ **Runtime status** *(as of 2026-06-07 12:52 UTC+5:30)*: **Section absent from active config.** `src/core/engine_runner.py` line 435 reads `config.get("cognitive_layer", {})`, returning an empty dict. The `CognitiveBus` background thread (advisory telemetry writer) is therefore **never started**. The code is clean and well-structured but stranded without the enabling config key.

---

## `regime_fusion_weights` — Per-Regime Fusion Overrides

*(Present in the active config but not in its own top-level section — exists within `fusion_engine` as a nested block.)*

⚠️ **Runtime status** *(as of 2026-06-07 12:52 UTC+5:30)*: This nested block specifies per-regime weight matrices (e.g. TRENDING: `crt: 0.38, gaussian: 0.20, zone_gate: 0.12, rr: 0.20, strategy_consensus: 0.1`). However, `FusionConfig` in `src/core/engine_runner.py` (lines 374–390) reads only the flat weights (`weight_crt`, `weight_gaussian`, etc.) — it does **not** read `regime_fusion_weights`. This means fusion behavior is regime-blind despite the config specifying regime-adaptive weights. The TRENDING/RANGING/VOLATILE distinctions in this block have zero effect on fusion output.

---

## `strategy_engine.s01..s10` — Strategy Configs

⚠️ **Runtime status** *(as of 2026-06-07 12:52 UTC+5:30)*: These 10 sub-sections configure the strategies (`s01_crt` through `s10_trap`). `StrategyOrchestrator` (`src/strategies/strategy_orchestrator.py`) reads these and injects a consensus score into the EngineRunner context as `strategy_consensus_score`. However, EngineRunner only uses this consensus value if it is `>= 0.0` — the consensus is advisory, not gating. Whether the individual strategy thresholds (`min_confidence`, `sl_atr_mult`, `tp_rr_ratio`) are actually enforced depends on whether `StrategyOrchestrator.compute()` is invoked in the active execution path. This path should be verified against the runtime code before relying on changes to individual strategy configs.

---

## Editing Rules

1. **Never edit the active file in place.** Create `v2_<label>_<YYYY_MM>.json`, validate, then promote.
2. **After any edit, rehash:** `python scripts/maintenance/_compute_hash.py`.
3. **Promote only through the governance path:**
   ```
   python src/governance/promotion_manager.py promote \
     --checkpoint results/tuner/checkpoint_multi.json \
     --version   v2_<label>_<YYYY_MM> \
     --data-dir  data/
   ```
4. **Rollback** by restoring the archived file (`{version}_archived_{ts}.json`) and re-running the active-config loader.
5. **Adding a new section** requires: (a) a fail-fast `_require` in the consumer module, (b) a matching entry in `docs/SCHEMAS.md §8`, (c) default values here, (d) a test in `tests/`.

---

## Appendix Z: Modules with No Documented Runtime Consumer

> *(As of 2026-06-07 12:52 UTC+5:30)*
>
> These files exist in `src/` but no documented spine path calls them.
> Verify against actual runtime before relying on them.

| Module | Possible Role | Notes |
| ------ | ------------- | ----- |
| `src/core/feature_store.py` | Reusable feature-store component | No import found in spine modules. May be future-use scaffolding. |
| `src/core/ultron_risk_gate_wrapper.py` | Regime pre-scaler for UltronRiskGate | Wraps `UltronRiskGate.evaluate()` with regime-based risk scaling. Not wired in `live_engine_hook.py` or `engine_runner.py`. |
| `src/bitnet/_smoke_test.py` | BitNet quality test | Utility/test file, no runtime dependency. |
| `src/bitnet/quality_check.py` | BitNet quality check | Utility file, no runtime dependency. |
| `src/bitnet/bitnet_tools.py` | BitNet utilities | Utility file, no runtime dependency. |
| `src/bitnet/benchmark.py` | BitNet benchmark | Utility file, no runtime dependency. |