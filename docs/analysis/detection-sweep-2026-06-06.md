# F-003 Phase B — CRT Detection-Supply Sweep (MEASURE-ONLY)

> Date: 2026-06-06 · Code: `scripts/analysis/detection_sweep.py` · Artifacts:
> `results/detection_sweep/{bnbusdt_all,solusdt_all}.json`. Single-knob attributed sweep of the
> Phase-A binding stage (DISPLACEMENT→EXPANSION ~5%). **No config change / no promotion.**
> Frozen pass/fail (set before results, user 2026-06-06): N ≥ +50% vs V0 · PF ≥ 90% V0 · expectancy
> ≥ 90% V0 · maxDD ≤ 125% V0 — **plus an absolute floor added mid-run** (PF ≥ 1.0 AND expectancy > 0;
> retention vs an unprofitable baseline is degenerate — see SOL).

## BNBUSDT (V0: 35 trades, PF 2.535, exp +0.545R, maxDD 3.10%)

| Variant | trades (Δ) | PF | exp R | maxDD | verdict |
|---|---|---|---|---|---|
| expansion ×0.66 (0.30→0.198) | 44 (+26%) | 2.049 | +0.415 | 3.06% | fail (N<+50%, PF 81%) — *best* |
| expansion ×0.33 (→0.099) | 50 (+43%) | 1.259 | +0.139 | 6.79% | fail (edge collapse) |
| displacement ×0.75 (0.8→0.6) | 41 (+17%) | 2.324 | +0.498 | 4.64% | fail (N<+50%, maxDD 150%) |
| displacement ×0.5 (→0.4) | 41 (+17%) | 2.068 | +0.430 | 4.68% | fail |
| body ×0.75/×0.5 | 35 (+0%) | 2.535 | +0.545 | 3.10% | non-binding (no effect) |

**BNB is already tuned-loose** (V0 `exp_atr_min=0.3`, `atr_min_disp=0.8`, `conf_body_min=0.3` — well
below defaults). Best quality-preserving relaxation buys **+26% trades (35→44) at PF 2.05 / flat maxDD**
— real but modest, and **below the +50% N target**. Nothing reaches +50% without collapsing edge
(PF→1.26, maxDD doubles). Body gate is non-binding. **No variant passes.**

## SOLUSDT (V0: 6 trades, PF 0.290, exp −0.478R)

SOL is **unprofitable at baseline** (PF 0.29; F-009 confirmed). Relaxation only manufactures more
losing trades: expansion ×0.33 → 17 trades (+183%) but PF 0.636, exp −0.219 (still losing). The
retention guardrail *falsely* passed displacement ×0.5 (PF 0.696 ≥ 90% of a losing 0.29) — which is
why the **absolute floor (PF≥1, exp>0)** was added. With it, **zero SOL variants pass.**

## Verdict — F-003 cheap throughput levers are EXHAUSTED

- **Sessions: exhausted** (Phase 6e, and Phase A shows RETEST→EXECUTION no longer session-bound).
- **Detection gates: not a quality-preserving lever** — BNB is at its quality-bounded ceiling
  (~35–44 trades); SOL has no edge to scale. Relaxation either destroys edge (BNB) or amplifies
  losses (SOL).
- **Conclusion:** executed-trade throughput is **NOT cheaply expandable** on BNB/SOL without harming
  the edge. You cannot manufacture the statistical power Trd-M6 needs by relaxing CRT gates.

## Implication — change the VALIDATION strategy, not the gates

The Trd-M6 (early-invalidation) A/B needs sample power, not more *per-instrument* trades. The
highest-leverage path is **cross-instrument POOLING**: the early-invalidation rule is per-trade and
instrument-agnostic, so pooling executed trades across BNB+ETH+BTC+SOL (+forex/XAU) into one A/B
sample lifts N (~35×N_instruments → ~100–200) **without relaxing any gate or diluting edge**. The
already-built `early_invalidation_exectrade_ab.py` runs per-instrument; a pooling wrapper aggregates
the equity/trade sets. Secondary: a brief ETH/BTC detection-headroom check (low prior — F-009 says ETH
degrades, BTC unprofitable). Lowest priority: more data history.

## Reproduce
```
python scripts/analysis/detection_sweep.py --instrument BNBUSDT --family all
python scripts/analysis/detection_sweep.py --instrument SOLUSDT --family all
```
Measure-only; results/detection_sweep/ only; live decision spine untouched.
