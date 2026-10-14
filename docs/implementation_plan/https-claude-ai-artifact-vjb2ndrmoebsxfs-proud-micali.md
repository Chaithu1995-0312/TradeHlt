# Plan: one timeframe truth, guards so features and bar sizes cannot silently mismatch (CH-timeframe-ssot-v1)

## Context
An H4 research check read "hammer"/"pin_lower" from the M15 feature pipeline, so the values described a 15-minute candle, not
the H4 candle. The user asked for SSOT + alignment + a clean sweep. Two read-only censuses (verified at source where it matters):
- No live/backtest path feeds M15 features into HTF logic. ParentCRT/HTFState use parent OHLC only; PDH/PDL use a closed D1
  parent (intentional, documented).
- Candle merging has no single authority: `research.resample` (batch), `features.calendar_periods.period_key` and
  `features.parent_candle.ParentCandleBuilder` (streaming) are cross-tested and calendar-aware. About 15 research scripts
  hand-roll it (`dt.floor("h")`, `.resample("4h")`, `groupby(dt.date)`), mostly naive UTC, several keep the trailing partial
  bucket, and my `xau_1009_*` scripts are among them.
- M15 assumptions are baked in and silent elsewhere: `FeaturePipeline` has no timeframe and assumes M15. `GapDetector`
  `gap_reset_minutes=120` fires on every H4 bar (240 min); verified `backtest_v2.py:826-850`. `crt_engine_v2.py:611`
  `remaining_htf_candles / 4` while the config window is 16 (verified). `*15/60` hour conversions at `crt_engine_v2.py:535,4013`.
  `crt_state_resolver.py:1054` defaults `htf_candles_per_range` to 4 while the active config says 16 (verified). Live rail
  accepts M1..D1 with an epoch floor (`inout/live_rail/bar_builder.py:15`) that is not calendar-aware above M15, but no
  `live_rail` config exists today.

User decisions: fix my scripts; add guards; name one merging authority + a test that blocks new copies; fix the telemetry
numbers. NOT now: re-checking F-027 (its H4 spine runs hit the every-bar gap reset; the new guard will make that path fail
closed, and that is reported, not fixed). No commit.

## A. My research scripts (scripts/research/xau_1009_*)
1. `xau_1009_winner_feature_repeat.py`: add H4 pattern columns computed on the real H4 candles. Use the H4 frames the frozen
   test already builds (`runpy` globals `ins_df`/`oos_df`) + `features.candle_patterns.compute_all` with the same H4 ATR and
   config params. Rename the M15 columns `m15_*` so names can no longer be confused. Re-run; report both views.
2. `xau_1009_prereg_{feature_direction_decode,range_decode,vol_sizing}.py`: replace the hand-rolled `dt.floor("h")` H1 grouping
   with `research.resample.resample(..., "H1", calendar=corpus.calendar)` plus the existing "4 children present" rule. Prove
   rows are identical (the fx_metals offset is whole hours, so H1 buckets should match) by asserting equality once, then
   re-run each and confirm the logged numbers reproduce exactly. `vol_sizing`'s "hour % 4 == 0" periods are its pre-registered
   rule (4-hour holding periods, not H4 candles): keep them, and say so explicitly in its docstring.
3. Fix the direction-decode docstring so it matches its code.

## B. Guards (fail-closed; byte-identical on today's M15 runs)
1. **One bar-size table + a measurer** in `src/features/calendar_periods.py` (it already owns `HOUR_GRID_HOURS`):
   `BAR_MINUTES = {"M15": 15, **{k: 60*h for k, h in HOUR_GRID_HOURS.items()}}` and `modal_bar_minutes(timestamps)`.
   `candle_patterns.contiguous_mask` reuses the measurer. `inout/live_rail/config._TF_SECONDS` derives from `BAR_MINUTES`
   (removes the duplicate table).
2. **FeaturePipeline(timeframe="M15")**: measures the frame's modal bar size and raises `ValueError` if it differs from the
   declared timeframe (frames with fewer than 2 rows skip). A declared non-M15 timeframe is allowed, with one WARNING that the
   indicator windows are bar counts tuned on M15. Callers on non-M15 data must now say so: `backtest_v2.py:2664` passes
   `self.cfg.timeframe`; `research/adapters/shape_signal_source.py:79` and `runtime/live_rail_feeder.py:187` pass theirs.
