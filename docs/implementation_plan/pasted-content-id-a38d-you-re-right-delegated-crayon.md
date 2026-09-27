# K23 Block-Heuristic Conditional-Expectancy Table: Design Discussion Summary

Status: DESIGN DISCUSSION ONLY. Codebase not read. No file modified. Everything below comes from the pasted conversation plus my own review notes (section 7). Anything not verified against the repo is marked UNVERIFIED.

## 1. The pivot (why K23 exists)
- The session had been doing defensive tracker work: K1–K22, the K11a/K11b split, reconciling 23/19/17/7 counts, and `bar_ts` vs `bar_open_ts`. That kind of work only makes sense once the direction is known, and it isn't known.
- The evidence so far points one way: 3 trades in 2 years at net −1.69R. F-086 found 0/84 state cells clear zero. F-087 found gross expectancy ≈ 0. F-055 found 0/4 instruments improve under BitNet. F-019–F-042 killed directional and selection edge across 4 asset classes. No edge shows up at any granularity tested.
- Two open questions:
  - **Q1:** Is there a conditioning signal at a granularity between F-086's 84 cells and F-087's every-bar level? Answered by a block-level table: 19 heuristics × 4 = 76 cells, scored on forward-walk net R. The prior is thin.
  - **Q2:** Does the strategy work once the clocks are fixed? n=3 proves nothing. Answered by state-machine fixes followed by a re-run.
- The model-layer architecture answers Q1 only. If Q1 comes back "no", the model layer has no substrate: the registry, contract, shadow harness, BitNet B, Gaussian B and RR gates would be "a catalogue of nothing."
- The sequence is: (1) build the 19 block heuristics (no training, labels, label contracts or reference populations), (2) run them on every oracle unit (`forward_walk` → `pnl_rr_net` under `ComponentCostModel`), (3) cross-tab and report cells whose 95% CI excludes zero, (4) decide.
  - If there is signal, build the registry, contract and harness around it.
  - If the table is empty, stop, retire the model layer, and keep only the spine and the cost model.
- Deferred until the table speaks: the registry, the MIAR join, the `MODEL_CATALOG` refactor, the floor test, and the Semantic OS nouns.
- **K23 opened:** run the block-level table before any further governance work.

## 2. Heuristic conventions
- Input: one bar's block features from `enriched_df` (canonical plus frame-only columns). Output: a scalar in [0,1].
- No training or labels. Deterministic. Nothing tuned on outcome. Scales are declared from the feature's own units. No abstention (the P4 "block specialist" class).
- Naming: `M1_{BLOCK}_{FAMILY}_HEURISTIC`.
- Primitives: `sigmoid`, `clamp`, `bell(x,c,w)=exp(-((x-c)²)/(2w²))`, `sign`, `mean`.

