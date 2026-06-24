# Program 6 — Carry / Basis (signal on cross-sectional spot dispersion) · PRE-REGISTRATION

> **Program 6 tests whether a coin's perp funding-rate / basis (premium-index) rank predicts its
> forward CROSS-SECTIONAL SPOT return — i.e. whether carry/basis is an informative ranking signal
> for a market-neutral spot dispersion trade. It is a NEW signal source on the (already-falsified)
> dispersion payoff, not a reopen of Program 5's price-derived interpreters.**

Status: **PRE-REGISTERED — design frozen, NOT yet run** · Date: 2026-06-18 · Branch: `patch`
Parents: Program 5 (F-032, dispersion machinery) + the carry/basis data corpus (frozen this session).
Governance: inherits the Edge Discovery Program / M4 gate verbatim (`src/research/qualification.py`)
+ CLAUDE.md §6.2 Epistemic Integrity ritual + §6.5 Authority Ladder. **No finding number is assigned
here** — F-033 is minted only once this is run and read.

---

## 1. The question (object = is carry/basis an informative cross-sectional SIGNAL)

*Does ranking the crypto majors by funding-rate / basis predict their forward relative SPOT return,
monetizably net of costs?* The **measured object is signal-on-spot-dispersion** (user-confirmed):
rank the N coins by the carry/basis signal at rebalance bar `t`, **long the low / short the high**
(and the inverse), market-neutral, hold `H` bars, measure the long-short **spot** close-to-close
spread net of a flat 12 bps/leg. This is **NOT** the funding-PnL carry-harvest payoff (holding the
perp to earn funding) — that is a distinct payoff structure deferred to a possible Program 6b, and
only if this shows informativeness.

## 2. Why this is a NEW axis, not archaeology

Program 5 (F-032) falsified dispersion monetizability for **price-derived** interpreters
(momentum/reversal/inverse-vol). Program 6 introduces a **different information source** — perp
funding/basis, an input the repo did not possess until this session — onto the same dispersion
payoff. A new signal source is a new ontology, not a parameter pass over Program 5; per the
anti-archaeology rule it earns its own pre-registration. (Per F-032 the *price-derived* dispersion
question stays closed; Program 6 does not re-run those interpreters.)

## 3. Universe & data (corpus frozen this session — no acquisition in this program)

The **6 crypto spot majors**, M15, inner-joined on common timestamps:
`BNBUSDT, BTCUSDT, DOGEUSDT, ETHUSDT, SOLUSDT, XRPUSDT`. Spot closes from `data/*_M15.csv`; perp
side-channels from `data/perp/{SYM}_FUNDING_8H.csv` (8h) + `{SYM}_BASIS_M15.csv` (M15), acquired +
verified this session (each 2,190 funding / 70,080 basis rows, 2024-05-22→2026-05-21, dup=0, zero
gaps, **basis↔spot coverage = 1.0000**; Program Carry Acquisition FROZEN). FX/metals excluded (no
perp corpus; different calendar). **No-lookahead:** the signal at rebalance `t` reads only data ≤
`t` — **basis** is the contemporaneous premium-index at `t`; **funding** is FORWARD-FILLED to the
last settlement with time ≤ `t` (`bisect_right − 1`). The spot position is entered at `close[t]`,
exited at `close[t+H]` (future bars strictly `> t`).

## 4. Interpreters (small cohort — BH-guarded, NOT a sweep)

`k = 2` (long bottom-2 / short top-2 of 6 by signal), equal-weight, market-neutral. Trailing mean
over `L` (mirrors the Program-5 `vol` window). **Both signs are registered** so neither direction is
cherry-picked (BH corrects the multiplicity). FROZEN cohort:

| name | kind | L (lookback bars) | H (hold bars) | direction |
|---|---|---|---|---|
| `carry_lo_96_16`   | carry      | 96 (1d)  | 16 (4h) | long LOW funding (classic carry, short the payers) |
| `carry_lo_672_96`  | carry      | 672 (1w) | 96 (1d) | long LOW funding |
| `carry_hi_96_16`   | carry_inv  | 96       | 16      | long HIGH funding (opposite sign) |
| `carry_hi_672_96`  | carry_inv  | 672      | 96      | long HIGH funding |
| `basis_lo_96_16`   | basis      | 96       | 16      | long LOW basis (convergence, short the rich) |
| `basis_lo_672_96`  | basis      | 672      | 96      | long LOW basis |
| `basis_hi_96_16`   | basis_inv  | 96       | 16      | long HIGH basis |
| `basis_hi_672_96`  | basis_inv  | 672      | 96      | long HIGH basis |

