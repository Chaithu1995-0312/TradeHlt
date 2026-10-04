# Phase-1 resolver replay — corpus denominator (denseness)

**Status:** METADATA / DIAGNOSTIC ONLY · no Case reopen · `economic_claims_allowed=false`

## Exact Phase-1 window (verified)

| Field | Value | Source |
|-------|-------|--------|
| dataset_id | `XAUUSD_MT5_PHASE1_20260521` | `docs/governance/datasets/XAUUSD_MT5_PHASE1_20260521.json` |
| csv | `data/mt5/XAUUSD_M15.csv` | replay provenance + Dataset Identity |
| csv_sha256 | `4d73f5cebe33ec91…` | bound |
| start | **2024-05-22T01:00:00** | canonical_artifact + CSV first row |
| end | **2026-05-21T23:45:00** | canonical_artifact + CSV last row |
| bar_count / rows | **47,275** | bound rows = CSV rows |
| resolution | M15 | |
| calendar span | **≈729.95 days ≈ 23.98 months ≈ 2.00 years** | end−start |

Eligible bars for Always-Long stride-20 ≈ **47,275 / 20 → 2,363** (replay reported n_universe 2364 / scored 2359).

## Shadow-collapse events on that denominator

| | |
|--|--|
| n SHADOW→EXP scored | **6** |
| event timestamps | 2024-06-13 … 2025-12-18 (553 calendar days between first and last event) |
| **events / month** | **≈ 0.25** |
| **events / year** | **≈ 3.0** |
| **events / 1000 bars** | **≈ 0.127** |
| bars / event | ≈ 7,879 |

## Interpretation of n=6 given the window

This is **not** “6 in one month.”  
It is **6 over ~2 years** of Phase-1 XAUUSD M15 → **≈0.25 events/month**.

That matches the “extremely sparse” row of the denseness table, not the “1-month rare but not absurd” row.

Methodological note: April-2026 mentions elsewhere were parity/context talk — **not** the replay corpus bounds. The replay denominator is the full Phase-1 artifact above.
