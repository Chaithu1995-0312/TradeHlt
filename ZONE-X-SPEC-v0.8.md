# ZONE-X — CANONICAL SPECIFICATION v0.8

**Status:** FROZEN
**Supersedes:** v0.7.
**Contains the programme's first registered null result (§6).**
**Domain:** XAUUSD, M15. Research only.

---

## 0. Instructions to any agent receiving this document

1. Canonical text. Work from it, not a paraphrase. Cite clauses by identifier.
2. Do not extend the spec. Name gaps; state minimal assumptions and flag them.
3. Agreement carries no information. Spend output on error.
4. Every claim derived symbolically or produced by code you include.

**Track record.** v0.4 contained a false clause and an invalid formula, both of
which survived review by two model instances. v0.5's power floor was wrong by
1.5×. v0.6's hypothesis budget ignored the generation-set cost. v0.7 carried a
mis-reasoned constraint (`S-9`) that had been in place since v0.4 and cost the
design a factor of 5.5 in difficulty. **Every one of these was caught by
execution or arithmetic, none by review.**

---

## 1. Problem statement

Discover a **region class X** — a decidable membership criterion over 3-hour
windows of raw OHLCV — whose members exhibit materially better forward
reward/risk than the unconditional population.

X must be evaluable on unseen windows. A list of historically good windows is
not an answer.

---

## 2. Hard constraints

Excluded by construction: ontology, taxonomy, named market-structure concepts,
pattern names, session labels, candlestick vocabulary, trading rules, entries,
exits, position sizing, and any feature engineered to encode a belief about how
markets work.

**Directional priors** were previously on this list. They are removed — see §7.

**Ordering:** discover first, explain second, decide last.

---

## 3. Data

### 3.1 Split — three-way, chronological

```
GENERATION   2024-05-22 → 2025-05-21   23,643 bars   17,707 windows   B ≈ 737
TEST         2025-05-21 → 2026-05-21   23,632 bars   17,673 windows   B = 736
```

The generation year is **searchable without restriction**; nothing measured
there is admissible as evidence. The test year is **untouched** and remains so.

This replaces v0.7's 15% carve-out, which cost half the hypothesis budget to buy
a generation set of ~110 blocks. The earlier year was already excluded from
testing, so using it for generation is free. It also acts as a regime filter:
generation sits at ~11 bp relative ATR, test at ~17 bp, so anything surviving
both is a stronger claim.

### 3.2 Structural facts — MEASURED

| | Generation | Test |
|---|---|---|
| ATR14 median | — | **$7.342** (p10 3.467, p90 15.489) |
| `open == prev_close` | — | **71.3%** (29% gap) |
| Close range | — | 3,249.52 → 5,586.28 |
| ATR14/SD14 | — | **1.6437** |

Both years: Mon–Fri only, no Sunday session, hour 00 absent, no duplicates, no
nulls, no OHLC-invalid bars.

### 3.3 Regime warning
The test year has no low-volatility regime. Any X validated there is a claim
about the 2025–26 regime, and `V-6` cannot detect that limitation because no
contrasting regime remains in-sample.

---

## 4. Definitions

- **Window** `W(t)` = bars `[t, t+L-1]`, **`L = 12`** (3 hours), step 1.
- **Anchor** `A(t)` = close of bar `t+L-1`. Nothing inside W may reference any
  bar at index ≥ `t+L`.
- **Horizon** `h = 12`. Forward evaluation over `[t+L, t+L+h-1]`.
- **Scale** `σ(t)` = Wilder ATR14 at the anchor; TR substituted by `high − low`
  across session gaps.
- **Admissibility**: all 24 bars mutually contiguous at 15-min spacing,
  including the observation/forward boundary.
- **`g(W) ∈ R^d`**: computed exclusively from the 12 bars inside W.

**`L + h ≥ 24` is a hard floor.** MEASURED: at L=h=8 the formula reports
B = 1,233 and M > 1,000, but 4-hour block spacing does not deliver independence
under volatility clustering. That budget is manufactured, not earned.

---

## 5. Objectives — both framings

### 5.1 Straddle (non-directional)
Open both sides at `A`; long target `A+kσ` stop `A−mσ`, short mirrored. Per
side: target before stop → `+k`; stop before or same bar → `−m`; unresolved at
`h` → mark to market. Subtract `c` per side.

