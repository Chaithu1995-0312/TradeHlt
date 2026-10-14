# Plan: Second-low live-vs-corpus parity check (read-only measurement)

## Context
The frozen second-low rule (H4, `at_or_above_pdl`, `rule_frozen.json`) was learned on the full 56,215-bar M15
corpus, but `second_low_algo.py live` (run every 4h by Windows task, `run_live.cmd`) recomputes everything from a
**60-day MT5 window** (`fetch_mt5(days=60)`) and **overwrites** `live_candidates.jsonl` each run. Reading the code
surfaced three untested hypotheses (all UNVERIFIED, derived from source only):

- **H1 spurious window-start trigger.** `_detect_raw_purge_mask` (`src/research/secondlow_v1/detector.py:81`) starts
  `armed=False`. `second_low_20d` is NaN until 20 trading days of daily lows exist (`min_periods=20`, then
  `.shift(1)`), so the first valid bar is ~29 calendar days into the window. If price is already below the level
  there, the window version fires a trigger the full-corpus run (already armed) would not.
- **H2 forward ledger is not append-only.** Only bars after that ~29-day warmup yield rows, i.e. ~31 days of a
  60-day window. `live_candidates.jsonl` is rewritten with `write_text`, so a trigger older than ~31 days vanishes,
  and `live_runs.jsonl`'s `closed` stats are recomputed from surviving rows (can shrink).
- **H3 feature drift.** `pdl_distance` (`features/smc/levels.py:26`, via the D1 parent builder in
  `feature_pipeline.py:1296-1356`) and `liquidity_sweep` (`feature_pipeline.py:882`) may differ between a short
  window and the full corpus; the frozen filter depends on `pdl_distance >= 0`. Sign convention itself is also
  UNVERIFIED (`feature_schema.py:85` says "signed ATR distance to previous-day low").

## Approach (no edits to `second_low_algo.py`; its SHA is pinned, any edit makes the live task `SystemExit`)
1. Write one throwaway script in the session scratchpad (not in the repo, so no SITS registration) that imports
   `build_rows`, `load_csvs`, `CONDITIONS` from `userinvestigation/second_low_algo/second_low_algo.py`.
2. Echo the exact CSV paths and row count first (corpus = `data/mt5/XAUUSD_M15.csv` +
   `XAUUSD_M15_2026-04-20_to_2026-10-06.csv`, expect 56,215 rows).
3. Reference = `build_rows(full_corpus, "H4")` (must equal `backtest_H4.jsonl`, 36 rows; assert this first).
4. Replay: for each as-of date A in monthly steps from 2025-10-01 to 2026-10-06, slice M15 to the last 60 calendar
   days ending at A, run `build_rows(slice, "H4", eval_start=A-31d)` (the span the live run could actually score).
5. Compare per trigger vs reference: trigger_ts set (missing / extra), `level`, `pdl_distance`,
   `liquidity_sweep`, `fvg_distance`, `passes_filter`. Report counts of extra (H1), missing/aged-out (H2),
   and value mismatches with max abs diff (H3).
6. Sign check: print `pdl_distance` vs (close − previous-day low) for 5 trigger bars to confirm `>= 0` means
   close at/above the previous daily low.

## Output
A short table (as-of date × extra / missing / feature-mismatch counts) and a verdict per hypothesis:
CONFIRMED / REFUTED / INSUFFICIENT. No config, rule, or live-task change. If H1/H2 confirm, the fix (e.g. append-only
ledger, longer fetch window, seeded armed state) is a separate user-approved turn, and re-freezing would be
required because the tool SHA is pinned.

## Verification of the check itself
Step 3's 36-row equality is the instrument gate: if the harness cannot reproduce the reference, stop and report.
Run in the foreground (H4 only, a few seconds per slice); do not touch `live_*.jsonl` or the scheduled task.
