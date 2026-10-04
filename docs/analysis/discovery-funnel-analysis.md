# DISCOVERY_FUNNEL_ANALYSIS

Run: `run_20260525_133555` · Instrument: BNBUSDT · Timeframe: M15
Trace source: `trade-discovery-trace.md` · Config: `configs/production/v1_multi_2026_03.json`
Analysis date: 2026-05-27

---

## 1. Funnel Compression — Directly Measured

These values come directly from run artifacts. No inference.

### 1.1 Candle-level state distribution

| Stage | Candle count | % of input |
|---|---:|---:|
| Raw CSV input | 14,016 | 100.0% |
| Feature pipeline output | 13,938 | 99.4% |
| Candles in RANGE state | 6,689 | 48.0% |
| Candles in SWEEP state | 1,095 | 7.9% |
| Candles in DISPLACEMENT state | 184 | 1.3% |
| Candles in EXPANSION state | 6,005 | 43.1% |
| Candles in RETEST state | 7 | 0.05% |
| Candles in EXECUTION state | 6 | 0.04% |
| TRADE_OPENED events | 2 | 0.014% |

> Total accounted: RANGE + SWEEP + DISPLACEMENT + EXPANSION + RETEST + EXECUTION = 13,986.
> Remainder ~48 candles: RESOLUTION state (not emitted in state distribution table).

### 1.2 Confirmed transition chain (from event log, 2 samples only)

Both accepted trades followed this exact timing:

| Step | Duration | Source |
|---|---|---|
| RANGE → SWEEP | 1 candle | TRADE_DISCOVERY_TRACE §3 |
| SWEEP → DISPLACEMENT | 1 candle | ibid |
| DISPLACEMENT → EXPANSION | 1 candle | ibid |
| EXPANSION → RETEST | 1 candle | ibid |
| RETEST → EXECUTION | 1 candle | ibid |
| EXECUTION → RESOLUTION | CRT-0001: 5 candles, CRT-0002: 1 candle | ibid |

### 1.3 HTF change frequency (confirmed)

From HTF ID deltas in event log:
- HTF-001496 to HTF-001591 = 95 HTF periods over ~380 M15 candles → **4.0 M15 candles per HTF period**
- htf_candles_per_range config value: **4** (confirmed)
- HTF changes every **1 hour** on a 15-minute chart

### 1.4 Known reset events in event log (sample)

The event log shows HTF-driven and structural resets in the CRT-0002 window alone:

| Timestamp | Reset reason | Prior state |
|---|---|---|
| 2024-07-27T07:45 | HTF changed | SWEEP |
| 2024-07-27T09:15 | Trade stopped + reset | EXECUTION |
| 2024-07-27T09:30 | HTF changed | RANGE |
| 2024-07-27T09:45 | HTF changed | RANGE |
| 2024-07-27T10:45 | HTF changed before sequence completed | SWEEP |

Total reset count for the full run: **not available in current artifacts** (event log not fully scanned).

---

## 2. Structural Unknowns

The following quantities are **not known** from available artifacts. Any value assigned to them
is a hypothesis until instrumentation is added and a replay is run.

| Unknown | Why it matters | Evidence required |
|---|---|---|
| True EXPANSION episode count | State distribution counts *time in state*, not unique entries. 6,005 EXPANSION candles ≠ 184 expansion events. | Transition counter per event type |
| True DISPLACEMENT episode count | Same issue. 184 DISPLACEMENT candles ≠ 184 displacement events. | Transition counter |
| True SWEEP episode count | Same issue. Includes both converting and expiring sweeps. | Transition counter |
| HTF-interrupted sweep count | Sweeps reset to RANGE by HTF change appear as RANGE candles, not SWEEP candles. Hidden loss. | Reset reason attribution |
| EXPANSION → RETEST failure reason breakdown | Did price never retrace? Did it retrace too deep (ceiling exceeded)? Did it retrace but `max_displacement_strength` blocked it? | Per-expansion outcome log |
| RETEST rejection reason breakdown | Was S < 0.30? Did soft confirmation window expire? News/spread filter? | Per-retest rejection log |
| Session exclusion count | `session: UNKNOWN` in CRT cached features at retest time suggests attribution issue, but true impact on exclusion count is unknown. | Session filter event log |
| Counterfactual acceptance rate | Of the estimated failed expansions (HYPOTHESIS), how many would qualify under a relaxed ceiling? | Replay with instrumented ceiling check |