## 3. The 19 heuristics (original spec: formula, then failure mode)
1. **GEOMETRY_CANDLE_QUALITY**: score = `body_ratio`. It saturates near 1 on trends and near 0 on ranges, by design.
2. **FLOW_VOLUME_DYNAMICS**: `clamp(sigmoid(2(volume_ratio−1)) + 0.2·volume_spike, 0, 1)`. FX/CFD volume is a broker proxy, so the signal is weak by construction.
3. **TREND_EMA_CONFORMITY**: `sigmoid(trend_strength_z/2) · (1 if sign(ema_spread)=sign(momentum_score) else 0.5)`. `momentum_score` saturates on ~99.7% of XAUUSD bars (F-061/F-064), so the sign term is robust and `trend_strength_z` does the real work.
4. **OSCILLATOR_MOMENTUM_CONFORMITY**: `sigmoid(macd_hist_z/2) · (0.5 + 0.5·sign(macd_hist_raw)·sign(rsi_14−50))`. RSI and MACD are correlated, so the score mostly tracks `macd_hist_z`.
5. **VOLATILITY_REGIME_DENSITY**: `bell(volatility_ratio, 1.0, 0.5)`. Symmetric around 1. If high vol is what matters, a one-sided kernel would need to be added.
6. **STRUCTURE_SWING_TOPOLOGY**: `(1 + mean(2·HH−1, 2·LL−1, 2·BOS−1, 2·CHoCH−1))/2`. Weights are equal even though the signals are not equally informative. Refining them would break the no-tuning rule.
7. **LIQUIDITY_PRESSURE**: `clamp(lps·(1 + sweep_detected + 0.5·double_sweep)/1.5, 0, 1)`. Possible double-count, because `lps` already uses exp-decay.
8. **SMC_ZONE_PROXIMITY**: `bell(min|distance|, 0, w=median)` over the 8 distances (ob, fvg, breaker, mitigation, pdh, pdl, eqh, eql). The distances are on different scales, so each should be normalized by its own median before taking the min. The normalization is declared, not tuned.
9. **TEMPORAL_DISPLACEMENT_CYCLE**: `sigmoid(disp_strength−1) · exp(−candles_since_sweep/20)`. The 20 was declared to match `max_sweep_age_candles`.
10. **CONTEXT_SESSION_CLOCK**: `max(london, ny, overlap, 0.5·asia)` using smooth bumps over UTC hours. The session hours are hardcoded and must match the fixed session windows.
11. **MICROSTRUCTURE_CANDLE_ANATOMY**: `|Δclose|/(|Δclose| + upper_wick + lower_wick + ε)`. Near-duplicate of #1.
12. **TREND_BASELINE_MA_DISTANCE**: `clamp(0.5 + 0.25(tanh(pvma20_z/2) + tanh(pvma50_z/2)), 0, 1)`. Treats "far above the MAs" as good, which only holds in a trend regime.
13. **VOLATILITY_BAND_CONFORMITY**: `(1 − 2|bb_position − 0.5|) · bell(bb_width_z, 0, 1.5)`. Deliberately excludes the breakout case.
14. **VOLATILITY_SPECTRUM_DISAGREEMENT**: `1 − (max − min)/2` over the three regime definitions {0,1,2}. This is a transition detector: a high score means "stable", not "safe".
15. **SWING_LINEAGE_BATCH_CAUSAL_DENSITY**: rolling agreement between batch (centered) and causal swings across the 10 swing columns. **Uses look-ahead by design.** It is a hindsight diagnostic and must never enter a point-in-time arbiter.
16. **VOLUME_PROXY_DYNAMICS**: `sigmoid(2(volume_range_proxy_ratio − 1))`. Near-duplicate of #2.
17. **STATE_TRANSITION_KERNEL**: empirical `P(curr|prev)` with `TRADE_OPENED` mapped to 1.0. Only 12 of 81 transitions are observed, so Laplace smoothing (α=1) is needed; otherwise an unseen transition scores "impossible" instead of "novel".
18. **STATE_OCCUPANCY_CYCLE**: `1 − clamp(bars_in_state/TTL)`, with 0.5 for states that have no TTL (RANGE, DISPLACEMENT). `bars_in_state` is not persisted anywhere, so this is the only heuristic that needs a code change or new emit (K22).
19. **PARENT_HTF_CONTEXT**: 1.0 if aligned, 0.5 if NONE, 0.0 if against. The current direction is a second input that must be declared, sourced either from the `direction` frame column or from L3 `curr_state`.

**Output:** an (N, 19) matrix. 47,197 bars × 19 = 896,743 cells. M4 (arbiter) and M3 (tracker) come after the table.

**Known limitations:**
- The scores are uncalibrated, so they are not probabilities. Cross-specialist comparison is invalid unless declared (P6).
- The blocks overlap: #1/#11, #2/#16, and #3/#4/#12.
- #15 uses look-ahead.
- #18 needs a new emit.
- The widths and slopes are declared, not fitted. If the table comes back null, that could be a scale problem, so the scales must be pre-registered and a sensitivity sweep run before calling it "no signal".

**Original build order:**
1. Build #1–17 and #19 from the 94-column frame.
2. Emit `bars_in_state` for #18.
3. Join to oracle `pnl_rr_net`.
4. Cross-tab, pre-register, and report CIs.

Only step 2 touches the spine.

## 4. Config sourcing (the magic-number round)
- The spec carried about 24 magic numbers. Each one should come from market config; otherwise it becomes a parallel source of truth whose scales disagree with the state machine's gates.
- Files needed: `market_ontology.yaml` (FM-020…FM-070), `market_crt_states.yaml` (TTLs, gates, sessions, HTF), `v2_htfcrt_2026_08.json` (live values), `miar_registry.json`, `active_models.yaml`.
- **Reading A** means aligning the heuristics to the current config. **Reading B** means adjusting the configs themselves: retrace 0.50→0.65, real session hours, structural SL, removing decorative TTLs. The concern with building on the current (unfixed) config is that the measurement ends up measuring the clocks, not the market.
- **Reading C (accepted):** the heuristic module reads config, fails closed on a missing key, and carries no constants. This removes silent constants (Drift D), but the residual is that it cleanly reads the *broken* values. #9, #18 and #15 measure the state machine's view of the market, not the market itself. That is fine only if the research question is explicitly about the state machine's view.

