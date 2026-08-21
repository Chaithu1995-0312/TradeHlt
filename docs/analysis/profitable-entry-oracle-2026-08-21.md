# Profitable-Entry Oracle → Pattern Reconstruction (XAUUSD M15)

**Point-in-time study, 2026-08-21.** Not a living doc. Research/diagnostic only:
`economic_claims_allowed: false`, no promotion, no fusion weight, no G001, no
`ACTIVE_VERSION` change.

---

## The question

Every research program on this spine so far has been **entry-first**: propose a detection
rule, measure what it caught. That couples statistical power to detector throughput, and
repeatedly produced samples too small to conclude anything.

This inverts it. Simulate a trade at **every bar, both directions**, under the repo's real
Entry/SL/TP1/TP2 geometry, keep the ones that made money, and only then ask what the
declared feature and state vocabulary was saying at that moment.

Scope is exactly `docs/analysis/feature-identity-state-inventory-2026-08-19.xlsx`: the 48
decision-vector slots, the 19 ontology feature-state families, the CRT resolver states and
the parent/HTF machine states. Nothing outside it; nothing inside it skipped — including
the surfaces prior findings called inert.

**Contamination posture.** Prior hypothesis results were treated as *unverified*, not as
evidence. No prior finding narrowed the search, no prior artifact was reused as input
(every corpus rebuilt at schema v5.0 from raw OHLCV), and this study cites no F-id as
support for its own conclusion. A null here does not confirm the prior nulls; a positive
would not overturn them.

---

## What was built

| Stage | Artifact | Result |
|---|---|---|
| 0 | `scripts/research/build_bar_matrix.py` | 47,197 rows x 124 cols — every declared feature and state, one row per bar |
| 0.5 | `scripts/research/validate_oracle_harness.py` | **GATE: PASS** (5 blocking checks) |
| 1 | `src/research/oracle/{multi_tp_walk,reference_walker,labeler}.py` | 377,256 labelled units in 10.6s |
| 3 | `scripts/research/oracle_pattern_scan.py` + `research/oracle/scan.py` | L1 / L2 / L3 on TRAIN only |

Two ontology nodes registered **before** the code that implements them (§6.6):
**SEM-017 `MULTI_TARGET_PARTIAL_EXIT`** and **SEM-018 `PROFITABLE_ENTRY_ORACLE_LABEL`**.
Both were mutation-tested to confirm they are actually enforced rather than merely present.

---

## Two corrections made during the build

**1. The production tie-break is SL-first, not `TP2 > SL > TP1`.**
`update_trade` (`crt_engine_v2.py:2456`) declares that branch order, but it is fed a single
scalar trigger price by `_intrabar_trigger_price` (`:2667`), which tests `sl_touch` before
any target — inline comment *"conservative: SL before TP1 on a spanning bar"*. The declared
branch order therefore almost never binds, and the **backtest path is already
conservative**. The optimistic target-first precedence exists only in
`analytics/sl_tp_comparator.simulate_exit`, which the backtest never calls. The plan
originally had this backwards; SEM-017 and the plan were corrected at source (E-001).

**2. `forward_walk` cannot express the object production trades.**
It models one TP, no partial, no trail. Production realises 50% at TP1, moves the stop to a
**half-way trail (not breakeven, despite `partial_tp_breakeven_enabled`)**, and runs the
remainder to TP2. So every outcome-bearing result in this repo has been measured on a
*different exit object* than the one production trades. `multi_tp_walk` closes that gap.

Correctness was established by **triangulation**, not by parity to `forward_walk` — that
would be circular when the whole program treats existing workflows as unverified:
a separately-written naive twin (two summed legs vs one blended position) agreeing on
20,000 randomised paths; a real ledger row (`entry 2318.21 → tp1 2319.3401428571433`)
reproducing to 1e-10; and `forward_walk` agreement under a degenerate config kept as a
*consistency signal only*.

---

## Stage 0.5 — the harness gate

A null from a blind miner is indistinguishable from a real negative. Five blocking checks,
all PASS:

