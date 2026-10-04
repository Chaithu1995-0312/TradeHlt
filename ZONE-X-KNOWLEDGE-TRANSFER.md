# ZONE-X — KNOWLEDGE TRANSFER

**Date:** August 2026
**Programme:** Pre-semantic region discovery on XAUUSD M15
**Current spec:** `ZONE-X-SPEC-v0.8.md`
**Status:** Feature search halted on a registered null. **O-1 measured; path (a) Stop chosen** (`ZONE-X-DECISION-2026-08-06.md`). Design default `c=0.055` ATR/side; empirical baseline `c=0.0238`.

This document is written so that someone joining cold — or you in six months —
can pick the programme up without re-reading the conversation.

---

# PART 1 — WHAT WAS ASKED

Find a 3–4 hour stretch of gold's price history that reliably precedes a good
trading opportunity, using **only geometry** — the shape of the candles. No
trading concepts, no pattern names, no ontology. Then, afterwards, derive the
vocabulary from whatever those stretches have in common.

**Discover first, explain second, decide last.** This ordering was correct and
was never violated.

---

# PART 2 — HOW THE PROBLEM WAS MADE PRECISE

The original statement — "maximum profit, minimum stop-loss" — is
underdetermined. One relation, many unknowns. Turning it into something
testable took four steps.

### 2.1 X is a sequence region, not a clock window

Initially misread as "13:00–17:00 is the good window." Corrected: X is any
3-hour stretch, anywhere. 17 March 09:15 and 2 May 18:45 both qualify or don't
based on shape, not time of day.

### 2.2 X is a recipe, not a list

The larger correction. A ranked list of historically good windows is worthless —
you cannot trade 17 March 2025 again. X had to become a **membership criterion**
that can be evaluated on a bar that hasn't happened yet.

> "Here are the winning tickets" → "here is how to spot a winning ticket."

### 2.3 The outcome space collapses to two numbers

From an anchor price `A`, over the forward horizon:

```
U = highest high − A        (up excursion)
D = A − lowest low          (down excursion)
```

The four conventional quantities (MFE/MAE for long and short) are relabelings of
these two. There is no third dimension.

### 2.4 Order matters — first passage, not extremum

`U` and `D` are maxima and **discard path order**. A window where gold falls
$20 then rallies $30 has excellent `U`, and is untradeable — every stop was hit
on the way. "Minimum stop-loss" is inherently a first-passage concept, so the
measurement became:

> From the anchor, did price travel `k × ATR` in one direction **before**
> travelling `m × ATR` the other way?

ATR ≈ how much gold typically moves in 15 minutes (~$7.34 in the test year).

---

# PART 3 — THE OBJECTIVE, AND WHY IT CHANGED TWICE

### 3.1 First attempt: disjunctive label — ABANDONED

`s = (clean up-move) OR (clean down-move)`. Direction-free, felt safe.

**Measured base rate at m = k: 0.978.** It reduces to "did gold move at all in
three hours." A tautology.

Worse, it has **no PnL**. A direction-free event cannot be monetised without a
direction layer, so no economic criterion applies. A breakeven formula written
for it (`p* = (m+c)/(k+m)`) priced a *directional* trade against a
*non-directional* label and was invalid.

### 3.2 Second attempt: symmetric straddle — ADOPTED

Open both sides at the anchor. One leg wins, one loses, keep the difference.
Mechanical, direction-free, and denominated in money.

```
long : target A + kσ, stop A − mσ
short: target A − kσ, stop A + mσ
EV(W) = pnl_long + pnl_short − 2c
```

### 3.3 Third: directional permitted — the constraint was mis-reasoned

Non-directional was adopted to avoid look-ahead bias. **That reasoning was
wrong**, and sat in the spec from v0.4 to v0.7.

The real objection is to *selecting the winning direction after seeing the
outcome*. It does **not** apply to *predicting direction from the window before
the fact*. A classifier trained on one period and tested on another has no
selection bias at all.

| framing | pays | can collect | must deliver |
|---|---|---|---|
| straddle | 2 costs (0.14) | `k − m` = 0.50 | 28% of maximum |
| directional | 1 cost (0.07) | `k` = 1.50 | 2.1 percentage points |

**The conflation made the problem ~5.5× harder for a benefit it never provided.**

---

# PART 4 — THE CENTRAL ARITHMETIC

Everything reduces to three measured numbers.

