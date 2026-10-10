# One day, one trade: how CRT-0007 earned +1.03R — XAUUSD H1, 2025-05-22

> **HYPOTHETICAL backtest, one trade.** This story explains mechanics and data. It is not evidence of an edge.
> **Selection disclosure:** I picked this day because it is the cleanest single-day chain that ends in a TP1 win (the sweep comes the evening before, 05-21 22:00). It is a winner, chosen for narrative clarity. It is not representative; the same method applies to a loser.
> **Provenance:** H1 file, `--htf 24`, engine with the EXECUTION rollover fix (commit `b4ecce2`). Engine values come from a read-only replay that wraps `CRTEngine.process_candle` and the engine loggers (`engine_trace.json`); the replay reproduces the committed trade row. Feature values are the committed `XAUUSD_trades.csv` row.

## 1. The day in bars

| H1 bar | O | H | L | C | State after bar | ATR(14) | What happened |
|---|---|---|---|---|---|---|---|
| 05-21 22:00 | 3314.38 | 3324.86 | 3314.38 | 3318.33 | **SWEEP** | 11.18 | High 3324.86 > range high 3320.55, close back below it → sweep of highs → **SHORT** |
| 05-21 23:00 → 05-22 10:00 | | | | | SWEEP | ~10–11 | 11 bars tried to become the displacement and failed (see §2.2) |
| 05-22 11:00 | 3327.65 | 3329.90 | 3310.24 | 3311.24 | **DISPLACEMENT** | 10.05 | Big bearish candle: body 0.835 of range |
| 05-22 12:00 | 3311.24 | 3313.89 | 3304.21 | 3304.82 | **EXPANSION** | 10.42 | Closes 6.42 below the displacement close |
| 05-22 13:00 | 3304.82 | 3307.48 | 3288.54 | 3289.68 | EXPANSION | 11.03 | Retest rejected: price too far from the range edge |
| 05-22 14:00 | 3289.66 | 3314.75 | 3283.03 | 3314.59 | **RETEST** | 12.82 | 31-pt bounce closes 5.96 under the range high; this close becomes the entry price |
| 05-22 15:00 | 3314.23 | 3314.56 | 3300.96 | 3304.13 | **EXECUTION** | 13.34 | Confirmation candle approved; short opened at 3314.59 |
| 05-22 16:00 | 3304.13 | 3315.80 | 3286.98 | 3287.78 | RESOLUTION → RANGE | 14.90 | Low 3286.98 ≤ TP1 3296.61 → **TP1 hit** |
| 05-22 17:00 | 3287.78 | 3304.57 | 3279.20 | 3297.09 | RANGE | 16.24 | Range rolled over (HTF-000246 → 000247) and reset |

## 2. The chain, step by step: threshold → value → verdict

### 2.1 Range and sweep (`RangeDetector`, `crt_engine_v2.py:396-494`)
- Reference range = high/low of the last 24 H1 bars (`htf_candles_per_range=24`): **L 3285.51, H 3320.55, size 35.04** (HTF-000246).
- Sweep of highs = `high > h_ref and close < h_ref`: 3324.86 > 3320.55 and 3318.33 < 3320.55. Overshoot 4.31, which later costs the sweep score (§2.4).

### 2.2 Displacement (`try_sweep_to_displacement`) — eleven misses, one hit
Three tests, all must pass: `|close−open| ≥ atr_min_displacement(1.2)·ATR`, `body_ratio ≥ body_ratio_min(0.70)`, bar range (named `wick_size`) `≥ atr_multiplier_min(1.5)·ATR`.
- 05-21 23:00 … 05-22 10:00: eleven rejections — ten on the move test (moves 1.2–6.1 vs the 1.2·ATR ≈ 11.5–13.7 needed), one (04:00, +14 pts) on body ratio 0.636 < 0.70.
- **05-22 11:00:** move 16.41 ≥ 12.06 ✓, body 0.835 ≥ 0.70 ✓, range 19.66 ≥ 15.07 ✓ → DISPLACEMENT.

### 2.3 Expansion and retest
- Expansion (12:00): bearish bar, close 3304.82 < displacement close 3311.24 ✓, distance 6.42 ≥ `expansion_atr_min_distance(0.2)·ATR` = 2.08 ✓.
- Retest, 13:00: **rejected.** Depth from the range high = 3320.55 − 3289.68 = 30.87 > ceiling 8.76 (`max(retest_depth_max(0.25)·35.04 = 8.76, 0.5·ATR = 5.51)`).
- Retest, 14:00: **accepted.** Depth = 3320.55 − 3314.59 = 5.96 ≤ 8.76, and ≥ `0.1·ATR`. In words: price swung down to 3283, then rallied to close just under the range high; the engine reads that as a "retest of the swept level".

### 2.4 Score (`UltronRiskEngine`, `crt_engine_v2.py:812-1020`) → entry approved on the 15:00 bar
Structural score **G = (0.35·sweep + 0.25·breakout + 0.20·retest + 0.20·time) × decay**:

