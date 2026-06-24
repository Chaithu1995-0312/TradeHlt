# Alpha Ledger — Evidence-Backed Edge Recovery

> **Recovered: 2026-06-03 · Point-in-time snapshot (NOT a living doc).**
> Scope: every evidence-backed edge ever discovered across all plans / reports / findings /
> audits / experiments / backtests / notes / analyses through 2026-06-03.
> Sources: `docs/current-findings.md` (F-001…F-012) · `docs/analysis/*` ·
> `assistant_project.md` SESSION LOG · `memory/project_phase*` · `configs/promotion_log.jsonl`.
> **This is a recovery, not invention** — every entry traces to an existing artifact and quotes
> its numbers verbatim. For *current* truth, see `docs/current-findings.md`; for replay, re-run
> the cited backtest. Edges cross-link to their `F-0NN` finding where one exists, so this ledger
> *composes* with the living findings rather than duplicating them.

## Through-line (read first)

Three findings frame everything below (`F-001/F-002/F-003`): **the edge is in the
execution-selection *process* and *throughput policy*, not in static feature intelligence.**
Per-candle features are at chance (`AUC 0.5149`); the entire selectivity edge appears at the
final RETEST→EXECUTION gate (`+0.545R`); and the one proven ROI lever is session policy, which
moved BNBUSDT `+4.91% → +20.59%` — ~12× larger than the best-case intelligence upside the
Phase-0 gate could find. Two engine-history lines coexist in the evidence: a **structural-
correctness development line** (Phases 1–4b, `run_20260527`, config `v2_multi_2026_04`) that
built SHADOW_PENDING + EXPANSION TTL + shadow-advisory into the CRT engine, and the **stabilized
measurement line** (Phase 6+, the 15-trade baseline → 35-trade V3) that found the ROI levers.

### Schema (per edge)
`Source · Exact evidence (verbatim) · Validation status · Implemented · Abandoned · Expected profitability impact`

---

## 1. High-ROI patterns

### E-01: Session-policy expansion (the #1 ROI lever)
- **Category:** High-ROI pattern · ties **F-003**
- **Source:** `session-sweep-bnbusdt-2026-06-01.md:44`
- **Exact evidence:** BNBUSDT V0→V3 (`allowed_sessions` += ASIA, OFF_SESSION): `15→35 trades (+20),
  PF 1.79→2.54, ROI +4.91%→+20.59% (4×), WR 60%→66%, avg_R +0.328R→+0.545R, MAR 2.38→6.65,
  maxDD 2.07%→3.10% (≈flat), fitness 0.569→0.686`. Additive composition: `+ASIA(+8) + OFF_SESSION(+12) = +20`. ConfigValidator hard+soft gates PASS.
- **Validation status:** Validated (Likely; F-003).
- **Implemented:** Yes — promoted into `v4_multi_2026_06` (BNBUSDT-scoped, F-007).
- **Abandoned:** No.
- **Expected profitability impact:** +15.7pp ROI on BNBUSDT (one-time; session universe exhausted at 35 — see E-04/E-05).

### E-02: ROI baseline (frozen reference)
- **Category:** High-ROI pattern (reference anchor)
- **Source:** `roi-baseline-bnbusdt-2026-05-29.md:27-44`
- **Exact evidence:** BNBUSDT M15, 70,080 candles ≈ 2.0 yr, config `v2_multi_2026_04 - deepdeektry`:
  `ROI +4.91%` (capital 100,000→104,913.44), `CAGR +2.43%`, `PF 1.79` (gross +11.13R / −6.21R),
  `MAR 2.38`, `15 trades / 0 rejected`, `WR 60%`, `avg_RR +0.328R`, `maxDD 2.07% (2.08R)`,
  cost drag `−0.99R (~17% of gross)`. Best session NEWYORK 71% WR / +2.99R.
- **Validation status:** Validated (deterministic replay; matches `project_phase4b_findings`).
- **Implemented:** Yes — the stabilized pre-session config; measurement-only (no gate change).
- **Abandoned:** Superseded as the *active* config by V3/`v4_multi_2026_06`, kept as the baseline anchor.
- **Expected profitability impact:** Reference floor (+4.91%/2yr); the number every lever is measured against.

