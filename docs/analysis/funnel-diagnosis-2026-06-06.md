# F-003 Phase A — CRT Detection-Funnel Diagnosis

> Date: 2026-06-06 · MEASURE-ONLY · Code: `scripts/analysis/funnel_diagnosis.py` ·
> Source: fresh BNBUSDT backtest, current config (`results/ei_ab_fresh/run_20260606_144837_BNBUSDT/`).
> Purpose: locate the binding choke point on the CURRENT config BEFORE touching any threshold
> (per the F-003 plan + user instruction: "refuse to change a single threshold until the funnel proves
> where the choke point actually is").

## Result (BNBUSDT, N_trades=35)

| Stage | count | conversion from prev |
|---|---|---|
| RANGE → SWEEP | 4638 | — |
| SWEEP → DISPLACEMENT | 1091 | 23.5% |
| **DISPLACEMENT → EXPANSION** | **55** | **5.04%** ← BINDING |
| EXPANSION → RETEST | 134 | (denominator includes shadow expansions) |
| RETEST → EXECUTION | 35 | 26.1% |
| EXECUTION → RESOLUTION | 35 | 100% |

Branches: `RANGE→SHADOW_PENDING` 144 · `SHADOW_PENDING→SWEEP` 144 · `SWEEP→EXPANSION` (shadow) 144 ·
`EXPANSION→EXPIRED` (TTL) 7.

## Findings

1. **The binding stage is DISPLACEMENT→EXPANSION at 5.04%** — 1091 displacements collapse to 55
   expansions. This is by far the steepest drop on the golden path and confirms the historical ~5.2%
   (MEMORY `project_phase0_findings`) still holds on current config. Governed by the expansion guard
   `expansion_atr_min_distance` (close must exceed disp_close + 0.2×ATR; `crt_engine_v2.py:323`) plus
   the upstream displacement-formation gates (`atr_min_displacement:343`, `confirmation_body_min:344`).
2. **The shadow path now produces MORE expansions than the normal path** — `SWEEP→EXPANSION` (shadow)
   = 144 vs `DISPLACEMENT→EXPANSION` (normal) = 55. Total expansions ≈ 199 → 134 retests.
3. **The RETEST→EXECUTION choke is no longer session** — only 29 `FILTER_REJECTED` (16 discount-zone +
   13 premium-zone). Of 134 retests → 35 executions; the ~99 non-executions are zone (29) + soft-
   confirmation/score (~70, `BEGIN_SOFT_CONF`=134). Sessions are genuinely exhausted as a lever (F-003).

## Implication for Phase B

The highest-leverage upstream supply lever is **`expansion_atr_min_distance`** (and secondarily the
displacement-formation gates): even a modest 5%→10% conversion at DISPLACEMENT→EXPANSION would roughly
double normal-path expansions and cascade to retests/executions. A secondary lever is the zone filter
at RETEST→EXECUTION (29 rejects). Phase B sweeps these single-knob, with quality measured alongside N.

**This does NOT authorize a threshold change** — Phase B is a measure-only attributed sweep
(`session_sweep.py` doctrine: V0-baseline-must-reproduce, one knob at a time, results/ only). A passing
per-instrument candidate then goes through a SEPARATE governed `ConfigValidator`→promotion decision.

## Reproduce
```
python src/runtime/backtest_v2.py --csv data/BNBUSDT_M15.csv --instrument BNBUSDT --output results/funnel
python scripts/analysis/funnel_diagnosis.py --events results/funnel/run_*/BNBUSDT_events.jsonl --instrument BNBUSDT
```
Next: repeat for SOLUSDT (F-009 per-instrument; BNB+SOL are the throughput targets) before Phase B.
