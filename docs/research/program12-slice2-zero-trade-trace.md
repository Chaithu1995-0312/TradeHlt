# Program 12 Slice 2 — zero-trade trace

Read-only trace of the 2026-10-06 ladder walk. No expectancy is stated. The sealed contract was not opened for this page.

## Artifacts found for this run

| Role | Path |
|---|---|
| Published funnel | `docs/research/program12-slice2-funnel.md` |
| Funnel object | `results/program12_slice2/funnel.json` |
| H1 events | `results/program12_slice2/H1/run_20261006_082906_XAUUSD__20260707..20260806_v2_htfcrt_2026_08_7de09f62/XAUUSD_events.jsonl` (204 lines) |
| H1 telemetry | same folder, `XAUUSD_crt_telemetry.jsonl` (162 lines) |
| H1 summary | same folder, `XAUUSD_summary.json` |
| H4 events | `results/program12_slice2/H4/run_20261006_082909_XAUUSD__20260707..20260806_v2_htfcrt_2026_08_7de09f62/XAUUSD_events.jsonl` (24 lines) |
| H4 telemetry | same folder, `XAUUSD_crt_telemetry.jsonl` (19 lines) |
| H4 summary | same folder, `XAUUSD_summary.json` |
| Projected series | `results/program12_slice2/H1/ladder_bars.csv`, `results/program12_slice2/H4/ladder_bars.csv` |
| Run log | `logs/backtest_debug.log` lines 1–42 (both clocks, 2026-10-06T13:59:06 through 13:59:09) |
| Config dumps | `logs/config_dumps/XAUUSD_run_20261006_082906_config.json`, `logs/config_dumps/XAUUSD_run_20261006_082909_config.json` |
| Per-bar snapshot | `logs/bar_structure/run_20261006_082906/XAUUSD_bar_structure.jsonl` (528 rows), `logs/bar_structure/run_20261006_082909/XAUUSD_bar_structure.jsonl` (137 rows) |
| Research clones on disk | `configs/research/ladder_h1.json`, `configs/research/ladder_h4.json` |

`configs/research/program12/ladder_h1.json` and `configs/research/program12/ladder_h4.json` are not on this worktree. The clones that are on disk are the two paths in the table.

The run log also names `results/layer_trace/XAUUSD_layer_trace.jsonl`. That file was not read. The per-bar snapshot already carries `parent_crt_state` and `parent_bias` for these two `run_id` values.

`XAUUSD_summary.json` `rejection_reasons` is `{}` and `rejected_trades` is 0 on both clocks (`H1` summary lines 6 and 20; `H4` summary lines 6 and 20). Those fields are the trade-gate map. The stage exits below are `RESET` reason strings in `events.jsonl`, which is a different field.

`state_distribution` counts bars spent in a state. The funnel counts entries. H1 summary `state_distribution` is RANGE 356, SWEEP 89, DISPLACEMENT 5 (lines 21–25). H1 telemetry line 1 `state_entry_counts` is SWEEP 40, DISPLACEMENT 3. The funnel’s SWEEP 40 is the entry count.

## Rejection reason codes

Counted from `event` / `state_from` / `state_to` / `reason` in each `XAUUSD_events.jsonl`. Reason code is the text before the first colon. An advance is a `STATE_TRANSITION` into the next state. No `EXPANSION`, `RETEST`, or `TRADE_OPENED` event exists in either file.

### H1 — `run_20261006_082906`

Entry counts: telemetry line 1, `state_entry_counts.SWEEP` = 40, `state_entry_counts.DISPLACEMENT` = 3. Events: 40 `STATE_TRANSITION` RANGE→SWEEP, 3 SWEEP→DISPLACEMENT.

| Stage | Exits in events.jsonl | Count |
|---|---|---|
| SWEEP → DISPLACEMENT | reason code `HTF changed` (`RESET` SWEEP→RANGE) | 37 |
| SWEEP → DISPLACEMENT | advance, `STATE_TRANSITION` SWEEP→DISPLACEMENT | 3 |
| DISPLACEMENT → EXPANSION | reason code `HTF changed` (`RESET` DISPLACEMENT→RANGE) | 3 |
| EXPANSION → RETEST | no event with `state_from` EXPANSION | 0 |
| RETEST → TRADE_OPENED | no event with `state_from` RETEST and no `TRADE_OPENED` | 0 |

The three displacement exits:

