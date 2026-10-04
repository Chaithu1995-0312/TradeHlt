# Part 4A (multi-instrument) — Feature-region OOS persistence generalizes (BNB/SOL/ETH/BTC, 2026-06-02)

> Point-in-time analysis (NOT living). Measure-only. Driver: `scripts/research/feature_region_oos_study.py`
> Supersedes the n=1 verdict in [`feature-region-oos-persistence-2026-06-01.md`](feature-region-oos-persistence-2026-06-01.md)
> (BNBUSDT-only). Method unchanged: temporal 70/30 split → `discover_zones.discover()` (inverse-std
> `--normalize` weights, train-only) → assign test to nearest train `center` (weighted-Euclidean) →
> per-zone `retention = test_avg_rr / train_avg_rr`. Tiers: Strong≥0.80 / Usable0.60–0.80 /
> Weak0.40–0.60 / Collapse<0.40 (gated on `train_rr>0` and `test_n≥20`).
> Artifacts: `results/feature_region_oos/{BNB,SOL,ETH,BTC}USDT_oos.json`.

## Question

Does the candle-geometry feature-region persistence found on BNBUSDT (Part 4A, n=1) **generalize
across instruments**? This is ReplayMemory advisory **precondition #1** (the per-instrument
confirmation the BNBUSDT study explicitly deferred).

## Results — all four instruments persist (n=139,942 each; train 97,959 / test 41,983; 8 zones, 2 gated)

| instrument | top zone (ret · test_n) | 2nd zone (ret · test_n) | tier mix | persist_share | collapse? |
|---|---|---|---|---|---|
| **BNBUSDT** | zone 3 — **1.51** · 2,348 | zone 0 — **0.93** · 3,080 | Strong 5,428 | **1.0** | none |
| **SOLUSDT** | zone 0 — **1.96** · 1,496 | zone 3 — **1.36** · 2,150 | Strong 3,646 | **1.0** | none |
| **ETHUSDT** | zone 3 — **1.46** · 2,396 | zone 0 — **1.27** · 2,702 | Strong 5,098 | **1.0** | none |
| **BTCUSDT** | zone 0 — **1.05** · 3,044 | zone 3 — **1.01** · 2,570 | Strong 5,614 | **1.0** | none |

In every case: exactly **2 of 8 zones** carry `train_rr>0`, **both retain positive expectancy OOS**
on large test samples (test_n 1.5k–3.1k), `persist_share = 1.0`, and **zero Collapse**. The
remaining 6 zones (~80k samples) are persistently negative — the same better-from-worse quality
gradient seen on BNBUSDT, reproduced on all four.

## Verdict — QUALIFIED YES generalizes (n=4)

- **Persistence is real and instrument-general.** Under geometry-driven (inverse-std) clustering,
  the train-profitable feature regions retain positive expectancy out-of-sample on **every** tested
  instrument — not a BNBUSDT artifact. The retention ranges from marginal (BTC ~1.0) to strong
  (SOL 1.96), but is **never** a collapse.
- **Magnitude remains economically marginal** (~+0.02–0.09R test_rr in the raw universe; the bulk
  of the feature space is persistently negative). This is a *better-from-worse* separator, not a
  standalone edge — consistent with the n=1 finding.

## Implications

- **ReplayMemory advisory precondition #1 (per-instrument OOS confirmation): CLOSED.** Combined with
  precondition #2 (the 2026-06-02 RME schema/weighting repair — see [`../topics/replay-memory.md`](../topics/replay-memory.md)),
  both gates on the Probability-Surface→Fusion branch are now satisfied.
- Because the edge is marginal and varies in strength by instrument, the surface must enter as a
  **low-weight advisory** (weight 0.0 default, measured additively — the Phase-6 ROI pattern),
  **never a primary gate**, and **per-instrument** (the strength gradient differs: SOL ≫ BTC).
- This is the evidence base for backlog **#6 (does ReplayMemory earn advisory status)**.

## Caveats

- Same harness/window for all four (full 2-yr M15, tp=2× / sl=1× ATR opportunity scan). Not a live
  forward test; OOS = temporal hold-out, not future data.
- Retention is an expectancy ratio on the *gated* zones; it does not by itself prove tradeable ROI —
  it proves the geometry partition is **stable**, which is what the advisory consumes.
