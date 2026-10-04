# BNBUSDT Trade Anatomy — Measure-First (Existing-Data-First)

## Context

The user wants a **measurement-only** anatomy of BNBUSDT trades: frequency, MFE/MAE,
time-to-peak, hold-time expectancy, feature clusters (winners vs losers), failure modes, and a
materialized per-trade dataset. Explicit constraints: **do not optimize, do not tune, reuse
existing artifacts, only derive what is genuinely missing, and list recovered-vs-derived up front.**

This aligns with the repo's measure-only research doctrine and with standing findings
(F-019/020/021, `exit_model_adoption`, `session_sweep`): under intrabar + 12 bps costs BNBUSDT
shows no promotable edge. The job here is to **measure and report neutrally**, possibly
re-confirming those findings at finer grain — not to chase an edge.

Decisions locked with the user:
- **Population = Both grains.** Opportunities (~140k) own anatomy/clusters/time/MFE-MAE;
  governed spine (~13–15) owns real PnL/costs/scores. Each output answered at its best grain.
- **Cost basis = gross + net, headline net 12 bps.**

## What is RECOVERED from existing logs vs DERIVED (the mandate, stated first)

**Recovered (reused as-is — Priority 1):**
| Field | Source |
|---|---|
| timestamp, direction, entry, sl, tp | `logs/BNBUSDT/20260530_011521/opportunities.jsonl` (139,943 rows) |
| outcome, rr_achieved, duration_candles, **mfe, mae** | same |
| 38-dim feature vector (ema/atr/volume/body/momentum/regime/session/disp/retest…) | same (`features{}`) |
| realized PnL, costs (slippage/spread), `bitnet_score_at_entry`, session, exit_reason | `results/.../BNBUSDT_trades.csv` (governed spine, ~13–15 rows) |
| per-engine scores (gaussian/zone/rr/crt/fusion) | `logs/collector.jsonl` + `logs/archive/202605/BNBUSDT_fusion.jsonl` (join to spine grain only) |
| logged ENTRY/EXIT trades (~3,899) w/ pnl_rr_net, win | `logs/trade_lifecycle.jsonl` (secondary cross-check grain) |

**Derived (genuinely absent everywhere — Priority 2, from `data/BNBUSDT_M15.csv`, 70,081 bars):**
| Field | Method |
|---|---|
| `return_15/30/45/60/90m` (=1/2/3/4/6 M15 bars fwd) | close-delta from entry candle; gross + net 12 bps |
| `time_to_peak`, `time_to_bottom` | argmax/argmin favorable excursion bar within horizon |
| horizon excursion (mfe_r, reached_Nr, favorable_first, bars_to_first_1r) | **reuse** `horizon_excursion()` in `src/research/measurement/forward_walk.py` |
| fixed 15/30/45/60/90m exit expectancy | mark-to-close at each cap, gross + net 12 bps |
| `capture_ratio = realized_return / MFE` | recovered realized rr ÷ recovered mfe |

Nothing else is recomputed. opportunities.jsonl's own `mfe`/`mae` are trusted for realized values;
candle-walk is used ONLY for the horizon/time fields that no artifact stores.

## Deliverables

1. **`results/research/bnbusdt_trade_anatomy/trade_dataset_BNBUSDT.csv`** — one row per
   opportunity: timestamp, direction, entry, mfe, mae, time_to_peak, return_15/30/45/60/90m
   (gross+net), duration, outcome, regime, session, all 38 features, capture_ratio. Governed-trade
   columns (bitnet_score, costs, realized_pnl) joined where a spine trade matches by timestamp.
   *(pyarrow is absent → `.parquet` only emitted if user installs pyarrow; plan ships CSV as the
   guaranteed format and notes the one-line `pip install pyarrow` to add parquet.)*
2. **`docs/analysis/BNBUSDT_TRADE_ANATOMY_2026_06_13.md`** — point-in-time report (history lives
   in `docs/analysis/` per truth doctrine) answering all 9 outputs + the user's added sections,
   opening with the recovered-vs-derived table above and the honesty caveats.
3. CLAUDE.md mandates on execution: append `📝 SESSION LOG ENTRY` to `assistant_project.md`; if a
   durable belief lands (e.g. continuation decays by bar K), write a `project`/`feedback` memory
   file + index line, and add/flip a finding in `docs/current-findings.md` only if a prior
   conclusion is validated/overturned.

## Implementation

Single driver script: **`scripts/analysis/bnbusdt_trade_anatomy.py`** (thin analysis wrapper,
sibling of existing `scripts/analysis/generate_cli_matrix.py`; imports research primitives, writes
no production logic). Steps:

