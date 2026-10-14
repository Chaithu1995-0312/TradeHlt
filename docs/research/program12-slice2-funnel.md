# Program 12 Slice 2 funnel

Lane: measurement / evidence. `economic_claims_allowed` is false. No G001.
Ladder corpus = the one-month slice (pre-registration §17, 2026-10-06).
Depth caveat stands. Path A long fetch stays deferred. D1 is not in this slice.
Native H4/D1 from 1998 stay on disk for F-080 parity.

- Parent: `data/XAUUSD_M15.csv`
- Bars: 2116
- First: 2026-07-07 01:00:00
- Last: 2026-08-06 23:45:00
- sha256: `478b075150935c950ccc749925709db783e337c55c886d6dda1e3ee8b9692c5b`
- Contract: `MC-LADDER-XAUUSD-HTF-V1`
- Cost ruler on the research walk: `component_measured.v1` (SEM-015). Journal pnl is a different ruler.

## H1

- Status: OK
- Projected bars: 528
- Funnel: SWEEP 40, DISPLACEMENT 3, EXPANSION 0, RETEST 0, TRADE_OPENED 0, journal 0
- Walked (R computed, not printed): 0
- Clusters: 0 (floor 30)
- Stop floor widened: 0
- ATR unpublished: 0
- Journal price fallback: 0
- Walk failures: 0
- Verdict: INSUFFICIENT
- Failing condition: n_clusters < 30
- expectancy_published: false
- Controls used as a gate: false

## H4

- Status: OK
- Projected bars: 137
- Funnel: SWEEP 6, DISPLACEMENT 0, EXPANSION 0, RETEST 0, TRADE_OPENED 0, journal 0
- Walked (R computed, not printed): 0
- Clusters: 0 (floor 30)
- Stop floor widened: 0
- ATR unpublished: 0
- Journal price fallback: 0
- Walk failures: 0
- Verdict: INSUFFICIENT
- Failing condition: n_clusters < 30
- expectancy_published: false
- Controls used as a gate: false

A cluster count under 30 is INSUFFICIENT. This page records the funnel and whether the ladder ran. It is not an E[R] result.
