# Program 5 — Cross-Sectional Relative-Value (dispersion monetizability) · PRE-REGISTRATION

> **Program 5 tests whether *relative strength between crypto majors* — cross-sectional
> dispersion, a market-neutral payoff structure — can be converted into money net of costs.
> It is a different payoff axis from Programs 1–4 (all per-instrument *directional*), not a
> reopen of any of them.**

Status: **PRE-REGISTERED — design frozen, NOT yet built/run** · Date: 2026-06-17 · Branch: `patch`
Parents: none (new axis). Governance: inherits the Edge Discovery Program / M4 gate verbatim
(`src/research/qualification.py`) + CLAUDE.md §6.2 Epistemic Integrity ritual + §6.5 Authority Ladder.
**No finding number is assigned here** — a finding represents *measured truth*; F-032 is minted only
once this is run.

---

## 1. The question (object = dispersion, not momentum)

*Can relative strength (cross-sectional dispersion) between the crypto majors be monetized net
of costs?* — **NOT** "can momentum predict?". Every prior falsification (F-019…F-031) tested a
**per-instrument directional** ontology (does the next bar / sweep / regime go up?). Cross-sectional
relative value is a **panel** object: at each rebalance, rank the N coins, **long the strongest /
short the weakest**, market-neutral, hold a fixed horizon, measure the long-short spread. Momentum,
reversal, and inverse-vol are merely **candidate interpreters** of the dispersion — a null kills the
*dispersion-monetizability* question for these interpreters, not a single indicator.

This program also gates a meta-question: *does a `CrossSectional` style deserve to exist?* Evidence
answers that, not architecture — hence zero engine/spine/domain-layer changes (CLAUDE.md §6.5).

## 2. Why this is a NEW axis, not archaeology

The four closed falsifications are all *single-name directional expectancy* under intrabar+12bps.
A market-neutral spread has **no per-leg SL/TP** and its statistical unit is *one spread return per
rebalance*, not a trade Outcome — so it cannot be reached by any parameter pass over the directional
machinery. Per the anti-archaeology rule, a different payoff structure = a different ontology = a
separate pre-registration.

## 3. Universe & data (already satisfied — no acquisition)

The **6 crypto spot majors**, M15, inner-joined on common timestamps:
`BNBUSDT, BTCUSDT, DOGEUSDT, ETHUSDT, SOLUSDT, XRPUSDT` (`data/*_M15.csv`, ~70,081 bars each,
2024-05-22→2026-05-21, byte-aligned range — verified this session). FX/metals excluded (30-day
snapshot; different trading calendar would corrupt the inner-join). Close-to-close convention:
the signal at rebalance bar `t` uses only closes ≤ `t`; the position is entered at `close[t]` and
exited at `close[t+H]` (future bars strictly `> t` — no lookahead).

## 4. Interpreters (small cohort — BH-guarded, NOT a sweep)

`k = 2` (long top-2 / short bottom-2 of 6), equal-weight, market-neutral. FROZEN cohort:

| name | kind | L (lookback bars) | H (hold bars) |
|---|---|---|---|
| `xs_mom_96_16`  | momentum | 96 (1d)  | 16 (4h) |
| `xs_mom_672_96` | momentum | 672 (1w) | 96 (1d) |
| `xs_rev_8_8`    | reversal | 8        | 8 |
| `xs_rev_32_32`  | reversal | 32       | 32 |
| `xs_vol_96_16`  | inverse-vol | 96    | 16 |

Momentum score = trailing L-bar return (long high). Reversal = −(trailing L-bar return) (long
losers). Inverse-vol = −(stdev of last L returns) (long calm). Ties broken by symbol name
(determinism).

## 5. Controls (gate-4 must beat the WINNING control) — per interpreter, same (L,H) grid

| control | construction | guards against |
|---|---|---|
| `reversed`           | the interpreter on −score | sign noise |
| `shuffled`           | interpreter score permuted across symbols (seeded) | ranking-information illusion |
| `long_only`          | top-k long, no short | "it's just the long leg" |
| `equal_weight_market`| all 6 long, equal weight | hidden market beta |
| `random_ls`          | random k long / k short each rebalance (seeded) | does ranking matter at all |

The winning control = the highest-mean control under that interpreter's grid. All controls share the
interpreter's rebalance grid (paired, same n, same H).

## 6. Gates (M4 reused verbatim) + the REDUNDANT class

Reuse `permutation_p_value` and `benjamini_hochberg` from `qualification.py`. Per interpreter, on the
**net** per-rebalance spread-return series (cost already deducted):

