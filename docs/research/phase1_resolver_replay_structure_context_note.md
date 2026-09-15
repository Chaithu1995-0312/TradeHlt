# Phase-1 resolver replay — structure context note

**Status:** DESCRIPTIVE_ONLY · economic_claims_allowed=false · no Case reopening · no promotion · no population expansion

**Date:** 2026-09-10 (Asia/Calcutta)

**Question:** Given path-only `A_one_mechanism` lock, do the same 6 XAUUSD SHADOW→EXP events also share one liquidity/structure environment?

## Short answer

**STRUCTURE_ENVIRONMENT_HETEROGENEOUS.** Same state-machine path; not the same structure/liquidity environment.

All six closes sit inside the prior closed D1 range (below PDH, above PDL) — a shared ambient PDH/PDL relation newly recovered from absolute prices. That is not enough for environment identity: order-block presence/side, session, regime, ATR, parent-track stage, and liquidity_distance still vary across the six.

## Recovered vs still unavailable

**Recovered**

- Absolute PDH/PDL prices + qualitative side relation for all 6 (ParentCandleBuilder D1; distance-validated vs bar_matrix).
- Active unmitigated OB identity/OHLC/formation timestamp for E1,E3,E4,E5; measured absence for E2,E6.

**Still UNAVAILABLE**

- S_score / soft-conf / decision_distance at collapse (no telemetry attachment; lifecycle scores null/zero). Not invented.

## Method (read-only measurement)

1. Stream `data/mt5/XAUUSD_M15.csv` with the same SMC config the pipeline uses (`swing_window=2`, `smc_max_window=100`).
2. PDH/PDL = most recently closed D1 parent high/low (`features.smc.levels` / `ParentCandleBuilder`).
3. OB = `find_active_order_block` on the trailing window; origin OHLC from the origin candle.
4. Validate reconstructed distances against `bar_matrix.parquet` rows joined by timestamp.
5. Decision fields: search `XAUUSD_crt_telemetry.jsonl` / `XAUUSD_events.jsonl` only — mark UNAVAILABLE when absent.

## Relation to census lock

Does **not** reopen or overturn provisional `A_one_mechanism` for formation-path identity. It answers the *next* descriptive question: path coherence ≠ structure-environment coherence in this n=6 set.

economic_claims_allowed=false always.

## Artifacts

- `results/analysis/phase1_resolver_replay/event_census/structure_context.json`
- `results/analysis/phase1_resolver_replay/event_census/structure_context.md`
- This note: `docs/research/phase1_resolver_replay_structure_context_note.md`

## Forbidden-work confirmation

No continuous_disp_to_expansion flip; no CHoCH wire; no occupancy reopen; no parity optimize; no April reclassify; no TV forensic adjudicator; no unit widening; no economic promotion; no years/instruments expansion.
