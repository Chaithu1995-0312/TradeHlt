# Phase-1 resolver CREATE census

**source_run_id:** `run_20260906_013609`  
**session_run_id:** `run_20260909_202201`  
**injection:** `none`  
**Claim class:** DESCRIPTIVE_ONLY · `economic_claims_allowed: false` · authority: none

**Producer:** resolver only. Do **not** join to engine CREATE n=69.

**Predicate:** `CRTStateResolver._force_range_reset` · `kind==htf` · `prev==DISPLACEMENT` · `shadow_on_htf_displacement_reset`.

Replay reproduced parquet `ontology_state` (0 mismatches) and captured 31/31 SHADOW→EXP.

## Count

```text
Resolver CREATE = 454
```

## Occupancy funnel (resolver CREATE objects)

```text
454 CREATE
 ├─ 407 EXPIRED_TTL (never SHADOW_PENDING)
 └─  47 reached SHADOW_PENDING
        ├─ 31 SHADOW_PENDING → EXPANSION
        └─ 16 reached SHADOW then EXPIRED_TTL
           (parquet occupancy exit: SHADOW_PENDING → RANGE n=16)
```

SHADOW entries without an open CREATE: **0**. So the 47 parquet RANGE→SHADOW_PENDING entries are descendants of these 454 CREATEs.

`CLEARED_NON_HTF_RESET=0` · `OVERWRITTEN_BY_NEW_MEMORY=0` · `UNRESOLVED_AT_EOF=0` · `SHADOW_PENDING_TO_RANGE` as a `_update_memory` outcome = 0 (the 16 closed as TTL expire).

## Rates (resolver producer only)

```text
P(SHADOW_PENDING | CREATE) = 47/454 ≈ 0.1035
P(EXPANSION | SHADOW_PENDING) = 31/47 ≈ 0.6596
P(EXPANSION | CREATE) = 31/454 ≈ 0.0683
```

Occupancy, not trades. Not comparable to engine 6/69 as one durability statistic.

## Artifact

`results/analysis/phase1_resolver_replay/run_20260909_202201/resolver_create_census.json`

## How to run

```powershell
$env:PYTHONPATH='D:\Tradelatest'
.\venv\Scripts\python.exe scripts\analysis\phase1_resolver_replay_evidence.py --resolver-create-census
```
