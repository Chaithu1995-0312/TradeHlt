# Trade Report — S0 Diagnosis (what actually gates `n`)

> **Status:** read-only measurement. **No code, config, or registry changed.** This doc corrects the
> F6 / G1–G6 decision surface with on-disk evidence from the Sep-09 reference artifact, because the
> prior run-spec was built on a premise ("the approval gate suppresses n") that the ledger refutes.
>
> Input artifact (verbatim):
> `logs/dual_construction_f069_remeasure_20260909/scratch_roots/arm_a_v2_baseline/results/run_20260909_182035_XAUUSD/`

---

## 1. Headline verdict

**The approval gate did not suppress `n`. A different, internal stage did.**

The reference run has `n = 3` trades across 47,275 candles. The prior "Path A vs Path B" run-spec
assumed the bottleneck was *approval_rate* suppressed by a `_vol_score ≡ 0` bug in `GateIntelligence`
(`src/core/gate_intelligence.py`). On-disk evidence shows that hypothesis is **false for this run**.

---

## 2. Evidence

### 2.1 The EngineRunner decision gate approved 100% and rejected nothing

`XAUUSD_summary.json` (footed):

| Field | Value |
|---|---|
| `total_setups` | 3 |
| `approved_trades` | 3 |
| `rejected_trades` | **0** |
| `approval_rate` | **1.0** |
| `rejection_reasons` | `{}` (empty) |

The backtest approval path is the optional **EngineRunner fusion/decision gate** —
`src/runtime/backtest_v2.py:2731-2787` (`engine_gate_enabled=true` in the production config it ran
under; e.g. `configs/production/v1_multi_2026_03.json:407`). It approved every candidate that reached
it, and adds to the MetricsEngine counters at `backtest_v2.py:1584-1586`
(`rejected_trades = len(journal.rejections)`), which were zero.

Critically, **`GateIntelligence` is not on this path at all**:
- `backtest_v2.py:2671-2673` (construction trace): *"backtest_v2 does not import
  ExecutionPlannerV1_2 or UltronRiskGate"*.
- `src/core/engine_runner.py` has no `GateIntelligence` / `ExecutionPlanner` reference;
  `EngineRunner.run()` (`engine_runner.py:642`) gates through its fusion/decision pipeline.
- `GateIntelligence.decide()` is referenced only by `src/config_layer/execution_planner.py:252`
  (live planner) and merged into the live hook (`src/runtime/live_engine_hook.py:1006-1009`).

**Consequence:** Option A (`atr_abs = atr × close`) applied to `GateIntelligence._vol_score` /
`_liquidity_score` of the earlier run-spec would alter **live** decision scores but cannot raise
a backtest `approval_rate` that is already 100%. It is a governed live-path behavior change, **not**
an `n` lever for the report.

---

### 2.2 The real choke: soft-confirmation reachability + internal filters

Event lane totals (`XAUUSD_events.jsonl`, 7,110 events):

| Event | n | Meaning |
|---|---|---|
| RESET | 2,887 | HTF-change / session-gap resets (primary funnel) |
| STATE_TRANSITION | 2,382 | CRT state machine advance |
| SWEEP | 1,792 | sweep detection |
| **BEGIN_SOFT_CONF** | **24** | setups that reached soft-confirmation |
| **FILTER_REJECTED** | **19** | rejected at the execution filter stage |
| **CONFIRMATION_FAILED** | **1** | soft confirmation not met within 3 candles |
| TRADE_OPENED | 3 | approved executions |

Funnel: **47,275 candles → 24 soft-confirmed → 19 filtered / 1 timeout → 4 survivors → 3 opened.**

### 2.3 The 19 internal rejections, by reason (verbatim)

| Count | reason | Source filter |
|---|---|---|
| **15** | `off_session:OFF_SESSION` | session-window filter — `src/config_layer/crt_engine_v2.py:3428-3447` |
| **4** | `Against parent-timeframe bias (LONG/SHORT)` | H4 parent-CRT bias gate — `crt_engine_v2.py:3363-3383` |
| **1** | `Soft confirmation not met within 3 candles` | `CONFIRMATION_FAILED` — `crt_engine_v2.py:2057` |

(There is also a discount/premium-zone pair of filters at `crt_engine_v2.py:3350-3359`; none fired in
this run.)

**These rejection reasons never reach the journal's `rejected_trades` counter** — they are internal to
the CRT engine's `process_candle` execution-gate section (`:3350-3447`), so the summary's
`rejected_trades=0` is consistent with `FILTER_REJECTED=19` being the true suppressant.

