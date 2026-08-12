# Feature-Math Drift Probe — GD-001/GD-002 (Matrix v2 measurement)

_Generated 2026-07-07T18:10:08.725152+00:00 · symbol BNBUSDT · 19922 bars · read-only._

## Value drift (canonical body/candle_range vs current body/total_wick)
- bars where the two differ: **19329** (97.0%)
- current ≥ canonical (systematic inflation): **99.2%**
- current body_ratio > 1.0 (bound violation, impossible for canonical): **9165** (46.00%)
- |Δ body_ratio|: mean 1.7572 · median 0.5000 · p95 7.1111 · max 494.0020

## CRT-score drift (real crt_engine.compute, canonical vs current body_ratio, all else fixed)
- bars where the CRT score changes: **19274** (96.7%)
- CRT score inflated by the current formula: **95.9%**
- |Δ CRT score|: mean 0.0281 · median 0.0263 · p95 0.0602 · max 0.1250

> CRT-score delta is the necessary channel to a fusion flip; live-hook path is F-010-unverified and backtests bypass it (F-037). Bounds potential impact only.