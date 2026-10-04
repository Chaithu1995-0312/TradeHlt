# K23 Block-Heuristic Conditional-Expectancy Table: Design Discussion Summary

**Status: PARKED 2026-09-24.** Design only; nothing in §9 has been executed. Resume trigger: "Continue K23", starting at the §9 step 1 K24 probe (read-only).

Where the earlier review notes (§7) and the later user decisions (§8b–§8d) disagree, the user decisions win.

Origin: design discussion only. The codebase was not read while producing it. Everything below comes from the pasted conversation plus my own review notes (section 7). Anything not verified against the repo is marked UNVERIFIED.

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

### 6b. K24 RESOLVED 2026-09-24 (read-only probe, VERIFIED against a recorded artifact)
Artifact: `results/run_20260923_072728_XAUUSD__20240522..20260521_v2_htfcrt_2026_08_7de09f62/XAUUSD_events.jsonl` (7,112 events; run of the active `v2_htfcrt_2026_08`, config hash `7de09f62`). Probe script was scratch-only (not committed). This reads the recorded events, not a fresh engine run; 32 uncommitted `src/` files exist, so it is NOT a re-measurement of current code.
- **The live engine HTF clock is 16.** HTF-reset spacing: 2,351 of 2,467 HTF resets are exactly 16 bars apart. `ResetLogic.should_reset` (`src/config_layer/crt_engine_v2.py`, class `ResetLogic`) compares `current_htf_id` to `active_range.clock_id` and emits reason `HTF changed: A → B`; EXPANSION/RETEST are exempt.
- **The "4" is a different reader.** `crt_state_resolver.py:906` defaults `lifecycle.htf_candles_per_range` to 4 and `market_crt_states.yaml:359` carries 4 with a comment calling it "active prod". That is DOC_DRIFT (active prod is 16), and it affects the RESOLVER (F-069), not the engine. Not fixed here.
- **The 98.5% is reproduced exactly:** SWEEP exits = 1,372 RESET:HTF + 399 →DISPLACEMENT + 21 RESET:session-gap + 6 →EXPANSION. 1,372 / (1,372+21) = 98.5% is the share of SWEEP *resets* caused by the HTF flip. It is not a crossing probability, so it is consistent with a 16-bar clock.
- **CORRECTED:** the earlier "mean dwell ≈ 2 bars" was wrong for SWEEP→HTF resets: mean 9.84, median 11, max 15 (≤15 because the window is 16). My §7 note 1 model ("12.5% vs 50% expected crossings") assumed the wrong quantity and is withdrawn.
- **What the clock does:** it kills 1,372 of 1,792 SWEEPs (76.6%); only 399 (22.3%) reach DISPLACEMENT (mean 4.9 bars). Sweeps cluster early in a window (357 at offset 1 after a flip).
- **`max_sweep_age_candles=20` cannot bind** under a 16-bar window (max observed SWEEP dwell to HTF reset is 15).
- Other resets in the run (CORRECTED: my first bucketing dropped the "50% retrace"/"1.618 extension" reasons into an empty bucket of 275; re-bucketed): DISPLACEMENT retrace 131 · DISPLACEMENT extension 56 · EXPANSION extension 53 · EXPANSION retrace 35 · session-gap 121 · off_session_filter 15 (RETEST) · Against parent-timeframe 4 (RETEST) · Post-resolution 4 · soft-confirmation timeout 1. So the 0.5 retrace kill is real but small next to the HTF clock (166 retrace resets vs 2,467 HTF resets); it falls in DISPLACEMENT/EXPANSION, so F1 (0.618) acts downstream of the SWEEP bottleneck.
- **Consequence for F4:** the fix is not "correct a mislabelled reason". The design choice is whether a SWEEP should survive an HTF flip (e.g. exempt SWEEP like EXPANSION/RETEST) or the window should change. That is a behavior change needing your decision. **Pending.**
- **Consequence for #9/#18:** use `htf_candles_per_range=16` for the current epoch. #9's decay is no longer nearly a step function, but #18's TTL for SWEEP is decorative (20 > 15).

