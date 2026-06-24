# Early-Invalidation A/B — Signal-Level Results (Consumer A)

> Date: 2026-06-06 · point-in-time analysis · Code: `scripts/analysis/early_invalidation_ab.py`,
> `src/replay/timing_reconstructor.py` · Artifacts: `results/analysis/early_invalidation_ab_<INST>.json`

## What this is

The decisive economic test of the timing-based early-invalidation rule, on the ~140k-opportunity
universe per instrument (deterministic, huge N). **Rule:** a trade that has NOT reached +0.25R by
candle K (and survived to K) is exited at that candle's close. Causal/no-lookahead. Control = rule
OFF (natural outcomes); treatment = rule ON.

## Headline — Net RR impact (k=3), 4/4 instruments POSITIVE

| Instrument | Cut losers (RR saved) | Cut winners (RR forgone) | **Net RR** | Expectancy ctrl→treat | Winner avg RR ctrl→treat |
|---|---|---|---|---|---|
| ETHUSDT | +2553.4 | −2251.9 | **+301.5R** | −0.0361 → −0.0340 | +0.4431 → +0.4418 |
| BNBUSDT | +2296.5 | −2032.0 | **+264.6R** | −0.0410 → −0.0391 | +0.4425 → +0.4423 |
| SOLUSDT | +2105.9 | −1773.2 | **+332.7R** | −0.0502 → −0.0478 | +0.4162 → +0.4162 |
| BTCUSDT | +2418.1 | −2263.8 | **+154.3R** | −0.0307 → −0.0295 | +0.4496 → +0.4485 |

## k-sensitivity (ETH / BTC) — net positive at every K, monotone

| k | ETH net | BTC net | ETH saved/forgone | cut (ETH) |
|---|---|---|---|---|
| 2 | +497.6 | +320.7 | 5139 / 4642 (1.11×) | 16,208 |
| 3 | +301.5 | +154.3 | 2553 / 2252 (1.13×) | 8,021 |
| 4 | +197.2 | +156.6 | 1352 / 1155 (1.17×) | 4,252 |
| 5 | +58.6 | +93.1 | 743 / 684 (1.09×) | 2,433 |
| 6 | +22.3 | +52.2 | 444 / 421 (1.05×) | 1,458 |

## Honest verdict (nothing hidden)

- **Direction confirmed, robust:** Net RR > 0 on **4/4 instruments and every K (2–6)**. The rule saves
  more on cut losers than it forgoes on cut winners.
- **BUT the margin is THIN.** Forgone winner RR offsets **~85–95%** of the loser savings — the
  slow-winner cost (your flagged failure mode) is **real and large**; it just doesn't exceed the
  savings. Net is ~5–13% of the gross RR the rule touches.
- **Winner-set avg RR is PRESERVED at every K** (Tier-2 guard PASSES): big winners move fast (reach
  +0.25R early) and are essentially never cut — the thinness comes from many *small* slow winners, not
  a few large outliers. This is the reassuring structural result.
- **Expectancy improvement is small** on the universe (~+0.002 to +0.004R/opportunity); win-rate drops
  (Tier-3, expected, not the objective); profit factor up marginally.
- **MaxDD — NOT measured here** (portfolio-level, ill-defined on overlapping universe positions). This
  is the likely *main* prize of cutting losers early, and it is unmeasured. Given the thin expectancy
  edge, the case for the rule now rests substantially on MaxDD.

## Activation-gate read (per the tier hierarchy)

- Tier 1 (must improve Expectancy OR MaxDD): Expectancy improves marginally 4/4; **MaxDD pending**.
- Tier 2 (must not materially worsen): Winner avg RR flat ✓; Net forgone ≥0 (net positive) ✓; PF up ✓.
- Tier 3 (diagnostic): win-rate down, hold-time down, trades-exited up — as expected.

**Verdict: conditional GO.** Direction is right, winners are protected, net positive and robust — but
the thin expectancy margin makes the **executed-trade backtest A/B (with MaxDD) the real decision
gate, not optional.** If MaxDD falls materially there, enable; if not, the thin universe-level
expectancy edge alone likely does not justify the added lifecycle complexity.

## Next

1. **Executed-trade backtest A/B** (the design's `early_invalidation` config flag + `backtest_v2`
   hook + `unified_replay_harness` two-mode) → measures MaxDD/PF/expectancy on the *actual* gated
   trade population (sequential, non-overlapping). This is now the decisive step.
2. Consider per-cluster K (slow-mover clusters carry later p50 time-to-+0.25R) and `action=scale`
   vs full `exit` as mitigations for the slow-winner cost.

## Reproduce
```
python scripts/analysis/early_invalidation_ab.py --instrument ETHUSDT \
    --opportunities logs/ETHUSDT/oos_ETHUSDT/opportunities.jsonl --csv data/ETHUSDT_M15.csv --k 3
```
