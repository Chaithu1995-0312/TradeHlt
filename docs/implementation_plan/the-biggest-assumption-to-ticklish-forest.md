# 20-Day Purge + Delayed Entry — Standalone Detection Script

## Context

The goal is **not** a research program. It's a small, standalone read-only script:

> Read an OHLCV file → mark where a 20-day high/low purge happened → flag whether an entry
> exists N hours (default 2h) later → write the annotated rows + a summary of setups.

Whether the rule *predicts* anything is a separate question, explicitly out of scope here. This
just **mechanically identifies the setups**.

### The one correctness trap to avoid

The proposed `df["High"].rolling(20)` treats each row as a day. But the data on disk is
**intraday** (verified: `data/*_M15.csv` = 15-min bars, `data/binance/*_H1.csv` = 1-hour bars,
`timestamp,open,high,low,close,volume`). On M15, `rolling(20)` is a **5-hour** window, not 20 days.
So the script **resamples to daily** to compute the 20-day level, then detects the purge on the
intraday bars. `.shift(1)` on the daily level excludes the current forming day (no lookahead).

Environment confirmed: `pandas 3.0.2` + `openpyxl` present → `.csv` and `.xlsx` both readable.

## Design — one file

**New:** `scripts/analysis/purge_delay_scan.py` (read-only; `scripts/analysis/` is the repo's
home for standalone analysis tools). No changes anywhere else. No spine/research/config wiring.

### Logic

1. **Load** OHLCV from a `--file` path (CSV or XLSX via pandas; auto-picks engine by extension).
   Parse `timestamp` to datetime, sort, set as index. Tolerate the repo's canonical header.
2. **Infer bar interval** from the median timestamp delta → `bar_minutes` (M15→15, H1→60).
   `delay_bars = round(delay_hours * 60 / bar_minutes)` (default `--delay-hours 2` → 8 on M15,
   2 on H1). Overridable with `--delay-bars`.
3. **Daily 20-day level** (no lookahead):
   ```python
   daily = df.resample("1D").agg(High="max", Low="min")   # calendar-day HH/LL
   daily["HH20"] = daily["High"].rolling(20).max().shift(1)  # prior 20 COMPLETED days
   daily["LL20"] = daily["Low"].rolling(20).min().shift(1)
   ```
   Broadcast `HH20`/`LL20` back onto the intraday index by forward-filling each day's level.
4. **Purge flags** on intraday bars:
   `higher_purge = high > HH20`, `lower_purge = low < LL20`.
   Optional `--min-penetration-atr` guard (default 0.0) to suppress micro-breaks, using a simple
   ATR (rolling true-range mean) — off by default so the base rule is exactly as specified.
   Debounce: collapse a run of consecutive purges of the same side into the **first** bar
   (`purge & ~purge.shift(1)`), so one purge = one event, not every bar price stays beyond.
5. **Delayed entry:** `entry_buy = lower_purge_event.shift(delay_bars)`,
   `entry_sell = higher_purge_event.shift(delay_bars)` (LOWER purge → BUY, HIGHER → SELL,
   mean-reversion as specified). Entry row carries the entry timestamp + entry price (that bar's
   open/close).
6. **Output:**
   - `--out <path.csv>`: the full frame annotated with `HH20, LL20, higher_purge, lower_purge,
     entry_buy, entry_sell` (default: alongside input, `<name>_purge_scan.csv`).
   - Console: a compact table of detected setups — `purge_time, purge_type, purge_price,
     level, entry_time, signal, entry_price` — plus counts. Windows-safe printing via
     `src/utils/console_safe.py` if non-ASCII sneaks in (defensive; likely unneeded).

### CLI
```
python scripts/analysis/purge_delay_scan.py --file data/EURUSD_M15.csv
python scripts/analysis/purge_delay_scan.py --file data/BNBUSDT_M15_2year.xlsx --delay-hours 2 --lookback-days 20
```
Args: `--file` (req), `--lookback-days` (20), `--delay-hours` (2) / `--delay-bars` (override),
`--min-penetration-atr` (0.0), `--out` (optional).

## Critical files
- New: `scripts/analysis/purge_delay_scan.py`.
- Reference only: `data/*_M15.csv` / `data/*.xlsx` (inputs), `src/utils/console_safe.py`
  (safe printing). Nothing else touched.

## Verification
1. Run on `data/EURUSD_M15.csv` → confirm it prints a setup table and writes the annotated CSV.
2. Spot-check one setup by hand: pick a printed `purge_time`, confirm that bar's high/low really
   breaks the printed HH20/LL20, and that `entry_time` is exactly `delay_bars` bars later.
3. **No-lookahead check:** confirm the level a bar is tested against uses only *prior* completed
   days — verify `HH20` at the first bar of day D equals the max of days D-20…D-1 (not including D).
4. Run once on an M15 file and once on `data/binance/BTCUSDT_H1.csv` → confirm `delay_bars`
   auto-resolves to 8 and 2 respectively for `--delay-hours 2`.
5. Sanity: total higher+lower purge events is small relative to row count (a 20-day extreme is
   rarely breached); if it's firing every bar, the debounce or `.shift(1)` is wrong.

## Notes / deferred
- This is mechanical detection only — **no** backtest, PnL, cost model, or statistical test.
- If you later want significance / OOS / multi-delay sweep / promotion, that's the heavier
  research-framework path (previously drafted) — kept out of scope by your direction.