---

## 3. Bottleneck Ranking

Ranked by *measured evidence*. Confidence level shown.

| Rank | Transition | Measured signal | Confidence | Primary hypothesis |
|---:|---|---|---|---|
| **1** | EXPANSION → RETEST | 6,005 EXPANSION candles vs 7 RETEST candles | **HIGH** | Retest depth ceiling too tight; most expansions never produce a qualifying retrace |
| **2** | SWEEP → DISPLACEMENT | 1,095 SWEEP vs 184 DISPLACEMENT candles | **MEDIUM** | `body_ratio_min=0.65` + `atr_multiplier_min=1.50×ATR` filters many candles; CRT-0001 displacement body_ratio was 0.697 (7% above threshold) |
| **3** | RETEST → EXECUTION | 7 RETEST candles, 2 trades | **MEDIUM** | Some retest episodes failed S-score gate (S < 0.30) or soft conf window expired |
| **4** | HTF sweep interruption | HTF changes every 4 candles; SWEEP/DISPLACEMENT are not HTF-protected | **MEDIUM** | ~25% of sweep detections (position 4 of 4 in HTF window) are reset before displacement can form |
| **5** | Feature pipeline | 78 rows dropped | **HIGH** | Warmup/ATR initialization; negligible, no action needed |

### Hypothesis notation key

- `MEASURED`: value comes directly from run artifacts with no inference
- `HYPOTHESIS`: value is inferred from candle counts or structural reasoning; requires Phase 0 to confirm
- `UNKNOWN`: not derivable from available artifacts

---

## 4. Structure Completion Metrics (to build in Phase 0)

These five metrics must be added as logged output before any threshold is tuned.

### 4.1 Structure Completion Curve

Track at each state transition:

```yaml
per_run_summary:
  stage_entry_counts:
    SWEEP: <int>           # times CRT entered SWEEP state
    DISPLACEMENT: <int>
    EXPANSION: <int>
    RETEST: <int>
    EXECUTION: <int>
  survival_rates:
    sweep_to_displacement: <float>
    displacement_to_expansion: <float>
    expansion_to_retest: <float>
    retest_to_execution: <float>
  avg_duration_candles:
    SWEEP: <float>
    DISPLACEMENT: <float>
    EXPANSION: <float>
    RETEST: <float>
  reset_rate_per_state:
    SWEEP: <float>         # resets from SWEEP / entries to SWEEP
    DISPLACEMENT: <float>
    EXPANSION: <float>
```

Goal: completion stability (high survival rate on late-stage transitions), not raw trade count.

### 4.2 Market Natural Retest Distribution

For every expansion episode, record the *actual* retrace depth (regardless of whether it qualifies),
and log it against the current ceiling:

```yaml
per_expansion_episode:
  episode_id: <str>
  expansion_close: <float>
  max_retrace_depth_abs: <float>       # peak retrace observed before reset/extension
  time_to_max_retrace_candles: <int>
  ceiling_at_time: <float>             # max(retest_depth_max × range, frac × ATR)
  qualified: <bool>                    # depth_abs <= ceiling
  regime: <str>                        # TRENDING | RANGING | VOLATILE
```

From this log, compute:
- `P(retrace_depth | qualified)` vs `P(retrace_depth | not_qualified)`
- Regime-conditional distributions
- Empirical ceiling that would capture 80% / 90% of natural retrace events

This drives threshold proposals from *observed market behavior*, not hand-tuned scalars.

### 4.3 Reset Attribution

For every reset event, record:

```yaml
per_reset:
  candidate_id: <str>
  from_state: <str>
  to_state: <str>
  reason: <str>          # HTF_CHANGE | RETRACE_EXCEEDED | EXTENSION_FIB | TRADE_CLOSE
  state_age_candles: <int>
  would_have_survived: <bool>   # True if from_state in [EXPANSION, RETEST] (already protected)
```

From this log, compute:
- `avoidable_reset_pct`: resets from unprotected states that interrupted in-progress sequences
- HTF-kill rate per sweep-entry position (position 1–4 in 4-candle window)
- Structural reset rate (retrace + extension) vs HTF reset rate

### 4.4 Candidate Lifecycle

The state machine thinks in *states*. The market moves in *candidates*. Track each candidate
from first detection through terminal event:

```yaml
per_candidate:
  candidate_id: <str>           # e.g. "{instrument}-CAND-{sweep_idx}"
  first_seen: <timestamp>
  last_seen: <timestamp>
  entered_states:               # ordered list of states reached
    - SWEEP
    - DISPLACEMENT              # only if reached
    - EXPANSION                 # only if reached
    - RETEST                    # only if reached
    - EXECUTION                 # only if reached
  max_score_seen: <float>       # highest S-score observed across all retest evaluations
  death_reason: <str>           # RESET_HTF | RESET_RETRACE | RESET_EXTENSION | SWEEP_EXPIRED
                                # | DEPTH_CEILING | DISP_STRENGTH | SOFT_CONF_EXPIRED
                                # | SCORE_BELOW_TIER2 | ACCEPTED
  age_candles: <int>            # last_seen_idx - first_seen_idx
```

This is the bridge between state-machine telemetry and market structure. It also feeds the
near-miss registry and eventually the training dataset.

### 4.5 Decision Distance

For every candidate that reached RETEST, record the gap between its peak score and the
acceptance threshold:

```yaml
per_retest_candidate:
  candidate_id: <str>
  score_actual: <float>         # S_score at best evaluation in the soft conf window
  score_threshold: <float>      # tier_2_threshold = 0.30
  decision_distance: <float>    # abs(score_actual - score_threshold)
  accepted: <bool>
  rejection_reason: <str>       # SCORE_BELOW_TIER2 | SOFT_CONF_EXPIRED | NEWS | SPREAD
```

From this log, build a **near-miss registry**:
- `near_miss`: candidates where `accepted=False` and `decision_distance <= 0.05`
- These are the highest-leverage targets for soft threshold tuning
- Near-miss count is the correct denominator for Candidate 4 (soft conf window) and any
  future `tier_2_threshold` relaxation — not total rejected candidates

Example: a candidate with score_actual=0.29 and threshold=0.30 (distance=0.01) is structurally
different from score_actual=0.11 (distance=0.19). Both show as REJECTED but only the first is
a tuning target.

Later: near-miss registry feeds training labels (borderline REJECT examples with known
feature vectors and realized market outcomes).

---

## 5. Parameter Sensitivity

> All values below are **contingent on Phase 0 findings**. Apply only after Structure Completion
> Curve, Reset Attribution, and Candidate Lifecycle logs are measured and confirm the hypothesis.

### 5.1 `retest_depth_max` (PRIMARY LEVER — HYPOTHESIS)

Current: `0.30`
Ceiling formula: `max(retest_depth_max × range_size, retest_atr_depth_fraction × ATR)`

Evidence supporting hypothesis:
- CRT-0001: depth_abs = 0.40, ceiling = 6.80 → passed comfortably (shallow retest)
- CRT-0002: depth_abs = 0.60, ceiling = 4.08 → passed comfortably
- 6,005 EXPANSION candles vs 7 RETEST candles implies most expansions never enter the depth window

What Phase 0 must confirm before tuning:
- Are failed expansions retracing *above* the current ceiling?
- Or are they failing to retrace at all (trend continuation)?
- What is the empirical P90 retrace depth for BNB M15 expansion episodes?

If Phase 0 confirms price retraces but depth exceeds ceiling → increase `retest_depth_max`.
If Phase 0 shows price does not retrace → threshold change does nothing; HTF structure or
regime filter is the real problem.