1. **Load candle index** from `data/BNBUSDT_M15.csv` → list of `Candle` + `timestamp→index` map.
2. **Stream opportunities.jsonl** (skip `run_header`); for each row build a `research.Signal`
   (`atr=|entry−sl|`, `sl_atr_mult=1.0`, `tp_atr_mult=|tp−entry|/atr`, `entry_index` via the map).
3. For each opportunity: recover mfe/mae/outcome/rr/features; **derive** return_Nm (gross+net),
   time_to_peak/bottom, and reuse `horizon_excursion()` for R-excursion/continuation primitives.
   No-lookahead is enforced by the primitive (raises on `bar.index ≤ entry_index`).
4. **Build dataframe** → write CSV (parquet if pyarrow present).
5. **Aggregations** (pandas/numpy/scipy):
   - *Frequency*: total + per day/week/month/year; split by hour/weekday/session/month/regime
     (opportunity grain) **and** governed-trade frequency (spine grain) — reported separately, never conflated.
   - *Time decay*: `P(return_Nm > 0)` for N∈{15,30,45,60,90}; time_to_peak median/mean/p90;
     median time_to_failure (survival of SL_HIT).
   - *Hold-time research*: expectancy (mean R) of fixed 15/30/45/60/90m exits, gross + net 12 bps;
     report which horizon maximizes net expectancy and where continuation edge decays.
   - *MFE capture efficiency*: capture_ratio distribution; "are winners peaking by 30–45m?", "does
     90m give back?", "what % of MFE is harvested?".
   - *Feature clusters (winners vs losers)*: standardize the listed features (ema_spread/slope,
     volume_ratio, atr/volatility_ratio, body_ratio, momentum_score, trend_strength, regime,
     session, disp_strength, retest_depth) → **sklearn KMeans** (sklearn 1.8 present) on the pooled
     set, then compare win-rate/expectancy per cluster (multivariate, not single-variable). Fallback
     to quantile cross-tabs only if a fit fails. Reuse `src/analytics/clustering.py` if its API fits;
     otherwise inline sklearn in the script.
6. **Cost model**: net = gross − 0.0012 round-trip (in price-fraction for return_Nm; in R as
   `0.0012·entry/risk_distance` for R metrics). Cost always reduces magnitude toward zero.

## The 9 required outputs (+ user additions) — all answered in the report

1 total trades · 2 avg monthly opportunity count · 3 avg MFE & MAE · 4 median time-to-peak ·
5 recommended holding duration (net-12bps expectancy max) · 6 top feature clusters ·
7 failure modes · 8 confidence level · 9 final recommendation. Plus: opportunity-frequency splits,
hold-time decay probabilities, MFE-capture efficiency, winners-vs-losers clusters, and the
materialized dataset.

## Honesty caveats baked into the report

- opportunities.jsonl is **unfiltered detection** (sampled ≈ 39,509 SL_HIT / 482 TP_HIT, fixed
  SL/TP touch, no costs) — **not** what the spine trades; opportunity frequency ≫ tradeable frequency.
- Engine/fusion scores exist only at the spine grain (~15 trades) → score-clusters are low-N and
  flagged as indicative only.
- Headline numbers are net 12 bps; gross shown alongside to expose where cost bites.
- Findings F-019/020/021 already establish no promotable BNBUSDT edge under intrabar+12bps; this
  measurement is reported as confirmation/anatomy, **not** a search for a lever. No tuning performed.

## Verification

- `python scripts/analysis/bnbusdt_trade_anatomy.py` runs clean; row count of CSV == non-header
  opportunity lines (139,942); no-lookahead assertion never trips.
- Spot-check: 3 random rows' return_Nm recomputed by hand from `data/BNBUSDT_M15.csv` match.
- mfe/mae columns equal the opportunities.jsonl source values (recovered, not recomputed).
- Sanity: P(return_Nm>0) monotonic-ish and capture_ratio ∈ plausible range; net < gross everywhere.
- Report opens with the recovered-vs-derived table and states confidence + final recommendation.

## Files

- **New:** `scripts/analysis/bnbusdt_trade_anatomy.py`,
  `results/research/bnbusdt_trade_anatomy/trade_dataset_BNBUSDT.csv`,
  `docs/analysis/BNBUSDT_TRADE_ANATOMY_2026_06_13.md`
- **Reused (read-only):** `src/research/measurement/forward_walk.py` (`horizon_excursion`),
  `src/research/contracts.py` (`Signal`/`Candle`), `src/analytics/clustering.py` (if API fits)
- **Appended:** `assistant_project.md` (session log); memory + `docs/current-findings.md` only if a
  durable belief is validated/overturned.
