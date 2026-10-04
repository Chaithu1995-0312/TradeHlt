# PIT Phase A — Centered-Swing Causal Blast Radius

_Generated 2026-07-11T07:22:25.941471+00:00 · ACTIVE_VERSION=v2_multi_2026_04 · read-only._

## Executive summary
- Leakage proved (B1): **True** (centered differ_rate=0.13%; causal invariant=True)
- Value-level any-of-10 differ (BNB): **63.5%**
- CRT final-score differ rate: **7.1%**
- Zone HARD flip rate (centered→causal): **0.0%**
- Live-zero (default-absent path): **True** (CONDITIONAL_PROVEN)
- RR model contaminated dims active: **10/10**

## A. Value level (centered production vs causal re-derived chain)

### crypto: BNBUSDT (29922 bars)

| feature | differ_rate | bars_differ | |Δ| mean | centered≠0 | causal≠0 |
|---|---:|---:|---:|---:|---:|
| `double_sweep` | 2.90% | 869 | 0.0290 | 2.67% | 5.38% |
| `sweep_detected` | 6.24% | 1866 | 0.0624 | 9.36% | 15.60% |
| `liquidity_sweep` | 6.32% | 1891 | 0.0640 | 9.36% | 15.60% |
| `break_of_structure` | 11.62% | 3476 | 0.1162 | 27.27% | 38.89% |
| `swing_high` | 29.57% | 8848 | 0.2957 | 14.97% | 14.97% |
| `swing_low` | 29.02% | 8684 | 0.2902 | 14.66% | 14.66% |
| `higher_high` | 9.30% | 2784 | 0.0930 | 19.34% | 28.65% |
| `lower_low` | 8.71% | 2607 | 0.0871 | 17.36% | 26.07% |
| `liquidity_distance` | 16.26% | 4866 | 0.1009 | 98.30% | 98.23% |
| `liquidity_pressure_score` | 16.26% | 4866 | 0.0277 | 100.00% | 100.00% |
- any-of-10 differ rate: **63.47%**

### fx: EURUSD (29922 bars)

| feature | differ_rate | bars_differ | |Δ| mean | centered≠0 | causal≠0 |
|---|---:|---:|---:|---:|---:|
| `double_sweep` | 3.83% | 1146 | 0.0383 | 2.96% | 6.45% |
| `sweep_detected` | 6.19% | 1853 | 0.0619 | 10.33% | 16.52% |
| `liquidity_sweep` | 6.32% | 1890 | 0.0644 | 10.33% | 16.52% |
| `break_of_structure` | 11.42% | 3416 | 0.1142 | 28.47% | 39.88% |
| `swing_high` | 28.04% | 8391 | 0.2804 | 14.11% | 14.11% |
| `swing_low` | 28.15% | 8422 | 0.2815 | 14.13% | 14.13% |
| `higher_high` | 9.12% | 2729 | 0.0912 | 20.33% | 29.45% |
| `lower_low` | 8.69% | 2601 | 0.0869 | 18.61% | 27.30% |
| `liquidity_distance` | 16.48% | 4931 | 0.1092 | 99.05% | 99.02% |
| `liquidity_pressure_score` | 16.48% | 4931 | 0.0288 | 100.00% | 100.00% |
- any-of-10 differ rate: **62.48%**

## B1. Prefix-invariance (leakage mechanism)

Symbol: BNBUSDT · prefix_raw=874 · full_raw=30000

| family | bars_checked | differ_rate | prefix_invariant |
|---|---:|---:|---|
| centered production (`swing_high/low`, sweeps) | 796 | 0.13% | False |
| `*_causal_confirmed` | 794 | 0.00% | True |

**Concrete example** at `2024-05-31 02:15:00` (swing_high): prefix_flag=0 → full_flag=1 (prefix_n=874)

> rolling(w=5, center=True, min_periods=5) at bar t uses bars t-2..t+2. On a prefix cut the future half is missing (NaN roll) so a true swing can be missed (flag 0→1 when future bars arrive). Causal = centered.shift(2) only needs data through t.

**Leakage proved:** True

## B3. Live ingestion contract

- Hypothesis status: **CONDITIONAL_PROVEN**
- May call variant live-zero: **True**
- Citations: `src/runtime/live_engine_hook.py:394-402`, `src/core/feature_store.py:115-131`
- Production feeder hits (non-hook): 0

> When trade_data omits structure/sweep keys, live_engine_hook defaults them to 0.0 (citations below). FeatureStore only rewrites double_sweep from liquidity_sweep history; if liquidity_sweep is also defaulted 0, double_sweep stays 0. No production inout feeder was found that runs FeaturePipeline or otherwise populates centered swing structure into trade_data. Therefore the observed-live-contract variant IS live-zero on the default-absent path. If an external feeder injects non-zero structure keys, that path is unobserved in-repo.

## B2a. CRT-score channel

- s_sweep differ rate: **7.07%**
- final CRT score differ rate: **7.07%**
- |Δ final|: mean 0.0171 · p95 0.2450 · max 0.3500

> CRT-score delta is a NECESSARY channel to fusion impact, not a production-loss claim (F-037 gate-OFF research spine; live always gate-ON).

## B2b. ZoneGate exposure (levels kept separate)

### ZONE_VALUE_EXPOSURE
- mean contaminated weight fraction: **40.00%**

### ZONE_SCORE_EXPOSURE
- centered vs causal score differ rate: **63.34%**
- centered vs observed-live-contract score differ rate: **100.00%**

### ZONE_GATE_EXPOSURE
- HARD flip rate centered→causal: **0.01%** (1 flips)
- HARD flip rate centered→live-zero: **0.00%**

### FINAL_LEDGER_EXPOSURE
- NOT_INFERRED_HERE: FINAL_LEDGER_EXPOSURE comes ONLY from pit_swing_gateon_ab.py (gate-ON execution). Never inferred from value/score/gate rates above.

## C. Artifact / dataset exposure

- RR model: ALL_10_ACTIVE (zero_indices=[0, 1, 2, 3, 4, 7, 8, 16, 17, 26, 27])
- Zone mean contaminated weight fraction: 40.00%
- Dataset embeddings enumerated: 6

> Exposure ≠ consequence. Active dims / weight mass prove the model SEES the contaminated channels; they do NOT prove a decision flip. Decision consequence requires gate-ON ledger A/B (deliverable 2). Where only exposure is shown, the decision record may recommend provenance annotation rather than retrain.

## Scope

- Zero production changes. Artifacts only under `docs/governance/`.
- Finding registration deferred (PENDING-REVIEW in decision record).
- F-029 gate-OFF claim is NOT challenged here; gate-ON ledger is deliverable 2.