---

## 3. Corrected implications (replaces G1–G6)

| Prior ask | Prior assumption | Corrected basis |
|---|---|---|
| Path A (widen window / add symbols) | scales bars, linear in n | Still valid as a lever, but **quantitatively too weak**: `trades_per_month` = 0.1853 (`summary.json`), ≈ 1 trade per 5.4 months/symbol. Even 5 symbols × 4.5 yr ≈ **50 trades** — far short of the n≥200 target. |
| Path B (fix `GateIntelligence` Option A) | raises approval_rate → n | **Invalidated.** approval_rate is already 1.0; rejecting 0. Not an n lever. Only relevant as a separate live-path governed change. |
| S1 / S3 (replay gate, before/after) | measure approval delta | Moot for `GateIntelligence`. The measurable `n` delta exists only for the **internal filter stage** (§2.3). |
| Actual `n` lever | — | (a) **CRT soft-confirmation reachability** (only 24/47,275 reached `BEGIN_SOFT_CONF` — the dominant funnel), and (b) **session-window filter** (15 recoverable), and (c) **parent-HTF bias gate** (4). |

### Real run-spec for n≥200 (if pursued)

No window/approval tweak reaches n≥200. Options that could, each a **governed** change (needs
`BUILD_IMPACT_MANIFEST`):

1. **Investigate `BEGIN_SOFT_CONF` frequency first (highest leverage).** 24 per 47k candles is the real
   limiter. Nothing else scales unless this rises. This diagnostic determines whether n≥200 is even
   structurally available from this engine.
2. If soft-confirmation is already near-maximal for the window, widen **session** and/or relax the
   **parent-HTF bias gate** to convert the 15+4 recoverable rejects — but that is a behavior/EPOCH
   change and re-opens regime-drift questions.
3. If none of the above yields a few hundred, **the n≥200 floor is structurally unreachable from the
   CRT-only engine** and the report should either (a) drop to a lower minimum-N (e.g. n≥30,
   unconditional/single-cut only), or (b) wait for a genuinely higher-frequency engine epoch.

---

## 4. Not-a-bug corrections worth noting

- `_vol_score ≡ 0` is **not fixed by code inspection**: `gate_intelligence.py:250-258` returns 0 only
  when `features["atr"] ≤ 0` or bar-range ≤ 0. Whether it is actually 0 in the live path is unproven
  and irrelevant to backtest `n`.
- The prior run-spec's terms "CONTINUATION scores 0.0" / "REVERSAL unreachable" match the CRT/decision
  layer, **not** `GateIntelligence` (whose intents are BREAKOUT/PULLBACK/LIQ_SWEEP/REVERSAL/UNKNOWN;
  REVERSAL returns `1 − |mom|` at `:235-237`). Another sign the "gate" was misidentified.
- **§2.3 count correction (post-publish, from the events-lane verbatim):** `off_session:OFF_SESSION` is
  **15**, not 14. §2.2/§3 figures using "14 recoverable" are updated to **15**; the totals (19
  `FILTER_REJECTED`, 20 internal losses, 24 soft-confirmed) are unchanged.

---

## 5. What this unblocks

- The **report design itself** remains valid and input-ready; it is only waiting on a ≥200-trade
  artifact, which §3 shows is not producible from this engine without a governed pipeline change.
- Recommend: before any further run-spec, run the `BEGIN_SOFT_CONF`-frequency diagnostic (§3.1) to
  decide whether n≥200 is structurally available. That is a measurement, not a code change.
---

## 6. Reachability audit (read-only) — resolution of "sparse firing vs filters"

> **Status:** read-only measurement. No code, config, or registry touched. This section answers the
> S0-new question ("is 24 / 47,275 `BEGIN_SOFT_CONF` the strategy, or its filters?") on the same
> Sep-09 reference artifact. Evidence: `XAUUSD_events.jsonl` (per-setup events + per-attempt `RESET`
> termination reasons) and `XAUUSD_crt_telemetry.jsonl` (`EXPANSION_RETRACE_CHECK` episode outcomes).

### 6.1 Correction notice — the earlier "funnel" was not a funnel

v1 of this section presented `TRANSITION_COUNTER.state_entry_counts` as a per-stage funnel with
"drops / survival %". That was a **category error**. `state_entry_counts` is a tally of transitions
*into* each state; it carries **no setup identity**, and the CRT states are re-entrant (frequent
`reset_to_range`, double-sweeps, retests). The earlier "drops" were differences of unrelated
transition tallies, **not attrition**, and are **withdrawn**. The earlier table's largest-drop claims
(SWEEP→DISPLACEMENT −1,399; EXPANSION→RETEST −83.8%) are **unsupported** and removed.