| Component | Formula | Value |
|---|---|---|
| sweep | 0.6 base − min(overshoot/range, 0.2) = 0.6 − 4.31/35.04 | **0.477** |
| breakout | 0.5·body_ratio + 0.5·min(range/ATR/3, 1) = 0.5·0.835 + 0.5·(19.66/13.34/3) | **0.663** |
| retest | 1 − depth/ceiling = 1 − 5.96/8.76 | **0.320** |
| time | 0.8 (retest bar inside exactly one session window: NEWYORK 13–16 UTC) | **0.800** |
| decay | exp(−0.10 · 1 bar since retest) | **0.905** |
| **G** | (0.1670 + 0.1658 + 0.0640 + 0.1600) × 0.905 | **0.504** |

Confirmation **C = 0.428**: body 1.00 (15:00 bar body ratio 0.743 ≥ 0.6), momentum 0.17 (EMA2−EMA5 gap / ATR), distance 0.03 (Gaussian penalty for sitting 5.96 from the edge), displacement 0.82; weak-link penalty applied. Fusion **S = G^0.7 · C^0.3 = 0.479**. Tier 1 needs ≥ 0.75, tier 2 ≥ 0.30 → **tier 2 approval**. Range-position filter: entry 3314.59 is above the range midpoint 3303.03 → "premium zone" OK for a short.

### 2.5 Trade construction (`ExecutionEngine.build_trade`, `crt_engine_v2.py:1135-1236`)
- Entry (raw) = **retest bar close = 3314.59**.
- SL = displacement high + `sl_atr_buffer(0.2)`·ATR = 3329.90 + 0.2·13.336 = **3332.567** → 1R = **17.977**.
- TP1 = entry − 1R = **3296.613**; TP2 = entry − 2R = 3278.635.

### 2.6 From price to R (`TradeJournal`, `backtest_v2.py:710-836`)
| Step | Value |
|---|---|
| Entry fill = raw + slippage + half-spread | 3314.590 → **3314.797** |
| Size = 1% × capital ÷ |fill − SL| = 1,025.42 ÷ 17.771 | **57.70 units** |
| Exit raw (TP1) | 3296.613 → fill **3296.428** |
| Net move | 3314.797 − 3296.428 = **18.369** |
| **R (net) = 18.369 ÷ 17.771** | **+1.0337R** (raw +1.0116R) |
| Capital | 102,541.50 → 103,601.43 (**+1,059.93**) |

## 3. Feature schema at entry (the 35 `CANONICAL_FEATURES` for the 15:00 bar)

Values are from `FeaturePipeline` (the batch "Universe A"); the engine's own audit values (`live_*`, `cached_*`, "Universe B") follow in §3.2. ⚠ = the monitor should flag it (details in §4).