`carry` score = −mean(funding over L) (long low); `carry_inv` = +mean (long high). `basis` /
`basis_inv` likewise on the premium index. Ties broken by symbol name (determinism).

## 5. Controls (gate-4 must beat the WINNING control) — reused VERBATIM from Program 5

| control | construction | guards against |
|---|---|---|
| `reversed`           | the interpreter on −score | sign noise |
| `shuffled`           | interpreter score permuted across symbols (seeded) | ranking-information illusion |
| `long_only`          | bottom-k long, no short | "it's just the long leg" |
| `equal_weight_market`| all 6 long, equal weight | hidden market beta |
| `random_ls`          | random k long / k short each rebalance (seeded) | does the ranking matter at all |

**Beta is already controlled — no new control is added.** "Carry can hide beta" is caught by
`long_only` (gate-4: if the long leg alone beats the L/S spread → beta artifact) and by the
`REDUNDANT` verdict vs `equal_weight_market` (spread ≤ market basket → not beta-orthogonal). This is
exactly how F-032 unmasked `xs_rev_32_32` as a long-leg/beta artifact — established machinery, not a
new knob.

## 6. Qualification gates (M4 — reused VERBATIM; payoff-agnostic)

`src/research/cross_sectional.qualify` → `_evaluate` (gates 1–6 + redundancy) → cohort BH (gate 7):
1. **n ≥ min_samples (30)** else INSUFFICIENT.
2. **E[spread_net] ≥ 0**.  3. **PF ≥ 1.0**.  4. **beats the winning control** (baseline_delta > 0).
5. **OOS retention** (chronological 70/30: IS>0 AND OOS>0 AND OOS/IS ≥ 0.5).
6. **permutation p ≤ 0.05** vs the winning control (seeded).  7. **Benjamini-Hochberg** across the
cohort at FDR 0.05.
**REDUNDANT** = passes 1–6 but spread ≤ `equal_weight_market` (real but beta-redundant).
Costs: `DEFAULT_ROUND_TRIP_BPS = 12.0`/leg. `n_permutations = 2000`, `α = 0.05`, `oos_split = 0.3`.

## 7. Verdict ladder & pre-registered priors

`INSUFFICIENT · REJECT · REDUNDANT · PROMOTE`. Per the F-019…F-032 prior the **expected outcome is
REJECT/REDUNDANT (null)** — recorded here BEFORE the run so a null is not rationalized and a positive
is not inflated. A PROMOTE would be the first non-null in the program and would earn **research
authority only** (§6.5) — never production/fusion weight without a measured ΔG001.

## 8. Forbidden until the gate speaks (E-001)

No "carry is promising / should work / is structural alpha" — those statements have **no authority**
until M4 runs and is read. **edge = UNKNOWN** until then. F-033 is minted only after, citing the
report artifact (`results/research/carry_report.json`) with non-empty evidence.

## 9. Determinism & isolation

Pure stdlib + research-internal; symbols/timestamps sorted; every RNG seeded from a stable string;
the serialized report carries NO wall-clock → byte-comparable across runs. Zero engine/spine/config
changes (the only code edit is additive to `src/research/cross_sectional.py`; Program 5 stays
byte-identical, proven by its unchanged test suite).

## 10. Research Envelope

| field | value |
|---|---|
| Payoff | market-neutral cross-sectional spot dispersion, carry/basis-ranked |
| Universe | 6 crypto majors, M15, 2024-05-22→2026-05-21 |
| Signal source | perp funding (8h ffill) · perp basis/premium-index (M15) |
| Costs | 12 bps/leg round-trip |
| Statistics | permutation (2000) + BH (FDR 0.05) + 70/30 OOS retention |
| Controls | reversed, shuffled, long_only, equal_weight_market, random_ls |
| Decision | INSUFFICIENT / REJECT / REDUNDANT / PROMOTE |
| Authority if PROMOTE | research only (§6.5); no production/fusion weight |
| Out of scope | funding-PnL carry-harvest (Program 6b); OI (Program 7); FX/metals |