## 5. Sourced constants (after the configs were received; K26 CLOSED)
**Tier 1 (canonical):**

| # | Heuristic | Constants and source |
|---|---|---|
| 1 | GEOMETRY | none |
| 2 | FLOW | `volume_ma_window=20`, `volume_spike_percentile=75`, `volume_spike_fixed_fallback=1.5` (`feature_pipeline`, FM-062/063) |
| 3 | TREND | `trend_strength_threshold=0.15`, `momentum_threshold=0.3` (`engine_runner.dual_engine`); `normalization_basis="atr_relative"` |
| 4 | OSCILLATOR | RSI 70/30, `zscore_window=50` |
| 5 | VOLATILITY | bell width is a declared convention |
| 6 | STRUCTURE | equal weights, declared |
| 7 | LIQUIDITY | `liquidity_decay_coeff=−0.5`, `liquidity_nan_sentinel=10.0` |
| 8 | SMC | none; the distances are already tanh-bounded (FM-075–082) |
| 9 | TEMPORAL | `disp_strength_clip=[0,3]`, `retest_depth_clip=[0,1]`; decay window = `htf_candles_per_range`, which is **16 or 4? (K24)** |
| 10 | CONTEXT | `session_windows_utc`: ASIA [0,9], LONDON [7,16], NEWYORK [12,21] |

**Tier 2 (frame context):**

| # | Heuristic | Constants and source |
|---|---|---|
| 11 | MICROSTRUCTURE | ε only |
| 12 | TREND_BASELINE | `ma_periods[0]=20`, `trend_strength_window=10`, `zscore_window=50` |
| 13 | VOLATILITY_BAND | `bb_period=20`, `bb_std=2.0`, `zscore_window=50` |
| 14 | VOLATILITY_SPECTRUM | {0,1,2} |
| 15 | SWING_LINEAGE | `swing_window=2` |
| 16 | VOLUME_PROXY | `volume_ma_window=20` |

**Tier 3 (state):**

| # | Heuristic | Constants and source |
|---|---|---|
| 17 | STATE_TRANSITION | empirical 9×9 matrix from the L3 trace, Laplace α=1 |
| 18 | STATE_OCCUPANCY | `max_sweep_age_candles=20`, `max_displacement_age_candles=3`, `max_expansion_age_candles=495`, `max_expansion_age_hours=124`, `soft_conf_max_candles=3` |
| 19 | PARENT_HTF | `htf_candles_per_range=16`, `parent_crt.timeframe="H4"`, `bias_gate_mode="reject_on_mismatch"` |

**DECLARED_CONVENTIONS block.** These are scale conventions with no config key, and are not config-overridable until they earn one:
- #2 sigmoid slope 2.0
- #3 divisor 2.0
- #4 divisor 2.0
- #5 bell width w=0.5
- #13 bell width w=1.5
- #17 Laplace α=1
- #10 Asia multiplier 0.5: this one must either move to config or be declared a non-configurable convention. Right now it is neither.

**Config confirmations:**
- `retrace_reset_pct=0.5` is live (the retrace kill that Fix 2 would widen).
- `extension_reset_fib=1.618` is live.
- `parent_crt` is enabled on H4 with `reject_on_mismatch`, so #19's input is real.

**Discrepancies (config is authority; neither blocks the heuristics):**
- `retest_atr_depth_fraction` is 0.3 in config vs 0.50 in the YAML.
- `body_ratio_min` is 0.65 in config vs 0.70 in the ontology comment. This affects how #1 is interpreted.

## 6. K24 history (the key blocker)
- **Round 1:** 4 vs 16 was raised. The 20-bar sweep age may never bind, because the HTF clock fires earlier.
- **Round 2 (closed as 4):** the YAML comment, the events cross-tab (1,372/1,393 = 98.5% of SWEEP deaths recorded as `HTF_changed`) and a mean dwell of about 2 bars were taken to confirm 4.
- **Round 3 (REOPENED):** `v2_htfcrt_2026_08.json` has `backtest.htf_candles_per_range: 16`, and its own comment says "4 = 1H, 16 = 4H". The config was created 2026-08-15 with params unchanged from `v2_multi_2026_04`.
  - With a 16-bar clock and a dwell of about 2, a boundary crossing should be about 12.5% likely, not 98.5%. The measurement and the config cannot both be right.
  - Hypotheses: (a) `HTF_changed` is recorded for resets caused by something else (gap, age, forced, or a shorter internal clock); (b) the YAML comment is stale, or the analysis ran on a config set to 4.