```
1. Unconditional gross EV ≈ 0        (market is a fair coin)
2. Round-trip cost = 0.14 ATR        (straddle) / 0.07 (directional)
3. Independent observations ≈ 737/yr (not 47,275)
```

**Therefore: X must manufacture 0.14 ATR — about $1.03/oz — out of nothing,
every trade, purely from the shape of the preceding three hours.**

### 4.1 Why 737 and not 47,275

Consecutive windows share 11 of 12 bars. They are not independent evidence, any
more than photographing the same person twice yields two people. Independent
observations = admissible windows ÷ (L + h).

This is the constraint that shaped every subsequent decision.

### 4.2 What 737 observations can and cannot resolve

Detecting a 0.14 ATR effect against a per-event sd of 0.92 requires **266 events
at 80% power**. That is feasible — barely — and it forces two conclusions:

- **You can test ~8 ideas, total.** Declared in advance, tested once. Any
  open-ended search finds noise and cannot distinguish it from signal.
- **X cannot be a rare setup.** A pattern occurring 30 times a year is
  unprovable here. Whatever X is, it must be common (≥13% coverage, target 65%).

---

# PART 5 — SOURCES OF TRUTH

Every load-bearing number, and where it came from.

### 5.1 Dataset — measured directly from the file

| Fact | Value | How established |
|---|---|---|
| Rows | 47,275 | file read |
| Span | 2024-05-22 → 2026-05-21 | file read |
| Integrity | no dups, nulls, invalid OHLC, zero-range, zero-volume | checks run |
| Session | Mon–Fri, no Sunday, hour 00 absent | step-diff analysis; **confirmed by you as a market fact** |
| Step structure | 46,758 × 15min; 394 × 75min (daily); 99 × 2,955min (weekend); 23 holiday | step-diff counts |
| `open == prev_close` | 76.7% (2yr), **71.3%** (1yr) | direct comparison |
| ATR14 median | $4.539 (2yr), **$7.342** (1yr) | Wilder ATR |
| ATR14 / SD14 | **1.6437** | direct ratio, stable across both years |
| Close range | 2,287 → 5,586 | file read |
| Relative ATR | 11 bp (2024) → 25 bp (2026 Q1) | non-stationary |

### 5.2 Objective baseline — REPLICATED across two implementations

| Quantity | Value | Provenance |
|---|---|---|
| Admissible windows (2yr, L=h=16) | 31,253 | **two independent implementations agree exactly** |
| Straddle EV, k=1.5 m=1.0 | −0.1499 / −0.149856 | both implementations |
| Per-event sd | 0.966 / 0.9658 | both |
| corr(ATR decile, EV) | −0.0013 / −0.001290 | both |
| Gross EV | ≈ −0.010 | slightly below martingale zero, as the conservative intrabar rule predicts |

**This is the strongest evidence in the programme.** DeepSeek wrote an
independent implementation from the written spec alone, never having seen the
numbers. Running its code against the data reproduced every figure.

### 5.3 Martingale confirmation — external cross-check

```
Gambler's-ruin prediction  m/(k+m) = 1.0/2.5 = 0.4000
Measured long win rate                        0.4071
```

Independent theoretical corroboration that the measurement is sound. If the
code had shown free money on random windows, the code would have been wrong.

### 5.4 What is NOT verified

| Quantity | Status |
|---|---|
| **`c = 0.07` ATR per side** | **ESTIMATED, NEVER VERIFIED. Most load-bearing number in the programme.** |
| Realized `m` under gapping bars (O-4) | **MEASURED descriptive 2026-08-06** — avg realized_m≈m; P(gap_through)≪0.1% (admissibility excludes weekend gaps); see `results/research/zone_x_o4_gap_study/` |
| Max tolerated drawdown | not supplied |

---

# PART 6 — VALIDATION RESULTS

### 6.1 The registered null — the programme's main empirical finding

**Setup:** three-way chronological split. Generation year (2024-05 → 2025-05,
B ≈ 737) searchable freely; test year (2025-05 → 2026-05, B = 736) sealed and
still untouched.

**Fifteen scale-free geometric features** on each 12-bar window: efficiency
ratio, anchor position, body fraction, upper/lower wick fractions, range
compression, range dispersion, up-bar fraction, bar overlap, return
autocorrelation, coil ratio, high/low positions, volume slope, volume dispersion.

**Seven failed the `V-6` volatility screen** (|corr| with anchor ATR ≥ 0.10) and
were discarded. **Both volume features failed** — volume in this data is a
volatility thermometer in disguise.

