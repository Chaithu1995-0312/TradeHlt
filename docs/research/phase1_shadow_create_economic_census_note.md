# Phase-1 shadow CREATE economic census

**session_run_id:** `run_20260909_202201`
**source_run_id:** `run_20260906_013609`

**Claim class:** DESCRIPTIVE_ONLY · `economic_claims_allowed: false` · no promotion

**REBUILT 2026-09-10 — timestamp→CSV join.** `created_idx` is event timestamp → CSV/parquet `bar_index`. Funnel 69/45/18/6 unchanged. `engine_candle_index` kept; `age_at_reset` is engine-domain. Load first: `docs/research/phase1_run_20260909_202201_coding_llm_context.yaml`.

Unit = **CREATE** of HTF-displacement pending memory (n=69), not SHADOW→EXP restore (n=6).
Restore rate given SHADOW_PENDING is already 6/6. Do not optimize that branch.

## Funnel

```
69 CREATE
├─ 45 EXPIRE
├─ 17 CLEAR
└─ 6 RESTORE → EXPANSION
```

Assembled outcomes: `{'EXPIRED_TTL': 45, 'CLEARED_OR_OVERWRITTEN': 18, 'RESTORED_TO_EXPANSION': 6}`

## Headline H20 on all 69 creates

| Arm | n | E | PF | WR | power |
|---|---:|---:|---:|---:|---|
| memory_dir | 69 | -0.0533 | 0.963 | 0.507 | WEAK |
| trendbias_dir | 69 | +1.0174 | 2.160 | 0.623 | WEAK |
| always_long | 69 | +0.7895 | 1.791 | 0.522 | WEAK |

Lift is E(memory_dir | bucket) − E(always_long | same bars).

## age_at_reset

| Feature | Bucket | n | E | E_AL | lift | PF | WR | power |
|---|---|---:|---:|---:|---:|---:|---:|---|
| age_at_reset_bucket | 1 | 30 | -0.0417 | +1.5800 | -1.6217 | 0.972 | 0.533 | WEAK |
| age_at_reset_bucket | 2 | 14 | -1.6224 | +1.5616 | -3.1840 | 0.369 | 0.286 | INSUFFICIENT |
| age_at_reset_bucket | 3 | 11 | +0.1574 | -0.4867 | +0.6441 | 1.196 | 0.545 | INSUFFICIENT |
| age_at_reset_bucket | 4+ | 10 | +0.6254 | -1.1289 | +1.7543 | 1.830 | 0.600 | INSUFFICIENT |
| age_at_reset_bucket | UNKNOWN | 4 | +3.0759 | +0.4637 | +2.6123 | 8.567 | 0.750 | INSUFFICIENT |

## pending_dir

| Feature | Bucket | n | E | E_AL | lift | PF | WR | power |
|---|---|---:|---:|---:|---:|---:|---:|---|
| pending_dir | SHORT | 41 | -0.7654 | +0.6529 | -1.4183 | 0.598 | 0.488 | WEAK |
| pending_dir | LONG | 28 | +0.9895 | +0.9895 | +0.0000 | 2.378 | 0.536 | INSUFFICIENT |

## parent CRT

| Feature | Bucket | n | E | E_AL | lift | PF | WR | power |
|---|---|---:|---:|---:|---:|---:|---:|---|
| parent_crt | RANGE_C1 | 38 | -0.4824 | +0.5995 | -1.0819 | 0.673 | 0.474 | WEAK |
| parent_crt | MANIPULATION_C2 | 21 | +0.5478 | +0.4184 | +0.1294 | 1.460 | 0.476 | INSUFFICIENT |
| parent_crt | DISTRIBUTION_C3 | 10 | +0.3153 | +2.2909 | -1.9756 | 1.183 | 0.700 | INSUFFICIENT |

## session

| Feature | Bucket | n | E | E_AL | lift | PF | WR | power |
|---|---|---:|---:|---:|---:|---:|---:|---|
| session_bucket | ASIA_0_8 | 19 | +0.6470 | +1.5596 | -0.9127 | 1.499 | 0.526 | INSUFFICIENT |
| session_bucket | LONDON_8_13 | 18 | -0.3878 | +0.1775 | -0.5653 | 0.645 | 0.389 | INSUFFICIENT |
| session_bucket | NY_17_22 | 17 | -0.2268 | +0.0344 | -0.2613 | 0.836 | 0.647 | INSUFFICIENT |
| session_bucket | LONDON_NY_OVERLAP_13_17 | 12 | +0.1207 | +1.2478 | -1.1270 | 1.088 | 0.500 | INSUFFICIENT |
| session_bucket | OFFHOURS_22_24 | 3 | -2.1936 | +2.0295 | -4.2231 | 0.529 | 0.333 | INSUFFICIENT |

