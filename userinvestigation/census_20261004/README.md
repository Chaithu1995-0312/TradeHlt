# Market-Movement Census - XAUUSD M15, 2026-07-06 -> 2026-08-07

**A measurement-trace / stabilization run.** No trading logic was changed. Every number below is
read from existing artifacts; the movement layer is derived from raw OHLC + `atr_abs` only.

| Identity | Value |
|---|---|
| run_id | `run_20260930_123522` |
| corpus | `XAUUSD_W2026-07-06-to-2026-08-07.csv` |
| corpus sha256 | `dcaf88a76b927d53...` |
| config | `v2_htfcrt_2026_08` (`7de09f6233b712f0...`) |
| feature schema | `6.0` (`d40e7c7d5b624ef6...`) |
| timestamp basis | **broker_local** (raw MT5 server clock, not UTC) |
| bars | 2222 LIVE (78 WARMUP excluded) |

## The chain, stage by stage

| # | Stage | What is measured | Exact rule | Input | Output pop | % of corpus | Why the next gate removes it |
|---|---|---|---|---|---|---|---|
| 0 | `RAW_BAR` | Raw OHLCV bar as admitted | `none (source data)` | data/mt5/XAUUSD_W2026-07-06-to-2026-08-07.csv | **2222** | 100.0000% | warmup bars that cannot seed ATR/EMA/range |
| 1 | `SWEEP` | Liquidity taken beyond active range, closed back inside | `_swept_high: high>h_ref AND close<h_ref ; _swept_low: low<l_ref AND close>l_ref` | crt_range_h_ref, crt_range_l_ref (frozen M15 structural envelope) | **72** | 3.2403% | no qualifying displacement candle within max_sweep_age_candles=20 |
| 2 | `DISPLACEMENT` | Impulse candle confirming the sweep | `|close-open|>=1.2*ATR_abs ; candle_range>=1.5*ATR_abs ; body_ratio>=0.65` | raw OHLC of bar, atr_abs (price units) | **13** | 0.5851% | close does not extend beyond displacement_close by >=0.3*ATR |
| 3 | `EXPANSION` | Post-displacement extension | `close extends past displacement_close AND |close-disp_close|>=0.3*ATR_abs` | displacement_candle.close, atr_abs | **4** | 0.1800% | price never retraces into the retest depth band before a RESET/TTL |
| 4 | `RETEST` | Retrace into the swept edge within the depth band | `retest_geometry.evaluate_retest_geometry: 0.1*ATR <= depth_abs <= max(0.15*range_size, 0.3*ATR) and FM-028 ratio <= 2.0` | close, h_ref, l_ref, atr_abs, displacement range | **2** | 0.0900% | soft-confirmation manifold, score>=0.45, zone, parent bias, objective, SESSION |
| 5 | `FILTERED_OUT` | Retest locked but a gate rejected it | `session_name NOT IN allowed_sessions[london,new_york,overlap]` | candle timestamp, crt_engine.session_windows (LONDON 07:00-10:00, NEWYORK 13:00-16:00) | **2** | 0.0900% | n/a - terminal rejection |
| 6 | `TRADE_OPENED` | Trade opened | `build_trade + try_retest_to_execution` | score>=0.45, all gates passed | **0** | 0.0000% | n/a |

### Units on every stage

- `RAW_BAR` - price (USD/oz), volume=tick_volume
- `SWEEP` - price comparison
- `DISPLACEMENT` - ATR multiples
- `EXPANSION` - ATR multiples
- `RETEST` - price / ATR
- `FILTERED_OUT` - wall-clock hour, broker-local
- `TRADE_OPENED` - lots / R

> Movement is recorded in BOTH price units and ATR-relative units. features['atr'] is RELATIVE (atr/close); atr_abs is the price-unit ATR the gates actually use.

## Movement distribution (ground truth, independent of CRT states)

| Quantity | mean | median | p90 | p99 | max |
|---|---|---|---|---|---|
| body move `|C-O|` (ATR) | 0.505 | 0.391 | 1.081 | 2.172 | 5.591 |
| true range `H-L` (ATR) | 1.012 | 0.892 | 1.663 | 2.988 | 6.531 |
| body ratio | 0.462 | 0.474 | 0.807 | - | - |