Candidate value (if confirmed): `0.30 → 0.42` (+40% ceiling).
G's `retest_score = max(0, 1 − depth_abs/ceiling)` provides built-in quality decay for deeper retests.

### 5.2 `retest_atr_depth_fraction` (SECONDARY — HYPOTHESIS)

Current: `0.50`
Candidate (if ATR ceiling is binding in tight ranges): `0.50 → 0.70`

### 5.3 `body_ratio_min` (DISPLACEMENT LEVER — HYPOTHESIS)

Current: `0.65` (production config; code default is 0.70)
CRT-0001 displacement body_ratio: 0.697 (7.2% above threshold; near-miss zone 0.65–0.70)
Candidate: `0.65 → 0.58`
Apply only after Phase 0 confirms displacement episode count is a binding constraint.

### 5.4 `soft_conf_max_candles` (CONFIRMATION WINDOW)

Current: `3`
Candidate: `3 → 5`
Both accepted trades converted on candle 1; S-score decay (λ=0.05) penalizes later candles naturally.
Low risk, low reward. Apply last.

### 5.5 `atr_multiplier_min` (WICK THRESHOLD — HYPOTHESIS)

Current: `1.50×ATR`
Candidate: `1.50 → 1.25×ATR`
Synergistic with 5.3. Measure displacement episode count in Phase 0 before applying.

---

## 6. Top 5 Candidate Thresholds

All candidates are labeled with their Phase 0 dependency.

| Rank | Candidate | Parameters | Phase 0 prerequisite | Confidence in gain |
|---:|---|---|---|---|
| 1 | Retest depth ceiling | `retest_depth_max: 0.30→0.42`, `retest_atr_depth_fraction: 0.50→0.70` | Confirm expansions retrace above current ceiling | **MEDIUM** (hypothesis) |
| 2 | Displacement body ratio | `body_ratio_min: 0.65→0.58` | Confirm displacement episode count (not candle count) is limiting | **MEDIUM** (hypothesis) |
| 3 | Wick threshold | `atr_multiplier_min: 1.50→1.25` | Same as Candidate 2; synergistic | **LOW-MEDIUM** |
| 4 | Soft conf window | `soft_conf_max_candles: 3→5` | Confirm retest episodes fail on window expiry; check near-miss registry | **LOW** |
| 5 | Session attribution fix | Investigate `session: UNKNOWN` at retest cache time | Code-level read of `try_expansion_to_retest()` ~line 737–756 | **UNKNOWN** |

---

## 7. Expected Trade Count Change

**Status: HYPOTHESIS** — all figures are estimates from state-candle count math, not confirmed
episode counts.

**Primary target: maximize structure completion stability while preserving expectancy.**
Trade count increase is a *diagnostic signal*, not the optimization objective.
`2→6 trades` with degraded expectancy is worse than `2 trades` with positive expectancy.

| Scenario | Retest episodes (est.) | RETEST→EXEC rate (est.) | Trades (est.) | EXPANSION→RETEST survival (est.) |
|---|---:|---:|---:|---|
| Baseline (current) | ~6 (HYPOTHESIS) | ~33% | 2 | ~3–4% (HYPOTHESIS) |
| Candidate 1 only | ~15 (HYPOTHESIS) | ~35% | ~5 | ~8–10% (HYPOTHESIS) |
| Candidates 1 + 2 | ~19 (HYPOTHESIS) | ~35% | ~7 | ~10–12% (HYPOTHESIS) |
| Candidates 1 + 2 + 4 | ~19 (HYPOTHESIS) | ~42% | ~8 | ~10–12% (HYPOTHESIS) |

These projections are **not recommendations**. They are target ranges to validate after Phase 0.
If Phase 0 shows expansions are failing to retrace (not exceeding ceiling), all estimates drop
significantly and the path forward changes.