## 7. My review notes (conversational LLM, not repo-verified)
1. **Even 4 doesn't explain 98.5%.** With a 4-bar clock and a dwell of about 2, you would expect roughly 50% crossings, not 98.5%. So 98.5% probably doesn't come from the boundary cadence under either value, which strengthens hypothesis (a): `HTF_changed` is likely being recorded for resets that happen before any boundary. Another possibility (UNVERIFIED) is that there are two separate HTF clocks: the `backtest` HTFBuilder range used by the SWEEP reset, and the `parent_crt` H4 used for bias. They could be read from different keys, which would let both 4 and 16 be live at once. The events cross-tab should check reset bar vs boundary bar directly, not dwell averages. The repo's own rule is decisions, not occupancy.
2. **Multiple testing.** 76 cells at 95% gives about 4 false positives expected under the null. Following the F-097 precedent, the rule needs BH-FDR, a train/holdout split, and a `long_only` control, not "any CI excluding zero".
3. **The user chose the "beats base rate" pass rule (see §8d). This note stands as the basis for the proposed INFORMATION/CONSUMABLE tier split.** Beating the base ≠ earning. The base rate is about −0.29R (F-086). A cell whose CI excludes zero on the *negative* side, or that only beats the base, is not a consumable signal. Pre-register that a qualifying cell must have net R > 0 with its CI above zero.
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
11. **SUPERSEDED by the user decision in §8 (K28 = FIX-FIRST).** Original K28 recommendation: run baseline-first. The fixes (retrace, sessions, clocks) mostly act on *which bars become trades*, while the oracle scores every bar regardless of the state machine. Only #9, #17, #18 and #19 read state-machine surfaces. So the baseline table is mostly fix-invariant, and a baseline-first run can be diffed against a post-fix run on just those 4.

## 8. Tracker (as of the end of the pasted thread)

| ID | Item | Status |
|---|---|---|
| K23 | Run the block table before further governance | open |
| K24 | `htf_candles_per_range`: 16 in config vs 4 in the YAML/measurement | **CLOSED 2026-09-24: engine clock = 16** (see 6b); the YAML 4 is the resolver default (DOC_DRIFT). F4 now needs a design decision |
| K25 | Reading A/B/C | resolved as C, pending user confirmation |
| K26 | Read the ontology and production configs | CLOSED |
| K27 | Per-specialist declaration: state-machine view or market view | open |
| K28 | Baseline-first or fix-first | **DECIDED 2026-09-24: FIX-FIRST** (user). The table is built once, on the post-fix config |
| K29 | #18 uses dwell derived from the events lane, not a new emit (a fourth pattern: derived-from-artifact) | open, would close K22 by derivation |
| K22 | `bars_in_state` not persisted | open |
| K21 | Layer-trace schema authority | open |
| K2, K11b, K13, K17, K19, K20 | — | open, unchanged |

Drift D: partially resolved. The residuals are the config values under review and the Asia 0.5 multiplier.

