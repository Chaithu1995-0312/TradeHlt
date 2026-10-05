# Program 12 — Timeframe Ladder (M15 retired; D1 regime → H4 structure → H1 trigger)

| Field | Value |
|---|---|
| Status | **DRAFT — design, not sealed.** Nothing has run. No measurement contract is sealed. |
| Date | 2026-10-05 |
| Ordered by | User (architectural order, 2026-10-05) |
| Authority | Research only. Grants no production authority (CLAUDE.md §6.5). No active-config edit. |
| Active config at drafting | `v2_htfcrt_2026_08` (`configs/production/ACTIVE_VERSION`) |
| Prior on the outcome | Null or INSUFFICIENT is the base case (F-027, F-086, F-097; the order says the same). |

---

## 1. The order, as accepted

- **M15 CRT is retired.** No new M15 runs, tuning or oracle labels. M15 artifacts stay as history.
- **Target stack:** D1 regime → H4 structure → H1 trigger. **Universe:** XAUUSD, BTCUSDT, EURUSD, GBPUSD, USDJPY, AUDUSD, US500, NAS100.
- **Fixed constraints:**
  - Hard stop ≥ 1.5×ATR on every trade.
  - Both directions, gated by D1 regime.
  - Keep the cost model (SEM-015 component, XAUUSD).
  - Keep `intrabar_touch` with SL-first.
  - Entry semantics `resting_order`.
- **Risk targets for later portfolio steps:** 0.5% per trade, max 5 concurrent, max 2% heat, 1–10 day holds.
- **Expectancy target:** +0.2R to +0.4R net.
- **Order of work:** ladder (Step 2) → frequency ladder (Step 3) → short side (Step 4) → universe (Step 5) → resolver drift (Step 6) → exit geometry (Step 7).

This document designs Steps 2–6. It changes none of the decisions above. Where the design needs a choice the order did not make, §12 names a default and the reason.

---

## 2. Evidence in the order — what is verified

The decision to move up does not depend on these numbers. The doc records their status so none of them become evidence by repetition.

| Number in the order | Status | Note |
|---|---|---|
| RETEST rate 0.02% of bars, ~0.5–0.7 trades/month | **RETRACTED** | This came from my 2026-10-05 reply. It was computed from `MC-CTXATTR` `n_units`, which are resolver bar×direction rows (F-069 caveat), not engine transitions. It is not an engine trade rate. Retracted the same day (session log). |
| Median stop 4.76 USD = 1.0 ATR; 48.8% of stops inside 1 ATR; 15.2% inside 0.5 ATR | UNVERIFIED | No source artifact located; data is absent from this clone. |
| Cost / 1-ATR stop 7.3%; 0.347 USD round trip | UNVERIFIED | F-082's measured components are half-spread 0.045, commission 0.040, stop slip 0.090 (n=7). The 0.347 figure does not follow from them by any rule checked here. The cost model stays as-is either way. |
| Oracle ceiling ₹108/month at 0.185 trades/month | UNVERIFIED | No artifact located. |
| Funnel 2,222 bars → 72 sweeps → 13 displacements → 4 expansions → 2 retests → 0 trades per month | UNVERIFIED | Plausible, but not reproduced here. |
| Gold +9.9% (2024) / +64.5% (2025) / +4.9% (2026), short mirror 14.5% hit rate | UNVERIFIED | Direction-of-market claims are reasonable. The short hit rate has no located artifact. |
| H4 1.2×ATR ≈ 20–25 USD on gold | UNVERIFIED | Step 2 measures it (median ATR per TF). |

---

## 3. Prior evidence that bears on this program

