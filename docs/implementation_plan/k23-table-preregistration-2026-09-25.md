# K23 Block-Heuristic Table: Pre-Registration v1

**Status: FROZEN on commit of this file's sha256 into the SESSION LOG (2026-09-25), BEFORE any outcome value (`y_R_*`) is read for this table.** Any later change is a new version (v2), never an edit. Design context: `k23-block-heuristic-table-design.md` (§8c, §8d, §9, §10). Where they disagree this document wins for the K23 run.

**Authority:** information tier only (CLAUDE.md §6.5 rung 1). No G001 claim, no config or production change, no `ACTIVE_VERSION` change, no model-layer authority. Result of this run is a descriptive table plus a routing decision (section 12).

## 1. Frozen inputs (identities)

| Item | Value |
|---|---|
| Shadow config | `v2_htfcrt_k23_shadow_2026_09` (clone of `v2_htfcrt_2026_08`; F1 0.618, F2 exchange_local + TOKYO, F3 sweep_extreme, F4 SWEEP exempt) |
| Spine run | `results/k23_shadow/run_20260924_194133_XAUUSD__20240522..20260521_v2_htfcrt_k23_shadow_2026_09_7de09f62` (28 setups, 27 trades) |
| `lt_id` | `lt_20260924_194133_XAUUSD` (all 47,197 bars `JOINED`) |
| Corpus | `data/mt5/XAUUSD_M15.csv`, sha256 `4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56`, 47,275 rows, 47,197 after the 78-row warmup |
| Bar matrix | `results/research/bar_matrix_k23/XAUUSD_M15/bar_matrix.csv`, sha256 `508ee96527ac3f0c9ab00a5f9cf08d6d69d08dbbee80f4c2aa4ea4db48784976` |
| Labels | `results/research/oracle_labels_k23/XAUUSD_M15/labels.csv`, sha256 `f801562fa012e19590889c480194af7562e89b63511ccd4bbb001d40ace582b4` (565,884 rows = 47,157 bars x 2 directions x 6 arms) |
| Fidelity (done before this doc) | matrix: 136 columns identical except `lt_id`, `trace_id`, `engine_state_after`; labels: the 2 pre-existing arms byte-identical to the pre-fix file on all 377,256 rows (14 value columns). Both consistent with "labels are CRT-state-independent". |
| Tree | dirty (other sessions' uncommitted `src/` edits; `code_sha` 09ffcb11, `tree_dirty: true`). Observation on the working tree, not HEAD. |

## 2. Population and outcome

- **Unit** = one bar `t` x one direction `d in {long, short}` (F-086 shape). 47,157 bars per direction (bars with a full 40-bar forward window).
- **Primary outcome** `y = y_R_net` from the arm `sl_geom = sweep_extreme`, `tie_break = production`. Reason: it is the spine's own trade object under F3 (swept-extreme stop) with SL-first precedence (F-088). Cost = SEM-015 component model, fill = SEM-016 adverse (as labelled).
- **Secondary arms** (`disp_bar`, `fixed_atr`, and the `optimistic` tie-break) are reported for the top cells only. They never gate a verdict.
- **Known measurement limits (carried, not fixed):** the sweep_extreme stop is a trailing 16-bar-extreme PROXY for the engine's swept wick (exact only where they coincide); this is the every-bar population, not production trades; F-086 effective n is about 941 independent units per direction, so n below is not independent n.

## 3. Heuristics (18 tested, 1 excluded)

Deterministic functions of one bar's row (plus declared state history for #17/#18). No training, no labels, no outcome used. Output in [0,1]. Constants come from config where a key exists; the rest are the DECLARED_CONVENTIONS below. Primitives: `sigmoid`, `clamp`, `bell(x,c,w)=exp(-((x-c)^2)/(2w^2))`.

| # | Name | Formula (columns in the K23 matrix) | Note / contamination |
|---|---|---|---|
| 1 | GEOMETRY_CANDLE_QUALITY | `body_ratio` | |
| 2 | FLOW_VOLUME_DYNAMICS | `clamp(sigmoid(2(volume_ratio-1)) + 0.2*volume_spike, 0, 1)` | broker tick-volume proxy (F-099) |
| 3 | TREND_EMA_CONFORMITY | `sigmoid(trend_strength_z/2) * (1 if sign(ema_spread)==sign(momentum_score) else 0.5)` | F-061/F-064 saturation of `momentum_score` |
| 4 | OSCILLATOR_MOMENTUM | `sigmoid(macd_hist_z/2) * (0.5 + 0.5*sign(macd_hist_raw)*sign(rsi_14-50))` | |
| 5 | VOLATILITY_REGIME_DENSITY | `bell(volatility_ratio, 1.0, 0.5)` | |
| 6 | STRUCTURE_SWING_TOPOLOGY | `(1 + mean(2*higher_high-1, 2*lower_low-1, 2*break_of_structure-1, 2*change_of_character-1))/2` | discrete (5 levels); F-051 swing lineage |
| 7 | LIQUIDITY_PRESSURE | `clamp(liquidity_pressure_score*(1+sweep_detected+0.5*double_sweep)/1.5, 0, 1)` | |
| 8 | SMC_ZONE_PROXIMITY | `bell(min_k(|d_k|/med_k), 0, 1)` over the 8 distances (ob, fvg, breaker, mitigation, pdh, pdl, eqh, eql); `med_k` = median of `|d_k|` over all 47,197 emitted bars (non-outcome) | F-051 lineage |
| 9 | TEMPORAL_DISPLACEMENT_CYCLE | `sigmoid(disp_strength-1) * exp(-candles_since_sweep/16)`; 16 = `backtest.htf_candles_per_range` | `candles_since_sweep` is since-sweep (F-107) |
| 10 | CONTEXT_SESSION_CLOCK | using F2 `exchange_sessions_at(timestamp, exchange_session_windows)`: 1.0 if LONDON or NEWYORK active; 0.5 if only TOKYO active; 0.0 otherwise | F-066 broker time handled by F2; the 0.5 is a declared convention |
| 11 | MICROSTRUCTURE_CANDLE_ANATOMY | `|delta_close| / (|delta_close| + upper_wick + lower_wick + 1e-9)` | near-duplicate of #1 |
| 12 | TREND_BASELINE_MA_DISTANCE | `clamp(0.5 + 0.25*(tanh(price_vs_ma20_z/2) + tanh(price_vs_ma50_z/2)), 0, 1)` | |
| 13 | VOLATILITY_BAND_CONFORMITY | `(1 - 2*|bb_position-0.5|) * bell(bb_width_z, 0, 1.5)` | |
| 14 | VOLATILITY_SPECTRUM_DISAGREEMENT | `1 - (max-min)/2` over `{volatility_regime_global_batch, volatility_regime_expanding_causal, volatility_regime_rolling_causal}` | discrete (3 levels); batch column is non-causal by name |
| 15 | SWING_LINEAGE_BATCH_CAUSAL_DENSITY | **EXCLUDED** | look-ahead by design (centered swings); a hindsight diagnostic must not enter a conditioning table |
| 16 | VOLUME_PROXY_DYNAMICS | `sigmoid(2(volume_range_proxy_ratio-1))` | near-duplicate of #2 |
| 17 | STATE_TRANSITION_KERNEL | `P(state_t | state_{t-1})` from `engine_state_after`, estimated on the **discovery partition only**, Laplace alpha=1 over the support {legal edges (18) + self-loops}; an observed edge outside the support scores 0 and is counted in the report | `TRADE_OPENED -> 1.0` is not applicable (that token is not in `engine_state_after`) |
| 18 | STATE_OCCUPANCY_CYCLE | `1 - clamp(bars_in_state/TTL)`; `bars_in_state` = 1-based position inside the maximal contiguous run of `engine_state_after` (derived from the matrix, K29). TTL table (post-F4 config): SWEEP 20, EXPANSION 495, RETEST 3, SHADOW_PENDING 4; states without a TTL (RANGE, DISPLACEMENT, EXECUTION, RESOLUTION, EXPIRED) score 0.5 | SWEEP TTL becomes binding under F4 |
| 19 | PARENT_HTF_CONTEXT | per unit direction `d` against `parent_bias`: 1.0 aligned, 0.5 `NONE`, 0.0 against | discrete (3 levels); reads `parent_bias`, not the CRT state |

**DECLARED_CONVENTIONS (no config key; not tunable after this freeze):** #2 slope 2.0 · #3 divisor 2.0 · #4 divisor 2.0 · #5 bell width 0.5 · #13 bell width 1.5 · #8 bell width 1.0 on median-normalised distance · #10 TOKYO-only weight 0.5 · #17 alpha 1 · #12 divisor 2.0 and factor 0.25.

**Directional heuristics** (#4, #6, #12 encode bullish/bearish) get no sign flip: cells are formed per unit direction, so the direction axis already separates them.

## 4. Cells

- **Continuous heuristics** (#1-5, 7-13, 16-18): quartile bins, edges at the 25/50/75th percentiles of that heuristic on the **discovery** partition, applied unchanged to the holdout. If edges tie, bins collapse and only the resulting distinct bins are cells (count reported).
- **Discrete heuristics** (#6, #14, #19): natural levels.
- **Cell** = (heuristic, bin, direction). Expect roughly 140 cells. Ineligible cells (section 6) are listed but excluded from the FDR family.
- **State strata** (SWEEP, DISPLACEMENT, EXPANSION, and RANGE as the null stratum, by `engine_state_after`) are a **diagnostic breakdown of cells that pass**, not extra tests. RETEST, EXECUTION, SHADOW_PENDING, EXPIRED and RESOLUTION are reported INSUFFICIENT (below the floor).

## 5. Split

Chronological by bar position. Discovery = bars `[0, 33,037)` (ends 2025-10-14 11:00). Embargo = the next 96 bars (dropped). Holdout = bars from 33,133 (2025-10-15 12:15) to the end, 14,064 bars. The 96-bar embargo exceeds the 40-bar label horizon. Bin edges, `med_k` (#8 uses all bars, no outcome) and the #17 matrix are fitted on discovery only. The holdout is read once, after the discovery verdicts are written to disk.

## 6. Inference

- **Statistic S1** (information): `mean(y | cell, d) - mean(y | d, pooled over the partition)`. Direction-matched base rate (about -0.29R in F-086, re-measured here, not assumed).
- **Statistic S2** (consumable): `mean(y | cell, d) - mean(y | long units, pooled over the partition)` (`long_only` control).
- **Block bootstrap**, joint resampling of blocks so cell and base move together. Two block schemes: (A) `episode_id` (maximal contiguous run of `engine_state_after`, 3,559 episodes over 47,197 bars); (B) fixed 40-bar blocks by `bar position // 40`. B = 2,000 draws, seed 20260925. Reported CI lower bound = the **lower** of the two schemes' 2.5th percentiles; reported p-value = the **larger** of the two one-sided p-values, `p = (1 + #{draw <= 0})/(B + 1)`. Reason: outcome windows (up to 40 bars) overlap across adjacent episodes, so scheme A alone is anti-conservative.
- **Eligibility floor (discovery):** at least 300 units and at least 30 distinct episodes in the cell. Cells below it are INSUFFICIENT, listed, not in the family.
- **Multiple testing:** BH-FDR at q = 0.05 over all eligible discovery cells (both directions, all heuristics), on the conservative p-values above.

## 7. Verdict tiers (a cell earns the highest that applies)

- **INFORMATION:** discovery S1 CI lower bound > 0 AND BH-FDR passes AND the holdout S1 point estimate is > 0 (same sign; holdout must itself meet the cell-size floor scaled to its length, at least 100 units and 10 episodes, else HOLDOUT_INSUFFICIENT and the cell stays at candidate).
- **CONSUMABLE:** INFORMATION AND discovery cell mean y > 0 with the cell-mean CI lower bound > 0 AND discovery S2 CI lower bound > 0 AND the holdout cell mean y > 0 AND the holdout S2 point estimate > 0.
- Anything else = NO_CLAIM. A cell whose CI excludes zero on the negative side is reported as such and is not a claim of any kind.

## 8. Gates that run BEFORE the real table (halting)

1. **Planted-signal gate (F-086 pattern):** add a synthetic `+0.30R` to `y` for units in one chosen cell of one heuristic on a copy of the discovery data; the machinery must recover it as INFORMATION (and as CONSUMABLE when the planted shift makes the cell mean and S2 positive). Repeat at `+0.10R`; the detection rate at each level is reported. A failure to recover `+0.30R` halts the run.
2. **Permutation null:** shuffle `y` across episodes (blocks kept intact), rerun the whole table 200 times; the mean number of BH passes must be at most `0.05 * (eligible cells)` with a maximum of 0 passes in at least 95% of shuffles at q = 0.05. A failure halts the run and the inference procedure is reviewed (a new version), never the data.
3. **Determinism:** two runs with the same seed produce byte-identical cell tables.

## 9. Sensitivity, and what it may and may not do

If the table returns no INFORMATION cell, the declared scales (bell widths, slopes) are re-run once at x0.5 and x2 (all scales together) and reported side by side **before** the words "no signal" are used. The sensitivity run never selects a scale, never adds cells to the family, and never upgrades a verdict; it can only qualify a null as "not robust to scale".

## 10. Reporting

Per cell: n units, n episodes, cell mean, S1, S2 with CI and p (both schemes), BH-adjusted q, holdout values, tier. Plus: the count of eligible cells, count of INFORMATION and CONSUMABLE cells, the largest `|S1|` cell regardless of tier, the strata table for any passing cell, the secondary-arm values for passing cells, and the permutation-null summary. Nothing is dropped for being inconvenient.

## 11. Known contamination and limits (carried into every reading)

F-061/F-064 (#3 saturation) · F-051 (#6, #8 centered-swing lineage) · F-066 (fixed here for the session filter by F2, not for `session`/`hour_of_day` features) · F-086 (base rate about -0.29R; every-bar population, effective n about 941/direction; the "beat the base" test alone is losing-less, not earning) · F-088 (trade object) · F-082 (cost basis) · F-097 (a CI can vanish once the stratum is controlled) · one instrument, one corpus, one 2-year window · the sweep_extreme stop is a proxy · the F1-F4 changes are bundled in one shadow run, so no cell result can be attributed to a single fix.

## 12. Decision rule (what each outcome means)

- **At least one CONSUMABLE cell:** the model-layer registry/contract/harness work is justified around that cell's block. This is still information-tier: no authority, no config change (§6.5); the next step would be a separate pre-registered replication on new data.
- **INFORMATION cells only:** "less bad", not "earning". No license to build the model layer. Report and stop.
- **No INFORMATION cell (and the section 9 sensitivity qualified):** the block conditioning question (Q1) is answered "no on this corpus and construction"; the model-layer catalogue has no measured substrate here. Report and stop. This is a statement about this instrument, corpus and set of 18 declared heuristics, not about every possible conditioner.

## 13. Out of scope

Retraining, any model, `use_bitnet`, `rr_fusion`, `ACTIVE_VERSION`, promotion, per-heuristic sizing, Q2 as an economic claim (the 27-trade spine result is reported as an observation only).
