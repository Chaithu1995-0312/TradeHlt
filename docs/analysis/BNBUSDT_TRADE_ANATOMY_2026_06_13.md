# BNBUSDT Trade Anatomy — Measurement Layer (2026-06-13)

> **Point-in-time study** (history, not a living doc — `docs/analysis/`). Measure-only; sits
> *underneath* F-019/020/021 and Phase D. It **explains behavior, it does not optimize it.** No
> tuning, no edge-search. Cost basis: gross + net, **headline NET 12 bps** round-trip.
>
> **Reproduce:** `python scripts/analysis/bnbusdt_trade_anatomy.py`
> **Primary artifact:** `results/research/bnbusdt_trade_anatomy/trade_dataset_BNBUSDT.csv`
> (139,942 rows) — the canonical substrate for survival / clustering / time-decay / future ML.
> **Aggregates:** `results/research/bnbusdt_trade_anatomy/anatomy_summary.json`.

---

## 0. Recovered vs Derived (stated first, per mandate)

| Layer | Field | Source | Status |
|---|---|---|---|
| **Recovered** | timestamp, direction, entry/sl/tp | `logs/BNBUSDT/20260530_011521/opportunities.jsonl` (139,943 lines) | trusted |
| **Recovered** | 38-dim feature vector | same (`features{}`) | trusted |
| **Recovered** | `art_outcome`, `art_rr`, `art_mfe`, `art_mae` | same | ⚠️ **UNRELIABLE — kept as flagged x-ref only** (see §1) |
| **Recovered** | bitnet_score, pnl_rr_net, costs (spine) | `results/research/bnbusdt_authoritative/run_20260613_025416_BNBUSDT/BNBUSDT_trades.csv` (`v2_multi_2026_04`, 13 trades) | trusted, low-N |
| **Derived** | realized `outcome`/`rr`/`mfe`/`mae`/`duration` | **governing** `forward_walk(intrabar_fixed)` over `data/BNBUSDT_M15.csv` (70,081 bars) — reuse `src/research/measurement/forward_walk.py` | trusted |
| **Derived** | `return_15/30/45/60/90m` (gross+net) | close-delta, 1/2/3/4/6 M15 bars fwd | trusted (spot-checked) |
| **Derived** | `time_to_peak`, `time_to_bottom`, `mfe_r`/`mae_r`/`reached_Nr` | inline + reuse `horizon_excursion()` | trusted |
| **Derived** | `capture_ratio`, `giveback` | governing realized ÷ governing MFE | trusted |

Verification: returns reconcile to raw candles (3×2 spot-checks); 139,942 rows; net<gross on all
horizons (0 violations); no-lookahead guard never tripped.

---

## 1. ⚠️ TruthConflict (the most important finding) — artifact labels are not realized exits

`opportunities.jsonl` is a **detection feed**, not a trade ledger. Its `outcome`/`rr_achieved` are
**internally inconsistent**: 91,126 rows are labeled `SL_HIT` while their own `mae` never reaches
the stop (a short with `sl` above entry, `mae` only −0.4 on a 1.5 risk, yet `SL_HIT`,
`rr_achieved=0.1`). **Only 36.8% of rows are self-consistent.**

| Outcome | Artifact (as logged) | Governing `forward_walk(intrabar_fixed)` |
|---|---|---|
| SL_HIT | 138,091 (98.7%) | 91,914 (65.7%) |
| TP_HIT | 1,830 (1.3%) | 46,580 (33.3%) |
| TIMEOUT | 21 | 1,448 |