- **F-027.** Coarser timeframes (H1/H4) did **not** rescue the directional edge on crypto majors. The toy pool had 0 PROMOTE at H1/H4, and the spine was non-decisive. That run used `forward_walk` (a single-TP object) and 12 bps. This program differs in instrument (XAUUSD), trade object (`multi_tp_walk`, SEM-017), cost (SEM-015/016) and stop floor. It is a legitimate re-measurement, not a repeat, but its prior is F-027's null.
- **F-097.** The M15 CRT engine ledger on XAUUSD is **n = 3** trades over the 2-year corpus.
- **F-086 / F-087.** Every-bar XAUUSD M15 entries average about −0.29R. The exit is not the binding constraint, and cost is set by stop width. A wider stop (H4) lowers cost per R by construction.
- **F-088.** Production's trade object is the 50% TP1 partial with a half-way trail and a runner to TP2 (`multi_tp_walk`). Single-target `forward_walk` results do not describe it.
- **F-110.** Entry chain timing: under `approval_bar_legacy` the trade is priced one bar stale. Under `resting_order` on M15, 16 of 16 filled orders ended within one bar and 0 were confirmed.
- **F-084.** A single-draw random-entry control is too noisy to gate on. Use ≥ 100 seeds.
- **F-089 / F-030 / F-040 / F-043.** The parent-CRT bias gate is decision-neutral on XAUUSD. Volatility-regime level and transition channels carry information that was not monetizable. A D1 "regime" gate must be one pre-registered definition, measured once, not tuned (§9).

---

## 4. Data reality (blocking for Step 2)

- **This clone has no market data.** `data/` holds only `.gitkeep` and `README.md`. The 2-year `data/mt5/XAUUSD_M15.csv` lives on the user's machine. **The ladder must run there**, or the data must be supplied to this environment.
- **Bar counts from the 2-year M15 corpus.** 47,197 M15 bars (F-069) at about 92 bars/day is about 513 trading days. That gives roughly **11.8k H1, 3.0k H4 and 0.5k D1 bars**.
- **Illustrative projection, not a prediction.** The M15 engine produced 3 trades in 2 years (F-097). If per-bar funnel rates were timeframe-invariant, H4 would produce about 3/16 ≈ 0.2 trades over the same span. Rates need not be invariant: wider ATR changes every gate. But no plausible change reaches n ≥ 30.
- **Consequence.** On the 2-year corpus, Step 2's **E[R] verdict is almost certainly INSUFFICIENT** for H4 and D1. The setup-count funnel, ATR, stop/ATR and cost/risk columns are still informative.
- **Recommendation (Step 2a, before Step 2).** Fetch **native** XAUUSD H1/H4/D1 history from MT5 as far back as the broker serves. The available depth is UNVERIFIED. On the overlap window, check the M15→H4 resample against native H4, using the F-080 method (bucket phase, daily-open slot). Run the ladder on the long native series; keep the 2-year resample only as the parity cross-check.

---

## 5. Engine portability audit — what is M15-shaped today

The engine (`crt_engine_v2.CRTEngine.process_candle`) accepts any candle stream. Most knobs are in **bars**, so the pattern keeps the same shape in bars at a higher timeframe. Some knobs are in **minutes or hours**, or are tied to M15 clock hours. Those break or change meaning. Every row below is config (CRTConfig, `backtest`, `setup`), so **no engine code changes are needed**. The ladder runs on a research clone of the config, never the active file.

