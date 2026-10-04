# Frozen Evidence Summary V1

_Generated 2026-07-14T08:12:37.280834+00:00_

## Policy

- Baseline hash parity general requirement: **SUPERSEDED**
- Historical artifacts: **PRESERVED**

## Baseline Trace V1

- SHA: `26e185b943ec5caeee31d32a0b598b543f00a48f953d9fefc9a272eb77ea72d7`
- Discovery: CRT guards do not consume 38-vector as primary transition surface

## Full-run funnel (transition truth)

```text
candles                 47275
RANGE → SWEEP           3390
SWEEP → DISPLACEMENT    315
DISPLACEMENT → EXP      17
shadow SWEEP → EXP      43
unique EXP episodes     60
EXP → RETEST            17
RETEST → EXECUTION       5
EXEC → RESOLUTION       1
TRADE_OPENED            1
```

Occupancy ≠ candidates: 4605 EXPANSION candles ≠ 60 episodes.

## Fail-reason diagnostic

- Class: DIAGNOSTIC_SAMPLE_EVIDENCE (not population rates)
- ON/OFF parity: True
- See raw counts in package index JSON

## Non-use of economic performance

Architecture decision does **not** use PnL/win-rate as evidence.
