# Phase-0 Economic Edge Diagnosis — funding gate (2026-06-03)

> Point-in-time, generated 2026-06-03T10:26:51.702917+00:00 (seed 1337). PURE MEASUREMENT — no fusion weight, no config write, no promotion. Executes the §4 experiment + §7 Kill Criteria + §8 ROI translation of [`economic-edge-gap-analysis-2026-06-03.md`](economic-edge-gap-analysis-2026-06-03.md). Full battery, one run, all instruments. Artifact: `results/phase0_economic_edge/phase0_diagnosis.json`.

## VERDICT: **FAIL** — 0/4 instruments cleared the gate

> **FAIL (per §7, valid after all three exhaustion conditions): no feature track moved OOS AUC ≥ +0.03 above its matched baseline with a surviving expectancy lift and N ≥ 50.** Do NOT fund Liquidity V2 / BitNet V2 / TradeNet V2 / Probability-Surface V2. Continue the governance / execution-selection track.

## Gate (§7, exact)

PASS(instrument) iff best track OOS AUC ≥ matched_baseline + 0.03 **AND** positive expectancy lift survives **AND** winning-slice OOS N ≥ 50. Repo PASS = majority of instruments. Baseline recomputed per split (never the 0.5149 constant). Sanity anchor (baseline ≈ near-chance): **OK**.

## Per-instrument tracks (OOS test split)

Incumbent bar = **+0.328R** (production realized expectancy). Baselines recomputed per split (near-chance, as expected).

| Instrument | N test | baseline AUC | path ΔAUC | best relabel AUC | best regime (AUC / mean rr) | inst PASS |
|---|---|---|---|---|---|---|
| BNBUSDT | 30,000 | 0.5226 | +0.0012 | mfe_positive=0.6259 | VOLATILE_REVERSAL (0.5731 / +0.154R) | no |
| SOLUSDT | 30,000 | 0.525 | +0.0007 | first_tp=0.6462 | VOLATILE_REVERSAL (0.5691 / +0.039R) | no |
| ETHUSDT | 30,000 | 0.5181 | -0.0005 | first_tp=0.6301 | BREAKOUT_CONTINUATION (0.5297 / +0.098R) | no |
| BTCUSDT | 30,000 | 0.5304 | -0.0007 | first_tp=0.6719 | BREAKOUT_CONTINUATION (0.561 / +0.091R) | no |

## Full-economics panel — every track must beat the incumbent on net rr

AUC clears the *statistical* floor; the **economic** floor is the net-rr of the best top-by-model slice (N ≥ floor) vs the incumbent +0.328R. A track PASSES only if BOTH clear.

| Instrument | track | AUC | ΔAUC | stat? | selected net rr | sel N | econ? | PASS |
|---|---|---|---|---|---|---|---|---|
| BNBUSDT | path | 0.5238 | +0.0012 | n | +0.1611R | 300 | n | no |
| BNBUSDT | regime:VOLATILE_REVERSAL | 0.5731 | +0.0505 | Y | +0.1539R | 263 | n | no |
| BNBUSDT | relabel:mfe_positive | 0.6259 | +0.1259 | Y | -0.0839R | 3,000 | n | no |
| SOLUSDT | path | 0.5257 | +0.0007 | n | +0.1297R | 300 | n | no |
| SOLUSDT | regime:VOLATILE_REVERSAL | 0.5691 | +0.0441 | Y | +0.0389R | 279 | n | no |
| SOLUSDT | relabel:first_tp | 0.6462 | +0.1462 | Y | +0.0698R | 600 | n | no |
| ETHUSDT | path | 0.5176 | -0.0005 | n | +0.2664R | 300 | n | no |
| ETHUSDT | regime:BREAKOUT_CONTINUATION | 0.5297 | +0.0116 | n | +0.0977R | 2,378 | n | no |
| ETHUSDT | relabel:first_tp | 0.6301 | +0.1301 | Y | +0.1656R | 300 | n | no |
| BTCUSDT | path | 0.5297 | -0.0007 | n | +0.1743R | 600 | n | no |
| BTCUSDT | regime:BREAKOUT_CONTINUATION | 0.561 | +0.0306 | Y | +0.0912R | 2,661 | n | no |
| BTCUSDT | relabel:first_tp | 0.6719 | +0.1719 | Y | +0.1704R | 300 | n | no |

> The relabel track's high AUC (mfe_positive / first_tp) is **label leakage**: those targets are partly mechanical functions of `atr`, which is itself an input feature — the `survival` relabel (not ATR-tied) stays at chance. High relabel AUC therefore does NOT survive the economic translation (it cannot *select* net-rr above the incumbent).

## §8 — Expected Maximum Upside (AUC → ROI; ΔAUC ≠ ΔROI)

ROI ≈ N × R̄ × risk% anchored to baseline (PF 1.79, R̄ +0.328R, N≈35). The AUC→R̄ map is a conservative order-of-magnitude proxy (stated in code).

| Scenario | ΔAUC | Expected ROI delta (pp) |
|---|---|---|
| Conservative | +0.03 | +0.420 |
| Base | +0.06 | +0.840 |
| Optimistic | +0.09 | +1.260 |

Realized best ΔAUC = **+0.0505** → est. ROI delta **+0.707pp**. Migration cost = `TBD (operator input)`. Economic floor clears: **False**.

> **Decision coupling:** funding requires BOTH the statistical floor (§7 ΔAUC ≥ 0.03) AND the economic floor (upside > migration cost). Statistical-pass + economic-fail = do not fund.

## Method & caveats

- **No lookahead:** temporal 70/30 split (sort by timestamp, no shuffle); inverse-std standardization, KMeans clusters, and per-cluster path-stats are all fit on TRAIN ONLY; TEST rows are assigned to train-derived clusters.
- **Path-stats train-only:** definitions mirror `ReplayMemoryEngine._build_cluster_stats` (win_rate, mean_rr, drawdown, stability, failure/trap freq, transition, entropy); computed inline rather than via the engine to avoid leaking test rows into cluster stats.
- **Label honesty:** path & regime tracks compare to the same `win` baseline; the relabel track is judged in absolute terms vs 0.5 (a different target, not a ΔAUC vs `win`).
- **Measure-only:** per-candle scanner opportunities (not executed trades); reproduces the known near-chance per-candle result. Deterministic (seed 1337).
- **ROI proxy:** the AUC→R̄ slope is an explicit conservative assumption; the realized number is indicative, not a promise. Migration cost is operator-supplied.
