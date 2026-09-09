# CRT spine journal grain (2026-08-27)

> Point-in-time. **Different grain** from the 94,332 bar×direction ledger.
> Legal join: `events` ↔ `telemetry` only. Illegal: 1:1 onto opportunities/clean_labels.
> Run: `results/research/_spine_entries/XAUUSD__v2_multi_2026_04/run_20260822_162108_XAUUSD/`
> Config: `v2_multi_2026_04`. Not the NS walk (`MC-CRT-SB-…`, TRADE_OPENED=16).
> No G001. No new F-id. TRADE_OPENED n=3 is a process count, not an economic sample.

## Event census (n=7,112)

| event | n |
|---|---:|
| RESET | 2,887 |
| STATE_TRANSITION | 2,382 |
| SWEEP | 1,792 |
| BEGIN_SOFT_CONF | 24 |
| FILTER_REJECTED | 19 |
| TRADE_OPENED | **3** |
| TRADE_STOPPED | 2 |
| CONFIRMATION_FAILED | 1 |
| TRADE_TP1 | 1 |
| TRADE_TP2 | 1 |

Matches the 2026-08-23 evidence-layer snapshot (RESET 2,887 · STATE_TRANSITION 2,382 · SWEEP 1,792 · TRADE_OPENED 3).

## Golden-path funnel (STATE_TRANSITION)

| Step | n | Keep vs previous |
|---|---:|---:|
| RANGE → SWEEP | 1,792 | — |
| SWEEP → DISPLACEMENT | 399 | **22.3%** (78% of sweeps die) |
| DISPLACEMENT → EXPANSION | 142 | 35.6% |
| SWEEP → EXPANSION (shadow) | 6 | — |
| EXPANSION → RETEST | 24 | **16.2%** of 148 expansions |
| RETEST → EXECUTION | 4 | **16.7%** of retests |
| EXECUTION → RESOLUTION | 3 | 3 of 4 |
| TRADE_OPENED | 3 | 3 of 4 executions |

Plus RANGE → SHADOW_PENDING → SWEEP: 6 / 6.

Candidate lifecycle rows = 1,798 = 1,792 RANGE→SWEEP + 6 shadow sweeps.

**Do not collapse with P-GOAL-04 NS study.** That walk’s RETEST→EXECUTION was 23/24 (96%) and TRADE_OPENED=16. This parquet run dies late as well as mid-graph.

## Where candidates die (telemetry `CANDIDATE_LIFECYCLE` n=1,798)

| death_reason | n | share |
|---|---:|---:|
| RESET_HTF | 1,442 | 80.2% |
| RESET_RETRACE | 166 | 9.2% |
| RESET_EXTENSION | 109 | 6.1% |
| RESET_OTHER | 58 | 3.2% |
| FILTER_REJECTED | 19 | 1.1% |
| ACCEPTED | 3 | 0.17% |
| SOFT_CONF_TIMEOUT | 1 | — |

Throughput dies **before a trade exists**. HTF clock is the loudest kill. Matches 2026-08-23 (RESET_HTF 1,442 · RETRACE 166 · EXTENSION 109 · ACCEPTED 3).

RESET *events* (2,887) ≠ candidate deaths (1,798). HTF-prefix reasons = 2,467; many fire on RANGE with no setup (`RANGE→RANGE` 1,089). Occupancy RESET from: SWEEP 1,393 · RANGE 1,089 · DISP 257 · EXP 124 · RETEST 20 · RESOLUTION 3 · EXECUTION 1.

## Late gate (RETEST_REPLAY n=23)

| result | n |
|---|---:|
| OFF_SESSION reject | 19 |
| LOW_SCORE reject | 1 |
| accepted | **3** (= TRADE_OPENED) |

All 19 `FILTER_REJECTED` events are `off_session:OFF_SESSION`. Direction on replay: 20 short-coded (`-1.0`) rejected, 3 long (`1.0`) accepted.

DECISION_DISTANCE n=26: 23 APPROVED / 3 `score_below_threshold` (engine score gate, not UltronRiskGate — P-FLOW-13 naming trap).

## The three TRADE_OPENED (process facts only)

All LONG. Do not join to `y_tp1`.

| ts | session_name in meta | S_score | subsequent event |
|---|---|---:|---|
| 2024-11-12 15:30 | NEWYORK | 0.573 | TRADE_STOPPED next bar |
| 2024-11-15 07:45 | LONDON | 0.487 | TRADE_STOPPED next bar |
| 2025-02-25 15:45 | NEWYORK | 0.565 | TRADE_TP1 then TRADE_TP2 |

n=3 → INSUFFICIENT for expectancy. P-GOAL-13 stands.

## Path B addendum (2026-08-28) — geometry at t=0

Source: `.grok/bot_drop/b9e45917-7abd-481e-92d3-781841c9e368/outbox/PATH-B-TRADE-OPENED.md`
(parquet bot; legal join events ↔ telemetry on `candle_index`; CANDIDATE_LIFECYCLE via `candidate_id`).
Identity MATCH to the table above (3 LONG, timestamps, session_name, S_score, next TRADE_*).
**Refused:** join to opportunities/clean_labels / leakage “survives” / y_tp1 / G001.

| id | entry | sl | tp1 | tp2 | (tp1−entry)/risk | next |
|---|---:|---:|---:|---:|---:|---|
| CRT-0001 | 2614.46 | 2610.0476 | 2618.8724 | 2623.2849 | **1.0** | STOPPED next bar |
| CRT-0002 | 2565.48 | 2564.5599 | 2566.8602 | 2567.3203 | **1.5** | STOPPED next bar |
| CRT-0003 | 2934.39 | 2933.2099 | 2936.1602 | 2936.7503 | **1.5** | TP1 then TP2 |

Process facts (not expectancy):

- All three SL = `disp_low − 0.2 × atr_abs` (engine `build_trade` LONG formula).
- Replay logs `sl_atr_buffer=0.2`, `tp1_mult=1.0`, `tp2_mult=2.0` on every row. The 1.0 is `crt_engine.tp1_atr_multiplier` (the default). Actual TP1 R is 1.0 / 1.5 / 1.5 — 1.5 is the **breakout** intent key (`tp1_atr_multiplier_breakout`). Replay does not log the intent-specific multiplier `build_trade` used. Different ≠ defect this turn.
- CRT-0002 / CRT-0003 entry sits 0.49 / 0.25 above `disp_low` (tight risk vs ATR 2.15 / 4.65). CRT-0001 has 3.28 of room.
- DECISION_DISTANCE `APPROVED` on all three (score gate 0.3, not UltronRiskGate — P-FLOW-13).
- `session_name` is stored metadata, not UTC (F-066). Engine journal, not resolver (F-069).

n=3 remains INSUFFICIENT. P-GOAL-13 stands.

## What this grain can / cannot say

CAN: process funnel, RESET family, session filter at RETEST, TRADE_OPENED count on **this** run.

CANNOT: profit; F-091 ΔMFE; 94k vocabulary; CRT CLOSED; G001; “session is the edge” (F-021 already killed that as selection=session on a different corpus; here it is a late filter on n=23).

F-066 still applies if anyone labels those `session_name` strings as UTC. F-089 (parent-bias reason-flip) is a different config comparison — not measured on this journal.