| Check | Result |
|---|---|
| Planted signal at known AUC 0.60 / 0.55 / 0.53 | recovered 0.606 / 0.549 / 0.532 |
| Label shifted a full horizon must collapse | 0.596 → 0.499 / 0.502 |
| Exact per-bar identities (FM-001, FM-002) | max error 2.8e-14 |
| Same identities under a one-bar shift must BREAK | error 176 / 162 |
| Permuted label returns the base rate | −0.26914 vs base −0.26914 |

The gate initially **FAILED**, and the failure was my own test, not the harness: it
asserted that a ±1-bar label shift collapses to AUC 0.5. It cannot. Adjacent oracle labels
share 39 of 40 forward bars and are genuinely correlated (**measured corr +0.292 at lag 1**,
decaying to +0.003 by lag 20). The check now shifts a full horizon, and the ±1 behaviour is
reported as the autocorrelation measurement it actually is.

That measurement has a useful by-product: outcome correlation dies by lag ~10–20, well
inside the 40-bar block used for every bootstrap here, so the intervals are **conservative**
rather than optimistic.

---

## Base rates — what any pattern must beat

Full corpus, 47,157 bars x 2 directions x 2 stop geometries x 2 tie-breaks:

| Arm | win (net) | E net | E gross | cost |
|---|---|---|---|---|
| disp_bar / production / long | 0.452 | −0.269R | −0.093R | 0.176R |
| disp_bar / production / short | 0.434 | −0.320R | −0.151R | 0.168R |
| disp_bar / optimistic / long | 0.487 | −0.126R | +0.042R | 0.168R |
| fixed_atr / production / long | 0.499 | −0.099R | +0.006R | 0.105R |
| fixed_atr / optimistic / long | 0.502 | −0.072R | +0.032R | 0.104R |

`cost_r` is `cost_price / risk_distance`, so the tight bar-local `disp_bar` stop pays ~1.7x
the cost in R that `fixed_atr` does for the same broker. Gross is carried on every row for
exactly this reason: a net figure dominated by a tight stop describes the geometry, not the
market.

**Tie-break divergence, measured:** the two same-bar conventions differ on **6.81%** of
188,628 paired units, worth **+0.0866R** across all units and **+1.27R** across those that
differ. That is *smaller* than the SEM-015 measured cost (0.084–0.176R), so cost remains
the dominant measurement-basis uncertainty on every arm. SEM-017's epistemic block was
refined in place with this result; an earlier synthetic estimate that pointed the other way
was superseded and recorded as such.

---

## Results (TRAIN only; the holdout has not been touched)

### L1 — no continuous feature separates

Max |AUC − 0.5| anywhere is **0.048**, on `momentum_score` — which is flagged contaminated
(FM-023 dimensional mix saturates it on 99.7% of XAUUSD bars, so it is near-constant for a
*units* reason). Every other feature lands at 0.51–0.53. **Every top-decile expectancy is
negative**, on every arm.

### L2 — 0 of 84 cells clear zero, on all 8 arm x direction combinations

| basis | cells beating base | cells clearing ZERO |
|---|---|---|
| net | 2–14 per arm | **0 / 84 everywhere** |
| gross | 0–8 per arm | 0–65, but see below |

Cells *do* shift relative expectancy — the best on the primary arm is
`candle_direction=BULL_STRONG` at −0.102R against a −0.294R base. Information exists. It
just never crosses zero.

**The gross-basis exception is drift, not information.** The two arms showing many cells
clearing zero (65 and 56) are exactly the arms whose *base is already positive* (+0.048,
+0.041) — XAUUSD rose across 2024-05 → 2026-05, so long-side gross expectancy is positive
at baseline and any sufficiently large cell inherits it. Controlled against passive
same-direction exposure, 65 → **8**, 56 → **1**, 2 → **0**. This is why `long_only` is the
binding control and not zero.

### L3 — conjunctions

68,473 depth-≤3 conjunctions scored per direction, pruned by *effective* support (blocks,
not rows), with the null **measured by block-permutation rather than assumed** (the
analytic 2.5%-of-scored expectation is invalid for heavily overlapping conjunctions).

| direction | beat BASE | permuted null | excess | clear ZERO | permuted |
|---|---|---|---|---|---|
| long | 12,898 | 1,592 / 1,942 / 1,549 (mean 1,694) | **×7.6** | 6 | 1 / 3 / 0 |
| short | 13,068 | 2,099 / 1,477 / 2,729 (mean 2,102) | **×6.2** | 5 | 0 / 0 / 0 |