## T1/T3 agree vs disagree

| Feature | Bucket | n | E | E_AL | lift | PF | WR | power |
|---|---|---:|---:|---:|---:|---:|---:|---|
| t1_t3 | AGREE | 61 | -0.2167 | +1.0837 | -1.3004 | 0.860 | 0.492 | WEAK |
| t1_t3 | DISAGREE | 8 | +1.1931 | -1.4537 | +2.6468 | 3.560 | 0.625 | INSUFFICIENT |

## funnel outcome (diagnostic, not a selector)

| Feature | Bucket | n | E | E_AL | lift | PF | WR | power |
|---|---|---:|---:|---:|---:|---:|---:|---|
| outcome | EXPIRED_TTL | 45 | -0.4806 | +1.3146 | -1.7952 | 0.733 | 0.467 | WEAK |
| outcome | CLEARED_OR_OVERWRITTEN | 18 | +1.2539 | +0.2154 | +1.0385 | 3.108 | 0.667 | INSUFFICIENT |
| outcome | RESTORED_TO_EXPANSION | 6 | -0.7699 | -1.4270 | +0.6571 | 0.279 | 0.333 | INSUFFICIENT |

## ATR tercile among creates

| Feature | Bucket | n | E | E_AL | lift | PF | WR | power |
|---|---|---:|---:|---:|---:|---:|---:|---|
| atr_tercile | T3_HIGH | 24 | -1.0785 | +1.6829 | -2.7613 | 0.495 | 0.458 | INSUFFICIENT |
| atr_tercile | T1_LOW | 23 | +0.1205 | +0.1501 | -0.0296 | 1.114 | 0.478 | INSUFFICIENT |
| atr_tercile | T2_MID | 22 | +0.8834 | +0.4834 | +0.4001 | 1.857 | 0.591 | INSUFFICIENT |

## Ranked lift (n≥5, H20, memory_dir vs always_long on the same creates)

| Feature | Bucket | n | lift | E | E_AL |
|---|---|---:|---:|---:|---:|
| t1_t3 | DISAGREE | 8 | +2.6468 | +1.1931 | -1.4537 |
| age_at_reset_bucket | 4+ | 10 | +1.7543 | +0.6254 | -1.1289 |
| outcome | CLEARED_OR_OVERWRITTEN | 18 | +1.0385 | +1.2539 | +0.2154 |
| outcome | RESTORED_TO_EXPANSION | 6 | +0.6571 | -0.7699 | -1.4270 |
| age_at_reset_bucket | 3 | 11 | +0.6441 | +0.1574 | -0.4867 |
| atr_tercile | T2_MID | 22 | +0.4001 | +0.8834 | +0.4834 |
| parent_crt | MANIPULATION_C2 | 21 | +0.1294 | +0.5478 | +0.4184 |
| pending_dir | LONG | 28 | +0.0000 | +0.9895 | +0.9895 |
| atr_tercile | T1_LOW | 23 | -0.0296 | +0.1205 | +0.1501 |
| session_bucket | NY_17_22 | 17 | -0.2613 | -0.2268 | +0.0344 |
| session_bucket | LONDON_8_13 | 18 | -0.5653 | -0.3878 | +0.1775 |
| session_bucket | ASIA_0_8 | 19 | -0.9127 | +0.6470 | +1.5596 |
| parent_crt | RANGE_C1 | 38 | -1.0819 | -0.4824 | +0.5995 |
| session_bucket | LONDON_NY_OVERLAP_13_17 | 12 | -1.1270 | +0.1207 | +1.2478 |
| t1_t3 | AGREE | 61 | -1.3004 | -0.2167 | +1.0837 |
| pending_dir | SHORT | 41 | -1.4183 | -0.7654 | +0.6529 |
| age_at_reset_bucket | 1 | 30 | -1.6217 | -0.0417 | +1.5800 |
| outcome | EXPIRED_TTL | 45 | -1.7952 | -0.4806 | +1.3146 |
| parent_crt | DISTRIBUTION_C3 | 10 | -1.9756 | +0.3153 | +2.2909 |
| atr_tercile | T3_HIGH | 24 | -2.7613 | -1.0785 | +1.6829 |

No bucket is a promotion. n=69 total; most cells are INSUFFICIENT.

JSON: `results/analysis/phase1_resolver_replay/run_20260909_202201/create_economic_census/census.json`
