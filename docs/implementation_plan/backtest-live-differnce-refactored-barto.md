# Sujan's 1-hour 3-candle CRT (C1 accumulation → C2 manipulation at an HTF location → C3 distribution)

## Context
Sujan sent a live example (25 Sep 2026) and the rule he wants automated:
- "1 hr CRT happening in XAU … C1 accumulation, C2 manipulation done & closed inside first range … & C3 distribution candle … that's all we need to automate. C2 manipulation must occur at HTF location."
- Same trade taken on his account; target hit in 15 min.

**His trade, read off his screenshots (MT5 M5):**
- BUY 0.4 lot (40 oz) at 4276.30, SL 4269.00, TP 4299.00.
- +$578.80 open profit at the moment of the screenshot (4290.77).

**TradingView 1H chart:**
- D HIGH 4315.795, D OPEN 4273.237, D LOW 4254.58, and red lines 4309.273 and 4255.613.
- C1 = the large bearish hour (from about 4299.54 down to ~4275).
- C2 wicked down to 4254.58 and closed back inside C1.
- C3 rallied toward C1's high; his TP of 4299 ≈ C1 high 4299.54.

**What already exists in the repo (reuse, and cite in the report):**
- **`ParentCRTTrack` (`src/config_layer/parent_crt.py:79`)** already runs the C1→C2→C3 state machine on closed parent candles. C2 = `swept_high`/`swept_low` of C1's range, and C3 = a directional impulse. The docstring lists H4/D1/W1/MN1, but it takes any `ParentCandleBuilder` output, so H1 works.
- **F-075** built that construct, **F-089** found the parent-CRT gate decision-neutral on XAUUSD, **F-077** says Sujan's CRT ≠ the repo's H4 ParentCRT, and **F-095** found the earlier mechanical Sujan steelman (M15, nested vetoes) to be a powered REJECT.
- What is new here: the **1H parent**, the **HTF-location gate on C2**, and **entry at the C3 open with the target at C1's far side**.

User decisions:
- Run all 3 location sets.
- Fetch recent MT5 data (read-only) for the live trade and as a fresh test period.
- Run two stop variants.

## Rules (fixed before any run)
- **Candles:** closed 1H candles from `ParentCandleBuilder("H1")` (as in Part 3), streamed into `ParentCRTTrack`.
- **C2 event:** the track moves RANGE_C1 → MANIPULATION_C2 on a closed hour. Extra condition, from Sujan's "closed inside first range": C2's close must be strictly between C1's low and high.
  - Low swept → LONG; high swept → SHORT.
  - If an hour sweeps both sides, it is skipped and counted.
- **HTF location** (three declared sets). The level must be swept by C2's own wick, meaning C2 trades through it and closes back on the entry side:
  - **L0:** no gate.
  - **L1:** PDH/PDL. For a LONG, C2 low < PDL and C2 close > PDL (mirror for SHORT).
  - **L2:** L1 levels + weekly open + day open.
  - PDH/PDL and weekly open use the verified arrays from `pdh_pdl_wo.py`. Day open = the open of the first M15 bar of the broker day.
- **Entry (y):** the open of the first M15 bar of C3, i.e. the next hour after C2 closes. This is the earliest moment the setup exists.
- **Target:** C1's far side (LONG → C1 high, SHORT → C1 low). A trade is skipped if the target is not beyond the entry.
- **Stops (two declared variants):**
  - **S1:** beyond C2's wick ± $0.50.
  - **S2:** the midpoint between the entry and C2's wick (a tighter stop, like his).
- **Unchanged:** walk every M15 bar, SL-first on ties, gap fills, measured costs + live swap, 1 oz, one position at a time, ₹84 per $.
- **Controls, as before:**
  - 100-seed coin-flip direction on the same entries
  - holding gold over the same windows
  - four 6-month blocks
  - Part 3's across-the-close check (entries whose C3 is the next day's first hour)