**Resolution (per Repository Truth doctrine — detect drift, don't silently consume):** every
realized metric in this study is **derived** via the governing intrabar-fixed exit; the artifact's
own outcome/rr/mfe/mae are retained in the dataset as `art_*` columns for traceability **only**.
This does **not** revive any finding — it is a data-provenance correction at the measurement layer.

---

## 2. The five questions (user-prioritized)

1. **When do winners peak?** *(de-censored — supersedes the Phase-1 censored "~22 bars / 5.5 h.")*
   Two metrics, kept separate (`PEAK_HORIZON=96`, realized layer held at 40):
   - **Within-trade peak** (the honest one, bounded by the realized exit): **winners median 6 bars
     (~90 min)**, p90 = 18; **losers median 1 bar**, p90 = 6. Winners mature over ~90 min — *not* 5.5 h.
   - **Exit-agnostic path peak** is a **random walk** and carries no information: winners p50 = 46 ≈
     losers p50 = 43, p90 pinned at 92/96 (still censored). The earlier "22 bars" was a 40-bar-window
     artifact — the de-censoring corrected it. See **F-024**.
2. **Do winners continue after peak, or give back?** Under the **TP-capped governing exit**, winners
   harvest **median 85% of their MFE** (`capture_ratio_winners = 0.85`) — they do *not* give back,
   because the exit fires at TP near the favorable extreme. (Pool-wide median capture is −0.92,
   dominated by the 66% losers.)
3. **What % of MFE is harvested?** Winners ~85%; pooled median negative (losers realize below a
   positive MFE); pooled `giveback` median = 1.92 (>1 ⇒ realized typically negative vs a positive peak).
4. **Do losers die immediately or after decay?** **Fast.** Survival `P(not stopped by bar k)`:
   0.87 (15m) → 0.59 (60m) → **0.51 (90m)** → 0.36 (6 h). ~Half are stopped within 90 minutes; their
   within-trade favorable peak is **median bar 1** — they resolve almost immediately. See **F-024**.
5. **Distinct morphologies?** **No expectancy separation.** KMeans (k=4) on standardized
   ema_spread/volume/vol/body/momentum/trend/disp/retest/atr splits feature space cleanly but every
   cluster has win_rate ≈ 0.33–0.34 and mean_R ≈ 0.00 ± 0.02. **Clusters are morphology, not edge.**

---

## 3. Required outputs

| # | Output | Value (governing, headline net 12 bps) |
|---|---|---|
| 1 | **Total** | 139,942 detection opportunities (≠ tradeable count); governed spine = **13** trades |
| 2 | **Avg monthly opportunity count** | **~5,851 / month** (192/day · 1,346/week · ~70,211/year), 728-day span 2024-05-23 → 2026-05-21 |
| 3 | **Avg MFE & MAE** | governing MFE mean **+3.37** / MAE mean **−2.91** price units; MFE_r median 2.78 |
| 4 | **Median time-to-peak** | *(de-censored)* within-trade: winners **6 bars (~90 min)**, losers **1 bar**; exit-agnostic path peak is random-walk/uninformative (winners≈losers ≈44–46, p90 pinned at cap). See F-024. |
| 5 | **Recommended holding duration** | **None is profitable.** Fixed-time exits: mean_R ≈ **0.00 gross / −0.43 net** at *every* 15/30/45/60/90m. "Best net" (90m) is still −0.428R. |
| 6 | **Top feature clusters** | 4 morphologies, all win_rate ≈ 0.34 / mean_R ≈ 0 — **descriptive only** |
| 7 | **Failure modes** | (a) directional coin-flip (P(next-bar>0) ≈ 0.495); (b) fast stop-outs (½ within 90m); (c) 12 bps cost flips a ~0 gross edge to −0.43R net |
| 8 | **Confidence** | **Certain** on null edge (N=139,942, governing exit, reconciles F-019/020/021) and on the artifact-integrity defect (**F-022**); **Likely** on morphology-≠-expectancy (**F-023**) and the de-censored timing asymmetry (**F-024**) |
| 9 | **Final recommendation** | Treat `trade_dataset_BNBUSDT.csv` as the canonical substrate. **Do not** pursue hold-time, session, or feature-cluster levers on BNBUSDT — all null under intrabar+12bps. Redirect to exit/cost structure (Phase D), consistent with the standing falsifications. |

---

## 4. Behavior detail

**Frequency is *anatomy*, not opportunity count.** The 139,942 are unfiltered detections (the
governing spine takes **13**). Cadence is roughly uniform across sessions (NEWYORK 46,656 · ASIA
40,800 · LONDON 34,992 · OFF 17,494) and across the three volatility-regime bands (~46k each) — i.e.
**detection density carries no session/regime concentration that survives to expectancy.**

**Time decay.** `P(return_Nm > 0)` gross is flat at **0.494–0.498** for every horizon — a random
walk; net (12 bps) sinks to 0.26 → 0.39 as the horizon grows (cost amortizes, direction never
improves). Continuation edge is gone by the first bar.

**Duration ↔ expectancy is survivorship, not a lever.** mean_R rises monotonically by holding
bucket (0–30m −0.46 → 180m+ +0.48), but this is **conditioning on survival** — trades that lasted
longer are *definitionally* those that didn't stop early. It is **not** ex-ante actionable and must
not be read as "hold longer to win."

**Spine grain (illustrative only, N=13).** Active `v2_multi_2026_04`; far too few for clustering or
score-distribution claims. Reported for traceability, never load-bearing.

---

## 5. How this connects to standing truth

Reconfirms at fine grain — does **not** overturn or revive anything:
- **F-019/020/021:** no promotable BNBUSDT edge; direction null incl. conditional; selection ≡
  session. This study adds the *anatomy*: null is visible at the single-opportunity level (coin-flip
  direction, 0 gross fixed-exit expectancy, expectancy-flat clusters).
- **F-002 (stale):** feature→outcome map — clusters separate features but not expectancy. Consistent
  with F-002 being stale.
- **exit_model_adoption / Backtest Trust Layer:** governing exit = intrabar_fixed; the artifact's
  inconsistent labels are exactly the kind of optimistic divergence the Trust Layer warns about.

**Biggest failure mode actively avoided:** interpreting a descriptive cluster (or the survivorship
duration gradient) as a predictive edge. Neither is.

### Findings elevated from this study (test-enforced ledger)
- **F-022 (GOVERNANCE, Certain)** — `opportunities.jsonl` is a detection stream, not a trade ledger
  (36.8% self-consistent); realized truth must be derived via the governing exit; frequency illusion
  (139,942 detections ≠ trades; spine = 13).
- **F-023 (ECONOMIC, Likely)** — feature morphology separates shape, not expectancy (kills "cluster harder").
- **F-024 (ECONOMIC, Likely)** — de-censored timing asymmetry: losers resolve ~immediately
  (within-trade peak median 1 bar), winners mature over ~90 min (median 6 / p90 18 bars); the
  exit-agnostic path peak is random-walk/uninformative. The Phase-1 "~22 bars / 5.5 h" was a window
  artifact, corrected by the `PEAK_HORIZON=96` run.

### Cost-domination — corroborates existing **F-025** (exit-grid)
- Fixed-time-exit expectancy is ≈ **0 gross** but **−0.43R net** at *every* horizon ⇒ economics are
  **cost-dominated, not signal-dominated**. This is the conclusion the existing **F-025** (exit/cost
  is a risk/cost lever, not expectancy) already owns — so it is **corroboration, not a new finding.**
  *(Correction: an earlier draft mislabelled this an "F-025 candidate / watch" — that was an id
  collision; F-025 was already taken by the Phase-D exit-grid finding.)* Cross-instrument confirmation
  (BNB/BTC/ETH/SOL, gross≈0 / net<0 on all): docs/analysis/cross-instrument-anatomy-2026-06-13.md.