Direction mix: **{'UP': 1114, 'DOWN': 1106, 'FLAT': 2}** - balanced, so no directional drift is contaminating the census.

**Read this against the gates:** a median bar moves only **0.391 ATR** and a median true range is **0.892 ATR**.
The displacement gate demands `>=1.2 ATR` body **and** `>=1.5 ATR` range **and** `body_ratio>=0.65` - i.e. roughly the
top decile of body move *and* the top third of range *simultaneously*. That is why DISPLACEMENT is only
**0.5851%** of bars while a median bar is nowhere near qualifying.

## Where observations leave the pipeline

| RESET cause | Count |
|---|---|
| `HTF_WINDOW` | 99 |
| `RETRACE_50PCT` | 6 |
| `SESSION_GAP` | 4 |
| `OFF_SESSION` | 2 |
| `EXTENSION_FIB` | 1 |

`HTF_WINDOW` dominates (99) because `htf_candles_per_range=16` flips the clock every 16 bars.

## Measurement gaps found

### GAP-001 (REAL) - Session-gap RESETs are invisible in the per-bar census.

- **Evidence:** events file records 4 RESET with reason 'Session gap detected: 2955min > 120min' at engine_candle_index 460, 920, 1380, 1840; bar_structure records crt_action=NONE at all four.
- **Cause:** backtest_v2.py:3666 gap_det.check() + :3688 engine.sm.reset_to_range() run BEFORE process_candle (:3710); bar_structure.emit() (:3741) reads result/action from that later call. The gap reset is therefore structurally unrepresentable per-bar.
- **Impact:** Any consumer reconstructing state from bar_structure alone will miss all gap resets and over-count SWEEP/DISPLACEMENT continuity across session boundaries.
- **Fix class:** MEASUREMENT (add a gap flag field to the snapshot) - NOT a trading-logic change.

## Join test - can the chain be rebuilt from `bar_structure` alone?

Yes, with one caveat. All 279 engine events join to a LIVE bar row on `engine_candle_index`.
Every `STATE_TRANSITION` the engine recorded is reconstructable, **plus 4 edge classes the events file
does not carry at all** (`SWEEP->RANGE` 58, `DISPLACEMENT->RANGE` 9, `RETEST->RANGE` 2, `EXPANSION->RANGE` 1):
these are reset-driven exits that `bar_structure` sees and `events` omits. That is `bar_structure` being
*richer* than events - except for GAP-001, where it is blind.

## Worked example - the first rejected retest

| Field | Value |
|---|---|
| bar | 709 / engine_candle_index 647 |
| timestamp | 2026-07-15T17:15:00 (**broker_local**) |
| raw OHLC | O 4064.34 H 4066.13 L 4055.63 C 4058.50, atr_abs 9.3193 |
| movement | body **-5.84 (-0.627 ATR)**, true range 10.50 (1.127 ATR), body_ratio 0.556 |
| range refs | h_ref 4060.51 / l_ref 4046.87 |
| state | EXPANSION -> RETEST |
| events on this bar | STATE_TRANSITION, BEGIN_SOFT_CONF |

**One bar later** (bar 710, 17:30): `FILTER_REJECTED` / `off_session:OFF_SESSION`.
Hour 17:15 broker_local is outside LONDON 07:00-10:00 and NEWYORK 13:00-16:00.

This is the complete chain from a single artifact: *the retest was real and geometrically valid*
(depth inside the band), *the score passed*, and it died purely on wall-clock policy.

## Artifacts

| File | Contents |
|---|---|
| `_per_bar.jsonl` | one row per LIVE bar: raw OHLCV, movement in price AND ATR units, CRT state/action, joined event types |
| `_stage_census.json` | machine-readable stage manifest + gap register |
| `_movement_summary.json` | movement distribution |

Reproduce: read `logs/bar_structure/run_20260930_123522/XAUUSD_bar_structure.jsonl` and
`results/xau_last_month_trace/run_20260930_123522_.../XAUUSD_events.jsonl`.
