# BNBUSDT M15 Process Analysis

> **Date:** 2026-06-11
> **Purpose:** Answer "What kind of process is BNBUSDT M15 actually?" using all available project forensics.
> **Source data:** `results/research/bnbusdt_forensics.json`, `results/research/bnbusdt_conditional_edge.json`,
> `results/research/qualification/qualification_report.json`, `docs/analysis/bnbusdt-forensics-2026-06-10.md`,
> `docs/analysis/bnbusdt-conditional-edge-2026-06-10.md`
> **Method:** Manual reconstruction. No strategy search. No optimization.

---

# 1. Trend persistence

## Observation

Two direct measurements of continuation behavior exist:

**Expansion breakout** (entry after ATR expansion, bet on continuation):
- Continuation probability: **47.8%** (qualification report)
- Gross expectancy: **−0.002R** (forensics)
- Net expectancy: **−0.439R** (forensics)

**Mean reversion** (entry after stretch from MA, bet on reversal):
- Continuation probability: **54%** (this is actually reversal probability since the hypothesis bets against the stretch)
- Gross expectancy: **+0.008R** (forensics)
- Net expectancy: **−0.409R** (forensics)

**Loss structure:**
- Expansion: 90.4% of R lost is `plain_stop_loss` — the entry was simply wrong
- Mean reversion: 89.5% of R lost is `plain_stop_loss`
- Max consecutive losses: 22 (expansion), 53 (mean_reversion)
- Win clusters are short (max 9/19)

## Inference

**Trends are not self-reinforcing.** After expansion, continuation is statistically indistinguishable from a coin flip. The market does not exhibit persistent directional memory. Loss clustering is extreme — far beyond what a real (even weak) edge would produce — consistent with a zero-drift process.

## Caveat

These measurements test only *one specific definition of trend* (post-expansion continuation with 1:2 SL:TP geometry). Multi-bar trend definitions (e.g., 3-bar momentum with state-dependent sizing) have **not** been tested. A negative result on this specific hypothesis does not prove no trend behavior exists — but the magnitude of evidence (gross≈0) is strong.

## Evidence supporting
- Both hypotheses produce gross E[R] ≈ 0
- Control comparison shows random entries produce identical statistics
- Conditional audit finds no pocket where trend beats random

## Evidence against
- Occasional strong trends clearly occur in price history
- Duration > 13 bars shows positive expectancy (but small n, not significant)

## Confidence: **High**

---

# 2. Mean reversion

## Observation

The mean reversion hypothesis (entry when price stretches away from a moving average, betting on reversion) is the **opposite** of the trend hypothesis. Both produce the same result: gross E[R] ≈ 0.

Specific measures:
- E[R] gross: +0.008R (marginally positive — but not significantly different from zero)
- E[R] net: −0.409R
- Win rate: 33.7% (at 1:2 SL:TP, break-even win rate is 33.3%)

**Conditional audit:** No month, hour, day, ATR quartile, or direction pocket shows significant mean reversion edge.

## Inference

**Distance from equilibrium alone does not predict reversion.** BNB does not strongly pull back toward a moving average in a way that produces tradeable edge. The price stretches that occur are as likely to continue as to revert.

## Caveat

Only one MA length was tested (likely 20-period SMA based on the code). Multi-timeframe mean reversion, volatility-adjusted distance, or state-dependent thresholds have **not** been tested.

## Evidence supporting
- Both continuation and reversal hypotheses produce identical (zero) gross edge
- This is the classic signature of a random directional process

## Evidence against
- Local reversals clearly exist in raw price data
- Not all mean reversion definitions were tested

## Confidence: **High**

---

# 3. Memory half-life

## Observation

**⚠ NOT DIRECTLY MEASURED.** This is the largest measurement gap.

No return autocorrelation matrix exists in the project:

```
corr(r_t, r_t+1)   ← NOT computed
corr(r_t, r_t+2)   ← NOT computed
...
corr(r_t, r_t+50)  ← NOT computed
```

**Indirect evidence only:**
1. Gross directional E[R] ≈ 0 across 12,666+ trades implies autocorrelation at the decision-relevant horizon is very weak
2. Control-random entries produce identical opportunity profiles — meaning the directional information at the entry point is zero
3. M4 pooled p-values: expansion p=1.0, mean_reversion p=0.0005 (but p=0.29 on BNB alone)

## Inference

Memory half-life is **unknown but likely short** (< 5-10 bars). The evidence is consistent with rapid decay of directional information, but this is inference, not measurement.

## What would answer this

```python
# Compute directly from OHLCV:
r_t = log(close_t / close_t-1)
for lag in 1..50:
    autocorr[lag] = corr(r_t, r_t+lag)
    
# Half-life = first lag where autocorrelation crosses zero or falls below 1/e
```