### 3.1 Canonical vector
| # | Feature | Value | Plain meaning |
|---|---|---|---|
| 1–5 | open, high, low, close, volume | 3314.23, 3314.56, 3300.96, 3304.13, 12,611 | The 15:00 bar itself ⚠ (F1) |
| 6 | volume_ratio | 1.62 | Volume vs its 20-bar average |
| 7 | double_sweep | 0 | Both sides swept in the window? No |
| 8–9 | ema_fast, ema_slow | 3312.73, 3314.63 | EMA9 / EMA21 of close |
| 10 | ema_spread | **−469.56** ⚠ | (fast − slow) ÷ `atr` where `atr` is ATR÷close (F4) |
| 11 | trend_bias | −1 | EMA fast below slow → bearish |
| 12 | trend_strength | −0.957 | 50-bar z-score of the 10-bar mean slope of MA20 |
| 13 | momentum_score | **−2,591.49** ⚠ | close change ÷ `atr` (fraction), so ≈250× too big (F4) |
| 14 | atr | 0.004036 | ATR(14) ÷ close = 0.4% (the engine's `live_atr` is 13.34 in price units) |
| 15 | volatility_ratio | 1.02 | Bar range ÷ ATR |
| 16 | rsi_14 | 44.14 | Neutral |
| 17–19 | macd_line, macd_signal, macd_hist | 1.70, 6.39, −1.65 | `hist` is a 50-bar z-score, so ≠ line − signal |
| 20–22 | sweep_detected, liquidity_sweep, break_of_structure | 0, 0, 0 | No sweep flagged **on this bar** (the sweep was 16 bars earlier) |
| 23–26 | swing_high, swing_low, higher_high, lower_low | 0, 0, 0, 0 | No new structure on this bar |
| 27 | body_size | 10.10 | |close − open| |
| 28 | wick_size | 13.60 | Actually high − low (the full bar range) |
| 29 | body_ratio | 0.743 | body ÷ range |
| 30 | volatility_regime | 2 ⚠ | High volatility: rank of ATR over the **entire file** (F5) |
| 31 | session | 1 ⚠ | Pipeline code: hour <8 → 0, <16 → 1, else 2 (F6) |
| 32 | hour_of_day | 15 | |
| 33 | disp_strength | 0.757 | body ÷ ATR of this bar |
| 34 | retest_depth | 0.645 | Pipeline version: |close − EMA9| ÷ ATR |
| 35 | candles_since_retest | 0 | |

### 3.2 Engine audit values (what the decision actually used)
| Column | Value | Meaning |
|---|---|---|
| live_atr | 13.336 | ATR(14) in price units; sizes SL (0.2 × this) |
| live_ema_fast / slow | 3304.61 / 3306.89 | EMA2 / EMA5 used in the momentum term of C |
| cached_retest_depth | 0.796 | Engine version: |retest close − disp open| ÷ disp move (**same name as #34, different formula**) |
| cached_body_ratio | 0.835 | Displacement bar's body ratio |
| cached_disp_strength | 1.533 | Displacement bar's range ÷ ATR (**same name as #33, different formula**) |
| cached_session / cached_double_sweep | UNKNOWN / 0 | ⚠ session never filled (F6) |

## 4. Monitor flags found while tracing this one trade
Each was checked in code, not assumed. Findings F1–F3 affect results, so they are listed first.

| ID | Finding | Evidence | Effect |
|---|---|---|---|
| **F1** | **One-bar lookahead on confirmation.** The 15:00 bar is evaluated in full (body ratio, EMA2/5 updated with its close) to decide the entry, yet the entry price is the **14:00 close = the 15:00 open**. A trade is only taken when the next bar already moved in its favor. | `crt_engine_v2.py:1519-1539` (`approve_with_soft_conf(self.state, candle)`; `entry_price = retest_candle.close`) | Biases win rate upward. Illustrative only, n=1: had CRT-0007 entered at the 15:00 *close* (3304.13) with the same SL, 1R = 28.44 and TP1 = 3275.69 — not reached in the next three bars (lows 3286.98, 3279.20, 3281.56). |
| **F2** | **Spread has the wrong sign on shorts.** Entry fill adds the half-spread and exit fill subtracts it for both directions, which is right for longs and favorable to shorts. | `backtest_v2.py:723, 794` (slippage is direction-aware, spread is not) | CRT-0007 shows net R **above** raw R (1.0337 vs 1.0116). Estimated from the trade rows (slippage unchanged): H1 htf=24 fixed run +2.35R → **+1.70R** (expectancy +0.18 → +0.13R); M15 fixed run +0.18R → **−1.48R** (expectancy +0.02 → **−0.15R**). The earlier validation "APPROVE, +0.037R" leaned on this. |
| **F3** | **TP2 is unreachable.** The engine moves to RESOLUTION at TP1 (the partial/runner logic is bypassed), so every TP1 win is booked as the full position at +1R. | `crt_engine_v2.py:1286-1300`, event `EXECUTION → RESOLUTION "Trade closed: TP1"` | TP2 hit rate is 0% in every run by construction; max win per trade ≈ +1R vs −1R loss. |
| F4 | `ema_spread` and `momentum_score` divide a **price** difference by `atr`, which is ATR **÷ close** | `feature_pipeline.py:384, 413, 419` | Values ~250× too large (−469.6 vs ≈ −0.14 ATR; −2,591 vs ≈ −0.78 ATR). Breaks z-scores and any model trained on them. |
| F5 | `volatility_regime` ranks ATR over the **whole file** (`rank(pct=True)`) | `feature_pipeline.py:274` | Non-causal: a bar's regime depends on future ATR values. |
| F6 | Session encoding disagrees: pipeline 0/1/2 by hour (comment "Asia=0, London=1, NY=2") vs `SESSION_MAP` (london 0, newyork 1, asian 2, overlap 3); `cached_session` is UNKNOWN | `feature_pipeline.py:294`, `feature_schema.py` `SESSION_MAP`, trade row | 15:00 is NY per the engine, but the vector's `1` means London by the pipeline's own comment. |
| F7 | Same names, different formulas: `disp_strength` 0.757 vs `cached_disp_strength` 1.533; `retest_depth` 0.645 vs 0.796 | §3.1 vs §3.2 | A monitor comparing them will see false drift. |
| F8 | EMAs are updated **twice** on soft-confirmation bars (top of `process_candle` and inside the soft-conf block) | `crt_engine_v2.py:1424, 1523` | EMA2/EMA5 step twice on the confirming bar, inflating the momentum term of C. |
| F9 | Engine suggests `risk_pct=0.005` (tier-2) but sizing uses the config's flat 1% | trade event `risk_pct 0.005`; size 57.70 = 1% ÷ 17.771 | Tiered sizing has no effect in the backtest. |
| F10 | Event log is not in candle order (flush chunks), which breaks naive replays | `XAUUSD_events.jsonl` (non-monotone `candle_index`) | Sort by `candle_index` before tracing. |

## 5. What this does and does not show
- It shows exactly how one trade's +1.03R is made: five tests, a score of 0.479, a stop 17.98 above entry, a target 1R below, and costs.
- It also shows that the +1.03R is not a clean measurement: F1 and F2 push in the direction of the result, and F3 caps wins at 1R. None of this changes the earlier conclusion that no edge is established, and F2 makes it weaker.
- Not changed: no code, config or tests. F1–F3 are open questions for you (see the summary message).
