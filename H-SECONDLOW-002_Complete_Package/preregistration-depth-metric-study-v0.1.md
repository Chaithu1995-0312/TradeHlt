# Depth Metric Descriptive Study — Pre-Registration v0.1

**Status**: DRAFT  
**Date**: 2026-07-06  
**ID**: H-SECONDLOW-METRIC-001  
**Version**: 0.1

## Purpose

Compare alternative **purge depth** definitions on the canonical MT5 corpus **without**
outcome inspection. Metric selection is not confirmatory; it informs whether a future
hypothesis (prospective-only) is worth drafting.

## Governance constraints

- **No** `close_disp_atr` or forward displacement on any event in this study.
- **No** threshold optimization on the sealed 21 PRE events.
- **No** carry-forward of H-SECONDLOW-002 or H-SECONDLOW-003 v0.1 exposure rules.
- Outcome-linked testing of any alternative metric requires a **new hypothesis ID** on
  **prospective events** (`secondlow_prospective_events.jsonl`) only.

## Universe

All **36** independent events on `data/XAUUSD_M15.csv` (trading-day SECONDLOW-v1 detector).

The sealed 21 PRE subset may be tagged for reporting but **not** used to rank metrics.

## Metrics compared (pre-specified)

| ID | Name | Formula |
|---|---|---|
| M0 | Baseline | `(second_low_20d − purge_low) / ATR_14` |
| M1 | Lowest low | `(lowest_daily_low_20d − purge_low) / ATR_14` |
| M2 | Regime-normalized | `M0 / (ATR_14 / ATR_100)` |

Optional descriptive only: rolling min z-score of daily low (50-day window).

## Outputs (descriptive only)

- Per-metric distribution (mean, median, std, min, max, % ≥ 1.0 ATR)
- Correlation: M0 vs M2; M0 vs regime factor
- Threshold flip counts at 1.0 ATR (M0 vs M1, M0 vs M2)
- Regime factor summary for sealed PRE events with M0 ≥ 1.0 (no outcomes)

## Decision use

This study **cannot** promote any metric. It may only:

1. Reject metrics with near-zero variance or trivial correlation with M0, or
2. Justify drafting a **prospective-only** hypothesis using M1 or M2.

## Script

`scripts/research/secondlow_depth_metric_descriptive.py`

## Approval

DRAFT — user approval required before treating results as input to hypothesis design.