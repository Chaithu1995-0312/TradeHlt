# Code review: working-tree diff on semanticos_impl (clock contract / corpus SSOT / v7–v9 features)

## Context
Ran /code-review at high effort over the uncommitted working tree. The review was read-only and its findings were reported with ReportFindings. Nothing has been edited.

## Proposed follow-up (only if the user asks for fixes)
1. `src/strategies/base_strategy.py:75`: treat `instrument_specs` as optional. Check that the section exists before calling `get_prod_section`, or declare the section in every config the strategies load.
2. `src/inout/live_rail/tickdb_adapter.py`: normalize tick timestamps through the resolved `ClockDef`, using `clock_contract.to_utc_scalar`, and update the XAUUSD `broker_local` guard. This is a live-rail behaviour change, so it needs user authorization first.
3. `src/features/bar_feature_frame.py`: pass an explicit calendar, or set `attrs["instrument"]`, in `from_candles` and `from_ohlcv_df`.
4. `corpus_store.load`: use `_timestamp_column` and the csv reader for start/end; pass the already-computed sha into `resolve_clock`; keep per-request fields outside the cached object; bound `_SSOT_CACHE`.
5. `market_calendar.load_calendars`: validate the zone and day_start for real (`ZoneInfo(tz)` and `_parse_hhmm`).
6. Add the dataset identity check to the in-process branch of `resolve_clock` and to `corpus_store.build()`.

## Verification
- `venv/Scripts/python.exe -m pytest tests/test_corpus_ssot.py tests/test_corpus_clock_contract.py tests/test_base_strategy_instrument_sizing.py -q`
- `venv/Scripts/python.exe scripts/maintenance/check_governance_invariants.py --all` (capture the baseline before any change)