### E-03: The entire selection edge is created at the final RETEST→EXECUTION gate
- **Category:** High-ROI pattern / process · ties **F-002**
- **Source:** `gate-contribution-bnbusdt-2026-06-03.md:13,18` (BNBUSDT on `v4_multi_2026_06`)
- **Exact evidence:** per-stage candidate expectancy: SWEEP `−0.028R (PF 0.83)` → DISPLACEMENT
  `+0.021R (PF 1.15)` → EXPANSION `−0.023R (PF 0.86)` → RETEST `−0.039R (PF 0.76)` → **EXECUTION
  `+0.545R (PF 2.54, WR 65.7%)`**. The full `+0.584R Δ` appears only at RETEST→EXECUTION; the
  geometric funnel cuts COUNT `186,399→4,126` but does **not** concentrate winners.
- **Validation status:** Validated (Likely; F-002).
- **Implemented:** Yes — the gate = session filter + score threshold + execution-planner SL/TP (live spine).
- **Abandoned:** No.
- **Expected profitability impact:** This *is* the edge; ~0 elsewhere in the funnel. Highest-leverage future work = this gate, not new features.

---

## 2. Repeatable market behaviors

### E-04: The post-score SESSION filter is the binding throughput constraint
- **Category:** Repeatable behavior · ties **F-003**
- **Source:** `roi-funnel-diagnosis-bnbusdt-2026-05-30.md:22,36-50`
- **Exact evidence:** funnel RANGE 16,187 → SWEEP 4,816 → DISPLACEMENT 1,103 → EXPANSION 202 →
  RETEST 134 → **EXECUTION 15 (11.2% conv ◄ binding)**. Of 93 `FILTER_REJECTED`: `off_session:OFF_SESSION 44 (47%)`,
  `off_session:ASIA 20 (22%)`, not-discount-zone 16, not-premium-zone 13 → **64/93 (69%) are session rejects**. Score gate NOT binding: `134/135 soft-confs APPROVED` (mean score 0.496, 1 rejected). System traded only 9 of 24 hours.
- **Validation status:** Validated.
- **Implemented:** Yes — the diagnosis directly drove E-01 (session expansion).
- **Abandoned:** No. **Invalidated** the prior plan to sweep detection thresholds (`body_ratio_min`, `atr_multiplier_min`).
- **Expected profitability impact:** Identified the lever worth +15.7pp; redirected effort off a dead end.

### E-05: DISPLACEMENT→EXPANSION is the true detection bottleneck (not EXPANSION→RETEST)
- **Category:** Repeatable behavior · memory `project_phase0_findings`
- **Source:** `project_phase0_findings.md:29-31` (run_20260527_074732, 14,016 candles)
- **Exact evidence:** survival `SWEEP→DISPLACEMENT 25.7% (154/600)`, **`DISPLACEMENT→EXPANSION
  5.2% (8/154)`**, `EXPANSION→RETEST 87.5% (7/8)`, `RETEST→EXECUTION 28.6% (2/7)`. True EXPANSION
  episode count = 8 (prior candle-count hypothesis was ~184 — wrong by 23×).
- **Validation status:** Validated by telemetry; **reversed** the prior `discovery-funnel-analysis.md` hypothesis that EXPANSION→RETEST (3–4%) was the bottleneck.
- **Implemented:** Partially — addressed by SHADOW_PENDING recovery (E-07).
- **Abandoned:** The `retest_depth_max 0.30→0.42` candidate and `soft_conf_max_candles 3→5` candidate were **invalidated** by this data.
- **Expected profitability impact:** Indirect — corrected the funnel model; throughput gains came via E-07 and E-01.

### E-06: HTF transitions dominate state resets
- **Category:** Repeatable behavior
- **Source:** `project_phase0_findings.md:34-36`
- **Exact evidence:** of 2,033 resets — `HTF_CHANGE 98.1% (1,995)`, retrace `1.3% (27)`, zone/session `0.2% (5)`.
- **Validation status:** Validated (telemetry).
- **Implemented:** Yes — motivated HTF-window protection (E-07).
- **Abandoned:** No.
- **Expected profitability impact:** Structural; established that the engine bleeds candidates to HTF resets, recoverable via shadow.

### E-07: SHADOW_PENDING recovers HTF-window-reset displacements
- **Category:** Repeatable behavior / entry-supply · memory `project_phase1_shadow_results`
- **Source:** `project_phase1_shadow_results.md:23-26,40` (run_20260527_082939, 70,080 candles)
- **Exact evidence:** `SHADOW_LEAK=0`, SHADOW_PENDING entries `69`, EXPANSION `93 total (24 normal +
  69 shadow)`, shadow recovery `69/379 HTF resets (18.2%)` capturing `59% of 117 would_expand=true`
  candidates. Trades `14 (vs 2 baseline)`, `WR 71.4% / avgRR +0.49R / PnL +6.83R`. All Phase-1 gates PASS.
