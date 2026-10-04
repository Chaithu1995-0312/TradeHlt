# Program 6b — Carry HARVEST (funding cashflow + price/basis) · PRE-REGISTRATION

> **Program 6b tests whether the funding cashflow a market-neutral perp basket accrues — long
> low-funding / short high-funding, plus basis convergence — can exceed trading costs. This is the
> CASHFLOW payoff, economically distinct from F-033 (which tested funding/basis as a predictive
> SIGNAL for spot dispersion and is closed). One pre-registered attempt; not a Program-6 reopen.**

Status: **PRE-REGISTERED — design frozen, NOT yet run** · Date: 2026-06-18 · Branch: `patch`
Parents: F-033 (signal null) + the frozen perp corpus. Governance: inherits the M4 gate verbatim
(`src/research/qualification.py`) + CLAUDE.md §6.2 Epistemic Integrity ritual + §6.5 Authority Ladder.
**No finding number is assigned here** — F-034 is minted only once this is run and read.

---

## 1. The question (object = cashflow harvest, NOT a predictive signal)

*Can a market-neutral perp basket that is long the lowest-funding and short the highest-funding coins
HARVEST net positive cashflow (funding received ± basis convergence) after costs?* F-033 already
answered the orthogonal SIGNAL question ("does funding rank predict forward spot dispersion?" — no).
6b is a different return construction, benchmark, and control set: you are not predicting which coin
outperforms; you are collecting the funding stream the position structurally earns.

## 2. Return constructions (two interpreters, SAME funding-ranked weights) — "both, side by side"

Position at rebalance `t`: rank by funding, **long low-funding / short high-funding**, equal-weight
market-neutral (`k=2`). Hold `(t, t+H]`. A LONG perp PAYS funding when the rate is positive, so the
long-low/short-high basket is structurally income-positive. `funding_accrued_s = Σ_{i=t+1}^{t+H}
funding_settle_s[i]` (discrete 8h settlements landing strictly after entry — **no-lookahead**: a
settlement at `t` itself is not counted).

- **`harvest_full`** (TRADEABLE) = `Σ_s w_s·perp_ret_s − Σ_s w_s·funding_accrued_s − cost`, where
  `perp_ret_s = spot_ret_s + (premium_{t+H} − premium_t)` (perp ≈ spot·(1+premium), so the
  premium-index change captures **basis convergence**), `cost = Σ|w_s|·12bps/1e4`. This is the
  realizable PnL of the actual trade.
- **`harvest_funding_only`** (DIAGNOSTIC) = `−Σ_s w_s·funding_accrued_s − cost` — drops the
  price/basis term. A PnL *decomposition*, NOT a tradeable strategy.

`funding_income = −Σ_s w_s·funding_accrued_s` (pre-cost) is reported as a diagnostic column.

## 3. Verdict authority — diagnostics CANNOT promote (the load-bearing rule)

