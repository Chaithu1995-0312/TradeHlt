# CRT XAUUSD Funnel Diagnostic

> **Policy (2026-07-14):** Historical full-run transition/event/trade hash equality is **not** a permanent golden acceptance criterion for future authorized behavior changes. See `TASK_CLASSIFICATION_BEHAVIOR_POLICY.md`. This diagnostic remains **preserved historical evidence**.

_Generated 2026-07-14T07:57:38.230949+00:00_  
**Run:** `results/cert_xau_phase2/run_20260711_202626_XAUUSD`  
**Mode:** MEASURE ONLY — no threshold changes

## Closure statement

```text
ROOT_CAUSE_CLASS = UPSTREAM_CRT_CANDIDATE_COLLAPSE
PRIMARY_VISIBLE_BOUNDARY = EXPANSION_TO_RETEST
SECONDARY_VISIBLE_BOUNDARY = SWEEP_TO_DISPLACEMENT
TERTIARY_VISIBLE_BOUNDARY = RETEST_SOFTCONF_TO_TRADE_OPENED_SESSION_FILTER
DOWNSTREAM_ENGINE_REJECTION = NOT_PRIMARY
ARCHITECTURAL_SUPPRESSION_RISK = SINGLE_ACTIVE_CANDIDATE + LONG_EXPANSION_DWELL + HTF_RESET
THRESHOLD_CHANGE_AUTHORIZED = NO — MEASURE COMPLETE; geometry fail-reasons still NOT_INSTRUMENTED
NEXT_AUTHORIZED_MEASUREMENT = Optional diagnostic hooks on try_sweep_to_displacement / try_displacement_to_expansion / try_expansion_to_retest fail branches for per-reason counts (behavior-preserving, default off)
```

## Headline

- candles: **47275**
- setups/approved: **1** / **1**
- rejected_trades: **0** reasons={}
- gap_resets: **121**
- config: `v2_multi_2026_04`

## Occupancy vs entries (caution)

| State | Occupancy (candles) | Entries (transitions) |
|---|---:|---:|
| RANGE | 35197 | None |
| SWEEP | 7005 | 3433 |
| DISPLACEMENT | 373 | 315 |
| SHADOW_PENDING | 43 | None |
| EXPANSION | 4605 | 60 |
| RETEST | 17 | 17 |
| EXECUTION | 5 | 5 |

## Exact transition funnel (from STATE_TRANSITION events)

```text
RANGE → SWEEP                 3390
SWEEP → DISPLACEMENT          315  (9.292% of RANGE→SWEEP)
DISPLACEMENT → EXPANSION      17  (5.397% of SWEEP→DISP)
SWEEP → EXPANSION (shadow)    43
unique EXPANSION episodes     60
EXPANSION → RETEST            17  (28.333% of episodes)
RETEST → EXECUTION            5  (29.412% of RETEST)
EXECUTION → RESOLUTION        1
TRADE_OPENED                  1
```

## EXPANSION episodes

- count: **60**
- ended_by: `{'reset': 43, 'retest': 17}`
- dwell (sane durations): `{'count': 40, 'min': 1.0, 'p25': 1.0, 'median': 1.0, 'p75': 2.0, 'p90': 11.0, 'p99': 212.0, 'max': 346.0, 'mean': 18.5}`
- max_retrace_depth_abs: `{'count': 60, 'min': 0.0, 'p25': 0.0, 'median': 0.8550000000000182, 'p75': 16.059999999999945, 'p90': 49.69999999999982, 'p99': 205.20000000000027, 'max': 225.5599999999995, 'mean': 19.667333}`
- distance_to_ceiling: `{'count': 60, 'min': -217.14649999999946, 'p25': -20.466999999999985, 'median': 0.0, 'p75': 0.0, 'p90': 0.23200000000031196, 'p99': 1.3345000000003435, 'max': 1.4240000000000463, 'mean': -18.094444}`
- Of 60 expansion episodes, 17 qualified retest, 43 ended by reset, 0 by TTL EXPIRED. Zero TTL expiry implies candidates die by HTF/retrace reset or qualify before TTL.

## Candidate deaths (single active lifecycle)

- candidates: **3433**
- death_reasons: `{'RESET_HTF': 3323, 'RESET_RETRACE': 66, 'FILTER_REJECTED': 12, 'ACCEPTED': 1, 'RESET_OTHER': 29, 'RESET_EXTENSION': 2}`

## RETEST → trade residual

- 17 RETEST entries and 17 soft-conf decision records (all APPROVED at score gate) but only 5 RETEST→EXECUTION transitions and 1 TRADE_OPENED. 12 FILTER_REJECTED off_session + retest_replay OFF_SESSION explain most non-trades; 4 EXECUTION resets without RESOLUTION remain secondary residual.
- FILTER_REJECTED: `{'off_session:OFF_SESSION': 12}`
- retest_replay: `{"(False, 'OFF_SESSION')": 12, '(True, None)': 1}`

## Downstream

- verdict: **NOT_PRIMARY**
- summary rejected_trades=0 and empty rejection_reasons; collapse is upstream

## Measurement gaps (status update)

Historical run telemetry lacked per-guard geometry fail reasons.  
**Follow-up (OBSERVATION_ONLY, 2026-07-14):** `CRTFailReasonCounters` +  
`docs/governance/crt_fail_reason_diagnostic-2026-07-14.json` measure try_* fail
reasons on a **3000-candle** deterministic prefix (ON/OFF parity PASS).  
Full 47k historical hash equality is **not** required (see  
`TASK_CLASSIFICATION_BEHAVIOR_POLICY.md`).

