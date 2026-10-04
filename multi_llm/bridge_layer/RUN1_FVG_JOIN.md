# RUN1 FVG JOIN

**Status:** JOINED (corpus-aligned cross-emit; not same-run emit)

## Provenance
- Run1 folder: `D:\Tradelatest\results\run_20260916_225925_XAUUSD` (content `run_20260916_172925`, config `v2_htfcrt_2026_08`)
- Snapshot: `D:\Tradelatest\logs\bar_structure\XAUUSD_bar_structure.jsonl` (emit `run_20260829_105725`, config `v3_unified_market_structure_2026_09`)
- corpus_sha256 match: `True`
- Carried fields: **fvg_*** geometry only. Snapshot `crt_state_*` excluded.
- Run1 events/trades/state remain lifecycle authority.

## Join key
- Events: `timestamp_equality` (match_rate=1.0)
- Event offset (if applicable): `None`
- Trades entry: timestamp `opened_at` / best offset `bar_index = candle_idx + (-1)` rate=1.0
- Trades exit: `closed_at` timestamp

## Row counts
- Events joined: 7112
- Trades joined: 3

## Census (measurement only)
- Events with fvg_present: 6433/7112 (90.4528%)
- Trades with fvg_present at entry: 3/3
- Distance when present: min=-0.9955023692044975, median=0.8588796517246159, p90=0.999681884775904

### By event type
- `BEGIN_SOFT_CONF`: 19/24 (79.1667%)
- `CONFIRMATION_FAILED`: 0/1 (0.0%)
- `FILTER_REJECTED`: 17/19 (89.4737%)
- `RESET`: 2623/2887 (90.8556%)
- `STATE_TRANSITION`: 2146/2382 (90.0924%)
- `SWEEP`: 1621/1792 (90.4576%)
- `TRADE_OPENED`: 3/3 (100.0%)
- `TRADE_STOPPED`: 2/2 (100.0%)
- `TRADE_TP1`: 1/1 (100.0%)
- `TRADE_TP2`: 1/1 (100.0%)

## Outputs
- `D:\Tradelatest\multi_llm\bridge_layer\RUN1_FVG_JOIN.json`
- `D:\Tradelatest\multi_llm\bridge_layer\RUN1_FVG_JOIN.md`
- `D:\Tradelatest\multi_llm\bridge_layer\RUN1_FVG_EVENTS.csv`
- `D:\Tradelatest\multi_llm\bridge_layer\RUN1_FVG_TRADES.csv`

## Caveats
- Cross-emit join: snapshot from run_20260829_105725 / v3_unified_market_structure_2026_09; Run1 is run_20260916_172925 / v2_htfcrt_2026_08.
- Only fvg_* geometry fields joined; snapshot crt_state_* intentionally excluded.
- Census is measurement-only; no trading edge interpretation.
- Alignment verified by timestamp equality / offset trial match rate; fail-closed if <0.99.

## Index-offset trials (secondary)
- Events ar_index = candle_index + 62: 6991/7112 (98.2987%); 121 mismatches (= gap_resets). Not used as primary.
- Trades ar_index = candle_idx - 1: 3/3 (100%). Consistent with prior forensic +1.
- Primary join remains timestamp equality (events 7112/7112, trades 3/3).