- **Validation status:** Validated.
- **Implemented:** Yes — `CRTState.SHADOW_PENDING` + `pending_displacement_ttl_candles=4` in `crt_engine_v2.py`, config `v2_multi_2026_04`.
- **Abandoned:** No — but downstream the shadow *trades* were later gated to advisory-only (E-27) for quality.
- **Expected profitability impact:** Raised trade supply 2→14; the structural unlock that made later throughput work possible.

### E-08: EXPANSION dwell is bimodal with a pathological stale tail
- **Category:** Repeatable behavior / structural risk · memory `project_phase2b_findings`
- **Source:** `project_phase2b_findings.md:35-47` (run_20260527_121953, 70,080 candles)
- **Exact evidence:** `73/93 episodes (78%) resolve in ≤1 candle`; dwell `mean 245.5, median 1,
  p90 81, MAX 20,115`. One episode idx 7,992→28,107 ran **20,115 candles ≈ 209 days** — a stale
  displacement still producing a trade because EXPANSION was HTF-reset-protected with no TTL.
- **Validation status:** Validated (structural correctness bug).
- **Implemented:** Yes — fixed by the EXPANSION TTL guard (E-19).
- **Abandoned:** No.
- **Expected profitability impact:** Correctness, not ROI — removed a class of stale-context trades.

---

## 3. Feature combinations that repeatedly worked

### E-09: candles_since_retest + volatility_ratio are the only durable static features
- **Category:** Feature combination · ties **F-001/F-002**
- **Source:** `edge-attribution-2026-06-03.md:8,22-23` (depth set N=203,588 ETH; 4-instrument cross-check)
- **Exact evidence:** Edge Score ranking — `candles_since_retest 0.4787` (marginal ΔR² 0.0024,
  Exp-spread +0.144R, cross-inst 0.54), `volatility_ratio 0.1005` (marginal ΔR² 0.0004, cross-inst
  0.97), `hour_of_day 0.0009`, then 0.0000 for the rest. Only **5 / 38 features** clear the
  meaningful-effect coverage gate; 33 never move binned expectancy ≥0.05R.
- **Validation status:** Validated as a *negative* result — even the top features are modest (marginal ΔR² ≤ 0.0024).
- **Implemented:** No (advisory ceiling only).
- **Abandoned:** Engineering-saving negative result against the static feature-cluster / Probability-Surface thesis.
- **Expected profitability impact:** Marginal/none as a standalone static map; retest-timing + volatility-context are the only faint signals.

### E-10: candles_since_retest × hour_of_day interaction (regime-conditional)
- **Category:** Feature combination
- **Source:** `edge-attribution-2026-06-03.md:70` (Phase 2 interaction table, cells N≥500)
- **Exact evidence:** best cell `exp +0.093R, PF 1.27, interaction-lift 0.067, temporal-stable True`
  → verdict *regime-conditional*. Top interaction pairs all cap at `PF ≈ 1.22–1.27`, `+0.057–0.093R`.
- **Validation status:** Validated but modest ("regime-conditional," not a standalone edge).
- **Implemented:** No.
- **Abandoned:** Not pursued — magnitude too small to gate on.
- **Expected profitability impact:** Marginal; best-cell PF ≈ 1.25–1.27.

### E-11: Gaussian direction-mirrored calibration model
- **Category:** Feature combination / model · `training.md` + Phase-5 SESSION LOG
- **Source:** `docs/reference/training.md` (correlation gate); SESSION LOG `v4_mirrored`
- **Exact evidence:** short records get 10 directional features negated + 2 pair-swapped;
  Pearson corr `+0.2066` (≥ `MIN_LOO_CORR_FOR_INTEGRATION = 0.10` gate), CV std `0.0072` (< 0.05 gate). Dataset ~242K opportunities, both directions.
- **Validation status:** Validated (passed correlation gate).
- **Implemented:** Yes — active Gaussian scorer (`v4_mirrored`), consumed by `backtest_v2` via `CRTCalibratedScorer.compute(direction=)`.
- **Abandoned:** No.
- **Expected profitability impact:** Calibration-level; corrects short-side scoring (correctness > headline ROI).

---

## 4. Probability cluster findings