### 6.2 What is measurable per-setup

Only the confirmation→execution tail is a true per-setup funnel (each soft-conf is one setup; a
rejection terminates it):

**24 `BEGIN_SOFT_CONF` → {19 `FILTER_REJECTED` (off_session 15, parent-bias 4), 1
`CONFIRMATION_FAILED`} → 4 reached EXECUTION → 3 `TRADE_OPENED`.**

Reachability *rate* (a rate, not a stage conversion): **24 / 47,275 candles = 0.05%**.

### 6.3 Per-attempt termination counts (event-level; NOT a nested funnel)

The `RESET` reason histogram records *where attempts die*. These are event counts, not setup
survival, and are labelled as such:

| RESET reason class | n | stage killed |
|---|---|---|
| `HTF changed:` (regime boundary) | **2,467** | aborts the in-flight attempt |
| `50% retrace hit` | **166** | displacement (`state_from=DISPLACEMENT → RANGE`) |
| `off_session_filter` | **15** | downstream session filter |
| `Against parent-timeframe bias` | **4** | downstream parent-HTF gate |
| `Post-resolution reset` | 4 | after a closed trade |
| `Session gap detected:` / `1.618 extension hit` | remainder of 2,887 | regime / geometry |

Expansion-stage episode outcome (`EXPANSION_RETRACE_CHECK`, episode-basis): **148** expansions
entered → **24 ended `retest`**, **124 ended `reset` (RESET_EXTENSION)**.

### 6.4 Reading and decision

- The dominant termination classes are **regime-driven** (`HTF changed` 2,467 + session gaps +
  extensions) and **displacement retrace** (166). None maps to a single configurable filter.
- The only measurable *filter* lever is downstream: `off_session` (15) and parent-bias (4), both
  matching the config the run used (`configs/production/v2_htfcrt_2026_08.json`:
  `allowed_sessions=[london,new_york,overlap]`; `session_windows` LONDON 07–10 / NEWYORK 13–16 / ASIA
  00–03 UTC; `parent_crt.enabled=true`). Downstream rejects match the declared session premise.
- Upstream rarity is **measurement-limited here, not provably intentional**: a true per-setup upstream
  funnel would need setup-id threading not present in `_events.jsonl`/`_crt_telemetry.jsonl` (a code
  change — out of scope for this doc).

**Decision — still accept n≈50, on the corrected basis:** soft-conf is rare (0.05%); downstream
rejects match the declared session premise; no single mis-calibrated lever is identifiable; upstream
is not funnel-decomposable from these artifacts. A corrected N-floor (n≈30–50) supports unconditional
+ single-cut tables with explicit power caveats (`feature_drift` self-flags `insufficient_data (need
30)`). **No behavior change.** n≥200 remains structurally unreachable from the CRT-only engine:
recovering all 15 `off_session` + 4 parent-bias rejects lifts n only 3 → ~22 per symbol / 4.5 yr.

### 6.5 Resolved sign-offs (H1–H4)

| # | Question | Resolution |
|---|---|---|
| H1 | Is the reachability audit the right next step? | **Yes** — run (read-only, §6.1 corrected); resolves "sparse firing vs filters" → **sparse firing** (24/47k = 0.05%), upstream not funnel-decomposable. |
| H2 | If "intentional" — write report on n≈50 or hold? | **Write on n≈50** with power caveats; hold n≥200 as structurally unreachable. |
| H3 | If "symptomatic" — governed-change owner/criterion? | **Not triggered** (no single mis-calibrated lever; downstream matches premise). Any later wider run is a governed session/EPOCH change judged against a ~n22 ceiling. |
| H4 | Is `approval_rate=1.0` a separate queue item? | **Absorb as a note** in this audit output; fusion/calibration observation, not an `n` lever. |
---

## 7. Capital-scale mapping — ₹1,00,000 bank / ₹10,000 per trade

> **Source:** `XAUUSD_trades.csv` (per-trade `pnl_rr_net`, `capital_before`/`capital_after`, `position_size`,
> stop `sl` → pip distance) and `XAUUSD_summary.json` (aggregate R-stats). All `*_rr`/`*_R` metrics are
> per-trade R-multiples net of costs; ₹ value = R-multiple × per-trade risk quantum.

### 7.1 R→₹ map at the backtest's actual frame (R = ₹1,000)