```
EV(W) = pnl_long + pnl_short − 2c
required lift = 2c = 0.14 ATR       max available = k − m = 0.50
→ must capture 28% of theoretical maximum
```

### 5.2 Directional
One side, chosen by a model trained on the generation split.

```
breakeven win rate  p* = (m + c)/(k + m) = 0.4280
max available = k = 1.50            cost = c = 0.07
```

**MEASURED baselines (generation year, resolved windows only):**

```
long  0.4071    (gambler's-ruin prediction m/(k+m) = 0.4000 — martingale confirmed)
short 0.3712
```

The long/short asymmetry is **gold's uptrend over the generation year, not
structure.** A long-biased rule would appear to work and would be pure
drift-capture. It must not be mistaken for edge.

### 5.3 Intrabar rule
Where a bar's range spans both target and stop, the stop resolves first.

### 5.4 Implementation warning — REPLICATED
Detecting "stop first" via first-passage index comparison must exclude the case
where *neither* index exists. A naive `t_stop <= t_target` fires when both are
the null sentinel and assigns `−m` instead of mark-to-market. This shifted EV
from −0.150 to −0.251. Found by cross-running two implementations.

**A related error, also recorded:** `1 − y_long` is **not** the short outcome.
The long tests `+kσ` before `−mσ`; the short tests `−kσ` before `+mσ`. Different
events. They must be labelled separately.

---

## 6. NULL RESULT — registered

### 6.1 What was tested
Fifteen scale-free geometric features computed from the 12 observation bars:
efficiency ratio, anchor position in window range, body fraction, upper/lower
wick fractions, range compression, range dispersion, up-bar fraction, bar
overlap, return autocorrelation, coil ratio, high/low positions, volume slope,
volume dispersion.

Seven failed the `V-6` volatility-leakage screen (|corr| with anchor ATR ≥ 0.10)
and were discarded: body_frac, upwick_frac, rng_dispersion, coil, hi_pos,
vol_slope, vol_disp. **Both volume features failed** — volume in this data is a
volatility proxy.

Eight survived. Tested with gradient boosting, purged chronological split
*inside* the generation year, 240-window embargo.

### 6.2 Result

**Straddle objective:**

| model | cov 0.20 | cov 0.35 | cov 0.65 |
|---|---|---|---|
| depth 2 | +0.0051 | −0.0049 | −0.0003 |
| depth 3 | −0.0308 | −0.0162 | +0.0065 |
| depth 4 | −0.0163 | −0.0115 | −0.0205 |

Required: **+0.1400**. Best observed: **+0.0051**. Shortfall ≈ 30×.

**Directional objective** (the 5.5× easier bar):

```
LONG   baseline 0.4040, breakeven 0.4280
       best out-of-fold 0.4298 at cov 0.20    z = +0.03
SHORT  baseline 0.3768, breakeven 0.4280
       best out-of-fold 0.3809                z = −0.74
```

Nothing approaches significance under block-adjusted standard errors.

### 6.3 What this does and does not establish

**Does not:** prove no X exists. Fifteen generic features from a single pass is a
weak probe of geometric structure.

**Does:** establish that obvious window geometry carries no forward asymmetry at
this horizon — consistent with the martingale confirmation in §5.2 and with an
efficient market at M15 on a major pair.

**Registered so that it cannot be re-derived and reported as novel.** Any future
work reusing these eight features must cite this null.

---

## 7. `S-9` RETRACTED — the non-directional constraint was mis-reasoned

**The claim, held since v0.4:** direction must be excluded because scoring a
region by whichever direction worked is look-ahead selection bias.

**Why it is wrong:** that objection applies to *selecting the better direction
after observing the outcome*. It does **not** apply to *predicting direction
from `g(W)` before the fact*. A classifier trained on the generation split and
evaluated on the test split has no selection bias whatever.

**What the conflation cost:**

| framing | cost paid | max edge | required capture |
|---|---|---|---|
| straddle | `2c` = 0.14 | `k − m` = 0.50 | 28% |
| directional | `c` = 0.07 | `k` = 1.50 | 5.1% relative (2.1pp on a 40.7% base) |

The straddle pays two costs and collects only the *difference* between the legs.
**A factor of 5.5 in difficulty, surrendered for a methodological benefit the
constraint does not actually provide.**

### 7.1 Replacement rule