### E-12: Feature-region OOS persistence is real across 4/4 instruments (DURABLE)
- **Category:** Probability cluster · ties **F-011**
- **Source:** `feature-region-oos-persistence-2026-06-01.md:30,68-71` (normalized/geometry-driven, temporal 70/30)
- **Exact evidence:** BNBUSDT zones `3: +0.022→+0.033R (retention 1.51)`, `0: +0.042→+0.039R
  (0.93)`, persist_share `1.0`, zero collapses. Generalizes: SOLUSDT `1.96 / 1.36`, ETHUSDT
  `1.46 / 1.27`, BTCUSDT `1.05 / 1.01` — all `2/8 zones gated, persist_share 1.0`. Magnitude grows BNB `+0.02–0.04R` → BTC `+0.08–0.09R`.
- **Validation status:** Durable (F-011; revalidate 2027-06-01). **Methodology caveat:** equal-weight K-Means gave a false collapse — inverse-std (geometry) normalization is authoritative.
- **Implemented:** No — research only; gated behind ReplayMemory schema repair (E-21/F-012).
- **Abandoned:** RESEARCH (Probability-Surface advisory path), not killed.
- **Expected profitability impact:** Marginal (`≤ +0.09R`, ~2–3% TP at 2:1); viable only as a low-weight (0.0-default) additive advisory, never a primary gate.

### E-13: Profitable zones are a thin gradient over a persistently-negative bulk
- **Category:** Probability cluster · ties **F-011**
- **Source:** `feature-region-oos-persistence-2026-06-01.md:31,44-46,77`
- **Exact evidence:** `6/8 zones (~80k samples) persistently negative (−0.018…−0.069R)`; the 2
  profitable zones carry `2× TP rate (2% vs 1%)`. `persist_share=1.0` is *conditioned on train-profitability*, not "the space is profitable."
- **Validation status:** Validated (Durable).
- **Implemented:** No.
- **Abandoned:** No (informs E-12).
- **Expected profitability impact:** Persistence ≠ discrimination — the durable lesson; the gradient is small.

---

## 5. Regime findings

### E-14: Per-candle feature→outcome is at chance (the binding negative result)
- **Category:** Regime / feature · ties **F-001**
- **Source:** `edge-attribution-2026-06-03.md:3,7` ; `phase0-economic-edge-diagnosis-2026-06-03.md:11`
- **Exact evidence:** full multivariate model `AUC(win) 0.5149, R²(rr) 0.0042`; drop-column marginal ΔR² ≈ 0 for all but the top feature. Baseline recomputed per split stays near-chance.
- **Validation status:** Validated (Certain; F-001).
- **Implemented:** N/A (negative result).
- **Abandoned:** Kills the static feature-edge thesis.
- **Expected profitability impact:** None from static features — the result that re-directed funding to process/throughput.

### E-15: VOLATILE_REVERSAL is the best regime by AUC but fails the economic floor
- **Category:** Regime · ties **F-001**
- **Source:** `phase0-economic-edge-diagnosis-2026-06-03.md:19,31,55`
- **Exact evidence:** BNBUSDT `regime:VOLATILE_REVERSAL AUC 0.5731, ΔAUC +0.0505 (stat PASS),
  selected net rr +0.1539R < incumbent +0.328R → ECON FAIL`. Realized best ΔAUC `+0.0505 → est.
  ROI delta +0.707pp`. **(Note:** the BNBUSDT *path* track is the lower `ΔAUC +0.0012`; the two numbers are different tracks, both real.) Relabel AUC `0.60–0.67` proven to be `atr` label-leakage.
- **Validation status:** Validated (Phase-0 gate **FAIL 0/4**).
- **Implemented:** No.
- **Abandoned:** Kills Liquidity/TradeNet/Probability-Surface/BitNet V2 (Funding Ledger).
- **Expected profitability impact:** Best-case intelligence upside `+0.42 → +1.26pp` (ΔAUC 0.03–0.09) — ~12× smaller than the governance/session lever's +15.7pp.

### E-16: Session/edge behavior is instrument-specific (per-instrument doctrine)
- **Category:** Regime · ties **F-009**
- **Source:** `session-sweep-bnbusdt-2026-06-01.md:63-72`
- **Exact evidence:** V3 session expansion — BNBUSDT strongly positive, SOLUSDT flips
  (`PF 0.29→1.17, −2.85%→+2.40%`), ETHUSDT **degrades** (`PF 1.73→1.11, maxDD 3.05%→6.88%`),
  BTCUSDT unprofitable both ways (`PF 0.42→0.86, −4.14%→−2.39%`).
