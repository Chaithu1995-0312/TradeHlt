# K23 — finish F3 (oracle arm + stamping) and build F2 (exact per-date session windows)

## Context
The last session added F3's engine half (`backtest.sl_anchor = displacement | sweep_extreme`,
default legacy) and stopped with three gaps: the oracle labeler has no swept-extreme stop, so the
table and the spine would measure different trades (F-088 class); the anchor isn't stamped on the
run; and F2 was waiting on a decision. Decisions made this turn:
- **F3 oracle arm:** the trailing N-bar extreme (the oracle labels every bar, and most bars have no sweep).
- **F2:** use exact per-date windows. Each session is defined in its own exchange time zone and
  converted to broker time bar by bar. This matches the design-doc decision in
  `docs/implementation_plan/k23-block-heuristic-table-design.md` §8c: Tokyo 09:00–18:00 JST
  (no DST), London 08:00–17:00 London time (EU DST), NY 08:00–17:00 NY time (US DST).

Everything stays default-off and byte-identical. No shadow config and no F1 in this plan; they come
next, as §9 step 3 of the design doc.

**Found during exploration (a gap the last turn didn't report):** `backtest_v2.py:1289` stamps
every trade `reference_level = BACKTEST_REFERENCE_LEVEL` (`"displacement_extreme"`, `:177`). With
`sl_anchor="sweep_extreme"` that stamp would be **wrong**, which makes it the silent-gap class
(F-079/F-083). So stamping is required, not optional.

## Preflight
`git status --porcelain` on `src/` and `tests/`. Concurrent sessions are active; stop if another
session has touched the files below. Interpreter: `venv/Scripts/python.exe`.

## Part A — F3 stamping (backtest)
1. `src/governance/measurement_basis.py:57-62`: add `REF_LEVEL_SWEEP_EXTREME = "sweep_extreme"` to
   `REFERENCE_LEVELS`. Check whether `COMPARE_TABLE` needs a row. Update the pinned set in
   `tests/test_measurement_basis.py:87`.
2. `src/runtime/backtest_v2.py`: replace the `:1289` constant with a per-run value derived from
   `self.cfg.sl_anchor` (`displacement` → `displacement_extreme`, `sweep_extreme` →
   `sweep_extreme`). Keep `BACKTEST_REFERENCE_LEVEL` as the legacy value because
   `tests/test_cost_model_stamped.py:187` pins it.
3. Stamp `sl_anchor` in the run summary exactly as F4 does: add a metrics field next to `:1508`, a
   `to_dict` entry near `:1568`, and pass it through the constructor at `:1682`, `:4116`.

## Part B — F3 oracle arm (`src/research/oracle/labeler.py`)
1. Add `SL_GEOM_SWEEP_EXTREME = "sweep_extreme"` to `SL_GEOMETRIES`. `PRIMARY_ARM` stays unchanged, and the new arm is declared as a robustness arm.
2. Add a new `label_corpus(..., sweep_lookback: int)` parameter. The stop is `min(low[p-N+1..p]) − sl_atr_buffer·atr_abs` for a long, mirrored for a short. The window includes bar p, so the stop is never tighter than `disp_bar`. Rows with `p < N-1` get a counted reject, `insufficient_sweep_lookback`.
3. Set `reference_level = REF_LEVEL_SWEEP_EXTREME` on those rows, which replaces the current two-way conditional at `:266-269`.
4. `main()`: read N strictly from `backtest.htf_candles_per_range` (16, the HTF range length) with no default. Record it in the manifest's `geometry` block, and add a caveat that the oracle anchor is a trailing-window proxy, not the engine's sweep candle.
5. Row count grows from 8 to 12 per bar. `_arm_summary` and `_tie_break_divergence` already group by `sl_geom`, so they need no change.

## Part C — F3 parity test
Add a new file, `tests/research/test_sl_anchor_oracle_parity.py`:
- Build a synthetic engine state with a sweep candle and run `ExecutionEngine(cfg, sl_anchor="sweep_extreme").build_trade`.
- Give the labeler a raw window whose trailing N-bar extreme **is** that sweep candle, with the same entry close and ATR.
- Assert that `sl`, `risk_distance`, `tp1` and `tp2` agree to 1e-12 for both directions.
- Add a negative control: a window whose extreme is *not* the sweep candle must differ. This documents the proxy boundary rather than hiding it.
- Add a labeler test that `sweep_extreme` rows exist, carry the new reference level, and leave the existing `disp_bar`/`fixed_atr` rows byte-identical. Extend `tests/research/test_oracle_labeler.py`.

## Part D — F2 exact per-date windows (default off)
1. **The function** lives in the existing clock authority, `src/features/broker_clock.py`: a new
   `exchange_sessions_at(broker_ts, windows) -> tuple[str, ...]`. It converts broker → UTC with the existing
   `mt5_server_to_utc_scalar` (the NY-DST rule, from one source), then UTC → each session's `ZoneInfo(tz)`,
   and tests `open <= local_time < close`. The interval is half-open because MT5 timestamps are bar OPEN (F-098).
   The result is in declared order, and the function is MT5-only (per the module's SCOPE note).
2. **Config**, following the F3/F4 pattern: two optional keys in the `backtest` section, not CRTConfig fields (so the census pins are untouched).
   - `session_window_basis`: `"broker_static"` (the default, legacy) or `"exchange_local"`. Any other value raises.
   - `exchange_session_windows`: `{"TOKYO": {"tz": "Asia/Tokyo", "open": "09:00", "close": "18:00"}, "LONDON": {...Europe/London 08:00–17:00}, "NEWYORK": {...America/New_York 08:00–17:00}}`.
   This key is **required** when the basis is `exchange_local`, and its time zones are validated at load.
   Both are parsed in `BacktestConfig` next to `:325` and threaded like `sl_anchor` (`:357`, `:2939`, `CRTEngine` `:2716`).
3. **Engine sites that must use the same resolver when enabled**, so the filter, the score and the label don't disagree:
   - The session filter, `crt_engine_v2.py:3516-3526`. The first matching name in declared order wins. Put NEWYORK before LONDON? No: keep the declared order, and note that the London/NY overlap resolves to the first one declared.
   - `score_time`, `:2017-2024`. It counts matches, so the natural London/NY overlap scores 1.0.
   - The backtest session labels at `backtest_v2.py:3283` and `:4314`.
   The legacy path stays byte-identical when the flag is off.
4. Admission: TOKYO must also be in `engine_runner.allowed_sessions`. That is a **shadow config** edit and is deferred. This plan only makes the mechanism exist. Fail closed: under `exchange_local`, an allowed session with no window raises at load, so a config can't silently never admit a session.
5. Stamp `session_window_basis` in the run summary (the Part A.3 pattern).

## Part E — tests for F2
Add a new file, `tests/test_exchange_session_windows.py`:
- Known dates in each DST regime: winter, summer, and both US/EU mismatch weeks (2025-03-10..27, 2025-10-27..31). Assert London open lands on the correct broker hour in each. Assert Tokyo doesn't move with EU/US DST except through the broker offset.
- Bar-open boundary: the 17:00 local bar is excluded.
- Config errors: a bad basis, a missing `exchange_session_windows`, an unknown tz, and an allowed session without a window each raise.
- Flag off: engine session names and `score_time` are unchanged versus legacy on a fixed candle set.

## Governance (the construction protocol)
- Write impact manifests before the code: `CH-k23-f3-oracle-arm-stamping.impact.json` and
  `CH-k23-f2-exchange-session-windows.impact.json`. Put the open items (shadow config, Tokyo admission) back as **blocking UNKNOWNs** unless you say otherwise. The last turn moved them to "authority not granted", which loosened the check.
- Update the design doc's §8c F2/F3 lines with IMPLEMENTED notes. Update `docs/reference/config-reference.md` for the 3 new backtest keys. Grounding check for a new session node (§6.6): run `query_semantic_os --ground` and add an `UNKNOWN_*`/node only if the tool requires it.
- Add the SESSION LOG entry to `assistant_project.md` (the commit hook needs it for `src/**`).

## Verification
1. `venv/Scripts/python.exe -m pytest tests/test_sl_anchor_sweep_extreme.py tests/test_htf_reset_sweep_exempt.py tests/research/test_sl_anchor_oracle_parity.py tests/research/test_oracle_labeler.py tests/test_exchange_session_windows.py tests/test_measurement_basis.py tests/test_cost_model_stamped.py -q`
2. Flag-off byte-identity: run the XAUUSD backtest (`src/runtime/backtest_v2.py --csv data/mt5/XAUUSD_M15.csv`) before and after, echoing the path and row count, and diff `trades.csv` and events. Only the new summary keys may differ.
3. Labeler smoke with `--limit-bars 2000`: the existing 8 arms are byte-identical to a pre-change run, and the 4 new `sweep_extreme` arms are present.
4. Record the governance floor (`check_governance_invariants.py --all`) failure count **before** the change and compare after. Report pre-existing reds; don't fix them.
5. `construction_protocol.py validate-completion` on both manifests.

Nothing is committed without your go-ahead.
