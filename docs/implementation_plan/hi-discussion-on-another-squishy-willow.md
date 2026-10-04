# Venky's day-start rule — how soon does a day-start entry show profit? (XAUUSD, last 3 months)

## Context
Venky (another trader) enters at the start of every day. The user doesn't want day-end results.
The question is: **after entering at day start, what is the shortest time price needs to put
the trade in profit, going up (buy) and going down (sell)?** Past 3 months, XAUUSD.
This is a quick approximation of his rule, labelled as such. Read-only; no `src/` or config edit.

## Time zone (source-verified, `src/features/broker_clock.py:64-68`, F-066)
- The data is in **MT5 broker server time**, and each candle is labelled by its **open** time (F-098).
- The broker follows New York daylight saving: **UTC+3** while New York is on summer time, UTC+2 in winter.
- The whole window (25 Jun – 24 Sep 2026) is summer time, so the broker is **UTC+3** throughout.
  New York summer time ends 1 Nov 2026.
- Broker day start 01:00 = **22:00 UTC the previous evening = 03:30 IST**.
  Broker 23:45 (last bar) = 20:45 UTC = 02:15 IST the next morning.
- Converting to IST: IST = broker time + 2h30m (in this window).
- The output table will show each day's start in broker, UTC and IST.

## Data
- `data/mt5/W2026-05-21_to_2026-09-26/XAUUSD_M15.csv` (fresh MT5 pull, 8,388 rows, 21 May → 25 Sep 19:45).
- Window: complete days 2026-06-25 → 2026-09-24 (~65 trading days). 25 Sep is dropped because the day
  isn't finished.
- Print the path, row count and first/last day before computing (CLAUDE.md §1.5).

## Rule as modelled
- Entry = open of the first M15 bar of each broker day (normally 01:00 broker), on both sides:
  a BUY and a SELL.
- "In profit" = price moves past entry by **cost + $X**. Cost = measured round-trip broker cost
  (F-082: half-spread $0.045 × 2 + commission $0.040 ≈ $0.13/oz). X ∈ {$1, $2, $5, $10, $20}
  per oz. At 1 oz, $1 ≈ Rs84.
  - BUY is in profit on the first bar whose **high** ≥ entry + cost + X.
  - SELL is in profit on the first bar whose **low** ≤ entry − cost − X.
- Time to profit = minutes from day start to that bar. M15 data can't show time inside a bar,
  so results come in 15-minute steps: "0–15 min" means the first bar.
- Also recorded: the **worst point against the trade before profit arrived** (how far it went
  the wrong way), since the rule has no stop yet.
- Days that never reach the target that day count as "not reached".

## Output (per X, BUY and SELL separately)
- % of days in profit within 15 min / 30 min / 1h / 2h / 4h / same day.
- Median and fastest/slowest time to profit.
- Median and worst move against the trade before profit ($ and Rs at 1 oz).
- **Fairness check**: repeat with entry at every other hour of the day. If 01:00 is no quicker
  than other hours, the day-start timing adds nothing; it's just normal gold movement.
- Day-by-day CSV: date, start time (broker/UTC/IST), entry, minutes to +$X for buy and sell,
  worst move against before profit.

## Build
- `results/venky_daystart/2026-09-26/daystart_time_to_profit.py` + `NOTE.md` (same pattern as
  `results/sleeve_mfe_ladder/2026-09-26/`), pandas on the raw CSV.
- Run on the first 2 weeks first and hand-check 3 days against the CSV rows. Then run the full 3 months.

## Honesty limits (state in the answer)
- Price almost always touches a small +$X in *both* directions early in the day, so "reached
  profit fast" alone doesn't prove an edge. What matters is how far it went against the trade
  first, and how it compares with other start hours.
- ~65 days is a small sample. This approximates Venky's rule; his exact trigger/stop/exit are still unknown.
- No finding registered.

## Verification
- Hand-check 3 days: entry = 01:00 open; first bar reaching the target matches the CSV highs/lows.
- The buy and sell counts for each X are consistent (never reached ≤ days).
- Append a session log entry to `assistant_project.md` after the run.
