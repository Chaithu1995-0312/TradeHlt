# SWEEP-conditional three-arm walk (2026-09-15)

Point-in-time. Not living truth. **Not a finding.** Framing: extends F-086 to the **M15 engine-SWEEP occupancy** population with three named geometries. No G001. No promotion.

Source run: `results/run_20260915_224051_XAUUSD` (H1 = run-id census, **not** H1 timeframe).
Artifact: `results/run_20260915_224051_XAUUSD/phase_b_three_arms_sweep.json`.

## Population (review §5 closed)

- Corpus: `data/mt5/XAUUSD_M15.csv` native M15. **No resample. Not H1 candles.**
- Construction: `crt_engine_v2.process_candle` via `BacktestRunner` (engine, **not** resolver; F-069).
- Occupancy: 1,792 `SWEEP` events from that run. Entry = that bar’s close. Direction = SWEEP event.
- Walk: `forward_walk(intrabar_fixed, max_forward=40)` = **40 × 15 min = 10 hours**, not 40 hours.

## Arms (review §6 closed)

| Arm | SL | TP | R unit |
|---|---|---|---|
| planner | bar extreme ± 0.2 ATR_abs (`compute_crt_levels`) | 1R of that risk | structural risk_dist |
| two_r | **same as planner** | 2R of that risk | same |
| atr | 1.0 × ATR_abs | 2.0 × ATR_abs | ATR |
| random_atr | 1.0 × ATR_abs | 2.0 × ATR_abs | ATR; n=1792 random M15 bars, 50/50 dir, seed 42 |

planner and two_r share a stop. atr does not. They are three (SL, TP) pairs with **two** R definitions.

## §2 closed: window MFE vs exit MFE

`P(MFE≥1R)=80.5%` was **`horizon_excursion`**: full 40 bars, **never exits**. That is a walk statistic, not “the trade reached 1R.”

Exit-bounded `Outcome.reached_1r` (MFE≥1R **before** SL/TP/timeout):

| Arm | TP hit | TP+timeout | P(MFE≥1R) **exit** | P(MFE≥1R) **window** |
|---|---:|---:|---:|---:|
| planner | 47.2% | 48.3% | **50.5%** | 80.5% |
| two_r | 31.3% | 34.9% | 50.5% | 80.5% |
| atr | 32.9% | 34.4% | 50.9% | 82.1% |
| random_atr | 32.9% | 34.7% | 51.0% | 80.0% |

Exit-bounded 50.5% ≥ planner TP 47.2%: SL-first can print MFE≥1R without a TP_HIT. Coherent. The 80.5% is explanation (1) in the review — window-bounded.

## §3 closed: risk_dist and the 4.85R

planner/two_r `risk_dist` (price units) and in ATR units:

| | min | p10 | median | p90 | max | mean |
|---|---:|---:|---:|---:|---:|---:|
| risk_dist | 0.37 | 1.46 | 4.38 | 14.53 | 90.33 | 6.85 |
| risk / ATR_abs | 0.22 | 0.46 | 0.97 | 1.81 | 7.50 | 1.08 |

Mean window MFE_R = **4.85** (planner/two_r). Do not quote as expectancy. Left tail of risk (p10 = 0.46 ATR, min = 0.22 ATR) inflates R. Median stop is ~1 ATR, not uniformly tiny.

atr arm risk is exactly 1.0 ATR by construction. Mean window MFE_R = 4.00.

## Load-bearing descriptive fact

Median realized R = **−1.0** on all four arms (including random). Mean R ≈ 0 gross.

**atr SWEEP vs random_atr (same geometry):** TP hit 32.92% vs 32.92%; exit P(MFE≥1R) 50.9% vs 51.0%; mean R +0.013 vs +0.015. SWEEP occupancy does not beat a random M15 entry on the ATR 1:2 walk.

Conditional on engine SWEEP, none of the three named geometries is favorable gross; cost would make all three worse. Not a strategy. Extends F-086 to this occupancy. Not an independent test.

## Session

OFF_SESSION n=1074 (60%) is a mixed bucket (dead hours + Asia-adjacent), not one session. Do not read “off-session is worse.” Descriptive only.

## Independence of the random control (required before F-106)

| Check | Result |
|---|---|
| pipeline rows | 47,197 |
| unique SWEEP bars | 1,792 |
| random draws | 1,792 (unique 1,755; 37 duplicate draws) |
| sweep ∩ random bars | **81** (i.i.d. expected ≈ **66.6**) |
| ATR TP-hit unique bars | 590 |
| random TP-hit unique bars | 581 |
| TP-hit set overlap | **15 / 590 = 2.5%** |

Not the same 590-bar TP set. Rate 590/1792 events on both arms is a count coincidence, not sampler collapse. **Independence PASS.** Random-parity applies to **ATR 1:2 only**.

Registered as **F-106** (Likely). Not G001. Not planner-as-live. Not 94k join.

Scope (2026-09-16): F-106 SWEEP is engine `process_candle`, not FeatureState `sweep_detected` (overlap 927/1792). F-106 session split is CRT filter hours, not FM-052. See `docs/analysis/feature-state-census-2026-09-16.md`.