> Directional prediction is permitted. Direction must be a **function of `g(W)`
> fitted on the generation split only**, declared before the test split is
> touched. Selecting direction by observed outcome remains forbidden.

### 7.2 Guard against drift-capture
Given the §5.2 asymmetry, any directional result must be reported **net of a
constant-direction benchmark** on the same sample. A rule that merely inherits
the sample's drift is not X.

---

## 8. Cost — now the critical unknown

`c = 0.07` ATR per side has **never been verified.** It is an estimate, and it
is now the most load-bearing number in the project.

### 8.1 Sensitivity — MEASURED against generation baselines

| c/side | straddle target | directional breakeven | gap vs long (0.4071) | gap vs short (0.3712) |
|---|---|---|---|---|
| 0.02 | 0.040 | 0.4080 | **+0.0009** | +0.0368 |
| 0.03 | 0.060 | 0.4120 | **+0.0049** | +0.0408 |
| 0.05 | 0.100 | 0.4200 | +0.0129 | +0.0488 |
| **0.07** | **0.140** | **0.4280** | **+0.0209** | +0.0568 |
| 0.10 | 0.200 | 0.4400 | +0.0329 | +0.0688 |

At the test-year median ATR of $7.34: `c = 0.07` is **$0.51/oz per side**;
`c = 0.03` is **$0.22/oz**.

### 8.2 Why this dominates every other open item

Halving `c` from 0.07 to 0.03 cuts the directional gap from 2.1pp to 0.5pp — a
**four-fold** reduction in what X must deliver. No feature engineering, model
class, or parameter choice on the table moves the target remotely that far.

> **`O-1` — verify actual all-in round-trip cost per ounce from the broker's
> terms and fill history: spread, commission, and realized slippage separately.
> This blocks all further modelling.**

An error of 2× in `c` invalidates every threshold in this document.

---

## 9. The volatility confound

Spanning rate falls monotonically with anchor ATR, 3.5× low-to-high — compression
**deflates** the disjunctive label (which is why that label was abandoned).

On straddle EV: `corr(ATR decile, EV)` = **−0.0013** on two years but
**+0.0440** on one year. **The cancellation does not replicate.** `V-6` is
mandatory with hard rejection, not confirmatory. MEASURED: seven of fifteen
candidate features failed it.

### 9.1 Complement constraint
Population gross EV ≈ 0, so a class covering `c` with gross +0.14 implies
`EV_complement = −0.14c/(1−c)`: −0.140 at c=0.50, −0.260 at c=0.65. At the
target coverage the excluded 35% must average −0.26 ATR gross. §6 found no such
structure.

---

## 10. Statistical capacity

```
straddle:  s = 0.9177, μ = 0.14 → N_min = 266 events, cov_min = 0.361
B_test = 736;  M ≤ 7.9 at cov 0.65, 3.9 at cov 0.55
```

Directional tests are on win-rate proportions, not EV means; power there is set
by the gap in §8.1 and must be recomputed once `c` is known.

**The headroom metric.** Maximum extractable edge in a cell ≈ `k − m` for the
straddle, `k` for directional. Required capture = target / max. `sd` scales with
`k − m`, so hypothesis budget and headroom trade off directly — a small spread
buys a large budget while shrinking the available edge. No cell in the grid wins
on both.

---

## 11. Validation protocol

- `V-1` Chronological three-way split (§3.1). No shuffling.
- `V-2` Test year untouched until `g`, `k`, `m`, `c`, direction rule and the
  hypothesis list are all frozen.
- `V-3` Hypothesis list frozen **and its count recorded** before the test year is
  touched. Bonferroni denominator = number declared, not number reported.
- `V-4` Block bootstrap on 736 test blocks; block-adjusted standard errors
  throughout (`n/24`, not `n`).
- `V-5` Baseline computed on the test year under identical (k, m, c).
- `V-6` Reject any `g` component with |corr| > 0.10 against anchor ATR or 12-bar
  local kurtosis. **Mandatory, not confirmatory** (§9).
- `V-7` Reject cells requiring capture > 40% of max available edge, or sd < 0.5.
- `V-8` Regime disclosure (§3.3).
- `V-9` **Drift benchmark.** Directional results reported net of a
  constant-direction rule on the same sample (§7.2).

---

## 12. Capital frame

```
W₀ = ₹1,00,000
k = 1.5, m = 1.0
```