| events.jsonl line | timestamp | candle_index | reason |
|---|---|---|---|
| 8 | 2026-07-10T20:00:00 | 14 | `HTF changed: XAUUSD-HTFCAL-2026-07-10T12:00:00 → XAUUSD-HTFCAL-2026-07-10T16:00:00` |
| 132 | 2026-07-28T20:00:00 | 290 | `HTF changed: XAUUSD-HTFCAL-2026-07-28T12:00:00 → XAUUSD-HTFCAL-2026-07-28T16:00:00` |
| 145 | 2026-07-29T20:00:00 | 313 | `HTF changed: XAUUSD-HTFCAL-2026-07-29T12:00:00 → XAUUSD-HTFCAL-2026-07-29T16:00:00` |

Telemetry `RESET_ATTRIBUTED` for those same candle indexes (H1 telemetry lines 4, 79, 85):

| line | candidate_id | would_expand_score | would_expand_threshold | would_expand |
|---|---|---|---|---|
| 4 | CAND-11 | 0.35 | 0.55 | false |
| 79 | CAND-287 | 0.35 | 0.55 | false |
| 85 | CAND-310 | 0.8 | 0.55 | true |

All three `reason` values are still `HTF changed`. CAND-310 scores above the recorded threshold and is reset on the same reason code.

Binding condition for the 3 H1 displacements: each one is a `RESET` whose reason code is `HTF changed`, and none is followed by an `EXPANSION` transition.

The 37 sweeps that never displaced use that same reason code. The file has no separate displacement-predicate reject code for them.

Four `Session gap detected` resets exist on this clock. Telemetry attributes all four to `from_state` RANGE. They are outside the SWEEP→DISPLACEMENT table.

### H4 — `run_20261006_082909`

Entry counts: telemetry line 1, `state_entry_counts` SWEEP 6, and no DISPLACEMENT key. Events: 6 `STATE_TRANSITION` RANGE→SWEEP, 0 SWEEP→DISPLACEMENT.

| Stage | Exits in events.jsonl | Count |
|---|---|---|
| SWEEP → DISPLACEMENT | reason code `HTF changed` | 4 |
| SWEEP → DISPLACEMENT | reason code `Session gap detected` | 1 |
| SWEEP → DISPLACEMENT | no later event; file ends in SWEEP | 1 |
| DISPLACEMENT → EXPANSION | no DISPLACEMENT event | 0 |
| EXPANSION → RETEST | none | 0 |
| RETEST → TRADE_OPENED | none | 0 |

The six sweeps:

| Sweep events.jsonl lines | candle_index | Exit | Exit line | Reason code |
|---|---|---|---|---|
| 2–3 | 8 | `RESET` SWEEP→RANGE | 4 | `Session gap detected` — `3120min > 600min` |
| 7–8 | 21 | `RESET` SWEEP→RANGE | 9 | `HTF changed` |
| 10–11 | 25 | `RESET` SWEEP→RANGE | 12 | `HTF changed` |
| 13–14 | 34 | `RESET` SWEEP→RANGE | 15 | `HTF changed` |
| 18–19 | 46 | `RESET` SWEEP→RANGE | 20 | `HTF changed` |
| 23–24 | 61 | none in this file | — | telemetry line 19 `death_reason` `RUN_END` (`CAND-61`, `entered_states` `["SWEEP"]`) |

`600` is `backtest_params.gap_reset_minutes` in the H4 config dump, line 19. Telemetry line 14 ties the gap to `CAND-8` with `death_reason` `RESET_OTHER`.

Binding condition for the 6 H4 sweeps: 4 end on `HTF changed`, 1 ends on `Session gap detected` (`3120min > 600min`), and 1 is still SWEEP when the event file ends (`RUN_END`). No displacement-predicate reject code is recorded.

## Warmup budget

`phase` is a field on the per-bar snapshot. `warmup_candles` is `backtest_params.warmup_candles` in both config dumps (line 21). The run log prints the engine-init candle.