**Eight survivors**, gradient boosting, purged split inside the generation year,
240-window embargo:

| objective | best out-of-fold | required | shortfall |
|---|---|---|---|
| straddle EV lift | **+0.0051** | +0.1400 | ~30× |
| directional (long) | 0.4298, **z = +0.03** | 0.4280 | at chance |
| directional (short) | 0.3809, z = −0.74 | 0.4280 | below chance |

### 6.2 Independent corroboration — three feature families, same answer

| source | features | directional result |
|---|---|---|
| this programme | 8 (V-6 screened) | z = +0.03 |
| DeepSeek | 10, independently generated | AUC 0.477–0.515 |
| Grok | 2 novel (of 10) | AUC 0.504, 0.505 |

No shared context between them. All landing on chance. This makes it unlikely
the null is an artifact of a badly chosen feature set.

### 6.3 The pre-registration paying off

DeepSeek, with no access to the spec, ran an open search and reported as its
headline discovery: **compression precedes expansion** (`coil = ATR12/ATR48`).

That is precisely the artifact **v0.4 §9 registered in advance** as the expected
false positive. Checked against our target:

```
corr(coil, anchor ATR) = +0.4399    → fails V-6 by 4×
directional AUC        =  0.4766    → below chance
EV spread              = −0.0377    → wrong sign, vs +0.14 needed
```

It is a volatility thermometer, not a shape measurement — unsurprising for a
ratio of two ATRs. **Pre-registration is what allowed this to be recognised
instead of celebrated.**

### 6.4 Modifications tested and rejected

Two proposed fixes were measured and failed.

**Longer horizons** (cost drag falls as horizon rises):

| L | h | k | cost drag | capture needed | B | sd |
|---|---|---|---|---|---|---|
| 12 | 12 | 1.50 | 9.3% | 28.0% | **737** | 0.93 |
| 12 | 24 | 2.12 | 6.6% | 19.8% | 405 | 1.36 |
| 12 | 48 | 3.00 | 4.7% | **14.0%** | **140** | 1.97 |

Economics improve, measurability collapses — at h=48 you'd need ~1,225 events
and have 140. **Also a hard structural ceiling: the one-hour daily break caps
any contiguous span at ~92 bars, so `L + h ≤ 92` regardless of preference.**

**CUSUM event sampling** (fewer, better-conditioned observations):

| threshold | events | base EV | sd |
|---|---|---|---|
| all bars | 8,419 | −0.132 | 1.97 |
| 3.0 | 534 | **−0.165** | 2.00 |

EV gets worse, sd unchanged, sample falls 16×. There was no concentrated edge
being diluted.

---

# PART 7 — ERRORS MADE, AND HOW THEY WERE CAUGHT

Recorded because the pattern matters more than the individual mistakes.

| # | Error | Caught by | Cost if undetected |
|---|---|---|---|
| 1 | X read as a time-of-day window | you | wrong problem entirely |
| 2 | §9 claimed compression *inflates* the label | measurement (3.5× deflation) | wrong mitigation strategy |
| 3 | `p* = (m+c)/(k+m)` — directional formula on a non-directional label | measurement (base rate 0.978) | fabricated edge across a whole grid |
| 4 | Power floor `(2s/μ)² = 128` — that's 50% power, not 80% | **Gemini Pro** | underpowered by 1.5× |
| 5 | Hypothesis budget ignored the generation-set cost | arithmetic | 5× over-budget |
| 6 | First-passage bug: `t_stop <= t_target` fires when neither exists | **cross-implementation** | EV −0.150 → −0.251 |
| 7 | `1 − y_long` used as the short outcome | self, on review | fake 0.61 win rate |
| 8 | `S-9` non-directional constraint mis-reasoned | self, late | 5.5× difficulty for nothing |
| 9 | In-sample GBM presented as a "ceiling test" | self, immediately | meaningless +0.46 lift |