Straddle: `N_min = 266` events; at ~478 qualifying events/year (cov 0.65),
~7 months to resolve at 80% power. Expected max drawdown ≈ `s²/2(μ−c)` ≈ 3.0 ATR
≈ $22/oz. Position fraction `f` open pending `O-3`.

R-efficiency: at `m = 1.0`, cost is 14% of risk per event and a null run of 266
events at 1% risk costs ~39% of capital. At `m = 0.25` it is 56% and ~140% —
the experiment would not finish.

---

## 13. Settled decisions

| ID | Decision |
|---|---|
| `S-1` | X is a **sequence region** anywhere in the series |
| `S-2` | X is a **region class** in geometry space, not a list of dates |
| `S-3` | Forward outcome collapses to `(U, D)` |
| `S-4` | Anchor at window **end** |
| `S-5` | `L = 12`, `h = 12`; `L + h ≥ 24` hard floor |
| `S-6` | `σ = ATR14` at anchor; ATR/SD = 1.64 |
| `S-7` | `k = 1.5`, `m = 1.0` |
| `S-8` | Conservative intrabar rule: stop resolves first |
| `S-9` | **RETRACTED** — directional prediction permitted under §7.1 |
| `S-10` | Overlap representative selection is EV-independent |
| `S-11` | Coverage target 0.65 |
| `S-12` | Full-year generation split; test year untouched |
| `S-13` | Eight-feature geometric family returns a **null** (§6) |
| `S-14` | `c` is unverified and blocks further modelling (§8) |
| `S-15` | Results are conditioned on the 2025–26 regime |

### Known misreadings to resist

- ✗ X is a clock window / price zone / list of dates. **No.**
- ✗ `1 − y_long` is the short outcome. **No** (§5.4).
- ✗ Long and short excursions are independent labels. **No.**
- ✗ Barriers are in per-bar SD units. **ATR; divide by 1.64.**
- ✗ Tight stops are cheaper. **Opposite.**
- ✗ Low sd means high power. **It means low headroom** (§10).
- ✗ Shrinking L and h buys independence. **It buys the appearance of it** (§4).
- ✗ Non-directional avoids look-ahead bias. **It does not** (§7).
- ✗ The volatility confound is cancelled. **Not on one year** (§9).
- ✗ The long/short baseline gap is edge. **It is drift** (§5.2).

---

## 14. Open items

| ID | Item | Status |
|---|---|---|
| `O-1` | **Verified all-in round-trip cost per ounce** | **BLOCKING** |
| `O-2` | Whether to continue past the §6 null, and on what feature family | decision |
| `O-3` | Max tolerated drawdown → position fraction `f` | open |
| `O-4` | Gap penalty: realized vs nominal `m` at 29% gapping bars | open |
| `O-5` | Horizon sensitivity `h ∈ {8, 16, 24}` | deferred |

---

## 15. Retractions from v0.7

| v0.7 clause | Status | Replaced by |
|---|---|---|
| `S-9` non-directional | **RETRACTED — mis-reasoned** | §7 |
| "directional priors excluded" (§2) | **Removed from the constraint list** | §7.1 |
| 15% generation split, M = 4 | **Superseded** — full earlier year is free | §3.1, M ≈ 7.9 |
| `O-1` "declare four criteria" | **Answered with a null** | §6 |
| `c = 0.07` treated as settled | **Unverified; now blocking** | §8 |

---

## 16. Non-goals

Semantic features, names, ontology. Backtests, Sharpe figures, execution models.
Any claim about tradability.

---

## 17. Change log

| Version | Change |
|---|---|
| v0.1–v0.3 | Objective; sequence region; `(U,D)` collapse; first-passage label |
| v0.4 | Expansion objective; compression null pre-registered |
| v0.5 | Rebuilt on measured data; straddle EV; confound falsified |
| v0.6 | Power floor corrected; `O-2`/`O-4` resolved; §6 replicated |
| v0.7 | Rebased to one year at L=h=12; headroom metric; generation split priced |
| v0.8 | **First registered null result (§6).** `S-9` retracted as mis-reasoned — directional permitted, 5.5× easier. Generation split moved to the full earlier year, restoring the budget. **Cost elevated to blocking unknown (§8)** with sensitivity table. Long/short asymmetry identified as drift, `V-9` added. |