## Confidence: **Moderate** (limited by indirect evidence only)

---

# 4. Volatility clustering

## Observation

Measured indirectly through Layer-2 opportunity profiling (forensics §6-7).

**Key finding — controls are definitive:**
Even SL losers reach +1R ~70% of the time within 40 bars. But random entries produce the **identical** statistic:

| Metric | expansion_breakout | mean_reversion | always_long (control) | random_uniform (control) |
|---|---|---|---|---|
| reach 1R | 69.4% | 71.4% | 69.5% | 69.5% |
| reach 1.5R | 56.6% | 57.0% | 55.5% | 55.7% |
| reach 2R | 45.2% | 43.6% | 43.1% | 43.6% |
| favorable_first | 25.1% | 27.4% | 24.9% | 25.0% |

**Interpretation:** The "70% reach +1R" is NOT entry timing. It is **BNB's natural volatility** — the market generates large swings in 40 bars regardless of where you enter. This is a volatility process, not a directional process.

**Additional indirect evidence:**
- Damage by ATR percentile: across all quartiles, expansion E[R] is similar (−0.09 to −0.05 R/trade by damage measure, which measures cost-only damage)
- MFE P50: 1.78R (expansion), 1.74R (mean_reversion), 1.71R (always_long), 1.73R (random)
- MFE P90: 8-12R (very extreme swings)

## Inference

**Volatility is strongly persistent.** BNB produces:
- Large swings regardless of entry point
- Symmetric upside and downside excursions
- Clustered excursions over 40-bar horizons

The market remembers *volatility state* much more than it remembers *direction*.

## Caveat

ATR autocorrelation `corr(ATR_t, ATR_t+lag)` was **not directly measured**. Persistence is inferred from the opportunity profile controls, which is valid but would benefit from direct measurement.

## Evidence supporting
- Control comparison is decisive: hypotheses are statistically indistinguishable from random on every opportunity metric
- Even losers eventually experience large favorable swings — this is volatility, not direction

## Evidence against
- None strong

## Confidence: **Very high**

---

# 5. Directional asymmetry

## Observation

Direct measurement from conditional audit:

**Expansion breakout:**
- Long delta_E: −0.0234R, p_raw=0.216, bh_q=0.569 — NOT significant
- Short delta_E: −0.0244R, p_raw=0.234, bh_q=0.586 — NOT significant

**Mean reversion:**
- Long delta_E: +0.0144R, p_raw=0.331, bh_q=0.672 — NOT significant
- Short delta_E: −0.0028R, p_raw=0.884, bh_q=0.979 — NOT significant

Neither direction shows any advantage over random for either hypothesis.

## Inference

**Upside and downside are structurally symmetric.** BNB M15 does not have a directional bias on this timeframe. Bullish and bearish moves are statistically similar in their continuation/reversal properties.

## Confidence: **High**

---

# 6. Regime behavior

## Observation

130 conditional tests across:
- Direction (2)
- ATR quartile (4)
- Hour (24)
- Day of week (7)
- Month (25)
- Trend proxy (3)

**Zero survivors** after Benjamini-Hochberg correction.

However, there were suggestive raw p-values that dissolved:

| behavior | bucket | ΔE | p_raw | bh_q | verdict |
|---|---|---|---|---|---|
| mean_reversion | month 2026-03 | **+0.186R** | **0.001** | 0.130 | dissolved |
| mean_reversion | month 2025-04 | +0.160R | 0.004 | 0.182 | dissolved |
| expansion_breakout | hour 14 | −0.177R | 0.007 | 0.182 | dissolved |
| mean_reversion | hour 15 | −0.134R | 0.006 | 0.182 | dissolved |
| expansion_breakout | month 2026-03 | −0.162R | 0.014 | 0.298 | dissolved |

**Key structural finding:** The same month (2026-03) shows mean_reversion +0.186R and expansion_breakout −0.162R. Opposite behaviors "winning" the same month is the signature of **regime variance, not edge**.

## Inference

**Regimes exist but are noisy and unstable.** BNB alternates between different volatility/trending states, but:
1. Regimes are temporary (monthly, not structural)
2. Transitions are unpredictable from available features
3. No conditional state survives multiple-comparison correction
4. Regimes appear to be **volatility regimes, not directional regimes** — they affect the magnitude of swings, not the predictable direction

## Caveat

No formal Markov regime transition matrix was computed. States were defined as a trend_proxy (up/flat/down based on SMA slope) — a richer state definition (e.g., compression vs expansion) was not tested.

## Evidence supporting
- BH correction eliminates all apparent regime pockets
- Mixed-sign deltas in the same month confirm regime noise

## Evidence against
- Temporary regimes clearly exist in price action
- Could be extracted with a different state definition

## Confidence: **Moderate-high**

---

# 7. Entropy / uncertainty

## Observation

