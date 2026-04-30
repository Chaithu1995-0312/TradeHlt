# CONFIG_REFERENCE.md

> Complete reference for `configs/production/v1_multi_2026_03.json`.
> This file is the **single source of truth** for every runtime tunable. No
> Python module is allowed to define a default that shadows a value here.

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

---

## `decision_engine` — Final ACCEPT/REJECT

| Key                          | Type  | Default |
| ---------------------------- | ----- | ------- |
| `score_threshold`            | float | `0.45`  |
| `p_win_threshold`            | float | `0.40`  |
| `rr_threshold`               | float | `1.20`  |
| `weak_component_threshold`   | float | `0.55`  |
| `weak_link_weight`           | float | `0.30`  |

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

---

## `llama_gate` — Local LLM Server

Consumed by `src/config_layer/llama_gate.py`.

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

---

## `governance` — Shadow Promotion

Consumed by `src/governance/shadow_promotion_gate.py`.

| Key                  | Type  | Default                                  |
| -------------------- | ----- | ---------------------------------------- |
| `min_shadow_trades`  | int   | `30` — must be positive integer          |
| `shadow_data_csv`    | str   | `"data/AUDUSD_M15.csv"`                  |
| `shadow_output_csv`  | str   | `"results/shadow_trades.csv"`            |

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

---

## `feature_monitor` — Drift Detector

| Key             | Type  | Default | Purpose                                   |
| --------------- | ----- | ------- | ----------------------------------------- |
| `window_size`   | int   | `500`   | Rolling stats window                      |
| `hard_drift_z`  | float | `3.0`   | Z-score above which WARNING is logged     |
| `soft_drift_z`  | float | `2.5`   | Z-score above which DEBUG is logged       |

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

---

## `training` — Training Pipeline

| Key                      | Type | Default |
| ------------------------ | ---- | ------- |
| `min_records_to_train`   | int  | `200`   |
| `min_records_recommend`  | int  | `500`   |

---

## `portfolio` — Multi-Instrument Allocator

| Key                     | Type  | Default                 |
| ----------------------- | ----- | ----------------------- |
| `initial_capital`       | float | `100000.0`              |
| `risk_pct`              | float | `0.01`                  |
| `slippage_atr_fraction` | float | `0.08`                  |
| `warmup_candles`        | int   | `100`                   |
| `output_dir`            | str   | `"results/portfolio"`   |

---

## `agent` — AI Automation Agent

Consumed across `src/agent/*`. Key subsections include BitNet 3B model path, REPL flags, and `copilot_auto_narrate=false`. See `docs/AGENT_REFERENCE.md` for the full tool/intent inventory.

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
