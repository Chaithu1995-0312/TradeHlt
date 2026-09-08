# L-003G — Entry-time predictability of JOINT_STATE_SL_TP

**Status:** MEASURED (falsification-oriented observation)  
**L-003 remains NOT frozen** — attribution remains blocked (IDENTITY + OUTCOME_SEMANTICS)  
**Date (UTC):** 2026-09-07T19:02:42.252Z  
**Branch pin:** `feature/trace-parquet-duckdb-query` @ `d7c25f6e55616261b8b229b000875abd3bd315eb`  
**run_id:** `l003g_joint_state_entry_predictability_20260907_190242`  
**version / doctrine:** `L-003G.v1`

Machine-readable: `docs/governance/analytics_joint_state_entry_predictability_l003g-2026-09-07.json`.

## Banner / discipline

**Observation → Measurement → Evidence → Promotion.**

- **Target y:** 1 iff `(art_outcome=='SL_HIT' & outcome=='TP_HIT')` ≡ canonical **`JOINT_STATE_SL_TP`** (SAFE_ALIAS: `EARLY_STOP_CANDIDATE`).
- **Base rate:** 31.5257% (n=559,768).
- **Question:** Can membership be predicted from information available **before the trade completes**?
- **Stance:** try to **falsify** entry-time predictability on available anatomy fields.

## Naming

| Role | ID |
|---|---|
| Canonical identity | `JOINT_STATE_SL_TP` |
| Research alias (SAFE_ALIAS) | `EARLY_STOP_CANDIDATE` |
| Formula | scanner=`SL_HIT` (art_outcome) × oracle=`TP_HIT` (outcome) |

## Forbidden features (post-hoc / path / outcome leakage)

`art_outcome`, `outcome`, `win`, `rr_achieved`, `art_rr`, `duration_candles`, `mfe`, `mae`, `art_mfe`, `art_mae`, `art_consistent`, `mfe_r`, `mae_r`, `reached_0_5r`, `reached_1r`, `reached_2r`, `favorable_first`, `bars_to_first_1r`, `bars_to_peak_path`, `bars_to_peak_within_trade`, `time_to_bottom_path`, `capture_ratio`, `giveback`, `return_15m_gross`, `return_15m_net`, `return_30m_gross`, `return_30m_net`, `return_45m_gross`, `return_45m_net`, `return_60m_gross`, `return_60m_net`, `return_90m_gross`, `return_90m_net`, `spine_pnl_rr_net`, `spine_cost_pips`

## Unavailable this pass (not on anatomy join — not measured)

CRT state, HTF, manipulation — do not invent joins.

## Allowed entry-time inventory

Candidates scanned: 52  
Kept after null/constant drop: 51

`direction`, `year`, `month`, `weekday`, `hour`, `session_derived`, `session_code`, `volatility_regime`, `trend_bias`, `entry`, `sl`, `tp`, `risk_distance`, `f_open`, `f_high`, `f_low`, `f_close`, `f_volume`, `f_volume_ratio`, `f_double_sweep`, `f_ema_fast`, `f_ema_slow`, `f_ema_spread`, `f_trend_bias`, `f_trend_strength`, `f_momentum_score`, `f_atr`, `f_volatility_ratio`, `f_rsi_14`, `f_macd_line`, `f_macd_signal`, `f_macd_hist`, `f_sweep_detected`, `f_liquidity_sweep`, `f_break_of_structure`, `f_swing_high`, `f_swing_low`, `f_higher_high`, `f_lower_low`, `f_body_size`, `f_wick_size`, `f_body_ratio`, `f_volatility_regime`, `f_session`, `f_hour_of_day`, `f_disp_strength`, `f_retest_depth`, `f_candles_since_retest`, `f_liquidity_distance`, `f_liquidity_pressure_score`, `f_volume_spike`

### Dropped

- `bitnet_score`: dropped_high_null:0.9999

### Absolute-price note (multivariate)

Absolute price levels (entry/sl/tp/f_open/f_high/f_low/f_close/f_ema_fast/f_ema_slow) remain in inventory+univariate; excluded from LOIO multivariate due to non-transferable scale across instruments.

## Univariate association (aggregate)

Top features by |association| vs base rate 0.3153 (mass levels only; n>=1000):