Two different answers in one table:

- **Beating the base is real.** A 6–8x excess over a measured null, with tight permutation
  draws, is not a multiple-comparisons artifact. The declared state vocabulary genuinely
  carries conditional information about *relative* outcome.
- **Clearing zero is not.** 6 against a permuted 1/3/0 is inside the noise. The short side's
  5 against 0/0/0 is suggestive, but three permutations bound the null coarsely and do not
  license a significance claim on a count of five.

---

## Determination

**The declared feature and state vocabulary does not mark a profitable entry bar on XAUUSD
M15 under the production exit geometry.**

The two halves are now separately established, and they disagree in an informative way:

- **Information exists, and it is measured, not asserted.** Conjunctions of declared states
  beat the base rate at a **6.2–7.6x excess over a block-permutation null**. The vocabulary
  is not noise.
- **That information is not economically consumable.** 0 of 84 state cells clear zero on the
  net basis on any of the 8 arm x direction combinations; the conjunctions that clear zero
  are indistinguishable from the permuted null; and every gross-basis exception collapsed
  once controlled against passive directional exposure.

This is an **information-exists / value-does-not** shape — the Authority Ladder's first rung,
granting nothing above it. The open question it leaves is narrower and more useful than the
one it started with: not *is there structure* (there is), but *why the structure will not
cross zero* — exit geometry, cost, or the size of the information itself.

### What this does NOT say

- It does not confirm or overturn any prior finding. Different measurement basis,
  independent evidence, by construction.
- It does not say no edge exists on this instrument. It says *this vocabulary*, under
  *this geometry*, over *this corpus*, does not carry one.
- Selecting bars by their realised outcome is lookahead by construction. Stages 0–3
  describe; they do not claim. The holdout remains unspent.

---

## Open

- **Only 3 permutations.** Enough to establish the 6–8x base-rate excess decisively (the
  draws are tight and the gap is an order of magnitude), but too few to put a p-value on a
  beats-zero count of 5 or 6. More permutations would sharpen only that second question.
- **Holdout power** — the non-overlapping stride test set is only **236 bars**. That is
  thin for validating an n≈60 conjunction, and was quantified before mining rather than
  discovered afterwards. Widening the holdout or adding an instrument is a decision to
  surface, not to take unilaterally.
- **`crt_state_resolved` is the resolver, not the engine.** This run's resolver dwell
  (RANGE 21,745 / SWEEP 15,186 / EXPANSION 7,092) differs substantially from the engine
  reference pinned in `market_crt_states.yaml` (RANGE 35,159 / SWEEP 6,995 / EXPANSION
  4,605). Reported, not gated — any pattern keyed on a resolved state is a statement about
  the resolver until an engine re-measurement runs.
- **Feature-layer freeze pin is stale** — `market_ontology.yaml` pinned
  `d2a6577e…`, but HEAD is `c45a63d8…` and the pre-existing working tree was `dad66e38…`.
  The pin was already stale before this work; the SEM-017/018 addition moved it again to
  `dc85440a…`. **Deliberately not re-pinned**: doing so would silently absorb another
  session's undocumented drift into this change set (§6.2 rule 3). The addition is proven
  behaviourally inert — `test_xauusd_window_vector_regression` and `test_schema_pins_match`
  both pass, so the emitted 48-dim vector is byte-identical.
- **Pre-existing floor failures, not from this work**: 15 unregistered scripts (all
  untracked WIP from concurrent sessions), one F-051 evidence-path false positive in
  `test_epistemic_invariants`, and one `msip_1_verification_package` census reconciliation.

---

## Reproduce

```bash
python scripts/research/build_bar_matrix.py --instrument XAUUSD --timeframe M15
python scripts/research/validate_oracle_harness.py --instrument XAUUSD
python -m research.oracle.labeler --instrument XAUUSD --timeframe M15
python scripts/research/oracle_pattern_scan.py --split train
```

Floor: `pytest tests/research/test_multi_tp_walk_parity.py tests/research/test_oracle_labeler.py`
(31 tests).