Correct success metrics after any Phase 1 change:
- EXPANSION→RETEST survival rate (Structure Completion Curve §4.1) — must increase
- Realized RR distribution (§8) — must not degrade vs baseline
- Near-miss registry count (Decision Distance §4.5) — should increase if threshold is near-optimal

---

## 8. Expected RR Change

| Candidate | Mechanism | RR change estimate |
|---|---|---|
| 1 (depth ceiling) | Deeper retests → lower retest_score in G → lower S → natural self-correction | −0.1 to −0.2 |
| 2 (body ratio) | Weaker displacement → lower breakout_score → lower G | −0.05 to −0.15 |
| 4 (soft conf window) | Later acceptances, lower G_decay; S still gates | −0.02 to −0.05 |
| Combined 1+2+4 | Net | **−0.15 to −0.35 RR** |

Baseline accepted trades: CRT-0001 hit TP1 (1:1 RR), CRT-0002 stopped (loss). Net portfolio RR
from 2 trades is marginal. A −0.2 RR decrease on newly admitted Tier 2 trades (S ≈ 0.30–0.45)
is tolerable if win rate remains above ~45%. Verify via Structure Completion Curve survival rates,
not raw trade count.

---

## 9. Blast Radius — Files and Functions

### Candidate 1 (depth ceiling) + 3 (wick threshold) — config only

Files:
- `configs/production/v1_multi_2026_03.json` → `crt_engine.retest_depth_max`, `crt_engine.retest_atr_depth_fraction`, `crt_engine.atr_multiplier_min`
- Rehash: `python scripts/maintenance/_compute_hash.py`

Source function (no code change):
- `src/config_layer/crt_engine_v2.py` → `StateMachine.try_expansion_to_retest()` (~lines 675–785)

Secondary effects:
- `ConfigValidator.validate()` reruns per-instrument backtest; fitness score checked against hard gate (`min_fitness_score=0.15`)
- `FeatureMonitor` drift stats update more frequently with more trades

### Candidate 2 (body ratio) — config only

Files:
- `configs/production/v1_multi_2026_03.json` → `crt_engine.body_ratio_min`

Source function (no code change):
- `src/config_layer/crt_engine_v2.py` → `StateMachine.try_sweep_to_displacement()` (~lines 574–621)

Secondary effects:
- Gaussian scorer: `body_mu=0.847`, `body_s2=0.021`. New trades with body_ratio 0.58–0.65 are 3+ sigma from the Gaussian mean → lower Gaussian score → lower fusion score (if fusion pipeline is active)
- Training pipeline: if retraining on new trade data, `body_mu` prior shifts

### Candidate 4 (soft conf window) — config only

Files:
- `configs/production/v1_multi_2026_03.json` → `crt_engine.soft_conf_max_candles`

Source functions (no code change):
- `src/config_layer/crt_engine_v2.py` → `UltronRiskEngine.approve_with_soft_conf()` (~lines 1004–1070)
- `src/config_layer/crt_engine_v2.py` → RETEST candle counter (~line 1646)

Secondary effects: Minimal. RETEST state may last up to 2 more candles per rejected episode.

### Phase 0 instrumentation — new code, no behavior change

Additions to `src/config_layer/crt_engine_v2.py`:
- `StateMachine` class: `_transition_counts` dict; increment on each state entry; emit `TRANSITION_COUNTER` event
- `try_expansion_to_retest()`: log `max_retrace_depth_abs`, `ceiling_at_time`, `qualified` for every expansion check; emit `EXPANSION_RETRACE_CHECK` event
- `ResetLogic.should_reset()`: log `from_state`, `reason`, `state_age_candles`; emit `RESET_ATTRIBUTED` event
- Candidate lifecycle tracker: new `_active_candidate` dict on `StateMachine`; assign ID at SWEEP entry; log full lifecycle at terminal event; emit `CANDIDATE_LIFECYCLE` event
- Decision distance logger: in `approve_with_soft_conf()`, after S-score computation, log `score_actual`, `score_threshold`, `decision_distance`, `rejection_reason`; emit `DECISION_DISTANCE` event

