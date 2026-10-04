# Exit Geometry & Dynamic Stop Modifications — a decomposition (XAUUSD M15)

**Point-in-time study, 2026-08-21.** Not a living doc. Research/diagnostic only:
`economic_claims_allowed: false`, no promotion, no fusion weight, no G001, no
`ACTIVE_VERSION` change. TRAIN partition only — the 236-bar stride holdout was not read.

---

## The question

The profitable-entry oracle program ended split: the declared state vocabulary beats the
base rate at a **6.2–7.6× excess over a measured block-permutation null**, and **0 of 84
state cells clear zero**. It left one question — is that bounded by the **exit**, by
**cost**, or by the **size of the information**?

This decomposes it. Three things made the question answerable now and make it *not* a
re-run of F-025:

1. **Every prior exit analysis measured the wrong object.** `research/exit_grid.py` (F-025)
   and `research/forensics.py` both drive `forward_walk` — one TP, no partial, no trail.
   Production realises 50% at TP1, moves the stop to a **half-way trail**, and runs the
   remainder to TP2.
2. **The cost basis changed.** `exit_grid.ceilings` derives `min_achievable_cost` from flat
   12 bps; on XAUUSD that is ~11× the measured broker cost (F-082).
3. **Production has exactly one dynamic stop** and whether it helps had never been measured
   in either direction. The rest of the class did not exist for the two-target object.

**Scope, not a correction.** F-025 was crypto, single-TP, flat-bps. This is XAUUSD,
two-target, measured-cost. Different object, different cost, different instrument — neither
confirms nor overturns the other, and this study cites no F-id as support.

---

## What was built

Two ontology nodes registered **before** the code (§6.6), both mutation-tested (6/6
mutations caught — missing field, illegal `knowledge_status`, duplicate id, on each):

- **SEM-019 `DYNAMIC_STOP_POLICY`** — the class of causal stop-modification rules.
- **SEM-020 `EXIT_CAPTURE_DECOMPOSITION`** — the ceiling accounting and which bound may be
  quoted as headroom.

| Artifact | Role |
|---|---|
| `src/research/oracle/exit_analysis.py` | SEM-020 ceilings, vectorised excursions, capture ratios |
| `src/research/oracle/stop_policy.py` | SEM-019 policy class, causal by construction |
| `src/research/oracle/exit_sweep.py` | geometry × policy grid over the dense bar universe |
| `scripts/research/exit_geometry_scan.py` | 3-stage driver (`ceilings` / `sweep` / `interaction`) |

`multi_tp_walk` gained two additive parameters (`stop_policy`, `trail_fraction=None`).
**Parity proved by regeneration**: all 377,256 on-disk oracle labels reproduce
**byte-identically** (sha256 `3027ea97…` before and after).

---

## The correction this program owes

**I asserted the same-bar arm was an optimism bound that "manufactures free money at
scale." That is measurably backwards for most of the grid.**

Arming a stop from the current bar's own extreme makes it **tighter sooner**, so the spike
that arms a ratchet becomes the bar that exits on it. Measured over 4,000 synthetic paths:

| policy | same-bar better | worse | mean Δ |
|---|---|---|---|
| `ratchet_0.5r` | 248 | **920** | −0.0976R |
| `ratchet_1r` | 30 | **197** | −0.0229R |
| `breakeven_at_1r` | **0** | 34 | −0.0060R |
| `time_decay_6_12` | **876** | 66 | +0.0044R |

Neither arm dominates and the sign is policy-dependent — `time_decay` goes the other way
precisely because it never reads the favourable extreme. The correct treatment is the
SEM-017 one: **a band, not a bound.** Corrected at source in `stop_policy.py`,
`multi_tp_walk.py` and SEM-019 (validation rule + candidate hypothesis), and pinned by
`test_same_bar_arm_is_a_band_not_an_optimism_bound` so the direction cannot silently
revert. The *causality rule itself is unchanged and still necessary* — what was wrong was
the claimed direction of its bias, not the need for it.

---

## Stage A — ceilings (the gate)