| Knob (source) | Active value | Meaning at M15 | At H4 if unchanged | Proposed for the ladder |
|---|---|---|---|---|
| `backtest.gap_reset_minutes` (GapDetector: reset if gap > N min) | 120 | Session gaps only | **Every H4 bar (240 min) and every D1 bar is a "gap" → reset to RANGE every bar.** The funnel could never leave RANGE. | Set > 2× bar interval: H1 = 180, H4 = 600, D1 = 3,000 (weekend and holiday gaps still reset). |
| `crt_engine.session_windows` + `allowed_sessions` (inclusive `start <= t <= end` on the bar-open time) | ASIA 00–03, LONDON 07–10, NY 13–16 (broker time) | Filters approval bars by M15 open time | H4 opens at 00, 04, 08, 12, 16, 20. Only 00 (ASIA), 08 (LONDON) and 16 (NY, inclusive end) pass. **Half the H4 slots are rejected by clock position, not by market.** D1 is always "ASIA". Also feeds `score_time` → G. | Session filter off for H4 and D1 (all sessions allowed). Keep it for H1 only if declared. Report `time_score` as a diagnostic. |
| `backtest.htf_candles_per_range` + `htf_clock_basis` | 16, `count` | 16×M15 = 4 h range reset clock | 16×H4 = 64 h (~2.7 days), not aligned to days (F-080: 92 bars/day ≠ k·16 at M15) | `htf_clock_basis: calendar`, rule = next TF up: H1 → H4, H4 → D1, D1 → W1. This makes "D1 → H4" literal: the H4 structure range is the D1 period. |
| `max_expansion_age_hours` | 124 | ≈ 496 M15 bars, same as the bar cap | 124 h = 31 H4 bars. The hour cap binds first. | 0 (off) so the bar caps govern consistently. |
| `max_expansion_age_candles` | 495 | ~5 trading days | ~82 days at H4 | Keep 495 (pattern stated in bars). Report the dwell distribution. |
| `max_sweep_age_candles`, `soft_conf_max_candles`, `pending_displacement_ttl_candles`, `atr_period`, `warmup_candles` | 20, 3, 4, 14, 78 | bar counts | same counts in H4 bars (e.g. ATR14 = 56 h) | Keep (scale-free in bars). |
| `setup.trade_ttl_candles` | None | no time stop | open-ended holds | H4: 60 (≈ 10 days, the order's upper hold). H1: 240. D1: 10. |
| `setup.entry_semantics` | `approval_bar_legacy` | F-110 stale entry | — | `resting_order` (per order). |
| `backtest.engine_gate_enabled` (4-engine fusion veto) | true | Models trained on M15 features | Out of distribution at H4 (models are also schema-stale, F-076) | **false** for the ladder (CRT isolation, F-037 precedent; F-070: it vetoed 0 of 30). Declared, not hidden. |
| `backtest.timeframe` + `timeframe="M15"` literals in `backtest_v2.py` (StrategyOrchestrator and several call sites) | M15 | metadata / orchestrator | Mislabelled metadata at minimum | Audit each literal before the run. Fix only if one affects a decision. |

The stop floor is new behaviour and does not exist in the engine. §6 applies it in the research walker, so no engine change is needed for Steps 2–4.

---

## 6. Step 2 — the ladder script (design)

**File:** `scripts/research/timeframe_ladder.py`. This is a thin CLI and must be SITS-registered the same turn (CLAUDE.md §3.1 1b). It adds no strategy logic.

**Inputs.** Instrument OHLCV per TF (native, or resampled with `research.resample.resample` / `features.parent_candle.ParentCandleBuilder`). The research config clone from §5. TF ∈ {H1, H4, D1}.

**Pipeline per TF:**
1. Run `BacktestRunner` on the TF series with the research config. Collect `events.jsonl`: state transitions, `TRADE_OPENED` and rejections.
2. For each opened trade, take entry = retest close (`resting_order`), structural SL (`displacement` anchor ± `sl_atr_buffer`·ATR), and direction.
3. **Stop floor.** If |entry − SL| < 1.5×ATR (ATR = the engine's `atr_abs` on the entry bar), move SL to entry ∓ 1.5×ATR. Recompute TP1/TP2 from the new risk with the configured multipliers.
4. **Re-walk** every trade with `research.oracle.multi_tp_walk` (SEM-017; 50% at TP1, half-way trail, runner to TP2). Use `tie_break="production"` (SL-first), SEM-015 component cost and SEM-016 adverse stop fill. The trade TTL closes at bar close.
5. **Arms.** The primary arm is the floored stop (the order's constraint). The diagnostic arm is the as-built structural stop, reported but never used for a verdict.
6. **Controls,** matched on direction, entry count, holding length and R geometry:
   - **Passive drift:** long-only and short-only from the same entry timestamps over the same holding windows. This is the "beta, not edge" test.
   - **Random entry:** 100 seeds; uniform entry bars within the same instrument and TF, same direction mix and geometry. Report the percentile of the CRT result in the 100-seed distribution (F-084).

**Metrics per TF (one row each):**
- median ATR (price units);
- median stop distance in ATR, as-built and floored;
- % of stops floored;
- cost as % of a 1.5×ATR stop;
- counts of SWEEP, DISPLACEMENT, EXPANSION, RETEST and TRADE;
- trades per month;
- E[R] gross and net with bootstrap 95% CI;
- E[R] net minus passive drift;
- random-entry percentile;
- LONG and SHORT split of every outcome row;
- holding-time distribution.

**Power rule (pre-registered).** n < 30 trades in a TF → verdict **INSUFFICIENT**: counts are reported, and no expectancy claim in either direction.

**Verdict per TF.** **CONTINUE** to Step 3 requires all three of the following:
- (a) n ≥ 30;
- (b) the CI lower bound of E[R] net minus passive drift is > 0;
- (c) the result sits above the 95th percentile of the random-entry distribution.

Otherwise **STOP**, with the failing condition named. A single TF passing is enough to continue on that TF only.

**What this cannot claim.** No economic or production claim (no G001). `economic_claims_allowed` stays false: the mt00/mt01 trust probes remain unrun repo-wide.

---

## 7. Step 3 — frequency ladder (redesigned; runs only on a TF that passed Step 2)

The order's version ("current gate → 2% → 5% → 10% of bars") needs three fixes before it is measurable:

1. **Name the gate.** Loosen only the **binding** gate, the one with the largest drop-off in Step 2's funnel. Loosen it by quantile of its own statistic (e.g. `atr_min_displacement` set to the q-quantile of observed displacement-bar `|close−open|/ATR`). Pick the four levels so trades/month hit about 1×, 2×, 4× and 8× the Step-2 count. "% of bars" is ambiguous: at 10% of H4 bars as entries the ladder becomes every-bar sampling, which F-086 measured at about −0.29R on M15.
2. **Compare totals with uncertainty, not point estimates.** The kill rule uses **net R per month** (n × E[R]) with its CI lower bound. A looser level "wins" only if its lower bound exceeds the current gate's lower bound. The "+0.58R current gate" in the order is UNVERIFIED and is not used.
3. **Multiplicity.** Four levels → Holm correction on the per-level tests. Expectancy must be non-increasing as the gate loosens (F-015: relaxation was not quality-preserving). A non-monotone curve is reported as unstable, not chosen from.

---

## 8. Step 4 — direction

The engine already trades both directions (sweep side sets direction). Step 4 is therefore a **split of Step 2/3 outputs**, not new code.

- **Comparison.** Each side is compared with its own passive drift.
- **Sample limit.** On a 2-year gold bull run, the SHORT sample will be small. A SHORT verdict needs the same n ≥ 30. Below that, "long-only gold beta" cannot be concluded from E[R]; it stays INSUFFICIENT.
- **Order's rule, kept.** If LONG passes and SHORT fails with adequate n, declare the system long-only and size it as a directional bet.

---

## 9. D1 regime gate — open design (not part of Steps 2–4)

No D1 regime classifier exists for this purpose. The existing pieces are `RegimeLabeler` (volatility terciles; F-030/F-043 non-consumable), `parent_crt` with `timeframe: D1` (a CRT bias, F-089 neutral) and `htf_state`. Any new definition is a new hypothesis.

- **Proposed default:** a single pre-registered rule: D1 close vs EMA(50) of D1 closes, with the sign of its 10-day slope. LONG is allowed when both are up, SHORT when both are down; otherwise no trade.
- **How it is measured:** once, as its own step after Step 4, with the same verdict rule and no tuning.

---

## 10. Step 5 — universe expansion (prerequisites)

"Re-run the same ladder per instrument" needs inputs that do not exist yet:

- **Data.** H1/H4/D1 history for 7 more instruments. FX majors were fetched as 2-year M15 for F-035. Binance crypto exists for the majors. **US500 and NAS100: no data located.**
- **Cost profiles.** Only XAUUSD has a measured component model (SEM-015, F-082). FX and crypto profiles are DRAFT (flat 12 bps was 11× too punitive on XAUUSD and cost-dominated on FX, F-035). Indices have none. Each instrument needs a calibrated cost before its E[R] means anything.
- **Breadth is smaller than 8.** XAUUSD, EURUSD, GBPUSD and AUDUSD share the USD factor. US500 and NAS100 are highly correlated with each other. The portfolio step must measure realized correlation of trade outcomes, not assume independence.
- **Risk arithmetic conflict.** 0.5% × 5 concurrent = 2.5%, which exceeds the 2% heat cap. The heat cap binds at 4 full-size positions. Decide which rule wins (default in §12). The active config's live `risk_percent` is 1.0 (user decision 2026-10-01, F-111). Changing it is an active-config edit, gated separately, and not needed before Step 5.

---

## 11. Step 6 — resolver HTF window drift (traced 2026-10-05)

**What the trace found (from source):**
- `backtest.htf_candles_per_range` was **4** in `v2_multi_2026_04` from 2026-04-30 and became **16** on 2026-09-09 (commit `63562ab`). `v2_htfcrt_2026_08` also has 16.
- The committed parity reports `reports/crt_state_confusion_matrix.md` (2026-08-12) and `reports/parity_iter0_baseline.md` record **`window=4`**. That was correct for the config at the time.
- F-069's re-measurement (68.69%, `results/decision_atlas_full`) is dated **2026-09-10**, one day after the 4→16 change.
- **Callers that pass the active backtest value (16):** `run_crt_state_on_mt5_xauusd.py`, `src/charts/resolver_overlay.py`, `src/research/rc003_distinct_object/driver.py`.
- **Callers that fall back to the resolver YAML (4):** `crt_state_confusion_matrix.py` (the F-069 instrument, unless `--htf-candles-per-range` is given), `crt_resolver_economic_comparison.py`, `link001_choch_measurement.py`, `retest_divergence_probe.py`, `crt_range_rebuild_probe.py`.
- **Inside the resolver**, `seed_ohlc` / `finalize_seed_range` cut the seed range on `lifecycle.htf_candles_per_range` (4) even when the caller supplies 16-bar `htf_id`s. The engine seeds from the 16-bar HTFBuilder window. This affects the initial range only; later HTF resets rebuild from `range_atr_period` (14) on both sides.

**Status.** The 4→16 change on 2026-09-09 is a **candidate** explanation for part of the 88.16% → 68.69% move. The timing matches, but it is not measured.

**Fix (≈30 min, separate turn):**
- Make the resolver read `backtest.htf_candles_per_range` from the production config, the same "read, don't copy" pattern as `crtconfig_read`, instead of the YAML literal.
- Make the five scripts stop defaulting to 4.
- Fix the stale `build_htf_id_timeline` docstring ("prod default 4").
- Re-run the F-069 confusion matrix once at 16 and record the delta in the F-069 Note.

**Scope note.** Step 6 is an **M15** measurement. Under Step 1 it closes a record; it does not feed Program 12's H4 work. It can run in parallel with Step 2 and does not block it.

---

## 12. Defaults set where the order was silent

| Decision | Default | Reason |
|---|---|---|
| HTF clock at H4 | Calendar D1 (`htf_clock_basis: calendar`) | Matches "D1 → H4" literally. The order's "16" applies to the M15 resolver fix (Step 6); 16×H4 = 64 h has no market meaning. |
| Session filter at H4/D1 | Off | M15 clock windows reject half the H4 slots by position (§5). |
| Gap reset | > 2× bar interval | Otherwise every H4/D1 bar resets (§5). |
| Fusion gate | Off | M15-trained, schema-stale models out of distribution; F-070 vetoed 0 of 30. |
| Stop floor implementation | Research walker (widen to 1.5×ATR, recompute TPs) | No engine change for Steps 2–4. An engine key comes later, behind strict config. |
| Heat vs concurrency conflict | 2% heat wins (max 4 at 0.5%) | Heat is the risk constraint; the count is a proxy for it. |
| Data | Native long H4/H1/D1 history first | The 2-year corpus cannot reach n ≥ 30 at H4 (§4). |
| Verdict thresholds | n ≥ 30; CI lower bound vs drift > 0; > 95th percentile random | Repo-standard power floor; F-084 control lesson. |

---

## 13. Governance checklist before any run

- [ ] Seal a measurement contract (`MC-*` instance, id assigned at sealing) with §6 metrics, controls, verdict rule and §12 defaults. No result is read before sealing (F-083).
- [ ] Research config clone written and its diff vs active recorded. The active config is untouched.
- [ ] `scripts/research/timeframe_ladder.py` SITS-registered. Green floor run.
- [ ] Data path, row count, first/last timestamp echoed at run start (CLAUDE.md §1.5 preflight).
- [ ] Results go to `docs/current-findings.md` the same turn (new F-id), with INSUFFICIENT stated as such.