Output: append to `logs/run_{ts}/{instrument}/crt_telemetry.jsonl` (new sidecar, does not pollute `BNBUSDT_events.jsonl`)

---

## 10. Implementation Order

```
Phase 0 — Instrumentation (mandatory before any threshold change)
│
│  Add to src/config_layer/crt_engine_v2.py (no config changes):
│    - TRANSITION_COUNTER events (state entry counts)
│    - EXPANSION_RETRACE_CHECK events (per-expansion depth vs ceiling)
│    - RESET_ATTRIBUTED events (per-reset reason + from_state + age)
│    - CANDIDATE_LIFECYCLE events (per-candidate full lifecycle)
│    - DECISION_DISTANCE events (per-retest score gap)
│
│  Re-run same backtest on same input CSV (no config changes).
│  Inspect crt_telemetry.jsonl to answer:
│    - True EXPANSION episode count (vs HYPOTHESIS)
│    - P(retrace_depth) distribution across all expansion episodes
│    - Avoidable reset % (HTF-kill rate vs structural reset rate)
│    - Near-miss count (candidates where decision_distance <= 0.05)
│
└── Decision gate:
      if P90 retrace depth > current ceiling        → proceed to Phase 1
      if most expansions fail to retrace at all     → investigate regime/HTF structure first
      if near-miss count > 5                        → Candidate 4 becomes higher priority

Phase 1 — Candidate 1 only (retest_depth_max + retest_atr_depth_fraction)
│
│  Config change: retest_depth_max 0.30 → 0.42, retest_atr_depth_fraction 0.50 → 0.70
│  Rehash → validate → re-run.
│  Target: EXPANSION→RETEST survival rate increases; realized RR does not degrade.
│
└── Decision gate:
      if structure completion improves and expectancy holds → stop here
      if trade count still low                              → inspect Phase 0 logs for next blocker

Phase 2 — Adaptive retest (post-Phase 1)
│
│  Replace fixed retest_depth_max with regime-conditional ceiling derived from
│  Phase 0's P(retrace_depth | regime) distribution.
│  Code change: try_expansion_to_retest() + new config keys in crt_engine section.

Phase 3 — Candidate 2 + 3 (body ratio + wick threshold)
│
│  Apply only if Phase 0 displacement episode count confirms SWEEP→DISPLACEMENT is binding.

Phase 4 — Candidate 4 (soft conf window) + Candidate 5 (session attribution)
│
   Low priority. Apply only if Phase 1–3 gains are below target and near-miss registry
   shows soft-conf expiry or session exclusion as a meaningful rejection reason.
```

---

## Appendix: Config keys and source locations

| Config key | Current value | Source function | File |
|---|---|---|---|
| `retest_depth_max` | `0.30` | `try_expansion_to_retest()` | `src/config_layer/crt_engine_v2.py` ~line 690 |
| `retest_atr_depth_fraction` | `0.50` | same | same ~line 691 |
| `body_ratio_min` | `0.65` | `try_sweep_to_displacement()` | same ~line 602 |
| `atr_multiplier_min` | `1.50` | same | same ~line 609 |
| `atr_min_displacement` | `1.20` | same | same ~line 584 |
| `conf_alpha` | `0.70` | `approve_with_soft_conf()` | same ~line 1054 |
| `conf_beta` | `0.30` | same | same |
| `tier_1_threshold` | `0.75` | same | same ~line 1062 |
| `tier_2_threshold` | `0.30` | same | same ~line 1065 |
| `soft_conf_max_candles` | `3` | same | same ~line 1646 |
| `htf_candles_per_range` | `4` | `HTFBuilder` | `src/runtime/backtest_v2.py` ~line 105 |
| `retrace_reset_pct` | `0.50` | `ResetLogic.should_reset()` | `src/config_layer/crt_engine_v2.py` ~line 1408 |
| `extension_reset_fib` | `1.618` | same | same ~line 1414 |
| `max_sweep_age_candles` | `20` | `try_sweep_to_displacement()` | same ~line 590 |