| rank | feature | kind | primary | secondary |
|---:|---|---|---|---|
| 1 | `hour` | categorical | best_lift=1.070 (level 5, n=23328) | max_abs_rate_delta=0.0219 |
| 2 | `f_hour_of_day` | categorical | best_lift=1.070 | max_abs_rate_delta=0.0219 |
| 3 | `year` | categorical | best_lift=1.010 | max_abs_rate_delta=0.0128 |
| 4 | `weekday` | categorical | best_lift=1.020 | max_abs_rate_delta=0.0097 |
| 5 | `session_code` | categorical | best_lift=1.029 | max_abs_rate_delta=0.0092 |

**Univariate caveat:** `trend_bias` / `f_trend_bias` raw best-lift (1.59) is driven by level 0.0 with **n=6** (y_rate=0.5); mass levels (-1/+1, n~272k/287k) have lift ~1.00. Not a usable entry signal. Continuous features near AUC 0.50 (e.g. `risk_distance` AUC=0.495).

Full top-20 in companion JSON. Per-instrument top-10 also in JSON.

## Multivariate (LogisticRegression, balanced)

Design cols after one-hot: **134** (excluding absolute prices listed above).

### LOIO (holdout of record)

| Fold | n_train | n_test | AUC | balanced_acc | top-decile lift | base_test |
|---|---:|---:|---:|---:|---:|---:|
| holdout BNBUSDT | 419826 | 139942 | 0.5178 | 0.5113 | 1.0904 | 0.3201 |
| holdout BTCUSDT | 419826 | 139942 | 0.5065 | 0.5013 | 0.9884 | 0.3101 |
| holdout ETHUSDT | 419826 | 139942 | 0.5237 | 0.5163 | 1.0944 | 0.3125 |
| holdout SOLUSDT | 419826 | 139942 | 0.5168 | 0.5127 | 1.0406 | 0.3184 |

- **LOIO mean AUC:** 0.5162
- **LOIO mean top-decile lift:** 1.0534

### Within-instrument chronological (last 25% holdout)

| Instrument | n_train | n_test | AUC | balanced_acc | top-decile lift |
|---|---:|---:|---:|---:|---:|
| BNBUSDT | 104956 | 34986 | 0.5084 | 0.5032 | 1.0861 |
| BTCUSDT | 104956 | 34986 | 0.5261 | 0.5179 | 1.0931 |
| ETHUSDT | 104956 | 34986 | 0.5228 | 0.5125 | 1.1133 |
| SOLUSDT | 104956 | 34986 | 0.5011 | 0.4991 | 1.0599 |

- **Within mean AUC:** 0.5146

### Aggregate stratified 25% holdout (descriptive only)

- AUC: **0.5218**
- balanced_acc: 0.5152
- top-decile lift: 1.1018

## Falsification / support lean

**Lean:** `FALSIFIED_on_available_entry_fields`

Entry-time observables on this anatomy join do NOT predict JOINT_STATE_SL_TP (LOIO mean AUC=0.516, mean top-decile lift=1.0534444626968038). Population remains path-defined, not entry-defined on available fields.

Threshold note: AUC≈0.5–0.55 and lifts~null => falsify entry-time predictability on available fields

## Explicit non-claims

- Predicting membership ≠ explaining trailing stops
- No attribution unlock
- `JOINT_STATE_SL_TP` remains OBSERVED population; `EARLY_STOP_CANDIDATE` remains alias
- No promotion to ontology/registry
- `economic_claims_allowed` false

## Reproducibility

| Field | Value |
|---|---|
| git_commit_sha | `d7c25f6e55616261b8b229b000875abd3bd315eb` |
| BNB dataset_sha256 match | True |
| BTC dataset_sha256 match | True |
| ETH dataset_sha256 match | True |
| SOL dataset_sha256 match | True |
| sklearn | LogisticRegression + roc_auc_score |

## Parent

L-003F joint-state census: `docs/governance/ANALYTICS_JOINT_OUTCOME_STATES_L003F.md` (run_id `l003f_joint_outcome_states_20260907_184519`).

## Child measurement (L-003H)

- Trail/exit transition candle replay: `docs/governance/ANALYTICS_TRAIL_EXIT_TRANSITIONS_L003H.md` (run_id `l003h_trail_exit_transitions_20260907_192115`).