3. **Backtest G2/G3** next to the existing G1 (`_validate_htf_clock`, `backtest_v2.py:4801`), using the same admission-measured
   `modal_delta_minutes`: G3 raises if `backtest.timeframe` ≠ the measured bar size; G2 raises if `gap_reset_enabled` and
   `gap_reset_minutes` ≤ one bar. Both run in `BacktestRunner` on every path (CLI and programmatic). Expected effect: Program 3
   `qualify_htf` H1/H4 runs now stop with a clear message instead of resetting silently.
4. **Live rail**: `live_rail.timeframe` limited to M15 (the only size where the epoch floor matches the gold calendar), with an
   error naming why; lifted only when bar_builder uses the calendar authority.

## C. One merging authority + a ratchet test
- Authority, documented in `docs/reference/conventions.md` (short subsection): batch = `research.resample.resample`, streaming =
  `features.parent_candle.ParentCandleBuilder`, both on `features.calendar_periods` grids with the corpus calendar.
- New `tests/test_aggregation_authority.py`: scans `src/`, `scripts/`, `tools/` (excluding `archive/`, `tests/`) for hand-rolled
  OHLC merging (`.resample("<n>h"|"D"|"W")`, `dt.floor("h"|"<n>h"|"D")`, `pd.Grouper(freq=`, `groupby(...dt.date)`).
  Existing hits go in a shrink-only allowlist `docs/governance/aggregation_authority_allowlist.json` (path + pattern + one-line
  reason). The test fails on any new hit, and on an allowlisted entry that no longer matches (so the list only shrinks).
  My `xau_1009_*` scripts are migrated in A, not allowlisted. Add the test to the governance GREEN_FLOOR.
- The three OHLC emitters inside the authorities (`resample._emit`, `calendar_periods._emit`, `parent_candle._aggregate`) are
  listed as known duplicates, not merged now: their volume handling differs, so merging needs its own parity proof.

## D. Telemetry that assumed M15
- `crt_engine_v2.py:611`: `/ 4` → `/ htf_candles_per_range` from the engine's config.
- `crt_engine_v2.py:535,4013`: `* 15 / 60` → bar minutes from the declared timeframe (`BAR_MINUTES`).
- `crt_state_resolver.py:1054`: `htf_candles_per_range` default 4 → strict read (raise if absent), sourced the way the active
  config supplies it. Check first where the resolver's thresholds come from; if they lack the key, read it from the backtest
  section instead.
These change logged numbers only; trades and state sequences must not move (verified in Verification).

## Process (repo rules)
- Preflight: `feature_pipeline.py`, `backtest_v2.py`, `crt_engine_v2.py`, `crt_state_resolver.py` already carry other sessions'
  uncommitted edits. Read `git diff` of each first, edit surgically, never touch their hunks.
- Construction protocol (§3.3b): classify against `docs/governance/change_contracts.json`, write
  `docs/governance/build_manifests/CH-timeframe-ssot-v1.impact.json` before code, `construction_protocol.py validate-completion`
  after. Doc drift (§6.2): update `docs/memory/feature-memory.md`/`runtime-memory.md` pointers and the feature-pipeline topic
  doc (§6.4) if one covers it. SESSION LOG each turn. No commit.

## Verification
1. Baseline BEFORE any edit: `venv/Scripts/python.exe scripts/maintenance/check_governance_invariants.py --all` (record the
   pre-existing failures), and an XAUUSD backtest
   `venv/Scripts/python.exe src/runtime/backtest_v2.py --csv data/mt5/XAUUSD_M15.csv --output results/tf_ssot/before`.
2. AFTER: the same backtest to `results/tf_ssot/after`. Trades and CRT state/event sequence byte-identical. Only the D
   telemetry fields may differ, and each difference is listed.
3. New tests: FeaturePipeline raises on an H4 frame declared M15 and passes when declared H4; G2 raises at 120 min on H4 bars;
   G3 raises on mislabeled timeframe; live rail rejects H4; the aggregation test fails on a planted `dt.floor("4h")` line and
   passes on the real tree.
4. Governance floor: no new failures versus the baseline. Script registry tests unchanged. `construction_protocol.py check` green.
5. `xau_1009_*` re-runs reproduce their logged numbers exactly; the winner check reports H4-candle pattern columns.