- **Validation status:** Validated (Likely; F-009).
- **Implemented:** Yes — promotion is instrument-scoped (BNBUSDT only); blanket global change rejected.
- **Abandoned:** Global/multi session config abandoned in favor of per-instrument.
- **Expected profitability impact:** Prevents a blanket change that would degrade ETH/BTC; "edge quality on some instruments" is a separate open problem.

---

## 6. Risk findings

### E-17: Concept drift is detected but not acted on
- **Category:** Risk · **F-008**
- **Source:** `src/inout/live_engine_hook.py:676`
- **Exact evidence:** HARD drift (Z>3.0) → logger "Trade signal unreliable"; **trade proceeds with no block / size-down / gate.**
- **Validation status:** Validated (Certain; F-008).
- **Implemented:** Detection only (no mitigation).
- **Abandoned:** No — FUNDED for wiring (governance/execution track).
- **Expected profitability impact:** Live downside protection unrealized; could silently degrade live PnL.

### E-18: Headline ROI is backtest-only; live PnL is UNVERIFIED
- **Category:** Risk · **F-010 (OPEN)**
- **Source:** `economic-edge-gap-analysis-2026-06-03.md` (caveats)
- **Exact evidence:** `ExecutionPlannerV1_2` + `UltronRiskGate` are **live-only, NOT in the backtest spine** that produced `+20.59%`. Recommended next experiment: replay execution-planner SL/TP on rejected RETEST candidates to split selection-vs-SL/TP (also `gate-contribution:29`).
- **Validation status:** Open (Likely; F-010; revalidate 2026-09-01).
- **Implemented:** N/A (gap).
- **Abandoned:** No — RESEARCH (execution-planner replay).
- **Expected profitability impact:** The +20.59% may not replicate live; the single biggest unquantified risk.

### E-19: EXPANSION TTL guard (temporal-causality restoration)
- **Category:** Risk / correctness · memory `project_phase3b_findings`
- **Source:** `project_phase3b_findings.md:21-23,32-38,67-69`
- **Exact evidence:** `max_expansion_age_candles=495` (+ `_hours=124`, warn 342); new `EXPIRED`
  state (`EXPANSION→EXPIRED→RANGE`). On 70,080 candles: `7 EXPANSION_EXPIRED` (all at 496 candles),
  `max_expansion_days 5.17 < 7 ✅`, `would_trade_if_alive=True` for all 7. Trade count `14→37`
  (engine freed from stale episodes); WR `71%→46%`, net `−1.67R` (slippage drag on newly-unlocked lower-quality structure). All integrity gates PASS except pre-existing `approval_rate` (100%, tier_2_threshold below floor).
- **Validation status:** Validated; PROMOTION GATE closed 2026-05-28 (`expired_counterfactual_rr` computed: 6/7 no retest, 1 simulated SL hit rr=−1.0 → TTL correctly cut stale structure).
- **Implemented:** Yes — `crt_engine_v2.py` EXPIRED branch.
- **Abandoned:** No.
- **Expected profitability impact:** Correctness fix; eliminates 209-day stale trades. The raw 14→37 expansion was net-negative, which is *why* selectivity (sessions/shadow-advisory) was retained over raw throughput.

### E-20: Cost drag is material
- **Category:** Risk · `roi-baseline`
- **Source:** `roi-baseline-bnbusdt-2026-05-29.md:40,57`
- **Exact evidence:** raw `+5.91R` → net `+4.92R` = `−0.99R (~17% of gross)` from slippage + spread.
- **Validation status:** Validated.
- **Implemented:** Yes — slippage + spread modeled on in backtest.
- **Abandoned:** No.
- **Expected profitability impact:** ~17% gross haircut; any low-avgRR throughput add (e.g. raw shadow) is disproportionately eroded.

### E-21: config_integrity gate is real but ORPHANED
- **Category:** Risk / governance · **F-006**
- **Source:** `src/governance/config_integrity.py` (only caller = one-off cutover script)
- **Exact evidence:** `validation_summary_is_fresh` / `active_version_is_governed` are real hard checks but enforced at **no** runtime path (backtest_v2 / live_engine_hook / promotion_manager). The deepdeektry bypass was closed by manual check, not an enforced gate.
- **Validation status:** Validated (Certain; F-006).
- **Implemented:** Built, not wired.
- **Abandoned:** No — FUNDED for wiring.
- **Expected profitability impact:** Governance-bypass risk remains until wired.

---

## 7. Entry patterns

