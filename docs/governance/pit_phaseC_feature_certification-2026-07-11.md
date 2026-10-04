# PIT Phase C — Empirical 38-Feature Certification

_Generated 2026-07-11T12:08:27.242209+00:00 · ACTIVE_VERSION=v2_multi_2026_04 · read-only._

## Verdict

**ALL 38 production canonical columns are PREFIX-INVARIANT** on every tested cut (real corpus + synthetic), with **zero tail exclusion** — bar *t* uses only information ≤ *t* across the entire production vector. Combined with the batch↔online structure parity tests (FC1-A) and the rolling-causal volregime bind (FC1-D), the canonical FeaturePipeline is certified **PIT-clean at the prefix-invariance level**.

> SCOPE: this certifies temporal correctness (no future dependence, no global-fit > leakage into production columns). It is NOT an economic claim, does NOT > un-taint PIT_UNCLEAN artifacts (rr/zone), and grants no authority (§6.5).

## Prefix invariance — BNBUSDT_M15 (30000 bars)

- cuts: [0.5, 0.75] · shared rows/cut: [14922, 22422]
- variant features: **none**

## Prefix invariance — synthetic_1200 (1200 bars)

- cuts: [0.6] · shared rows/cut: [642]
- variant features: **none**

## Warmup / missing-value census

- pre-finalize rows: 29922 · post: 29922 · dropped: 0
- finalize() dropna(subset=CANONICAL_FEATURES) removes warmup rows; a NaN policy is therefore a ROW-DROP policy for the production vector

## Global-fit scan (feature_pipeline.py)

- line 335: `.rank` chain=[] windowed=False
- line 339: `.rank` chain=['expanding'] windowed=True
- line 343: `.rank` chain=['rolling'] windowed=True
- line 744: `.quantile` chain=['rolling'] windowed=True

> unwindowed rank/quantile = full-frame fit. Post-FC1-D the only such site must feed research-only columns (volatility_regime_global_batch), never a production canonical column — section 1 is the empirical proof.