# Phase-1 four-arm resolver replay evidence note

**run_id:** `run_20260909_202201`

**Claim class:** DESCRIPTIVE_ONLY · `economic_claims_allowed: false` · authority: none

Four-arm H20 on this run remains VALID (`schema_bridge.surfaces.four_arm_H20`). Load first: `docs/research/phase1_run_20260909_202201_coding_llm_context.yaml`. Coverage is n/47255, never 31/148.

Frozen standing contract: Unit=ENTRY · Corpus=Phase-1 · Horizon=H20 · Cost=SEM-015 TIMEOUT · Control=Always-Long (stride H20).

Arms (separate event generators; Resolver EXP ⊄ Engine EXP):
- **Engine-Atlas** — EXP entry + atlas direction (mostly DISP→EXP)
- **Resolver-Memory** — SHADOW→EXP + `pending_displacement_dir` (strict_memory; skip trend_bias fill)
- **Resolver-TrendBias** — SHADOW→EXP + `trend_bias` sign
- **Always-Long** — stride H20 on the same `close_at_horizon` / SEM-015 TIMEOUT path

coverage = n_entries / eligible corpus. Never Resolver-n / Engine-n.
Every arm prints n | coverage | expectancy | PF | win rate, including ugly / n<30 cells.

**source_run_id (dual-construction parquet):** `run_20260906_013609`

Resolver CREATE census (same grain, injection=none, not a join to engine 69): `docs/research/phase1_resolver_create_census_note.md` · n=454.

## Scoreboard

| Arm | n | coverage % | expectancy | PF | win rate | power |
|---|---:|---:|---:|---:|---:|---|
| Engine-Atlas | 148 | 0.3132 | +0.027665 | 1.0221 | 0.4662 | WEAK |
| Resolver-Memory | 31 | 0.0656 | +0.348100 | 1.3739 | 0.5484 | WEAK |
| Resolver-TrendBias | 31 | 0.0656 | -0.466977 | 0.6508 | 0.4516 | WEAK |
| Always-Long | 2359 | 4.9921 | +0.255069 | 1.2143 | 0.5354 | WEAK |

**n_eligible_corpus (H20-walkable bars):** 47255
**n_resolver_shadow_exp (universe for Memory/TrendBias before strict_memory):** 31
**n_engine_atlas_exp:** 148

## Object attribution (frozen)

- Engine EXP = mostly DISP→EXP (plus a small SHADOW_EXPANSION_CONFIRMED remainder).
- Resolver EXP = SHADOW→EXP. 0 DISP→EXP on this resolver object.
- A result on one arm is not a result about the other construction's EXPANSION label.

## Direction attribution (this run)

- Engine atlas `from_state`: `{'DISPLACEMENT': 142, 'SWEEP': 6}` (the 6 shadow-resume collapses are labeled SWEEP→EXP in the atlas, not SHADOW_PENDING).
- strict_memory skips: `{'none': 31}`
- Memory vs TrendBias direction agree: `0` / `31`

## Cases A–D (interpretive only; Memory / TrendBias vs Always-Long)

- **Case A:** Memory expectancy > Always-Long AND TrendBias expectancy <= Always-Long → pending_displacement_dir carries directional information beyond drift on this object; trend_bias does not. **← CALL**
- **Case B:** TrendBias expectancy > Always-Long AND Memory expectancy <= Always-Long → trend_bias carries the signal on this object; memory direction is not load-bearing.
- **Case C:** Both Memory and TrendBias expectancy > Always-Long → both arms informative vs drift on this object (agreement is diagnostic only, not an objective).
- **Case D:** Neither Memory nor TrendBias expectancy > Always-Long → null on this ENTRY/H20/SEM-015 TIMEOUT object; no Case promotes.

**Case call: A**

- Memory expectancy: `0.3481`
- TrendBias expectancy: `-0.466977`
- Always-Long expectancy: `0.255069`
- Memory beats control: `True`
- TrendBias beats control: `False`

Case call is interpretive only on this frozen object. economic_claims_allowed=false. No promotion. Engine-Atlas is a fourth directional source on the scoreboard, not a Case letter.

## SUPERSEDED object (do not reuse as this scoreboard)

The 2026-09-09 n=6 scoreboard captured **engine** `SHADOW_EXPANSION_CONFIRMED` via `StateMachine.try_shadow_pending_to_expansion`. That is not Resolver EXP. See `docs/research/phase1_resolver_replay_n6_funnel_diagnostic.md`. Kept, not deleted.

## How to run

```powershell
cd D:\Tradelatest
$env:PYTHONPATH='D:\Tradelatest'
.\venv\Scripts\python.exe scripts\analysis\phase1_resolver_replay_evidence.py
```

## Provenance

- run_id: `run_20260909_202201`
- source_run_id: `run_20260906_013609`
- csv_sha256: `4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56`
- cost: `SEM-015` (MEASURED)
- config_version: `v2_htfcrt_2026_08`
- git_sha: `61094ea6ff4fc6736b27e171b0141623f27955a5` tree_dirty=`True`
- generated_at (UTC): `2026-09-09T20:22:49.301518+00:00`
- resolver replay mismatches: `0`

## Forbidden-work confirmation

All forbidden flags in the JSON artifact are `false` (no continuous_disp flip, no CHoCH, no occupancy reopen, no parity optimize, no April reclassify, no TV forensic adjudicator, no economic promotion, no UI/L-003).

---
No economic promotion language. Measure-before-promote. Cases A–D only.