### E-22: Edge is timing *inside* a state (RETEST→EXECUTION), not pattern identity
- **Category:** Entry pattern · ties **F-002**
- **Source:** `gate-contribution-bnbusdt-2026-06-03.md:18,23`; CRT 9-state golden path (`event-taxonomy.md`)
- **Exact evidence:** the only edge-CREATING gate is EXECUTION (`+0.584R`); DISPLACEMENT is the only mildly-positive pre-execution stage (`+0.048R`); EXPANSION/RETEST are dead-weight on expectancy. "Selection + execution structure create the edge; timing inside a state beats pattern identity" (F-002 reversal).
- **Validation status:** Validated (Likely).
- **Implemented:** Yes — CRT state machine + session + score selectivity (live spine).
- **Abandoned:** Abandons the "find the magical predictive pattern/state" thesis.
- **Expected profitability impact:** Concentrates all effort on the entry-selection gate.

### E-23: BitNet hard-rejects entries at score < 0.55
- **Category:** Entry pattern (rejection gate) · **F-004**
- **Source:** `src/config_layer/crt_engine_v2.py:1752`; `src/runtime/backtest_v2.py:276`
- **Exact evidence:** `if bitnet_main_score < 0.55: return False, RejectReason.LOW_SCORE`;
  `bitnet_score_at_entry` persisted to TradeRecord. Threshold hardcoded 0.55; `get_bitnet_threshold(regime)` (adaptive) never called.
- **Validation status:** Validated (Certain; F-004) — reverses the prior "BitNet score is dead/unpersisted" claim.
- **Implemented:** Yes (live v1 gate).
- **Abandoned:** Adaptive-threshold layer FROZEN (BitNet V2).
- **Expected profitability impact:** Active filter; v1 contribution baked into current results, adaptive upside unproven.

### E-24: Zone-position filter (discount/premium) gates entry side
- **Category:** Entry pattern
- **Source:** `roi-funnel-diagnosis-bnbusdt-2026-05-30.md:42-43,52`; `project_phase0_findings.md:39-41`
- **Exact evidence:** of 93 filter rejects, `not-in-discount-zone 16 + not-in-premium-zone 13 = 29` (entry on wrong side of range mid). Early telemetry: `3× "Not in discount zone"` of 5 RETEST resets.
- **Validation status:** Validated as a real (secondary) gate; zone-model relaxation was deferred behind Phase-3b promotion.
- **Implemented:** Yes (active filter); the BNBUSDT zone model (`bnb_v1`) wiring remained a deferred research item.
- **Abandoned:** No — secondary to the session lever (E-04).
- **Expected profitability impact:** Smaller than session (29 vs 64 rejects); unquantified for promotion.

---

## 8. Exit patterns

### E-25: Execution-planner structure-based SL/TP is part of the EXECUTION edge
- **Category:** Exit pattern · ties **F-002/F-010**
- **Source:** `gate-contribution-bnbusdt-2026-06-03.md:29` (critical caveat)
- **Exact evidence:** the `+0.58R` EXECUTION jump conflates (a) *which* retest candles are selected (session+score) and (b) the execution-planner's structure-based SL/TP vs the counterfactual's vanilla fixed SL/TP — both part of the execution process. Method cannot separate them.
- **Validation status:** Open — the split is the recommended next experiment (E-18).
- **Implemented:** Yes — `ExecutionPlannerV1_2` (live-only, hence F-010 risk).
- **Abandoned:** No — RESEARCH (selection-vs-SL/TP replay).
- **Expected profitability impact:** Unknown share of the +0.58R; until isolated, the exit contribution is unquantified.

### E-26: Baseline exit definition (tp 2× / sl 1× ATR + 0.5R trail)
- **Category:** Exit pattern (measurement convention)
- **Source:** `feature-region-oos-persistence-2026-06-01.md:4`; `edge-attribution-2026-06-03.md:84`
- **Exact evidence:** scanner outcomes use `tp=2× / sl=1× ATR` with a `0.5R trail`; the caveat notes a different exit definition could move feature ranks.
- **Validation status:** Validated as the consistent measurement basis (not an optimized exit).
- **Implemented:** Yes (scanner / opportunity datasets).
- **Abandoned:** No.
- **Expected profitability impact:** Defines the R-unit; exit *optimization* is unexplored territory.

---

## 9. Position sizing findings