Only `harvest_full` (tradeable) interpreters run the full gate ladder
(INSUFFICIENT/REJECT/REDUNDANT/PROMOTE) and enter the Benjamini-Hochberg cohort. `harvest_funding_only`
specs receive **only** `DIAGNOSTIC_POSITIVE` (E>0) / `DIAGNOSTIC_NEGATIVE` (E≤0) and are **excluded
from BH** and from the promotion surface. They live in a separate `diagnostics` appendix in the
report — never in the ranking table. Rationale: a *component* of PnL must never receive more authority
than the *trade* being decomposed (the failure mode is "funding-only looks positive while the full
trade loses"; the most likely outcome here). This is an Authority-Ladder invariant (§6.5), pre-set
before the run.

## 4. Universe, data, cohort (FROZEN — no parameter search)

6 crypto majors, M15, 2024-05-22→2026-05-21; spot closes `data/*_M15.csv`; funding/basis from the
frozen corpus `data/perp/` (coverage 1.0000). `k=2`. Holds **{96, 288, 672} = {1d, 3d, 1w}**
(H=288 included because funding economics often mean-revert faster than a week; **NO further H
values, ever**). Direction is long-low/short-high only (the harvest thesis; the `reversed` control
tests the opposite). FROZEN cohort:

| name | L (rank) | H (hold) | return | authority |
|---|---|---|---|---|
| `harvest_full_cur_96`  | 1 (current funding) | 96  | full | TRADEABLE (BH) |
| `harvest_full_cur_288` | 1                   | 288 | full | TRADEABLE (BH) |
| `harvest_full_cur_672` | 1                   | 672 | full | TRADEABLE (BH) |
| `harvest_full_1d_96`   | 96 (1d-avg funding) | 96  | full | TRADEABLE (BH) |
| `harvest_fund_cur_96`  | 1                   | 96  | funding-only | DIAGNOSTIC |
| `harvest_fund_cur_288` | 1                   | 288 | funding-only | DIAGNOSTIC |
| `harvest_fund_cur_672` | 1                   | 672 | funding-only | DIAGNOSTIC |
| `harvest_fund_1d_96`   | 96                  | 96  | funding-only | DIAGNOSTIC |

## 5. Controls (gate-4 must beat the WINNING control)

The 5 Program-5 controls **plus `cash`** (user-required): `reversed` · `shuffled` · `long_only` ·
`equal_weight_market` (all-long perp basket = beta/redundancy benchmark, drives `REDUNDANT`) ·
`random_ls` · **`cash` = a zero series** (harvest must beat *doing nothing*, not merely the basket).
Each control is measured with the same harvest return construction as the interpreter it guards.

## 6. Gates (M4 — reused VERBATIM; payoff-agnostic)

`_evaluate` (gates 1–6 + redundancy, with the harvest control set) → cohort BH over tradeable only →
`_finalize`: (1) n≥30 else INSUFFICIENT · (2) E≥0 · (3) PF≥1 · (4) beats the winning control (incl.
cash) · (5) 70/30 OOS retention (IS>0,OOS>0,OOS/IS≥0.5) · (6) permutation p≤0.05 · (7) BH FDR 0.05.
REDUNDANT = passes 1–6 but ≤ `equal_weight_market`. Costs 12bps/leg, n_perm 2000, α 0.05,
oos_split 0.3.

## 7. Pre-registered priors & forbidden claims (E-001)

Expected outcome = REJECT/REDUNDANT for `harvest_full` and most likely `DIAGNOSTIC_POSITIVE`
funding-only + `REJECT` full (funding exists but is overwhelmed by price/basis drag + costs) —
recorded BEFORE the run. No "carry harvest works / funding is structural alpha" until the gate
speaks; **edge = UNKNOWN** until then. F-034 minted only after, citing `results/research/
harvest_report.json`. **No parameter archaeology** (`carry_zscore/ema/combo/smoothed`, extra H/L/k)
— F-033/F-034 forbid it. **STOP after F-034** regardless of outcome; Program 7 (OI) / FX-metals are
NOT automatic and each needs a fresh structural thesis + pre-registration.

## 8. Determinism & isolation

Pure stdlib + research-internal; sorted symbols/timestamps; RNGs seeded from stable strings; report
body carries NO wall-clock → byte-comparable. The only code edit is additive to
`src/research/cross_sectional.py` (Programs 5 & 6 stay byte-identical — proven by their unchanged
test suites). Research authority only (§6.5); no production/fusion weight even on a PROMOTE.

## 9. Research Envelope

| field | value |
|---|---|
| Payoff | market-neutral perp carry HARVEST (funding cashflow + basis convergence) |
| Universe | 6 crypto majors, M15, 2024-05-22→2026-05-21 |
| Signal source | perp funding settlements (discrete 8h) + premium-index (basis) |
| Costs | 12 bps/leg round-trip |
| Statistics | permutation (2000) + BH (FDR 0.05, tradeable only) + 70/30 OOS retention |
| Controls | reversed, shuffled, long_only, equal_weight_market, random_ls, **cash** |
| Decision | tradeable: INSUFFICIENT/REJECT/REDUNDANT/PROMOTE · diagnostic: DIAGNOSTIC_POSITIVE/NEGATIVE |
| Authority if PROMOTE | research only (§6.5) |
| Out of scope | OI (Program 7); FX/metals; any further H/L/k (frozen) |
