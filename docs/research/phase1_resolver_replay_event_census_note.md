# Phase-1 resolver replay — event object-identity census note

**Status:** DESCRIPTIVE_ONLY · economic_claims_allowed=false · no Case reopening · no promotion · no population expansion

**Date:** 2026-09-09 (Asia/Calcutta local task day)

**Question:** Do the 6 Phase-1 XAUUSD SHADOW→EXP collapses share one mechanism, or multiple?

## Short answer (provisional)

**A_one_mechanism** for formation identity: every collapse is the same shadow-resume gate
(RANGE → SHADOW_PENDING → SWEEP → EXPANSION, prior-window displacement restore, strength check skipped, shadow_used=true).
Ambient/context fields and post-path death modes vary; those are subtypes on measured fields, not a second resume mechanism in this n=6 set.

## What was measured

Joined, without inventing ontology:

1. collapses.json / scoreboard.LATEST.json (dirs + H20/SEM-015 net_R)
2. bt_run XAUUSD_events.jsonl + XAUUSD_crt_telemetry.jsonl (T3 path, lifecycle, expansion retrace)
3. bar_matrix.parquet by timestamp (T1 crt_state_resolved, parent track, PDH/PDL distances, OB distances, session/feature states)

## Coherence call detail

| Option | Verdict |
|---|---|
| A_one_mechanism | **Provisional call** — shared formation path/reason/telemetry flags |
| B_multiple_mechanisms | Not selected — no second distinct formation gate/reason template observed |
| C_insufficient_fields_to_decide | Not selected for formation identity (though PDH/PDL abs prices, OB ids, decision scores remain UNAVAILABLE) |

economic_claims_allowed=false always. Scoreboard Case B remains interpretive-only and is not reopened here.

## Common vs not-common (headline)

**Common:** identical SHADOW→EXP resume path; strength skip; shadow_used; unqualified expansion; reset-ended; null approval score; no soft-conf decision row; NoCHoCH; both resolver arms scored.

**Not common:** dir mix (2 SHORT / 4 LONG); T1/T3 agree 3/6; parent stage C1/C2/C3 mix; death RESET_RETRACE(4)/RESET_EXTENSION(2); mem↔trendbias dir agree only 1/6; sessions ASIA/LONDON/NEWYORK/OVERLAP; ATR ~1.3–10.1.

## UNAVAILABLE columns

- Absolute PDH/PDL prices (distances only)
- Order-block id/OHLC/window (distance only)
- Decision / S_score / decision_distance at these collapses

## Artifacts

- results/analysis/phase1_resolver_replay/event_census/census.json
- results/analysis/phase1_resolver_replay/event_census/census.md
- This note: docs/research/phase1_resolver_replay_event_census_note.md

## Forbidden-work confirmation

No continuous_disp_to_expansion flip; no CHoCH wire; no occupancy reopen; no parity optimize; no April reclassify; no TV forensic adjudicator; no unit widening to 148 EXP; no economic promotion.