**Pattern: every error was caught by execution, arithmetic, or independent
implementation. Only one (#4) was caught by review.** Prose review of
quantitative claims has a poor track record here.

### 7.1 On the multi-agent structure

Five rounds, four models, human bridge. Yield:

- **One** material catch (#4, the power floor).
- **One** genuine contribution (DeepSeek's independent implementation, which
  found #6).
- **One** useful negative (three independent feature families converging on the
  same null).
- Two literature responses came back **byte-identical** — correlated error made
  concrete rather than argued.

The value was concentrated in *independent implementation* and *unprimed
generation*, not in review or derivation. Route accordingly.

---

# PART 8 — WHAT IS ESTABLISHED

**Established:**

- The market behaves as a fair coin at this horizon. Measured 0.4071 against a
  theoretical 0.4000.
- Obvious 12-bar geometry carries **no** forward directional information in
  XAUUSD M15. Four independent probes, all at chance.
- The barrier is entirely **cost**. Gross EV is zero; the 0.14 ATR target is the
  toll, not a market obstacle.
- The effective sample is ~737/year, which permits ~8 declared hypotheses and
  forbids open search.
- Volume, in this dataset, is a volatility proxy and fails the leakage screen.

**Not established:**

- That no X exists. Roughly 35 features across three sources is a shallow probe
  of the space of computable geometry.
- That the result generalises beyond the 2025–26 volatility regime.
- Anything about longer horizons beyond h = 48 (structurally untestable here).

---

# PART 9 — NEXT ACTIONS

### 9.1 Cost (O-1) — CLOSED

**Status (2026-08-06): O-1 COMPLETE (demo MEASURED).**  
Artifacts: `results/research/xauusd_mt5_cost_calibration/`, `ZONE-X-COST-NOTE.md`.  
Binding decision: `ZONE-X-DECISION-2026-08-06.md`.

| Role | `c` ATR/side | gap vs long 0.4071 |
|---|---|---|
| Empirical baseline (report) | **0.0238** | +0.24 pp |
| **Design default** | **0.055** | +1.49 pp |
| Legacy v0.8 reference | 0.070 | +2.09 pp |

Design uses **0.055** until live stop fills across regimes justify tightening.  
Empirical **0.0238** stays for reporting/benchmarks. Sensitivity grid:
`{0.0238, 0.055, optional 0.070}` — see decision D-S1/D-S2.

### 9.2 Path decision — RECORDED: **(a) Stop**

**(a) Stop — CHOSEN 2026-08-06.** Four probes at chance; pre-registered compression
artifact; O-1 unblocked but stop-slip sample thin → conservative design `c=0.055`
and **no further ZONE-X geometry search** on gold M15. Full record:
`ZONE-X-DECISION-2026-08-06.md`.

Not chosen (retained for reopen language only):

**(b) Continue, with the constraint relaxed.** Declared priors — only via a **new**
decision record if reopen conditions fire.

**(c) Change instrument or timeframe.** Not chosen; protocol transferable if ever
picked.

### 9.3 Deferred (path a allows descriptive O-4 only)

- `O-3` Max tolerated drawdown → position fraction `f`
- `O-4` Gap penalty — **done** (descriptive; avg realized_m≈m; rare fat-tail gap-through)
- `O-5` Horizon sensitivity — now known to be capped at h ≈ 48

---

# PART 10 — PENDING / CLOSED

| # | Item | Status |
|---|---|---|
| 1 | All-in cost (spread, commission, stop slip) | **CLOSED** — MEASURED demo; dual `c` adopted |
| 2 | Path 9.2 (a/b/c) | **CLOSED — (a) Stop** |
| 3 | Larger live stop sample across vol regimes | **Open** — may revise design `c`; does not auto-reopen search |
| 4 | Max drawdown → `f` (O-3) | Open, deferred |
| 5 | O-4 gap penalty descriptive | **CLOSED 2026-08-06** — avg penalty ~0 at m=1; report in `results/research/zone_x_o4_gap_study/` |
| 6 | Parquet layer join | **CLOSED 2026-08-23** — occupancy linked; §6 null remains NOT_REACHABLE; path (a) unchanged |

---

# PART 11 — ARTIFACT INDEX

| File | Contents |
|---|---|
| `ZONE-X-SPEC-v0.8.md` | current frozen spec — definitions, settled decisions, validation protocol, retractions |
| `ZONE-X-DESIGN-CONTINUATION-v0.9.md` | post-null design — O-1→threshold→path(a/b/c) gate (path a taken) |
| `ZONE-X-DECISION-2026-08-06.md` | **binding** — path (a), design/empirical `c`, sensitivity + ontology stability rule |
| `ZONE-X-COST-NOTE.md` | O-1 measurement + adopted dual-`c` |
| `src/research/mt5_cost_calibration.py` | O-1 extraction library |
| `scripts/research/xauusd_mt5_cost_calibration.py` | O-1 CLI entry |
| `scripts/research/xauusd_mt5_cost_seed_stops.py` | DEMO STOP fill seeder |
| `scripts/research/zone_x_o4_gap_study.py` | O-4 descriptive gap penalty study |
| `results/research/zone_x_o4_gap_study/` | O-4 report + JSON |
| `results/research/zone_x_parquet_link/` | 2026-08-23 join to the XAUUSD Parquet projection layer (window occupancy + O-4 sample). See Part 13. |
| `ZONE-X-SPEC-v0.7.md` | previous — one-year rebase, headroom metric |
| `ZONE-X-SPEC-v0.6.md` | previous — power correction, `O-2`/`O-4` resolution |
| `ZONE-X-SPEC-v0.5.md` | previous — straddle EV substitution, first measured rebuild |
| `ZONE-X-agent-prompts-v0.5.md` | agent prompt templates with epistemic role assignments |
| this document | knowledge transfer |

**Reading order for someone new:** this document → v0.8 §6 (the null) →
`ZONE-X-DECISION-2026-08-06.md` → `ZONE-X-COST-NOTE.md` → v0.8 §13.

---

# PART 12 — THE ONE-PARAGRAPH VERSION

Gold at 15-minute resolution behaves like a fair coin over three-hour horizons —
measured win rate 0.4071 against a theoretical 0.4000. Four independent geometric
probes found nothing above chance; the lone positive ("compression precedes
expansion") was a pre-registered volatility artifact. O-1 was then measured on
the IC Markets demo: empirical all-in cost ≈ 0.0238 ATR/side, but stop slippage
rests on a thin near-market sample, so design defaults to **0.055 ATR/side** and
keeps 0.0238 for reporting. The operator chose path **(a) Stop** — no further
ZONE-X geometry search on gold M15. Any future economic or labeling claim that
depends on cost must be shown on the {0.0238, 0.055, optional 0.070} grid;
stability across that grid is required before treating a rule as ontology-ready
(`ZONE-X-DECISION-2026-08-06.md`).

---

# PART 13 — PARQUET LAYER LINK (2026-08-23)

**Lane:** measurement/evidence. **Path (a) Stop is unchanged.** This does not seek X,
does not unseal the test year for search, and does not form CRT states from ZONE-X.

The XAUUSD parquet layer is a JSONL projection (`src/utils/parquet_store.py`), not the
candle store. Canonical OHLC stays `data/mt5/XAUUSD_M15.csv`. The join grain is the
ZONE-X window **anchor timestamp** (close of bar `t+L-1`) against parquet row timestamps.

## What was projected

| Artifact | Rows | Parquet status | Verify |
|---|---:|---|---|
| `zone_x_windows.jsonl` (occupancy, no `g(W)` features) | 47,252 | FRESH, 17.3× | 0 mismatches |
| O-4 stop-event sample CSV | 5,000 | FRESH, 9.3× | 0 mismatches |

Window counts **hold** against O-4 on the same CSV (`sha256 4d73f5ce…`, 47,275 bars):
generation 23,541 / test 23,711 windows; admissible 17,639 / 17,743.

## Occupancy join (existing XAUUSD parquet, FRESH)

| Corpus | n | Calendar split | Admissible-anchor hits |
|---|---:|---|---|
| opportunities | 94,332 | gen 46,888 / test 47,444 / outside 0 | 70,620 (74.86%) |
| clean_labels | 94,332 | same | 70,620 (74.86%) |
| events | 7,112 | gen 3,483 / test 3,629 / outside 0 | 5,380 (75.65%) |
| telemetry | 4,883 | 4,860 rows have no timestamp | 20 (0.41%) — sparse `kind` stream |
| mother-range ledger | 299 | gen 150 / test 149 / outside 0 | 163 (54.52%) |

Opportunities and clean_labels sit entirely inside the ZONE-X generation+test calendar.
They are **not** a ZONE-X window corpus — they are a detection/label stream that happens
to timestamp onto the same gold M15 bars.

## What parquet cannot see

| Object | Verdict |
|---|---|
| v0.8 §6 eight-feature null | **NOT_REACHABLE_VIA_PARQUET** — no JSONL of per-window `g(W)` vectors; path (a) forbids rebuilding them under ZONE-X branding |
| O-1 cost calibration | **SEMANTIC_LINK_NOT_PARQUET_GRAIN** — JSON/CSV summaries already consumed by SEM-015 / F-082; not a row stream |

Regenerate: `python results/research/zone_x_parquet_link/link.py`
(gitignored `results/`, same pattern as the H-019 parquet revalidation).
Artifact: `results/research/zone_x_parquet_link/report.json`.
