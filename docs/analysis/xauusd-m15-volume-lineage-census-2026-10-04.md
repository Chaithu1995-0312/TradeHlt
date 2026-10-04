# XAUUSD M15 volume lineage census — MT5 terminal → research corpus → live rail → GateIntelligence (2026-10-04)

> Point-in-time, read-only data-lineage census. Nothing was repaired; no code or config was changed.
> Extends F-099 (BC-4, `TICK_VOLUME_APPROXIMATE`) and gives F-113 (inert gate liquidity) its data
> lineage. The scratch probes `mt5_volume_census.py` and `mt5_volume_monthly.py` used MetaTrader5
> 5.0.6180 under `.venv` (the only interpreter with the package). They made no login, no
> `symbol_select`, and no repo writes.

## 1. What the live MT5 terminal supplies (latest completed month)
The terminal identifies as MetaTrader 5 build 6230, connected; the symbol is
`Commodities\Metals\XAUUSD`, digits 2. The broker/server identity was not read, so producer-family
match stays UNVERIFIED, as in F-098. The window is the broker-labelled clock `[2026-09-01, 2026-10-01)`.
MT5 `time` is the bar OPEN (F-098), on broker-server time stored as UTC (F-066). The server clock at
fetch time was 2026-10-02 23:56 broker-labelled, so September is complete.

| Field | Result |
|---|---|
| bars | 2,014: first 2026-09-01 01:00, last 2026-09-30 23:45; 22 trading days, 82–92 bars/day |
| timestamp alignment | 2,014/2,014 on the 15-min grid; 0 duplicates, 0 non-monotonic |
| gaps ≠ 15 min | 16 × 75 min (daily 23:45 → 01:00 break), 4 × weekends, 1 × 225 min |
| session open | 22/22 days open at 01:00 broker (as F-080 measured) |
| `tick_volume` | **non-zero on 2,014/2,014**; min 682, median 6,728, max 50,342 |
| `real_volume` | **0 on 2,014/2,014** (the symbol reports `volume_real 0.0`) |
| `spread` | non-zero on 2,009/2,014, median 5 points |

## 2. Research corpus vs the terminal
`data/mt5/XAUUSD_M15.csv` has 47,275 rows, 2024-05-22 01:00 → 2026-05-21 23:45, all with
non-zero `volume`. The writer is `src/inout/mt5_candle_fetcher.py:198`
(`"volume": int(r["tick_volume"])`).

I re-fetched the whole corpus window from the terminal and compared it bar by bar:
- **47,275/47,275 timestamps match**, with 0 extra rows on either side.
- **OHLC is exact on 47,275/47,275.**
- **`volume == tick_volume` on 47,275/47,275**; `volume == real_volume` on 0.

This extends F-099's `artifact_binding` from 17/17 sampled bars to the full corpus. The corpus
volume column *is* MT5 `tick_volume`, which F-099 measured as `TICK_VOLUME_APPROXIMATE`: about 0.6%
from independently counted ticks, and not traded volume.

**The level is not stationary.** Monthly median `tick_volume` (terminal; equal to the corpus in every
fully covered month):

| Period | Median `tick_volume` |
|---|---|
| 2024-06 … 2025-09 | about 1,300 – 2,000 |
| 2025-10 | 2,594 |
| 2026-01 | 2,687 |
| 2026-03 | 3,050 |
| 2026-04 | 3,998 |
| 2026-05 | 5,654 |
| 2026-06 | 6,222 |
| 2026-09 | 6,728 |

This is a trend that crosses the corpus end, not a step at it. Ratio features (`volume_ratio` =
volume / rolling mean) are scale-free against it; any absolute volume threshold is not. Spread median is 5 points in most months. It was 6–9 in seven months: 9 in 2024-12; 7 in 2025-01,
2025-02, 2025-03 and 2025-11; 6 in 2025-04 and 2026-02.

## 3. Does the production path preserve volume?
Traced at source, not executed end to end:

1. **Live-rail bar source: there is no MT5 bar source.**
   - `DataVenue.MT5_CANDLES` builds no port (`src/inout/live_rail/factory.py:23-24` returns `None`),
     and nothing calls `ingest_closed_bar` with MT5 candles.
   - The only XAUUSD live-rail spec is the TickDB paper config
     (`configs/experimental/spec/live_rail_tickdb_paper*.json`, `volume_mode: sum_size`).
     `BarBuilder` sums tick `size` there (`bar_builder.py:82-85`), and the TickDB adapter uses 0.0 on
     quote ticks (`tickdb_adapter.py:105`).
   - Whether TickDB XAUUSD bars carry traded size, quote zeros, or something else is **UNVERIFIED**.
     No recorded TickDB bar volumes exist: `results/live_rail_paper_20260916_212321` replayed
     *corpus* bars (Arm A), so it carries `tick_volume`.
   - If TickDB volume were all zero, the pipeline's dead-volume branch would set
     `volume_ratio = 1.0` on every bar (`feature_pipeline.py:545-569`).
   - So the live rail's volume semantics are **not established to equal** the research corpus's MT5
     `tick_volume`.
2. **`LiveRailFeeder` → `FeaturePipeline`.** Bar `volume` is passed through
   (`live_rail_feeder.py:155`). The pipeline computes `volume_ma20` (rolling,
   `feature_pipeline.volume_ma_window`) and the canonical `volume_ratio = volume / volume_ma20`
   (`feature_pipeline.py:563-568`). `build_features` returns exactly the 48 canonical keys:
   `volume_ratio` is among them; `volume_ma20` is not.
3. **`live_engine_hook` → `FeatureStore`.**
   - `_build_ohlcv_and_auxiliary` requires `volume` (`:561`) and `volume_ratio` (`:614`, strict).
   - `FeatureStore._merge_inputs` keeps both (`feature_store.py:129-134`). Its silent
     `volume_ratio = 1.0` fallback (`:108-109`) is not reachable on this path, because the hook
     requires the key first.
4. **Planner → GateIntelligence.**
   - The planner receives that dict. `_liquidity_score` reads `volume` (present) and `volume_ma20`
     (absent, default 0.0), so `vol_score = 0` (F-113 / SEM-004).
   - The quantity the gate wants, `volume / volume_ma20`, **already exists canonically as
     `volume_ratio` in the same dict, and the gate never reads it.**
   - `real_volume` is never read anywhere on the path, and is 0 at the source anyway.

## 4. Summary

| Question | Answer |
|---|---|
| Does the terminal supply `tick_volume`? | Yes. Non-zero on 100% of September bars and on every corpus bar. |
| Does it supply `real_volume`? | No. 0 on every bar in both windows; the symbol reports `volume_real 0`. |
| Timestamp alignment | Exact 15-min grid, bar-open labels, 01:00 broker session open, daily 75-min break. Corpus and terminal agree bar for bar. |
| What is the corpus `volume` field? | MT5 `tick_volume`, bound on 47,275/47,275 bars (F-099 `TICK_VOLUME_APPROXIMATE`). Its level rises about 3–5× from mid-2025 to Sep 2026. |
| Does the production path preserve it? | Yes as far as `volume` and the canonical `volume_ratio` reaching the gate, **if** the bar source supplies MT5-like volume. No MT5 bar source exists on the live rail; the configured TickDB source's volume is UNVERIFIED. |
| Why is the gate's volume half still 0? | The gate reads the non-canonical `volume_ma20`, which the path never carries, instead of the canonical `volume_ratio`, which it does. |

Closures (§6.8):
- Terminal and corpus volume: ALIGNED (F-099 extended, not changed).
- No MT5 live bar port: DORMANT BUT VALID / known scope (F-073).
- TickDB volume semantics: INSUFFICIENT EVIDENCE.
- The gate reads `volume_ma20` while `volume_ratio` is present: CONFIRMED DEFECT of consumer wiring,
  already F-113. Whether to wire it is a separate question, and F-113's outcome test found no stable
  information in the volume half.
