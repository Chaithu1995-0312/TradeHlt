# Phase-1 resolver replay — sample acquisition note

**Claim class:** DESCRIPTIVE_ONLY · `economic_claims_allowed: false` · authority: none

**Object definition unchanged:** Unit=ENTRY · Corpus=Phase-1 · Horizon=H20 · Cost=SEM-015 TIMEOUT · Control=Always-Long stride H20 · Resolver-Memory = SHADOW→EXP + `pending_displacement_dir` (strict_memory) · Resolver-TrendBias = SHADOW→EXP + `trend_bias` sign. No widening to the 148 EXPANSION entries; no forbidden work.

## How XAUUSD was chosen

XAUUSD was chosen because it is the sole Phase-1 bound Dataset Identity (dataset_id=XAUUSD_MT5_PHASE1_20260521) in docs/governance/dataset_identity_registry.json; the existing replay defaults (_DEFAULT_CSV / bar_matrix / SEM-015 XAUUSD cost manifest) all pin that same admitted artifact (sha256 4d73f5ce…). Sibling MT5 M15 CSVs share a similar calendar window but are unbound (path_passthrough only) and lack Phase-1 dataset records, bar_matrix, and SEM-015 costs.

## Inventory (Phase-1 vs siblings)

| Instrument | Phase-1 bound | CSV | bar_matrix | SEM-015 cost | Status | Blockers |
|---|---|---|---|---|---|---|
| XAUUSD | True | True | True | True | PHASE1_RUNNABLE | — |
| EURUSD | False | True | False | False | PRESENT_UNBOUND | not_in_phase1_dataset_identity_registry, missing_bar_matrix_parquet_trend_bias, missing_sem015_cost_manifest_for_instrument |
| GBPUSD | False | True | False | False | PRESENT_UNBOUND | not_in_phase1_dataset_identity_registry, missing_bar_matrix_parquet_trend_bias, missing_sem015_cost_manifest_for_instrument |
| AUDUSD | False | True | False | False | PRESENT_UNBOUND | not_in_phase1_dataset_identity_registry, missing_bar_matrix_parquet_trend_bias, missing_sem015_cost_manifest_for_instrument |
| USDJPY | False | True | False | False | PRESENT_UNBOUND | not_in_phase1_dataset_identity_registry, missing_bar_matrix_parquet_trend_bias, missing_sem015_cost_manifest_for_instrument |
| EURCAD | False | True | False | False | PRESENT_UNBOUND | not_in_phase1_dataset_identity_registry, missing_bar_matrix_parquet_trend_bias, missing_sem015_cost_manifest_for_instrument |

**Phase-1 runnable for this object:** ['XAUUSD']
**Present unbound siblings (NOT scored as Phase-1):** ['EURUSD', 'GBPUSD', 'AUDUSD', 'USDJPY', 'EURCAD']

## Per-instrument SHADOW→EXP n

| Instrument | n_collapses | Memory n | TrendBias n | Always-Long n | Always-Long E | Case vs own AL | power (Memory) |
|---|---:|---:|---:|---:|---:|---|---|
| XAUUSD | 6 | 6 | 6 | 2359 | +0.255069 | B | INSUFFICIENT |

## Pooled resolver scoreboard (Memory / TrendBias)

**Pooled n (SHADOW→EXP collapses):** 6
**n ≥ 30 reached:** False

| Arm | n | coverage % | expectancy | PF | win rate | power |
|---|---:|---:|---:|---:|---:|---|
| Resolver-Memory | 6 | 100.00 | -1.933541 | 0.4240 | 0.3333 | INSUFFICIENT |
| Resolver-TrendBias | 6 | 100.00 | +1.475456 | 1.8970 | 0.3333 | INSUFFICIENT |

### Always-Long controls (per-instrument; not pooled into resolver n)

| Instrument | n | coverage % | expectancy | PF | win rate | power |
|---|---:|---:|---:|---:|---:|---|
| Always-Long (XAUUSD) | 2359 | 99.79 | +0.255069 | 1.2143 | 0.5354 | WEAK |

## Cases A–D (interpretive only)

**Case call (pooled resolver vs Always-Long reference `XAUUSD`): B**

- Memory expectancy: `-1.933541`
- TrendBias expectancy: `1.475456`
- Always-Long expectancy (reference): `0.255069`
- Memory beats control: `False`
- TrendBias beats control: `True`

TrendBias expectancy > Always-Long AND Memory expectancy <= Always-Long → trend_bias carries the signal on this object; memory direction is not load-bearing.

Case call is interpretive only on this frozen object. economic_claims_allowed=false. No promotion.

**Power labels:** Memory=`INSUFFICIENT`, TrendBias=`INSUFFICIENT` (MIN_N_LABEL=30). economic_claims_allowed=false.

## Blocker (if n < 30)

Only Phase-1-runnable instrument(s): **['XAUUSD']**. Pooled SHADOW→EXP n=6 < 30.

Sibling M15 CSVs exist on disk (EURUSD, GBPUSD, AUDUSD, USDJPY, EURCAD) with a similar 2024-05→2026-05 window, but they are **not** Phase-1 Dataset Identities. Treating them as Phase-1 would invent corpora. Missing for each unbound sibling: dataset identity admission, bar_matrix (trend_bias), and instrument-specific SEM-015 cost.

### What acquisition would require (new data / admission — not invented here)

- Admit a new Dataset Identity record under docs/governance/datasets/ with dataset_id matching *_PHASE1_* and register it in dataset_identity_registry.json (do not silently treat unbound CSVs as Phase-1).
- Canonical admitted M15 CSV at the bound path (native_fetch; hash-bound).
- Build results/research/bar_matrix/<SYM>_M15/bar_matrix.parquet for trend_bias + atr_abs (same SEM-018 surface used by Resolver-TrendBias / Always-Long).
- Measure SEM-015 ComponentCostModel for that instrument (do not reuse XAUUSD oz costs on FX).
- Re-run this sample_acquisition wrapper to pool SHADOW→EXP collapses with instrument tags.
- Object definition stays SHADOW→EXP + pending_displacement_dir / trend_bias sign — do not harvest the 148 EXPANSION entries.

## Forbidden-work confirmation

All forbidden flags in the JSON artifact are `false`.

## Artifacts

- Inventory + scoreboard JSON: `D:\Tradelatest\results\analysis\phase1_resolver_replay\sample_acquisition\scoreboard.json`
- Pooled collapses: `D:\Tradelatest\results\analysis\phase1_resolver_replay\sample_acquisition\collapses_pooled.json`
- This note: `D:\Tradelatest\docs\research\phase1_resolver_replay_sample_acquisition_note.md`

generated_at (UTC): `2026-09-09T17:57:28.681605+00:00`

---
No economic promotion. Object unchanged. Measure-before-promote. Cases A–D only.