**Conditional (given state) expectancy is statistically indistinguishable from unconditional (random entry) expectancy.**

Evidence chain:
1. Both hypotheses: gross E[R] ≈ 0
2. Controls: random entries produce identical results
3. Conditional audit: 130 tests, zero BH survivors
4. Opportunity profile: hypotheses indistinguishable from random on every metric
5. M4 permutation test: expansion p=1.0, mean_reversion p=0.29 on BNB alone

**The information ratio of available conditioning variables is near zero.** Knowing the direction, volatility quartile, hour, day, month, or trend regime does not improve your ability to predict next-bar direction above random.

## Inference

**Entropy is high.** Conditioning on the tested features barely reduces uncertainty. BNB M15 is surprisingly close to a random directional process — on the timeframe and features tested.

## Caveat

This conclusion is limited to:
- 1:2 SL:TP geometry
- Tested conditioning variables (direction, ATR Q, hour, day, month, trend)
- Tested behaviors (expansion continuation, MA reversion)

Nonlinear conditioning (e.g., mutual information, neural embeddings, multi-bar patterns) has NOT been tested and could reveal structure invisible to linear/simple tests.

## Evidence supporting
- Overwhelming: 130 tests, 0 survivors, controls match hypotheses

## Evidence against
- M4 pooled across 11 instruments: mean_reversion p=0.0005 (directional information exists somewhere)
- BNB alone: p=0.29 (suggestive but not significant)

## Confidence: **Very high** — for the testable space

---

# 8. Opportunity structure

## Observation

Measured directly in Layer-2 (forensics §6):

**BNB naturally generates large excursions at a rate that is unrelated to entry timing:**

| Metric | Any entry | Interpretation |
|---|---|---|
| 40-bar reach +1R | ~70% | 70% of 40-bar windows contain a +1R swing |
| 40-bar reach +1.5R | ~56% | 56% contain +1.5R |
| 40-bar reach +2R | ~44% | 44% contain +2R |
| MFE P50 | ~1.73R | Median best excursion at 40 bars |
| MFE P90 | 8-12R | 90th percentile — extreme swings |
| favorable_first | ~25% | In 75% of cases, adverse comes before favorable |

**Critical insight:** The 70% reach +1R looks like an opportunity, but favorable_first is only 25% — meaning price goes against you first. The market gives you the excursion, but only after it has stopped you out.

## Inference

BNB naturally generates:
- **Large excursions: Yes.** Very large (MFE P90 = 8-12R).
- **Symmetric excursions: Yes.** Upside and downside are similar.
- **Clustered excursions: Yes.** Over 40-bar windows, excursions cluster.
- **Entry-timable excursions: No.** Random entries get the same excursions as timed entries.

The market supplies **volatility opportunity** but not **directional opportunity**.

## Confidence: **Very high**

---

# 9. Time structure

## Observation

Hour, day-of-week, and month effects were tested with multiple-comparison correction.

**Hour effects:** No hour survived BH correction. Best raw p-values:
- Hour 14: p_raw=0.007 (BH dissolved to q=0.182)
- Hour 9: p_raw=0.055
- Hour 12: p_raw=0.083
- Hour 1: p_raw=0.081

**Day-of-week effects:** No day survived. Best: Wednesday at p_raw=0.055 (BH q=0.298).

**Monthly effects:** The raw p-values looked promising (2026-03 at p=0.001) but dissolved to BH q=0.130.

## Inference

**No persistent time-of-day, day-of-week, or monthly effect was demonstrated.** The apparent patterns are consistent with multiple-comparison noise.

## Caveat

This does not prove no time structure exists — only that none of the 56+ time-based tests survived correction. A dedicated study with:
- Fewer comparisons
- Out-of-sample validation
- Economic significance thresholds

might find structure. But the current evidence says it's noise.

## Confidence: **High**

---

# 10. Adversarial falsification

## Observation

Multiple layers attempted to break these conclusions:

| Layer | Method | Result |
|---|---|---|
| M4 qualification gate | 11-instrument pooled test with permutation | Both hypotheses REJECTED |
| Forensic decompositions | Gross edge, cost drag, loss mechanisms | Gross E[R] ≈ 0; cost is the swing factor |
| Layer-2 opportunity + controls | Exit-agnostic excursion measured vs random | Hypotheses = random on all metrics |
| Adversarial JSONL audit | Net-expectancy permutation on BNB alone | p=0.96 (expansion), p=0.29 (mean_reversion) |
| Conditional pocket search | 130 tests, BH-corrected, economic floor | Zero survivors |
| Intrabar counterfactual | close-only vs intrabar | Optimistic bound still decisively negative |

**All layers converge on the same answer.**

## Self-correction during the process

The initial Layer-2 interpretation ("opportunity exists but exits squander it") was a narrative fallacy. The control comparison corrected this: the opportunity profile measures BNB volatility, not entry information. World A (entries carry no information) stands.