## 8b. What fix-first means (design talk, 2026-09-24)
- **K24 becomes a precondition of the fix list.** You can't fix "the clock that kills 98.5% of SWEEPs" until you know which clock that is (a 16-bar boundary, a 4-bar key elsewhere, or a mislabelled reset reason). If the fix changes the wrong key, the table silently measures a clock that was never fixed.
- **The fixes must be justified without looking at outcomes.** With n=3, any fix chosen by how the trades turned out is curve-fitting. Each fix needs a stated domain rationale (for example, "sessions should match real exchange hours" or "retrace tolerance of 0.65 is the Sujan-narrated value") and must be frozen before the table runs.
- **The fixes land in a new config version, not in place.** Treat them as a shadow clone of `v2_htfcrt_2026_08`, following the §6.5 and F-055 pattern. Whether `v2_htfcrt_2026_08` is the ACTIVE_VERSION on this branch is UNVERIFIED.
- **What the fixes change for the table:** only the state-machine-surface heuristics (#9, #17, #18, #19) and #10 (session windows) move. The other 14 read feature math the fixes don't touch.
- **The candidate fix list as it stands in the thread:**
  - widen retrace from 0.50 to 0.65–0.70
  - use real session hours (this interacts with the F-066 broker-time issue)
  - structural SL
  - remove decorative TTLs
  - an HTF clock correction, pending K24
- **Q2 comes along for free.** Re-running the spine on the fixed config answers "does the strategy work with fixed clocks" (expect a small n again).

## 8c. Fix list: all 4 selected (user, 2026-09-24)

| Fix | Rationale that doesn't come from outcomes (to confirm) | Design issue |
|---|---|---|
| F1 Retrace 0.50→0.65–0.70 | The narrated setup tolerates a deeper pullback | Pre-register **one** value. A range invites choosing whichever value wins after seeing results |
| F2 Real session hours | Session windows should match real exchange hours | F-066 deliberately left `crt_engine.session_windows` on broker time as "a separate economic decision". This fix **is** that decision. It needs `session_timestamp_basis=utc_corrected` plus new windows, or a translation of the exchange hours into broker time. Pick one |
| F3 Structural SL | The stop belongs where the idea is invalidated: at the swept extreme | Define the buffer. The existing `sl_atr_buffer=0.2` (F-056) is a candidate. Also: the oracle's `forward_walk` geometry must use the same SL, or the table and the spine measure different trades (the F-088 class) |
| F4 HTF clock + TTL cleanup | Time limits and clocks should be the ones intended in the design | Blocked on the K24 probe. "Remove decorative TTLs" means deleting only those shown never to bind. Which TTLs those are is unknown until K24 and the dwell census are done |

**Decisions (user, 2026-09-24):**
- **F1:** `retrace_reset_pct = 0.618`. Rationale: Fibonacci, consistent with the existing `extension_reset_fib=1.618`. Frozen as a single value.
- **F2:** convert real exchange hours into **broker time**, with a US-DST-aware conversion (F-066). Timestamps stay `broker_local`, the feature session labels are unchanged, and only the CRT filter windows change.
- **F2 hours:** FX sessions, each converted to US-DST broker time using its own DST rule:
  - Tokyo 09:00–18:00 JST (no DST)
  - London 08:00–17:00 London time (EU DST)
  - NY 08:00–17:00 NY time (US DST)
- **F3:** SL = swept extreme ± 0.2 ATR, reusing `sl_atr_buffer=0.2` (F-056). The oracle's `forward_walk` must use the same SL geometry, which rules out a table-vs-spine trade-object mismatch (F-088 class).
- **F4 (decided 2026-09-24 after K24 closed):** exempt SWEEP from the HTF-flip reset, like EXPANSION/RETEST (`ResetLogic.should_reset`). Must be config-gated with the default byte-identical (§6.5), governed by the Construction Protocol (manifest first, CRT closure stays OPEN). **IMPLEMENTED 2026-09-24 (code only, flag OFF everywhere; no shadow config yet):** `ResetLogic(config, htf_reset_exempt_sweep=False)` ← `CRTEngine(..., htf_reset_exempt_sweep=False)` ← `BacktestConfig.htf_reset_exempt_sweep` ← optional `backtest.htf_reset_exempt_sweep` (JSON bool; non-bool raises; stamped in the run summary). Wired as a backtest key, NOT a CRTConfig field: adding a CRTConfig field tripped 7 count-pinned tests (field count 53→54, scalar-required 47→48, the one "complete" config, threshold-authority census) on top of 5 pre-existing reds in the same files. Manifest: `docs/governance/build_manifests/CH-k23-f4-sweep-htf-exempt.impact.json` (IMPACT: APPROVED). Tests: `tests/test_htf_reset_sweep_exempt.py` (19). Also drop only TTLs proven never to bind (`max_sweep_age_candles=20` is one candidate, but with SWEEP exempt it BECOMES binding, so it must be kept; re-run the dwell census on the post-fix config before removing anything).

**F3 remainder IMPLEMENTED 2026-09-24 (code only, flag OFF everywhere; no shadow config yet):** oracle `labeler.py` gains a third `sl_geom`, `sweep_extreme`, opt-in via `label_corpus(sweep_lookback=N)` (`main()` reads N strictly from `backtest.htf_candles_per_range`, =16). It anchors to the **trailing N-bar extreme** (window includes bar t) -/+ `sl_atr_buffer*atr`, a PROXY for the engine's swept wick because most bars have no engine sweep; exact parity holds only where the engine's sweep candle IS that extreme (negative control pins the boundary). `reference_level` is now per-run: `TradeJournal` derives it from `sl_anchor` (a hardcoded `displacement_extreme` would have mislabelled every `sweep_extreme` trade), new vocabulary member `REF_LEVEL_SWEEP_EXTREME`; `sl_anchor` is stamped into `summary.json`. Tests: `tests/research/test_sl_anchor_oracle_parity.py`. Manifest: `CH-k23-f3-oracle-arm-stamping`. Flag-off XAUUSD run vs the recorded 2026-09-23 run: trades and all 7,112 events identical (ids aside), summary differs only by the new stamp keys. Spine-vs-table equality on a real `sweep_extreme` run is UNMEASURED (needs the shadow config).

**F2 IMPLEMENTED 2026-09-24 (code only, flag OFF everywhere; no shadow config yet), exact per-date windows (chosen over static windows):** `backtest.session_window_basis` (`broker_static` default | `exchange_local`) + `backtest.exchange_session_windows`, `{NAME: {tz, open, close}}` half-open in the zone's own local time. `features.broker_clock.exchange_sessions_at` = broker -> UTC (the existing NY-DST rule) -> each session's own zone, so London's 08:00 is 10:00 broker in normal weeks but 11:00 broker in the US/EU DST-mismatch weeks (tested). Used by the CRT session filter, `UltronRiskEngine.score_time` and `BacktestRunner._session`. Fail-closed at load: bad tz/HH:MM, missing windows, or an `allowed_sessions` name with no window (`OVERLAP` exempt: inert in both modes). NOT done: TOKYO is not in any `allowed_sessions` (shadow-config edit); first-declared session wins on London/NY overlap. Tests: `tests/test_exchange_session_windows.py`. Manifest: `CH-k23-f2-exchange-session-windows`.

## 8d. Table pre-registration decisions (user, 2026-09-24)
- **Cells:** quartile bins for continuous heuristics; natural levels for the discrete ones (#6, #14, #19). Direction is split into LONG and SHORT, giving roughly 150 cells.
- **Pass rule:** the cell's net-R block-bootstrap CI lower bound sits above the pooled base rate (≈ −0.29R, to be re-measured on the post-fix config). Holdout must keep the same sign.
- **Holdout:** chronological 70/30 with a 96-bar embargo. Discovery on the first 70%, confirmation on the last 30%.
- **Recommended additions (not yet agreed):**
  - Label each passing cell with one of two tiers:
    - **INFORMATION:** beats the base rate.
    - **CONSUMABLE:** net R > 0 and beats `long_only`.
  - Per §6.5 "information ≠ value", only a CONSUMABLE cell should license building the registry and harness. An INFORMATION-only table means "less bad", so the model layer stays deferred.
  - Apply BH-FDR across roughly 150 tests in both tiers, since about 7 false hits are expected at 95%.

## 9. Proposed next step (after approval)
**Sequence:**
1. **K24 probe (read-only).** Cross-tab reset reason against bar-distance to the HTF boundary on the XAUUSD events. Find which config key each HTF clock reads (`backtest.htf_candles_per_range` vs the one in `market_crt_states.yaml`). Build a dwell census per state to find TTLs that never bind. This closes K24 and defines F4.
2. **Pre-registration document.** Write F1–F4 with their rationales, the 19 heuristic formulas plus the DECLARED_CONVENTIONS block, per-heuristic K27 declarations (state-machine view vs market view, contamination F-ids), and the bins, pass rule, split and FDR from 8d. Freeze it before any outcome is computed.
3. **Shadow config.** Clone `v2_htfcrt_2026_08` to a new version carrying F1 (0.618), F2 (broker-time FX windows), F3 (structural SL with 0.2 ATR) and F4. Not promoted; check ACTIVE_VERSION first.
4. **Oracle SL parity.** `forward_walk`/`multi_tp_walk` uses the F3 SL geometry. Confirm with a parity test against the spine.
5. **Build the heuristic module (Reading C).** Config-read, fail-closed. #18 uses dwell derived from the events (K29).
6. **Run the table** on the post-fix config, and re-run the spine for Q2.
7. **Decide** from the table: a CONSUMABLE cell means building around it; none means retiring the model layer.

**Verification:**
- Heuristic determinism: identical output across two runs.
- Config fail-closed: removing a key raises an error.
- SL parity test between oracle and spine.
- Planted-signal gate before the real run (F-086 pattern): recover a known injected edge.
- The governance green floor must stay green.
- SESSION LOG entries go to `assistant_project.md`.

## 10. Link to the States schema (2026-09-24; read from source, NOT re-run)

**Sources of the schema (authority order):** `configs/formulas/market_crt_states.yaml` (`states:` predicates over `feature_states:`, `valid_transitions:`, `thresholds:` + `lifecycle:`, `threshold_refs:`) → generated `CRTState`/`VALID_TRANSITIONS`/`EXECUTION_TIMEFRAME_STATES`/`PARENT_TIMEFRAME_STATES` (`src/config_layer/state_identity.py` ← `_crt_state_generated.py`) → the engine (`crt_engine_v2.py`) and the research-shadow resolver (`crt_state_resolver.py`, F-069: a different construction). Recorded state surfaces: `engine_state_after` and `ontology_state` on `results/research/bar_matrix/XAUUSD_M15/bar_matrix.parquet`; `STATE_TRANSITION`/`RESET` events; `results/decision_atlas_full/{transition_decision,episode}.parquet`.

**Schema facts that constrain the design**
- **Two disjoint sub-graphs.** 9 execution states (RANGE, SHADOW_PENDING, SWEEP, DISPLACEMENT, EXPANSION, EXPIRED, RETEST, EXECUTION, RESOLUTION) and 3 parent states (RANGE_C1, MANIPULATION_C2, DISTRIBUTION_C3). No edge crosses them. The parent track reaches the M15 engine only through the `parent_state` keyword (a bias/objective gate).
- **18 legal execution edges** (count from `valid_transitions:`: RANGE 2, SHADOW 3, SWEEP 3, DISPLACEMENT 2, EXPANSION 3, EXPIRED 1, RETEST 2, EXECUTION 1, RESOLUTION 1).
- **Entry decisions vs occupancy** (memory: entry-decisions-not-occupancy). Bar-matrix occupancy: RANGE 21,745 · SWEEP 15,186 · EXPANSION 7,092 · DISPLACEMENT 3,127 · SHADOW_PENDING 47. RETEST, EXECUTION, EXPIRED, RESOLUTION have no bar occupancy in the matrix. Decision populations (from the all-states probe): SWEEP 1,798 · DISPLACEMENT 399 · EXPANSION 148 · RETEST 24 · SHADOW 6.

**Corrections this link forces on the design**
1. **#17 smoothing.** Laplace over 81 cells is wrong: 63 of them are illegal edges (impossible, not "novel"). Smooth over the **18 legal edges** only; score illegal edges as not-a-transition. The parent 3 states are NOT in the matrix (the "12×12" worry in note §7.7 is withdrawn). Observed-vs-legal count of 12 is UNVERIFIED.
2. **#19 must not read `curr_state`.** Parent states never appear as engine states; #19 reads `parent_track_state` / `parent_bias` / `htf_state` columns, and the direction from `direction`/`crt_direction`.
3. **#18 TTL table is per-state from `lifecycle`/`thresholds`.** SWEEP's 20-bar TTL never binds today (max SWEEP→HTF-reset dwell 15) but BECOMES binding under F4, so its constant must come from the post-F4 config.
4. **State axis is a stratifier, not 19 extra tests.** Cross-tab each heuristic within the 4 states with real decision populations (SWEEP, DISPLACEMENT, EXPANSION, plus RANGE as the null stratum). RETEST/EXECUTION/SHADOW are below the n=30 floor and are reported as INSUFFICIENT, not measured. Bootstrap blocks by `episode_id` (4,159 episodes), not by bar, because decisions in one episode are not independent.
5. **Two state authorities → declare per heuristic (K27).** `engine_state_after` (engine) vs `ontology_state` (resolver) disagree by construction (F-069). Default the table's state column to `engine_state_after`. #9/#17/#18 read the engine surface; #10/#19 read frame columns. Never mix the two in one cell.

**Per-state map: which fix and which heuristic touches which state**

| State | Legal exits (schema) | Observed killers (2026-09-23 run, K24 probe) | Fix | Heuristics reading it |
|---|---|---|---|---|
| RANGE | SWEEP, SHADOW_PENDING | HTF reset re-founds range every 16 bars | F4 (clock) | #9 (age), #17 |
| SHADOW_PENDING | SWEEP, EXPANSION, RANGE | n=6 decisions | — | #17 |
| SWEEP | DISPLACEMENT, EXPANSION, RANGE | HTF 1,372 (76.6%) · →DISPLACEMENT 399 (22.3%) · session gap 21 · →EXPANSION 6 | **F4 exempt** | #9, #17, #18 |
| DISPLACEMENT | EXPANSION, RANGE | retrace 131 · extension 56 | **F1 (0.618)** | #9, #17, #18 |
| EXPANSION | RETEST, EXPIRED, RANGE | extension 53 · retrace 35 (HTF-exempt already) | F1 | #17, #18 |
| EXPIRED | RANGE | TTL soft archive | F4 TTL cleanup (only proven-nonbinding) | #17, #18 |
| RETEST | EXECUTION, RANGE | off_session 15 · parent-mismatch 4 · soft-conf timeout 1 | **F2 (windows)** | #10, #19 |
| EXECUTION | RESOLUTION | trade open (3 in 2 years) | **F3 (structural SL)** | #10 |
| RESOLUTION | RANGE | post-resolution 4 | — | #17 |

**Schema edits the fixes imply (all config-first, default byte-identical, per §6.5)**
- **F4:** engine gate in `ResetLogic.should_reset`; the resolver mirror is `thresholds.lifecycle.htf_protect_states: [EXPANSION, RETEST]` → add SWEEP, and correct `lifecycle.htf_candles_per_range` 4 → 16 (DOC_DRIFT found in K24). Both need the parity gate (F-069 stays a *structurally different* construction; do not claim agreement).
- **F1:** `retrace_reset_pct` 0.5 → 0.618 (CRTConfig).
- **F2:** `crt_engine.session_windows` converted to broker time; RETEST→EXECUTION uses `session:` predicate over LONDON/NEWYORK/OVERLAP in the EXECUTION state's `when:`.
- **F3:** SL geometry at EXECUTION; oracle `labeler.py` needs a third `sl_geom` arm (swept-extreme ± `sl_atr_buffer`) beside `disp_bar`/`fixed_atr`, or the table measures a different trade than the spine (F-088 class).
- After any of these, regenerate: `bar_matrix.parquet` (`engine_state_after`), `labels.csv`, and the decision-atlas parquet; the current ones (2026-09-23) are pre-fix. **CORRECTED: see §10b** (label values do not depend on F1/F2/F4; only F3 changes them).

**Existing artifacts reused (nothing new needs building for the join):** `src/research/oracle/labeler.py` (entry/SL/TP1/TP2 + `ComponentCostModel` at every bar, both directions, 4 arms → `labels.csv`, y_R_net), `src/research/oracle/scan.py` (block-bootstrap, direction-matched base rate, `long_only` control, embargoed partition), `build_bar_matrix.py` (state columns).

**Decided (user, 2026-09-24):** (a) strata = SWEEP, DISPLACEMENT, EXPANSION + RANGE as the null stratum; RETEST/EXECUTION/SHADOW_PENDING reported INSUFFICIENT; (b) state axis = `engine_state_after`; (c) resolver mirror of F4 DEFERRED (only the 4-vs-16 resolver drift is logged).

## 10b. Regeneration chain after the fixes (read from source 2026-09-24; CORRECTS an overstatement in §10)

**CORRECTED:** an earlier statement said the bar matrix AND `labels.csv` "predate every fix so both need regenerating". Only partly right. Verified in `scripts/research/build_bar_matrix.py` and `src/research/oracle/labeler.py`:
- `labels.csv` values (`entry`, `sl`, `tp1`, `tp2`, `risk_distance`, `y_R_*`, `cost_r`) come from bar OHLC/ATR + `multi_tp_walk` + the measured cost model. The labeler reads **no CRT state column**; from the matrix it only copies `lt_id` / `trace_id` / `bar_open_ts`. So **F1, F2 and F4 change no label value.** Only **F3** (new swept-extreme stop arm) changes/extends label content.
- The bar matrix's feature columns don't depend on F1–F4. Its state columns do: `engine_state_after`, `lt_id`, `trace_id`, `bar_open_ts` are stamped from ONE backtest run's layer trace (`--lt-id` is required; the labeler refuses a matrix mixing lt_ids).

**Chain (each step needs the previous):**
1. **New backtest run on the shadow config** (F1–F4 applied) → new `XAUUSD_layer_trace.jsonl` + events; new `lt_id`. (Current: `lt_20260923_072728_XAUUSD`, pre-fix, config hash `7de09f62`.)
2. **`build_bar_matrix.py --instrument XAUUSD --timeframe M15 --lt-id <new>`** → new state/identity stamps. Reruns the full pipeline; feature columns should come out identical (use as a check). Do not pass `--allow-*` flags.
3. **`labeler`** (`python -m research.oracle.labeler --instrument XAUUSD --timeframe M15`) **after adding the F3 arm** → new `labels.csv`, new `lt_id`. Without F3 this only re-stamps identity (last run took ~30 s per manifests).
4. **`scripts/analysis/build_decision_atlas.py`** from the new run's events → new `episode`/`transition_decision`/`excursion` parquets (state strata and episode blocks depend on them). Its arguments are UNVERIFIED (not read).
5. **Fidelity checks:** feature columns byte-identical to the pre-fix matrix; label values for the two existing arms byte-identical to the pre-fix `labels.csv`; only state columns + the new arm differ. A difference anywhere else means the "labels are state-independent" claim is wrong: STOP and report.

**Consequence:** the risky step is #1 (a governed run on a config that does not exist yet), not the labels. F3 is the only fix that forces new label content.