- Proposed resolution: grep the events log for reset-reason strings and cross-tab them against bar distance from the last HTF change. Roughly 10 minutes.
- K24 blocks #9 and #18. The other 17 can be built once the design is approved.

## 7. My review notes (conversational LLM, not repo-verified)
1. **Even 4 doesn't explain 98.5%.** With a 4-bar clock and a dwell of about 2, you would expect roughly 50% crossings, not 98.5%. So 98.5% probably doesn't come from the boundary cadence under either value, which strengthens hypothesis (a): `HTF_changed` is likely being recorded for resets that happen before any boundary. Another possibility (UNVERIFIED) is that there are two separate HTF clocks: the `backtest` HTFBuilder range used by the SWEEP reset, and the `parent_crt` H4 used for bias. They could be read from different keys, which would let both 4 and 16 be live at once. The events cross-tab should check reset bar vs boundary bar directly, not dwell averages. The repo's own rule is decisions, not occupancy.
2. **Multiple testing.** 76 cells at 95% gives about 4 false positives expected under the null. Following the F-097 precedent, the rule needs BH-FDR, a train/holdout split, and a `long_only` control, not "any CI excluding zero".
3. **Beating the base ≠ earning.** The base rate is about −0.29R (F-086). A cell whose CI excludes zero on the *negative* side, or that only beats the base, is not a consumable signal. Pre-register that a qualifying cell must have net R > 0 with its CI above zero.
4. **Effective n.** Overlap gives an effective n of about 941 per direction (F-086), not 47k. CIs need block bootstrap or equivalent.
5. **What "×4" means is unspecified.** Quartiles? Direction × 2 bins? It must be pre-registered, including tie handling for discrete heuristics (#6, #14, #19), which can't be split into quartiles.
6. **Heuristics are directionless but the outcome has direction.** #4, #6 and #12 encode bullish/bearish; the others are magnitude-only. The join needs a declared direction axis (long and short units separately, as in F-086), or bullish heuristics will cancel out against short outcomes.
7. **State-matrix size.** Per CLAUDE.md F-075, `CRTState` went from 9 to 12 states, so #17's 9×9 (81 cells) may be 12×12 on `v2_htfcrt`. UNVERIFIED.
8. **Session timezone.** F-066: MT5 timestamps are broker time labelled UTC, and 53% of XAUUSD bars carry the wrong session label. The `session_windows_utc` values feeding #10 inherit this unless `session_timestamp_basis=utc_corrected`.
9. **Known-contaminated inputs.** #3 (`momentum_score`, F-064), #15 (centered swings, F-051) and #8/#6 (the SMC/structure lineage) should carry their finding IDs in the module docstring (K27).
10. **Internal inconsistencies in the pasted spec** (cosmetic):
    - The "6 fully config-derived / 8 need config" counts don't match the table, which lists 11 needing config.
    - #7 appears twice in the mapping table.
    - The "16 heuristics blocked" claim became 17 buildable in the next round.
11. **K28 recommendation.** Run baseline-first. The fixes (retrace, sessions, clocks) mostly act on *which bars become trades*, while the oracle scores every bar regardless of the state machine. Only #9, #17, #18 and #19 read state-machine surfaces. So the baseline table is mostly fix-invariant, and a baseline-first run can be diffed against a post-fix run on just those 4.

## 8. Tracker (as of the end of the pasted thread)

| ID | Item | Status |
|---|---|---|
| K23 | Run the block table before further governance | open |
| K24 | `htf_candles_per_range`: 16 in config vs 4 in the YAML/measurement | **REOPENED**, blocks #9 and #18 |
| K25 | Reading A/B/C | resolved as C, pending user confirmation |
| K26 | Read the ontology and production configs | CLOSED |
| K27 | Per-specialist declaration: state-machine view or market view | open |
| K28 | Baseline-first or fix-first | open, decision required |
| K29 | #18 uses dwell derived from the events lane, not a new emit (a fourth pattern: derived-from-artifact) | open, would close K22 by derivation |
| K22 | `bars_in_state` not persisted | open |
| K21 | Layer-trace schema authority | open |
| K2, K11b, K13, K17, K19, K20 | — | open, unchanged |

Drift D: partially resolved. The residuals are the config values under review and the Asia 0.5 multiplier.

## 9. Proposed next step (after approval)
1. A read-only K24 probe: reset-reason × distance-to-HTF-boundary cross-tab on the XAUUSD events, plus a grep for which key each HTF clock reads.
2. Draft the pre-registration (bins, direction axis, FDR, holdout, controls, effective-n CI).
3. Build the 17 unblocked heuristics.