## Confidence: **Very high** — the measurement survived its own adversarial challenge

---

# Unknowns (gaps that would sharpen the picture)

These are measurements that DO NOT exist in the project and would materially improve confidence:

## 1. Return autocorrelation (PRIORITY)
```
corr(r_t, r_t+1) through corr(r_t, r_t+50)
r_t = log(close_t / close_t-1)
```
Would directly measure memory half-life. Currently inferred from indirect evidence.

## 2. ATR autocorrelation (PRIORITY)
```
corr(ATR(14)_t, ATR(14)_t+1) through ATR_t+50
```
Would directly measure volatility persistence. Currently inferred from opportunity profile controls.

## 3. Sign persistence matrix
```
P(+|+), P(-|-), P(+|-), P(-|+)
Streak distributions for 1,2,3,4,5,6+
```
Would directly measure trend persistence. Currently inferred from win/loss clusters which are confounded with SL/TP geometry.

## 4. Markov regime transition matrix
```
States: Compression-Up, Compression-Down, Normal-Up, Normal-Down, Expansion-Up, Expansion-Down
P(state_j | state_i) for all i,j
```
Would reveal process structure: Are trends self-reinforcing? Does compression predict expansion?

## 5. Hurst exponent / Variance ratio
```
H (returns)
H (price)
VR(2), VR(4), VR(8), VR(16), VR(32), VR(64)
```
Would formally classify: trending (<0.5), random walk (=0.5), mean-reverting (>0.5).

## 6. Mutual information
```
I(r_t; sign(r_t+1))
I(ATR_t; sign(r_t+1))
I(body_ratio; sign(r_t+1))
I(dist_from_SMA20; sign(r_t+1))
```
Would measure nonlinear predictability missed by linear autocorrelation.

---

# Final answer

## Observation

BNBUSDT M15 exhibits:

| Property | Finding | Confidence |
|---|---|---|
| **Trend persistence** | Zero gross edge. Continuation ≈ coin flip. | High |
| **Mean reversion** | Zero gross edge. Reversion ≈ coin flip. | High |
| **Memory half-life** | Unknown, but short (< 10 bars inferred) | Moderate |
| **Volatility clustering** | Strongly persistent. Process generates large swings independent of entry. | Very high |
| **Directional asymmetry** | None detected. Long/short ≈ symmetric. | High |
| **Regime behavior** | Temporary regimes exist but are noisy, unstable, and not exploitable with tested features. | Moderate-high |
| **Entropy** | High. Conditioning on direction/volatility/time barely reduces uncertainty. | Very high |
| **Opportunity structure** | Large, symmetric, clustered excursions — but driven by volatility, not entry timing. | Very high |
| **Time structure** | No persistent hour/day/month effect survives correction. | High |
| **Falsification** | All layers survive adversarial challenge. No hidden pocket found. | Very high |

## Classification

### Strong trend process
❌ **No.** No trend persistence, no directional memory, zero continuation edge.

### Mean reverting process
❌ **No.** No reversion edge, distance from equilibrium does not predict return.

### Volatility process
✅ **Yes.** Strong volatility clustering, large excursions independent of entry, symmetric swings.

### Regime-switching process
✅ **Yes.** Temporary regimes exist (monthly patterns dissolve under BH correction). But regimes are volatility-driven, not directional.

### Near-random process
✅ **Yes** (directionally). Residual uncertainty after conditioning is high. Directional behavior is statistically indistinguishable from random on tested features.

### Hybrid
✅ **Yes** (definitive classification).

## Final classification

> **BNBUSDT M15 is a regime-switching volatility process whose directional component is near-random.**

Or, more precisely:

> **BNB M15 behaves like clustered volatility wrapped around rapidly-decaying directional information. The market remembers volatility state much more than it remembers direction. Regimes exist but are temporary, volatile, and not stationary.**

## What this means

The available 2-year analysis decisively falsifies:
- Simple trend-following (post-expansion continuation)
- Simple mean reversion (pullback to MA)
- Conditional pockets by hour/day/month/direction/volatility
- The narrative that "entry timing exists but exits squander it"

What remains **unproven** (and could theoretically contain information):
- Multi-bar state transitions (compression → expansion → continuation)
- Non-linear interactions (mutual information)
- Alternative state definitions (not just trend_proxy)
- Return autocorrelation at specific lags
- The Hurst exponent / variance ratio

**But note:** The burden of proof has shifted. After 130+ tests with zero survivors, any future claim of directional information on BNB M15 must demonstrate superiority over the random control on **realized net expectancy** with multiple-comparison control. The current evidence says direction is close to random.

---

*Analysis produced from project research outputs. Gaps marked explicitly. No strategy search, no optimization, no parameter tuning.*