1. `n ≥ min_samples` (30) else **INSUFFICIENT**
2. `mean_net ≥ 0`
3. `PF ≥ 1.0`
4. `mean_net > winning_control_mean` (baseline_delta > 0)
5. IS mean > 0 AND OOS mean > 0 AND `oos_retention ≥ 0.5` (OOS = last 30% chronological)
6. one-sided two-sample permutation `p ≤ α` (0.05) vs the winning control (`n_permutations = 2000`)
7. cohort Benjamini-Hochberg FDR across the 5 interpreters

**Verdict ladder** (pre-committed): `INSUFFICIENT` (gate 1) · `REJECT` (gate 2–6, or gate-7 BH) ·
**`REDUNDANT`** (passes 1–6 but `mean_net ≤ equal_weight_market mean` — dispersion is *real but not
monetizable beyond beta*; mirrors F-030's informational-vs-exploitable distinction; non-promotable) ·
`PROMOTE` (passes 1–6, beats the market basket, survives BH). REDUNDANT is checked *before* BH.

## 7. Cost (conservative, deterministic)

Non-overlapping holds (rebalance every `H` bars ⇒ independent observations, full turnover). Reuse the
research cost standard `DEFAULT_ROUND_TRIP_BPS = 12.0` (`costs.py`). Per rebalance:
`net = gross − (Σ|wₛ|)·(12/10⁴)`. For a k=2 L/S book Σ|w| = 2 ⇒ a 24 bps round-trip haircut; the
market control (Σ|w| = 1) pays 12 bps. Each unit of gross notional pays the full open+close.

## 8. Fixed, pre-committed parameters (anti-archaeology)

FROZEN for the single pass — changing any after a null is forbidden archaeology: the §4 interpreter
grid, `k=2`, the §5 control set, `min_samples=30`, `oos_split=0.30`, `oos_retention_min=0.5`,
`n_permutations=2000`, `alpha=0.05`, the 6-coin universe, 12 bps, close-to-close. **One shot.** A null
⇒ STOP; reopen only via a genuinely different axis (a different payoff structure — carry / funding /
basis / volatility / market-making — most currently data-blocked), NOT a parameter pass over k / L / H.

## 9. Epistemic-integrity pre-registration check (CLAUDE.md §6.2, the 6 questions)

1. **Artifact supporting the claim?** `results/research/cross_sectional_report.json` (n, mean_net,
   IS/OOS, PF, baseline_delta, p, verdict per interpreter) — does not yet exist; produced by the run.
2. **Could INSUFFICIENT explain it?** With H≤96 and ~70k bars, n ≈ 700–4,400 per interpreter — well
   powered; INSUFFICIENT is unlikely, so a null here is decisive, not underpowered.
3. **Upgrading sign noise into meaning?** Guarded: `reversed` + `shuffled` controls + permutation null
   + BH FDR across the cohort.
4. **Statistical or economic?** The gate is economic (net-of-cost expectancy beating controls AND the
   market basket), not mere significance — REDUNDANT exists precisely to catch significant-but-beta.
5. **Parent stronger than children?** N/A (no parent finding); the cohort is flat under BH.
6. **Would I phrase it differently after seeing raw counts?** Verdict is mechanical from the frozen
   gates + raw n/means in the artifact — no post-hoc narrative latitude.

## 10. Verdict-binding

The result is registered as **F-032** (next free id) the same turn it is produced (Findings Mandate,
§6.2): row in `docs/current-findings.md` + the CLAUDE.md §6.2 Repository Truths Index. On a null,
Program 5 is KILLED/FROZEN in the Funding Ledger with new-axis-only reopen conditions. A PROMOTE earns
*research authority only* (shadow measurement / docs) — never fusion/sizing/production weight, and
never a `CrossSectional` style layer on a single pass (§6.5 Authority Ladder).

## 11. Build checklist (this session)

1. `src/research/cross_sectional.py` — panel loader (inner-join, fail-fast on misalignment), score
   fns, weight formers (L/S, long-only, market, random, shuffled), net-return series, `qualify`.
2. `configs/research/research_config_cross_sectional.json` — universe + k + interpreter grid + the
   reused q_* / costs sections.
3. `scripts/research/qualify_cross_sectional.py` — thin driver → deterministic report + manifest.
4. `tests/research/test_cross_sectional.py` — determinism, no-lookahead, alignment fail-fast, control
   sanity, cost monotonicity.
5. Run once across the 6 majors → register F-032 with the verdict the same turn.