Full corpus, 47,157 bars × both directions, SEM-017 object, SEM-015 measured cost.

| cell | MFE_r | E_gross | E_net | minCost | perfect | struct | gap | cap p50 | passive |
|---|---|---|---|---|---|---|---|---|---|
| disp_bar/long/h40 | 7.539 | −0.093 | −0.269 | 0.022 | 7.517 | −0.115 | 7.632 | −0.050 | +1.063 |
| disp_bar/short/h40 | 7.481 | −0.151 | −0.320 | 0.022 | 7.459 | −0.173 | 7.633 | −0.062 | −1.104 |
| fixed_atr/long/h40 | 4.034 | +0.006 | −0.099 | 0.022 | 4.012 | −0.016 | 4.028 | +0.037 | +0.566 |
| fixed_atr/short/h40 | 3.801 | −0.075 | −0.160 | 0.022 | 3.779 | −0.097 | 3.877 | −0.102 | −0.566 |
| fixed_atr/long/h96 | 6.737 | +0.007 | −0.098 | 0.022 | 6.716 | −0.015 | 6.731 | +0.023 | **+1.368** |

**GATE: EXIT_AXIS_OPEN** (12/12 cells) — and the honest reading is that this gate is
**near-vacuous on a dense every-bar universe**, because every bar has favourable excursion
in at least one direction. It has discriminating power on a *selected* entry population
(F-025's use), not here. It ran first, cost 35 seconds, and did not close the axis; that is
all it establishes. `mean/p50` on MFE_r is 1.3–1.9×, so the mean is right-skewed but not
tail-dominated, and the **median** MFE_r (1.8–8.2R) already dwarfs the 0.022R cost floor —
the result is robust to the summary statistic.

Three findings here are *not* vacuous:

1. **Median capture ratio is negative on 9 of 12 cells** (−0.03 to −0.15). More than half
   the time the exit converts a favourable excursion into a loss. The 3 positives are all
   `fixed_atr|long` — the drift side.
   > **CORRECTED 2026-08-21: `10 of 12` -> `9 of 12`.** Recounted from `ceilings_cells.csv`
   > (9 negative / 3 positive). Checked against every other capture-like column in
   > `ceilings_report.json` to rule out a different-metric explanation: `capture_ratio_p90`
   > 0/12 negative, `mfe_capture` 0/12, `ceiling_utilization` 12/12 — none yields 10, so this
   > was a miscount. The claim direction ("more often than not") is unchanged. p90 capture never exceeds
   0.55, so no cell is anywhere near converting what the path offered.
2. **Passive exposure beats the strategy by an order of magnitude.** `fixed_atr/long/h96`:
   the two-target exit realises **+0.007R gross** while simply holding the same direction
   for the same 96 bars realises **+1.368R**. The exit geometry is a *drift destroyer* on
   this instrument — expected in kind, not in magnitude.
3. **The one positive unconditional cell is drift, not skill.** `fixed_atr/long` is gross
   positive (+0.006 to +0.007R) and net negative, and loses to passive by ~100×. Per the
   pre-declared rule, an unconditionally positive cell is investigated as a defect signal
   before being reported; it survived that check as drift.

### A defect check that fired, and was a rounding artifact

The full-corpus run reported **1 capture-ratio violation** (a trade realising more than its
own favourable excursion — arithmetically impossible). Investigated before anything else,
per SEM-020's own rule. Cause: `multi_tp_walk` stores `rr_gross` rounded to 6 decimals
while `mfe_r` is exact, so a TIMEOUT whose final close *is* the window high divides a
slightly-rounded-up numerator by an exact denominator. One unit, `_pos 44965`, ratio
1.0000, agreeing to every stored digit. Tolerance corrected to the stored precision (1e-6);
0 violations remain and p90 capture is ≤0.55, nowhere near the boundary.

*(Second time this session that stored precision, not logic, produced an apparent
inconsistency — the first was `horizon_excursion` rounding `mfe_r` to 4dp in the parity
test.)*

---

## Stage B/C — geometry × dynamic stop policy

**390 cells**: 5 stop geometries × 13 arms (production + 12 policies) × 3 horizons × 2
directions, every cell over all 47,157 bars, entries identical everywhere so a difference
is attributable to the exit alone.

### The decomposition, in one table

Mean over horizons and directions, by stop width:

| stop | gross | cost | net |
|---|---|---|---|
| `disp_bar` (production) | −0.1097 | 0.1707 | −0.2804 |
| `fixed_0.5` | −0.1119 | 0.1755 | −0.2874 |
| `fixed_1` | −0.0332 | 0.0940 | −0.1272 |
| `fixed_2` | −0.0099 | 0.0510 | −0.0609 |
| `fixed_3` | **+0.0010** | 0.0349 | −0.0339 |

**Gross expectancy converges on zero as the stop widens, and net is then just −cost.** At
`fixed_3` gross is +0.0010R — indistinguishable from zero — and the entire net loss is the
cost line. Tight stops are gross-*negative* (−0.11R) because a near stop is reached by
noise, and they simultaneously pay ~5× the cost in R (cost_r = cost_price / risk_distance).
Both terms penalise the same thing.

### Cost is ~12× the entire dynamic-stop axis, at every horizon

| horizon | policy spread | width spread | ratio |
|---|---|---|---|
| h20 | 0.0198R (0.49 CI) | 0.2540R (6.35 CI) | **12.8×** |
| h40 | 0.0212R (0.41 CI) | 0.2521R (4.93 CI) | **11.9×** |
| h96 | 0.0205R (0.33 CI) | 0.2545R (4.14 CI) | **12.4×** |

The stop-width axis is real (4–6 confidence-interval widths). **The entire span from the
best to the worst of the 12 stop policies is 0.33–0.49 of ONE cell's confidence interval** —
below the noise floor, at all three horizons independently. Whatever a dynamic stop does on
this instrument, it is smaller than the uncertainty on any single measurement of it.

### 2 of 390 cells clear zero — and both are drift

`fixed_3 / long / h96`, arms `fixed` (+0.0582R, CI [+0.0009, +0.1206]) and
`breakeven_at_1.5r` (+0.0560R, CI [+0.0001, +0.1168]). Widest stop, longest horizon, long
side of an instrument that rose across the corpus, and both CI lower bounds sit within
0.001R of zero.

Against the binding control they collapse: passive same-direction exposure over the same 96
bars returns **+0.2290R**, so the cells capture **25% and 24%** of what simply holding the
position would have earned. Pre-declared rule applied — an unconditionally positive cell is
a defect signal before it is a result — and it resolves as drift, badly captured.

Across the whole sweep: **0 of 156 long cells beat passive.** 103 of 156 short cells do,
but the best short cell in absolute terms is **−0.065R**: beating a negative benchmark by
losing less is not an edge.

### The production half-way trail, audited

The question that had never been asked: does production's TP1 trail help or hurt versus
leaving the stop alone?

| horizon | direction | production | fixed | delta |
|---|---|---|---|---|
| h20 | long | −0.26948 | −0.25704 | **−0.01244** |
| h20 | short | −0.31850 | −0.30819 | **−0.01032** |
| h40 | long | −0.26914 | −0.25663 | **−0.01251** |
| h40 | short | −0.31960 | −0.31027 | **−0.00933** |

On `disp_bar` — **the geometry production actually uses** — the trail ranks **12th of 12
arms in all four horizon×direction combinations**, and 12/12 again on `fixed_0.5`, the other
tight geometry: 8 of 8 tight-stop combinations, worst arm every time. The delta is stable to
three decimals across horizons, which is what you would expect from a mechanism that binds
shortly after TP1 rather than accumulating over the hold.

On wide stops it is middling (rank 5–10 of 12), consistent with the mechanism: the half-way
trail sits close to entry when risk is small, so it converts would-be runners into
partial-only exits; when risk is large the trail is far away and rarely binds.

**What this does and does not license.** The sign and the rank are consistent across 8
independent geometry×direction×horizon combinations. The magnitude — about −0.012R, roughly
**15–25% of one confidence-interval width** — is not individually significant, and the
combinations share the same bars, so no p-value is computed from their agreement. The
defensible statement is: *production's trail is the worst point estimate in the grid on the
geometry it actually runs on, consistently, while the whole grid is below the noise floor.*
It grants no authority to change anything (§6.5) and no config was touched.

### Most of the policy grid cannot be ranked from OHLC at all

The synthetic estimate of the same-bar ambiguity was carried forward as provisional, and
re-measuring it on the real corpus changed the picture materially — the corpus band is
**2–3× the synthetic one**, because real bars carry far larger intrabar ranges relative to
their close-to-close moves than Gaussian paths do.

| policy | mean band | min | max | reads the running extreme? |
|---|---|---|---|---|
| `ratchet_1r` | **−0.2985R** | −0.3077 | −0.2918 | yes |
| `ratchet_0.5r` | **−0.2633R** | −0.3068 | −0.2213 | yes |
| `breakeven_at_1r` | **−0.2200R** | −0.2413 | −0.2001 | yes (as a trigger) |
| `time_decay_6_12` | **+0.0003R** | −0.0002 | +0.0014 | **no** — elapsed bars only |

Across the **12 extreme-following arms** — the ones the restriction governs — mean |band| is
**0.261R** (range 0.200–0.308R), against policy spreads of 0.0198 / 0.0212 / 0.0205R at h20 /
h40 / h96. The ambiguity is **12× to 15×** the thing it would be used to measure (12.3× for the
mean band at h40, 15.5× for the worst arm at h20).

> **SHARPENED 2026-08-21: `0.196R / 9.2×–14.5×` -> `0.261R / 12×–15×`.** The superseded
> 0.196R was a correctly-computed mean over all **16** rows of `same_bar_band.csv` — including the
> four `time_decay` arms, whose band is ~0.0005R *precisely because they never read the running
> extreme*. Those four are the mechanical CONTROL that identifies the cause; they are not subjects
> of the restriction, and averaging them in understated the constraint on the 12 arms it binds.
> This is a scope refinement, not a computational error, and it moves the figure in the
> conservative direction — the restriction is stronger, so nothing downstream loosens.

`time_decay`'s band is zero to four decimals, and that is the mechanistic confirmation: it
is the one policy that never consults the favourable extreme, so there is nothing for the
within-bar ordering to change. The band is caused entirely by extreme-following.

**Consequence — a ranking restriction, applied:**

- **Not licensed from OHLC at M15**: `ratchet_*`, `breakeven_*`. The differences between
  them sit inside an ambiguity the data cannot resolve. Ranking them would need tick data.
- **Licensed**: `fixed`, `production`, `time_decay_*` — all level- or time-triggered.

Restricted to the licensed arms, the result is unchanged and cleaner:

| horizon | ranking (best → worst) |
|---|---|
| h20 | fixed −0.15642 · time_decay_18_12 −0.15647 · time_decay_6_12 −0.15687 · **production −0.16423** |
| h40 | time_decay_6_12 −0.15750 · fixed −0.15850 · time_decay_18_12 −0.15851 · **production −0.16600** |
| h96 | time_decay_6_12 −0.15710 · fixed −0.15742 · time_decay_18_12 −0.15772 · **production −0.16550** |

**Production is last among the licensed arms at all three horizons**, worse than `fixed` by
0.0078 / 0.0075 / 0.0081R — stable to three decimals. The licensed spread is 0.0085R =
**0.16 CI widths**, so the whole comparison remains below the noise floor.

**Why this strengthens rather than weakens the determination.** The causal arm is the
*optimistic* end of the band in **14 of 16** cases (same-bar updating is worse, because
tightening sooner converts the spike that armed the stop into the exit). Everything reported
here used the causal arm. So the true value of every policy lies at or below what was
measured, and every policy already fails to clear zero — the ambiguity cannot rescue any of
them, only make them worse.

### Governance detail

**34 of 390 cells are `NEARLY_INERT`** (altered <1% of trades) and 0 are exactly
`STRUCTURALLY_INERT`. These are reported as unreachable-in-effect rather than as
measured-no-effect: a trail wider than the distance to the target cannot bind because the
target ends the trade first, and quoting such a cell's expectancy would be reporting the
control twice under two names.

### A pattern I tested and had to discard

The `fixed_3/long` column ranks the arms in near-perfect order of how much they intervene —
`fixed` (0 changes) best, `ratchet_0.5r` (27,014 changes) worst — which looks like "the more
a stop policy intervenes, the more it costs you." Tested across all 10 geometry×direction
groups, that is **not** a general law: the correlation between trades-changed and net R is
strongly negative on longs at wide stops (−0.88 to −0.94) and strongly **positive** on
shorts (+0.83 to +0.91), mean +0.175, negative in only 3 of 10 groups.

The sign flips with direction, which makes it a drift signature, not a policy property: on
an instrument that rose, tightening cuts winners on the long side and cuts losers on the
short side. Recorded because the single-column version was persuasive and wrong.

---

## Stage D — the interaction test

The question the whole program exists for: does the exit **interact** with the entry
information the oracle program found, or does it merely shift every cell's level together?

The test is **paired**, which matters — every exit is measured on the same bars, so the
sampling noise is shared and an unpaired comparison of two exits' cell expectancies would
attribute common noise to the exit. Pairing collapses the question to something already
tested: for exits A and B define `d = y_A − y_B` per bar, and ask whether **d is predictable
from the state**. If the state says which exit wins, that is interaction. If not, the exit
is a level shift. `l2_state_cells` answers exactly that, so it was reused verbatim on the
difference series rather than reimplemented, with a 19-fold block-permutation null.

**Result: 0 of 16 comparisons show INTERACTION.** 10 LEVEL, 6 INDETERMINATE, 0 INTERACTION.

| geometry | direction | arm | mean d | cells | permuted mean | p |
|---|---|---|---|---|---|---|
| disp_bar | long | production | −0.01743 | 3 | 0.58 | 0.10 |
| disp_bar | long | ratchet_1r | +0.00582 | 3 | 1.26 | 0.15 |
| disp_bar | long | breakeven_at_1r | −0.01312 | 1 | 1.63 | 0.85 |
| disp_bar | long | time_decay_6_12 | −0.00109 | 4 | 2.05 | 0.15 |
| disp_bar | short | production | −0.00757 | 3 | 1.16 | 0.20 |
| disp_bar | short | ratchet_1r | +0.02192 | 5 | 1.58 | 0.15 |
| fixed_1 | long | production | −0.00810 | **0** | 1.21 | 1.00 |
| fixed_1 | long | time_decay_6_12 | −0.00413 | 5 | 1.42 | 0.10 |
| fixed_1 | short | breakeven_at_1r | +0.00108 | **0** | 0.74 | 1.00 |

*(9 of 16 rows shown; the remaining 7 are all LEVEL at p ≥ 0.45.)*

The smallest p anywhere is **0.10**, against an attainable floor of 1/(19+1) = 0.05. The
real counts (0–5 cells of ~87 scored) sit inside the permuted distribution everywhere. Note
what the counts would mean even if one had cleared: a handful of cells carrying a fraction
of a policy difference that is itself below the noise floor.

**Exit geometry does not unlock the entry information. It moves every cell together.**

---

## Determination

**The exit is not the binding constraint. The information is too small relative to cost —
and cost is set by stop width, not by stop policy.**

The oracle program's open question resolves into a four-line decomposition, each line
measured rather than argued:

1. **Gross expectancy is ≈ 0 at the every-bar level** — exactly +0.0010R at the widest stop.
   An exit cannot create expectancy that the entry did not contain; it can only decide how
   much of a zero-mean quantity gets converted into cost.
2. **Net = gross − cost, and cost dominates.** Stop width moves net by 0.25R (4–6 CI
   widths); it moves it almost entirely through `cost_r = cost_price / risk_distance`.
3. **The dynamic-stop axis is inert, and most of it is unmeasurable anyway.** All 12
   policies span 0.33–0.49 of **one** cell's confidence interval at three horizons
   independently — about 1/12th of the width axis. Worse, the extreme-following half of the
   grid (`ratchet_*`, `breakeven_*`) carries a same-bar ambiguity band of 0.261R mean —
   **9–15× the spread it would be used to measure** — so those arms cannot be ranked from
   M15 OHLC at all. Among the licensed arms (`fixed`, `production`, `time_decay_*`)
   production's half-way trail is last at all three horizons, by a stable ~0.008R, itself
   0.16 CI widths.
4. **No interaction with the entry information** — 0 of 16, minimum p 0.10.

So the answer to *"exit geometry, cost, or the size of the information?"* is: **not exit
geometry.** Between the other two it is both, and they are the same statement — the
information is not large enough to clear the cost that any real stop placement incurs.

### The uncomfortable observation

Every one of the 390 exit configurations loses to passive same-direction exposure on the
long side — **0 of 156**. The widest stop minimises cost *and* has gross ≈ 0, so
"widen the stop" converges toward "hold the position", whose limit on this corpus is the
instrument's drift (+0.23R over 96 bars where the best exit configuration returns +0.058R).

This is a **measurement about this corpus, not a recommendation.** Passive exposure has an
entirely different risk profile — no stop means unbounded drawdown, which the R-normalised
comparison deliberately does not price. What it does establish is that the exit machinery
on this instrument, over this period, subtracted from a passive baseline rather than adding
to it. That is a fact about where effort has been going, not an argument for any position.

### What this does NOT say

- **It does not confirm or overturn F-025.** Different exit object (two-target vs single-TP),
  different cost basis (measured components vs flat 12bps), different instrument (XAUUSD vs
  crypto). Arriving at a structurally similar conclusion from an independent basis is
  corroboration worth noting and is **not** cited as support in either direction.
- **It does not say production's trail should be removed.** The pattern is consistent but
  sub-noise, and removing it is a behaviour change requiring its own authorisation and a
  measured G001 improvement (§6.5). No config was touched.
- **It does not generalise beyond XAUUSD M15** under this cost calibration and this corpus.
- **It is not an economic claim.** `economic_claims_allowed: false`; mt00/mt01 remain UNRUN.

---

## Open / not claimed

- **Pre-existing failures, not from this work** (each verified by reverting my change and
  re-running): `test_ohlcv_corpus_freeze` (`data/XAUUSD_M15.csv` hash drift — last written
  2026-08-16, and this program never writes to `data/`), `test_feature_layer_freeze::
  test_source_file_pins_match` (pinned `d2a6577e…`, already stale before this session), and
  3 script-registry coverage tests failing on **18 unregistered scripts from concurrent
  sessions** — this program registered its own runnable and strictly reduced that count.
- **Freeze pin deliberately not updated.** Re-pinning would absorb another session's
  undocumented drift into this change set (§6.2 rule 3). The addition is proven
  behaviourally inert: `test_xauusd_window_vector_regression` and `test_schema_pins_match`
  both PASS, so the emitted 48-dim vector is byte-identical; only the text hash moved.
- **The sweep's `passive_price_mean` column is in price units**, not R (it is computed with
  a unit risk denominator). The R-unit passive control is the ceilings stage's
  `passive_exposure_r`. Labelled honestly rather than silently mixed.
- **The synthetic same-bar estimate was superseded by the corpus, as planned.** The
  direction table in the correction section is on Gaussian paths; the corpus measurement
  (mean band 0.261R over the 12 governed arms, vs synthetic 0.098R) is in Stage B/C and is the one that carries. Same
  pattern as SEM-017, where a synthetic estimate also had to be superseded — recorded rather
  than quietly replaced.

## Reproduce

```bash
python scripts/research/exit_geometry_scan.py --stage ceilings --instrument XAUUSD
```
then `--stage sweep` (~24 min, writes incrementally per horizon) and
`--stage interaction --n-perm 19` (~3 min).

Floor: `pytest tests/research/test_stop_policy.py tests/research/test_exit_ceilings.py tests/research/test_multi_tp_walk_parity.py tests/research/test_oracle_labeler.py` (95 tests with the semantic registry).