### E-27: Shadow-advisory-only — the system gates on quality (PF/DD), not raw return
- **Category:** Position sizing / governance · memory `project_phase4b_findings`, `phase6e`
- **Source:** `phase6e-shadow-advisory-ab-bnbusdt-2026-06-01.md:19-35`
- **Exact evidence:** control (`shadow_advisory_only=True`): `35 trades, PF 2.5351, WR 65.7%, avgRR
  +0.545, maxDD 3.1%, ret +20.6%`. Treatment (False): `89 trades, PF 1.5249, WR 56.2%, avgRR
  +0.248, maxDD 8.2%, ret +23.7%`. → `PF −40%, maxDD ~2.6×, avgRR halved`; return rises only `+3pp` for 2.5× trades. Phase 4b RE-CONFIRMED at n=89.
- **Validation status:** Validated (re-confirmed under the session-expanded regime).
- **Implemented:** Yes — `shadow_advisory_only=True` in production (shadow trades tracked, EXECUTION blocked).
- **Abandoned:** Raw-throughput shadow execution abandoned under current doctrine (flipping = explicit `goal.md` deviation).
- **Expected profitability impact:** Protects PF 2.54 / maxDD 3.1%; forgoes +3pp raw return for a 40% PF / 2.6× DD penalty avoided.

### E-28: Shadow age-decay (λ) is pure threshold-shifting — cannot select quality
- **Category:** Position sizing · memory `project_phase4b_findings`
- **Source:** `project_phase4b_findings.md:15-33`
- **Exact evidence:** `effective_S = final_S × exp(−λ·age)`; all shadows share age=4. `λ=0.10`: 22
  shadows survive, RR `−0.290` unchanged. `λ=0.20`: 18 cut, survivors' RR **worsens to −0.394**
  (score inversely correlated within shadows — survivors are the worst). `λ=0.35`: 0 shadows (≡
  advisory-only). `shadow_quality_improves = FALSE`; A/B (Variant A/B reparam) parity confirmed.
- **Validation status:** Validated (decay rejected as a quality lever).
- **Implemented:** No (λ left at 0.0; advisory-only chosen instead).
- **Abandoned:** Yes — age-decay sizing abandoned; structural staleness isn't score-filterable.
- **Expected profitability impact:** None positive; confirmed shadows are uniformly stale.

### E-29: shadow_advisory_only delivers a 77% drawdown reduction
- **Category:** Position sizing / risk · memory `project_phase4b_findings`
- **Source:** `project_phase4b_findings.md:74-79`; `project_phase2b_findings.md:50-54`
- **Exact evidence:** normal-only state `maxDD 2.08R vs 9.23R baseline (−77%)`, DD gate `<5R` PASS,
  15 trades / WR 60% / avgRR +0.328. (Phase-2b: shadow vs normal WR both 71%, avgRR 0.554 vs 0.421 — the early "shadow is better" signal was N=7 noise; score-inversion r=−0.07 on N=14.)
- **Validation status:** Validated.
- **Implemented:** Yes.
- **Abandoned:** No.
- **Expected profitability impact:** ~77% DD reduction (9.23R→2.08R) is the single biggest risk-control win in the development line.

---

## 10. Ideas validated by evidence (and the ones evidence killed)

### Validated theses
- **E-30 · F-001 — Intelligence is NOT the binding constraint.** Source `phase0-economic-edge-diagnosis-2026-06-03.md` (FAIL 0/4) + `edge-attribution` (AUC 0.5149). *Validated/Certain.* Killed 4 initiatives; governance/throughput/consumption are the constraints.
- **E-31 · F-002 — The edge is the decision process, not a static feature→outcome map.** Source `gate-contribution-bnbusdt-2026-06-03.md:18`. *Validated/Likely.* Implemented in the live execution-selection gate.
- **E-32 · F-003 — Throughput (N) is the ROI bottleneck; session policy is the proven lever.** Source `session-sweep-bnbusdt-2026-06-01.md:44`. *Validated/Likely.* Implemented (E-01).
- **E-33 · F-007 — Active prod config is the governed `v4_multi_2026_06`.** Source `configs/production/ACTIVE_VERSION`, `promotion_log.jsonl` (PROMOTED 2026-06-02, score 0.6458, supersedes ungoverned deepdeektry). *Validated/Certain.*
- **E-34 · F-005 / F-012 — TradeNet v2, ReplayMemory, CognitiveBus, Cluster, HMF are built-but-unwired sidecars** (zero spine consumption). Source `trade_net_v2.py` + `fusion_engine.py:8`; `intelligence-artifact-evidence-map-2026-06-02.md`. *Validated/Certain.* Risk is rebuilding, not building.

