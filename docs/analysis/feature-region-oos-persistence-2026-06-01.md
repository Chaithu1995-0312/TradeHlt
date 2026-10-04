# Part 4A — Feature-region OOS persistence (BNBUSDT M15, 2026-06-01)

> Point-in-time analysis (NOT living). Measure-only. Driver: `scripts/research/feature_region_oos_study.py`
> Data: `logs/BNBUSDT/20260530_011521/opportunities.jsonl` (139,942 records, unbiased scan, tp=2×/sl=1× ATR).
> Method: temporal 70/30 split (no shuffle) → `discover_zones.discover()` on train → assign test to nearest
> `center` (weighted-Euclidean, reusing `_vector_from_record`; ForwardTester + `_assign_cluster` bypassed) →
> per-zone `retention = test_avg_rr / train_avg_rr`. Tiers: Strong≥0.80 / Usable0.60–0.80 / Weak0.40–0.60 /
> Collapse<0.40 (zones with `train_rr>0` and `test_n≥20`).

## Question

Do CRT candle-geometry feature regions carry **persistent** edge out-of-sample, or are profitable-looking
regions in-sample coincidence? (Determines whether the Probability-Surface→Fusion branch is real — Part 4B.)

## Methodology finding (load-bearing)

The first run used **equal feature weights**. `CANONICAL_FEATURES[0:5]` are raw OHLCV (BNB close ~$600) +
volume — O(100s–1000s) — while geometry features (`body_ratio`, `retest_depth`, …) are O(0–1). Equal-weight
Euclidean K-Means is therefore **dominated by price/volume scale**: the zones are price-era bands, not
geometry clusters. That run gave a misleading mix (the highest-train-RR zone collapsed OOS). **Fix:**
inverse-std feature weights computed on train only (`--normalize`, default) ≈ standardization → geometry
drives the clustering. Both runs are reported; **the normalized run is authoritative.**

## Results

**Normalized (authoritative)** — n=139,942 (train 97,959 / test 41,983), 8 zones, 2 gated:
| zone | train_n | train_rr | tp% | test_n | test_rr | retention | tier |
|---|---|---|---|---|---|---|---|
| 3 | 7,788 | +0.022 | 2% | 2,348 | +0.033 | **1.51** | Strong |
| 0 | 9,240 | +0.042 | 2% | 3,080 | +0.039 | **0.93** | Strong |
| 1,2,4,5,6,7 | (bulk) | −0.018…−0.069 | 1% | — | neg | — | insufficient (train_rr<0) |
- tier trade-counts: **Strong 5,428 / Usable 0 / Weak 0 / Collapse 0** · persist_share **1.0**.

**Equal-weight (diagnostic, price-dominated):** 3 gated — zones 1 & 3 Strong (ret 1.94/1.32) but zone 0
**Collapsed** (0.150→0.007, ret 0.04). The collapse was an artifact of price-scale clustering; it disappears
under normalization.

## Verdict — QUALIFIED YES (persistence is real; magnitude is marginal)

- **Persistence is REAL, not coincidence.** Under geometry-driven clustering, *both* train-profitable regions
  retain positive expectancy OOS on large test samples (retention 0.93–1.51, test_n 2.3k–3.1k, **no collapse**).
  The profitable zones also have 2× the TP rate (2% vs 1%) of the negative mass — a genuine, persistent
  quality gradient.
- **But the edge is economically marginal in the raw universe.** The persistent expectancy is ~+0.02–0.04R
  with ~2% TP-at-2:1; the bulk of the feature space (6/8 zones, ~80k samples) is persistently *negative*.
  Feature geometry separates better-from-worse, but the absolute raw edge is small.

## Implications for Part 4B

- **"Are feature regions real?" → YES** (tiered: Strong, no Collapse). The Probability-Surface branch is
  **not** a dead end — feature regions carry persistent structure worth consuming as an **advisory** signal
  (uncertainty-band tie-break), where even a small persistent gradient can help.
- **Two hard preconditions before any Fusion wiring (frozen Schema-Consistency-Before-Fusion invariant):**
  1. **Per-instrument confirmation** — this is BNBUSDT-only (n=1). Re-run for SOLUSDT/ETHUSDT/BTCUSDT
     (needs `opportunity_scanner` first; no existing opps). The session sweep proved instruments differ.
  2. **ReplayMemory schema repair** — `center`↔`centroid` + weighting + correct registry + assignment/replay
     tests (the RME forensic audit). The OOS harness here is self-contained and does **not** validate RME.
- **Magnitude caveat:** because the raw edge is marginal, the surface should enter as a low-weight advisory
  input (`weight_*` small, 0.0 default) and be measured additively (the proven Phase-6 ROI pattern), never
  as a primary gate.

## Per-instrument confirmation (2026-06-02) — GENERALIZES

Ran the same normalized harness on SOL/ETH/BTC (fresh `opportunity_scanner` data, tp2×/sl1×, n=139,942 each):

| instrument | gated zones | persist_share | Strong trades | profitable zones — train→test RR (retention) |
|---|---|---|---|---|
| BNBUSDT | 2/8 | 1.0 | 5,428 | +0.022→+0.033 (1.51); +0.042→+0.039 (0.93) |
| SOLUSDT | 2/8 | 1.0 | 3,646 | +0.038→+0.075 (1.96); +0.023→+0.032 (1.36) |
| ETHUSDT | 2/8 | 1.0 | 5,098 | +0.051→+0.074 (1.46); +0.071→+0.090 (1.27) |
| BTCUSDT | 2/8 | 1.0 | 5,614 | +0.087→+0.091 (1.05); +0.076→+0.077 (1.01) |

**Generalizes: 4/4 instruments, zero collapses, every train-profitable region persists OOS.** Edge magnitude
*grows* from BNB (+0.02–0.04R) to BTC (+0.08–0.09R). The Probability-Surface branch is **not a BNB curiosity**.

**Honest caveats (do not over-read):**
- `persist_share=1.0` is **conditioned on train-profitability** — it means "of the ~2/8 train-profitable
  zones, all persist," NOT "the feature space is profitable." ~6/8 zones (the bulk of samples) are
  persistently *negative*. The signal is a small, durable *gradient*, not a broadly profitable space.
- The cross-instrument uniformity (always 2/8, always zones 0 & 3, persist exactly 1.0) is partly an
  artifact of fixed-seed (1337) K-Means + identical scanner data geometry → similar cluster structure.
  The *substantive* finding is persistence + no collapse, not the exact zone IDs.
- Magnitude still **marginal** (≤ +0.09R, ~2–3% TP at 2:1) in the raw unbiased universe.

## Verdict (final)

**QUALIFIED YES — confirmed across 4 instruments.** Feature-geometry regions carry a small but genuinely
persistent, cross-instrument edge gradient. The Probability-Surface→Fusion branch is a **serious low-weight
advisory candidate** (never a primary gate; enter at small/0.0-default weight, measured additively).

**Part 4B preconditions:** #1 per-instrument confirmation **✅ now satisfied (4/4)**. #2 **ReplayMemory schema
repair remains the sole blocking precondition** before any Fusion wiring (frozen Schema-Consistency-Before-Fusion
invariant). Magnitude is marginal, so wiring is worth doing **only** after the RME repair + as an additive,
low-weight, measure-first experiment.
