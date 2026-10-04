# Early-Invalidation — Executed-Trade A/B (OFFLINE sanity check)

> Date: 2026-06-06 · **STATUS: DIRECTIONAL EVIDENCE — NOT PRODUCTION EVIDENCE
> (research-complete / production-pending).** Code: `scripts/analysis/early_invalidation_exectrade_ab.py`.
> Population: fresh BNBUSDT backtest, current config, **N=35 trades**
> (`results/ei_ab_fresh/run_20260606_144837_BNBUSDT/BNBUSDT_trades.csv`).

## Why this is a sanity check, not a gate

Executed-trade N is tiny (≤15 on disk; 35 fresh). MaxDD/Recovery/Ulcer/TUW on a 35-trade equity
curve are noise-dominated — a single path's extremes. This run verifies **mechanism + direction +
winner-preservation**, NOT promotion. Method: offline direct-effect (apply the rule per trade by
re-walking candles; rebuild control vs treatment equity curves; **ignores capital-recycling**, so
treatment is conservative on upside). No spine change.

## Results (BNB, N=35)

| Metric | k=2 (cut 12) | k=3 (cut 10) | k=4 (cut 7) |
|---|---|---|---|
| RR saved (cut losers) | +4.23 | +2.81 | +2.33 |
| RR forgone (cut winners) | −1.68 | −1.21 | −0.63 |
| **Net RR** | **+2.55** | **+1.60** | **+1.70** |
| Expectancy_R ctrl→treat | 0.545→0.617 | 0.545→0.590 | 0.545→0.593 |
| Winner avg RR (guard) | 1.369→1.359 | 1.369→**1.394** | 1.369→**1.419** |
| **Max drawdown (PRIMARY)** | 3.10%→**3.10%** | 3.10%→**3.10%** | 3.10%→**3.10%** |
| Recovery factor | 6.65→7.67 | 6.65→7.29 | 6.65→7.32 |
| Ulcer index | 0.975→0.803 | 0.975→0.853 | 0.975→0.877 |
| Time under water | 0.500→0.472 | 0.500→0.472 | 0.500→0.472 |
| Win rate | 0.657→0.629 | 0.657→0.629 | 0.657→0.629 |

## Verification of the four checks (user-requested)

1. **Rule behavior — PASS.** Cuts 7–12 trades (k=4→2); monotone, sensible.
2. **Winner preservation — PASS (strong).** Winner avg RR flat/up at every k — the rule cuts *small*
   slow winners; the big winners reach +0.25R fast and are untouched. The slow-winner failure mode
   does not materialize on this sample.
3. **Counterfactual table — PASS.** Net RR positive at every k; saved > forgone (forgone ≈ 27–43% of
   saved — a better ratio than the 85–95% on the raw universe, because gated trades skew to winners).
4. **Drawdown direction — MIXED / WEAK.** Ulcer ↓ and Time-under-water ↓ (drawdown *shape* improves),
   but **headline MaxDD is FLAT** — the rule didn't touch the trades forming the single worst trough.
   Expectancy *rose* (not the expected "small cost"). At N=35 none of this is reliable.

## Honest verdict

- **Mechanism confirmed; winners protected; net-positive counterfactual on real gated trades.** The
  signal-level finding (F-014) reproduces directionally on the executed population.
- **The "drawdown engine" thesis is only partially supported here:** Ulcer/TUW improve, but the
  headline MaxDD does not move on 35 trades. Whether the rule materially cuts MaxDD is **unproven and
  unprovable at this N**.
- **Expectancy did not degrade** (rose slightly) — so the Tier-2 "do no harm to return" guard holds.

## Status & gate

**FREEZE: research-complete / production-pending.** Do NOT promote Trd-M6, enable live, or modify the
production spine. The promotion gate (material MaxDD ↓ with expectancy intact, across instruments and
OOS) is **unmeasurable at current throughput**. Re-run the executed-trade A/B — and only then consider
the spine-integrated version (which adds capital-recycling) — once executed-trade throughput is
materially higher (ties to F-003 session/detection-supply work). Until then, F-014's signal-level
evidence stands as the primary record; this executed-trade view is corroborating, directional only.

## Reproduce
```
python src/runtime/backtest_v2.py --csv data/BNBUSDT_M15.csv --instrument BNBUSDT --output results/ei_ab_fresh
python scripts/analysis/early_invalidation_exectrade_ab.py \
    --trades results/ei_ab_fresh/run_*/BNBUSDT_trades.csv --csv data/BNBUSDT_M15.csv --instrument BNBUSDT --k 3
```
