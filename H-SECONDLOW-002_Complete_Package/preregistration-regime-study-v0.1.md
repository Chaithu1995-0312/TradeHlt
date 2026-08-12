# Volatility Regime Descriptive Study — Pre-Registration v0.1

**Status**: DRAFT  
**Date**: 2026-07-06  
**ID**: H-SECONDLOW-REGIME-001  
**Version**: 0.1

## Purpose

Describe the volatility environment at second-low purge events on the canonical MT5
corpus. **Not** a rescue study for H-SECONDLOW-003 v0.1.

## Constraints

- Universe: 36 independent events (`data/XAUUSD_M15.csv`).
- **No** `close_disp_atr` or forward outcomes.
- **No** regime-based threshold retuning on the sealed 21 PRE events.
- Outcome-linked regime filters require prospective data + new hypothesis ID.

## Methods (pre-specified)

| ID | Definition |
|---|---|
| R1 | `ATR_14 / ATR_100` |
| R2 | `ATR_14 / ATR_200` (lookback stability) |
| R3 | Parkinson realized vol ratio: `sqrt(mean(Parkinson_20)) / sqrt(mean(Parkinson_100))` |
| R4 | Binary high-vol: R1 > 1.2 |
| R5 | Binary high-vol: ATR_14 ≥ rolling 70th percentile over 200 bars |

## Outputs

- Distributions of R1–R3 at purge time
- Correlations: R1 vs R2, R1 vs R3, R1 vs baseline depth
- High-vol fractions (all events + depth ≥ 1.0 subset)
- Lookback stability |R1 − R2|

## Use of results

May inform **future** regime-as-filter hypotheses on prospective events only.  
May **not** promote regime-normalized depth or regime filters on sealed data.

## Script

`scripts/research/secondlow_regime_descriptive.py`