# PIT Phase A — Gate-ON Ledger A/B

_Generated 2026-07-11T07:23:02.126706+00:00 · ACTIVE_VERSION=v2_multi_2026_04 · read-only._

## Staged expansion: `IDENTICAL_THEN_ONE_MORE`
- expanded: ['SOLUSDT']

## BNBUSDT — status=OK
- isolation: **PASS** (bars=7922)
- PC-1: **PASS**
- PC-2 sensitivity: **False** — PC-2 failure is a REPORTED SENSITIVITY LIMITATION, not harness failure
- gate-ON A/B: trades 11→11 identical=True overlap=100.0% +0/-0
- gate-OFF F-029 replay: identical=True truth_conflict=False

## SOLUSDT — status=OK
- isolation: **PASS** (bars=7922)
- PC-1: **PASS**
- gate-ON A/B: trades 6→6 identical=True overlap=100.0% +0/-0

## Scope

- Intervention = TOTAL causal structure-graph swap (10-feature dependency closure).
- No feature-level attribution claimed.
- FINAL_LEDGER_EXPOSURE lives here only (not inferred from ZoneGate score deltas).
- F-029 gate-OFF claim refined-not-reversed unless truth_conflict flagged.