Risk quantum is **₹1,000 per trade** — the frame the reference run actually used, confirmed on
CRT-0001: position 198.61 units × stop distance ₹5.035/unit = ₹1,000.1.

| Trade | `pnl_rr_net` | ₹ at ₹1,000 R | `capital_before → after` |
|---|---|---|---|
| CRT-0001 | −1.0547 | −₹1,055 | ₹1,00,000 → ₹98,945.27 |
| CRT-0002 | −1.2504 | −₹1,250 | ₹98,945.27 → ₹97,708.02 |
| CRT-0003 | +0.6128 | +₹613 | ₹97,708.02 → ₹98,306.80 |
| Total | −1.6923 | **−₹1,692 net** | −₹1,693 net |

Cross-check: `−1.0547 + −1.2504 + 0.6128 = −1.6923 = total_pnl_rr_net` ✓. The per-trade values are row
citations from `trades.csv`, **not** derived from summary aggregates.

### 7.2 Scaled frames (₹ per trade; DD = 2.3052 R; ruin = capital ≤ one more R)

| R per trade | ₹/trade (0.5641 R) | Drawdown ₹ | ~n at ruin | Survives n=50? |
|---|---|---|---|---|
| ₹1,000 (backtest) | −₹564 | ₹2,305 | ~175 | Yes (but −28.2% bank by n=50) |
| ₹1,900 (10× leverage ceiling) | −₹1,072 | ₹4,380 | ~91 | Yes (but −54% bank by n=50) |
| ₹3,851 (20×) | −₹2,172 | ₹8,877 | ~44 | **No — ruins before n≈50** |
| ₹9,627 (50×) | −₹5,431 | ₹22,189 | ~16 | No |

Ruin count: `n_ruin ≈ (1,00,000 − R) / (0.5641 × R)`.

### 7.3 Capital trajectory and feasibility verdict

Observed backtest trajectory (₹ frame), trough after CRT-0002:

| Sequence | Cumulative R | Capital | Note |
|---|---|---|---|
| Start | 0 | ₹1,00,000 | — |
| After CRT-0001 | −1.0547 | ₹98,945.27 | −1.05% |
| After CRT-0002 (trough) | −2.3051 | ₹97,708.02 | −2.29% bank |
| After CRT-0003 | −1.6923 | ₹98,306.80 | −1.69% net |

At the observed **−0.5641 R** expectancy, no feasible risk level is viable on ₹1,00,000:
- **Low R** (₹1,000–₹1,900, i.e. 1–10× leverage): survives to n=50 arithmetic-wise but is 28–54% of the
  bank underwater by then — a long bleed, not sudden ruin.
- **High R** (≥ ₹3,500, ≥ ~18× leverage): ruins **before** n≈50.
- **₹10,000 R** — the proposed frame — is **infeasible**: XAUUSD 503.5-pip stops → ₹5.035/unit →
  ₹10,000 R = 1,986 units = ₹5.19M notional = **52× leverage**, unavailable in retail.

**Verdict:** the ₹10,000 per-trade frame is not achievable on ₹1,00,000 at XAUUSD's stop distances, and
the observed expectancy is not survivable at any feasible risk level — either it bleeds the bank out
slowly or it ruins before n≈50. This is why the report's n≈50 floor (§6.4) carries power caveats.

### 7.4 Footnotes

1. **Backtest frame vs hypothetical frame.** The backtest ran at ₹1,000 risk/trade (1.0% of ₹1,00,000).
   Every ₹ figure quoted at another risk level (§7.2) is an arithmetic rescaling, not backtest-observed.
2. **Leverage constraint.** ₹10,000 risk/trade on ₹1,00,000 at XAUUSD's observed 503-pip stops requires
   52× leverage — infeasible in retail. The feasible ceiling is ~₹1,900/trade at 10×.
3. **n=3 backing.** All figures are point estimates off three trades. `feature_drift` in the summary
   self-flags `insufficient_data (need 30)`. The n≈50 projection is illustrative of scale, not predictive.
4. **Frame mismatch.** The summary's `max_drawdown_pct = 2.29%` and `capital_curve`
   (₹1,00,000 → ₹98,306.80) are the backtest's own pip-based sizing frame (≈ ₹1,000 R). The ₹23,052
   drawdown figure at ₹10,000 R is a different, infeasible frame — do not quote the two as the same number.
5. **Concurrency.** "Up to 10 concurrent opens" (₹1,00,000 ÷ ₹10,000) is a **math identity**, not a risk
   policy. No reasonable risk policy authorizes such exposure on this capital.