| | H1 | H4 |
|---|---|---|
| Projected bars | 528 (`XAUUSD_summary.json` `total_candles`; snapshot rows 528) | 137 (same fields) |
| Warmup consumed | 78 (`phase` `WARMUP`, `bar_index` 0–77) | 78 (`phase` `WARMUP`, `bar_index` 0–77) |
| Decision-window bars | 450 (`phase` `LIVE`, `bar_index` 78–527). Log line 1: `FeaturePipeline built: 450 rows` | 59 (`phase` `LIVE`, `bar_index` 78–136). Log line 22: `FeaturePipeline built: 59 rows` |
| Engine start | Log line 9: `Engine init @ candle 78`. First LIVE row: `bar_index` 78, `engine_candle_index` 4, timestamp `2026-07-10T10:00:00` | Log line 30: `Engine init @ candle 78`. First LIVE row: `bar_index` 78, `engine_candle_index` 6, timestamp `2026-07-24T00:00:00` |
| Live window | `2026-07-10T10:00:00` → `2026-08-06T22:00:00` | `2026-07-24T00:00:00` → `2026-08-06T16:00:00` |
| Parent timeframe | `H4` (log line 5; `configs/research/ladder_h1.json` `parent_crt.timeframe`, line 430) | `D1` (log line 26; `configs/research/ladder_h4.json` `parent_crt.timeframe`, line 432) |
| Parent bars in the live window | 118 distinct `htf_candle_id` values, all 450 LIVE rows non-null | 10 distinct `htf_candle_id` values, all 59 LIVE rows non-null |
| Parent warmup requirement | `parent_crt` in both clones (H1 lines 428–440, H4 lines 430–442) has `enabled`, `timeframe`, `bias_gate_mode`, `htf_state`, and `objective_gate`. It has no warmup field. | same |

`htf_candle_id` is null on all 78 WARMUP rows of each clock and set on every LIVE row. Parent state is present from the first live bar (next section). This run’s records do not show parent-available below a parent warmup requirement: the parent block declares no such number, and the live window carries a parent id on every bar.

`engine_candle_index` on the first live bar is 4 (H1) and 6 (H4). That is the index written into `events.jsonl` `candle_index`. The log’s “candle 78” is the snapshot `bar_index`.

## Parent CRT state

Fields are on the LIVE rows of the per-bar snapshot. `parent_enabled` is true on every live bar of both clocks. `parent_timeframe` is `H4` on all 450 H1 live bars and `D1` on all 59 H4 live bars.

| Field | H1 live bars (450) | H4 live bars (59) |
|---|---|---|
| `parent_crt_state` | `RANGE_C1` 282, `MANIPULATION_C2` 126, `DISTRIBUTION_C3` 42 | `RANGE_C1` 35, `MANIPULATION_C2` 24 |
| `parent_bias` | `NONE` 408, `LONG` 28, `SHORT` 14 | `NONE` 59 |
| `htf_state` | `ACCUMULATION` 174, `EXPANSION` 124, `REVERSAL` 79, `DISTRIBUTION` 73 | `ACCUMULATION` 36, `EXPANSION` 11, `REVERSAL` 6, `DISTRIBUTION` 6 |
| `parent_range_h_ref` / `parent_range_l_ref` | non-null 450/450 | non-null 59/59 |
| `crt_reject_reason` containing `bias` | 0 | 0 |

H1 `DISTRIBUTION_C3` rows (42) carry `parent_bias` `LONG` 28 and `SHORT` 14. H4 has 0 `DISTRIBUTION_C3` rows, and `parent_bias` is `NONE` on the whole live window (`bar_index` 78–136, `2026-07-24T00:00:00` through `2026-08-06T16:00:00`).

The parent series is loaded and non-degenerate on both clocks: the id changes (118 H4 ids; 10 D1 ids), `parent_crt_state` is one of the three candle labels above, and the range refs are filled. H4 `parent_bias` stays `NONE` across that entire live range. The bias string is not the stage-exit reason: both clocks record 0 `crt_reject_reason` values containing `bias`, and H4 `crt_action` on the snapshot is `NONE` 43, `RESET` 10, `SWEEP_DETECTED` 6.

At engine init the log already names a parent id: H1 line 9 `HTF=XAUUSD-HTFCAL-2026-07-10T04:00:00`; H4 line 30 `HTF=XAUUSD-HTFCAL-2026-07-22T00:00:00`.

## Verdict

**SELECTIVE.**

The detector ran on a live window (H1 450 bars after 78 warmup bars; H4 59 bars after 78 warmup bars). Parent CRT state is non-empty on every live bar. Every recorded exit from SWEEP or DISPLACEMENT is a named reset: `HTF changed` for all 3 H1 displacements and for 37 H1 sweeps and 4 H4 sweeps; `Session gap detected` for 1 H4 sweep; `RUN_END` for the last H4 sweep. EXPANSION, RETEST, and TRADE_OPENED were never entered, so those stages contribute no reason code.