- **Pre-declared prediction:** close to the H1 sweep results in Part 3 (≈0R, CI crossing zero). A win rate of 45–60% is possible, because the C1-far-side target is often near. The location gate cuts trades by a lot; whether it raises R is the test.

## Data
- **Main:** registered `data/mt5/XAUUSD_M15.csv` (May 2024–May 2026).
- **Fresh (user-approved, read-only):**
  - Fetch with `scripts/data/fetch_candles_mt5.py --pair XAUUSD --timeframe M15 --start 2026-05-21 --end 2026-09-27 --out data/mt5/W2026-05-21_to_2026-09-26`, using the existing `MT5CandleFetcher`.
  - It is research-only and unregistered, loaded via `--raw-csv` if the strict loader rejects it (the same treatment as the 2022 file).
  - Printed before use: path, row count, first/last timestamp, missing-bar count.
  - Two uses: (1) trace Sujan's 25 Sep trade candle by candle; (2) an out-of-sample Jun–Sep 2026 check of the rule, reported separately.

## Change
- **New script** `results/pdh_pdl_weekly_open/2026-09-25/crt_h1.py`:
  - imports `ParentCRTTrack`, `ParentCandleBuilder`, `period_key`, and `swept_high/low`
  - reuses the walk/money/stats/control/block logic by importing it from `pdh_pdl_wo.py` (refactor those helpers into a small module in the same folder, `sleeve_kit.py`, with `pdh_pdl_wo.py` importing it too)
  - after the refactor, `pdh_pdl_wo.py` is re-verified byte-identical in all three modes
- **Outputs:** `grid_crt_h1*.json` and `tradelog_crt_h1*.csv` (full period and the fresh window).
- **Live-trade trace:**
  - The scratchpad `trace_trade.py` gains an `--hourly` summary.
  - It prints C1, C2 and C3 OHLC for 25 Sep, whether each rule and location fired, and our mechanical entry/stop/target and ₹ result, next to his actual 4276.30 / 4269 / 4299 and 40 oz.
  - It also compares his TradingView price with our MT5 feed at the same minute; his two screenshots at 21:29 show 4285.79 vs 4290.77.

## Report (continuation of the same artifact, after section 19)
- **20 · Sujan's live CRT, 25 Sep 2026.** His rule (quoted), his trade (entry/SL/TP, 40 oz, ₹ at 84), and our candle-by-candle C1/C2/C3 from MT5. Which HTF levels C2 swept. What our mechanical rule would have done.
- **21 · 2-year results.** L0/L1/L2 × S1/S2: trades, win %, ₹/month, R + CI, coin-flip p95, holding gold, 6-month blocks, across-close check. Plus the Jun–Sep 2026 fresh-data results as a separate table.
- **22 · Check-it-yourself week.** Every CRT trade in 11–15 May 2026, with UTC times, C1/C2 OHLC, levels, entry/stop/target and ₹.
- **23 · What's still undefined, as questions:**
  - his exact entry inside C3 (he used 5m)
  - his stop rule
  - which red line is the weekly open
  - the TradingView "1H-1D Model" indicator's rules
- **24 · Sources and checks.** Re-read the artifact first, then republish to the same URL and read it back.

## Verification
- After the refactor, `pdh_pdl_wo.py` output is `cmp`-identical for M15/H1/M15H1.
- Every CRT trade is re-derived independently from pandas hour candles (C1/C2 geometry, close-inside, location sweep, entry = C3 first bar open, stop, target): 0 errors.
- Log sums equal grid totals, and the blocks sum to the total.
- One winner and one loser are traced to the paisa.
- The fresh file's row count and gap count are printed. The live trade's C1/C2/C3 match his chart within the feed difference, which is stated.
- NOTE.md addendum, SESSION LOG, one memory line. No finding registered, no src/config edits (`ParentCRTTrack` used unchanged).