### Ideas tested and abandoned (recovered so they aren't re-run)
- **E-35 — `retest_depth_max 0.30→0.42`** (Phase-1 Candidate 1): **INVALIDATED** — retest depth is not the binding constraint (`project_phase0_findings.md:50,53`).
- **E-36 — EXPANSION→RETEST is the bottleneck** hypothesis: **REVERSED** — it survives at 87.5%; the real gate is DISPLACEMENT→EXPANSION 5.2% (E-05).
- **E-37 — Score inversion is real:** **INVALIDATED** — N=5 noise; `r=−0.07 on N=14` (`project_phase2b_findings.md:14-20`). No score recalibration.
- **E-38 — Sweep detection thresholds (`body_ratio_min`, `atr_multiplier_min`) to raise frequency:** **INVALIDATED** as the frequency lever — early funnel already delivers 134 retests; the binding gate is the session filter (E-04).
- **E-39 — Raise `tier_2_threshold` (0.30→0.55) for selectivity:** **DEFERRED/not adopted** — drops 29% of trades at N=14 (gate requires drop <5%); candidates cluster 0.44–0.63, threshold sits below the floor (`project_phase2b_findings.md:22-32`, `phase4b:85`).

---

## Closing Table A — Funding Ledger (reproduced from `current-findings.md`)

| Initiative | Status | Evidence (findings) | Reopen condition (verbatim gist) |
|---|---|---|---|
| Liquidity V2 | **KILLED** | F-001, F-011 | feature track ΔAUC ≥ +0.03 OOS **and** expectancy lift survives **and** cross-instrument pass |
| TradeNet V2 | **KILLED** | F-001, F-005 | Phase-0 gate clears **and** wiring TradeNet v1 into fusion earns measured weight |
| Probability Surface V2 | **KILLED** | F-001, F-012 | Phase-0 gate clears **and** ReplayMemory path-stats beat static zone features |
| BitNet V2 (adaptive threshold) | **FROZEN** | F-004 | enough `bitnet_score_at_entry` outcomes **and** adaptive beats static 0.55 on net rr |
| Governance/execution wiring (integrity gate + drift→size-down) | **FUNDED** | F-001, F-006, F-008 | — |
| Per-instrument session/throughput sweeps | **FUNDED** | F-003, F-009 | — |
| ReplayMemory → deterministic advisory path | **RESEARCH** | F-012, F-008 | — |
| Execution-planner replay (selection vs SL/TP) | **RESEARCH** | F-010, F-002 | — |

## Closing Table B — Cross-instrument session matrix (from `session-sweep:63-68`)

| Instrument | V0 (`LONDON,NEWYORK,OVERLAP`) | V3 (`+ASIA,+OFF_SESSION`) | Verdict |
|---|---|---|---|
| BNBUSDT | 15 / PF 1.79 / +4.91% | 35 / PF **2.54** / +20.59% | strongly positive → **promoted** |
| SOLUSDT | 6 / PF 0.29 / −2.85% | 29 / PF **1.17** / +2.40% | flips losing → profitable (staged, not promoted) |
| ETHUSDT | 9 / PF 1.73 / +2.22% | 28 / PF **1.11** / +1.37% (maxDD 3.05%→6.88%) | **degrades** — not promoted |
| BTCUSDT | 9 / PF 0.42 / −4.14% | 23 / PF 0.86 / −2.39% | unprofitable both ways — not promoted |

---

## Coverage map (edge → finding / phase)

`F-001` E-09,E-14,E-30 · `F-002` E-03,E-22,E-25,E-31 · `F-003` E-01,E-04,E-32 · `F-004` E-23 ·
`F-005` E-34 · `F-006` E-21 · `F-007` E-33 · `F-008` E-17 · `F-009` E-16 · `F-010` E-18,E-25 ·
`F-011` E-12,E-13 · `F-012` E-12,E-34. Phase memories: P0 E-05,E-06 · P1 E-07 · P2b E-08,E-29,E-37 ·
P3b E-19 · P4b E-27,E-28,E-29 · P6 E-02 · P6b E-04 · P6e E-27.

> **Honest limits of this recovery.** Phase-1–4b figures come from the `run_20260527` development
> line (config `v2_multi_2026_04`); the 35-trade results are the later session-expanded `v4`
> line — do not chain them as one time series. All ROI/PF here is **backtest** (F-010 open).
> Per-candle feature studies use scanner *opportunities*, not executed trades. Where a source said
> "marginal/none," this ledger records that rather than inflating it.
