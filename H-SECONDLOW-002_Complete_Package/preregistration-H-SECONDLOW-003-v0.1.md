# H-SECONDLOW-003 v0.1 — Pre-Registration (Amended)

**Status**: APPROVED (2026-07-06)  
**Date**: 2026-07-06  
**Hypothesis ID**: H-SECONDLOW-003  
**Version**: 0.1

---

## 1. Research Question

On the canonical MT5 corpus, does a second-low purge that occurs after short-term weakness produce systematically positive price displacement in the following 2 hours?

## 2. Analysis Universe (Locked)

**Sole population**: The 21 sealed PRE timestamps listed in `data/sealed_evaluation_set_v1.json`.

- Discovery-window events (15 independent events from 2026-04-17 → 2026-05-22) are **permanently excluded** per `SECONDLOW_RESEARCH_DATA_POLICY.md`.
- No POST_DISCOVERY events exist yet. Future events enter analysis only via `data/secondlow_prospective_events.jsonl` under a future amendment to this pre-registration.

## 3. Exposure Definition (Pre-Specified, Not Mined)

An event is labeled **EXPOSED** if **both** conditions are true on the purge bar:

- **Condition A**: `pre_2h_return_atr` ≤ **-1.5**
- **Condition B**: `purge_depth_atr` ≥ **1.0**

**Reference group** = All events that do **not** meet both conditions (PARTIAL and BASELINE pooled). There is no separate PARTIAL analysis in this study.

**Implementation pins** (to prevent silent drift):

| Field | Definition |
|---|---|
| ATR | True-range rolling mean, period 14 (`compute_true_range_atr`) |
| `pre_2h_return_atr` | `(purge_close − close_8_bars_prior) / atr_at_purge` |
| `purge_depth_atr` | `(second_low_20d − purge_low) / atr_at_purge` |
| Post window | Exactly 8 bars with +15 min timestamp continuity from purge bar |

## 4. Primary Endpoint

`close_disp_atr` at exactly +120 minutes (close of the 8th bar after the purge bar).

## 5. Primary Effect Estimand

Median(`close_disp_atr` | EXPOSED) − Median(`close_disp_atr` | Reference)

**Secondary reporting** (for completeness only):

- Proportion of positive `close_disp_atr` in each group
- Bootstrap percentile 95% CI on the median difference (5000 resamples)
- BCa interval recorded as optional secondary only

## 6. Analysis Plan

- Apply the exact detector implementation pinned in `tests/research/test_secondlow_v1_detector_regression.py`.
- Compute exposure labels and primary endpoint **only after** this pre-registration is approved and the sealed set is explicitly unsealed for H-SECONDLOW-003.
- No threshold sweeping, no covariate adjustment, no subgroup analysis, no multiple testing.

## 7. Holdout Strategy

Given current constraints (21 PRE events, 0 POST_DISCOVERY):

- This study is **descriptive / internal validation only** until forward data creates a genuine chronological OOS window.
- Optional internal split: A 70/30 development vs holdout split will be pre-committed in `sealed_evaluation_set_v1.json` using a fixed random seed **before** any outcome inspection. The split is recorded in the manifest.

## 8. Decision Rules (Realistic & Pre-Declared)

The study will be considered **worth further investment** only if **all** of the following are met:

1. ≥12 EXPOSED events observed in the 21 PRE sample.
2. Lower bound of the 95% bootstrap percentile CI on the median difference > +0.3 ATR.
3. Directionally consistent result in the internal holdout split (if used).
4. At least 15 new independent events appear in `secondlow_prospective_events.jsonl` within 12 months (per `SECONDLOW_RESEARCH_DATA_POLICY.md` §5.1 forward-fetch protocol), and the effect remains stable on those events.

**Explicit statement on Rule #1**: With only 21 PRE events available, Rule #1 is **expected to fail by design**. The primary deliverable of this pre-registration is a clean, bounded point estimate + confidence interval. Failure to meet Rule #1 is a pre-specified stop signal, not an inconclusive result that justifies threshold adjustment on the same 21 events.

## 9. Power & Precision Expectations

Historical rate ≈ 18 independent events per year on the canonical corpus.

- Expected EXPOSED count under the -1.5 / 1.0 rule on 21 PRE events: **roughly 4–8**.
- With small arm sizes, the 95% CI around the median difference will be wide.
- This study has **low power** to detect effects smaller than ~0.8–1.0 ATR. This limitation is accepted upfront. The value lies in producing an unbiased estimate that informs whether the idea merits continued data collection.

## 10. Data Provenance & Governance

| Artifact | Role |
|---|---|
| `data/XAUUSD_M15.csv` | Canonical corpus only (hash `4d73f5cebe33ec91`) |
| `data/sealed_evaluation_set_v1.json` | Sealed until user approves this prereg |
| `src/research/secondlow_v1/detector.py` | SECONDLOW-v1 trading-day implementation (regression-pinned) |
| `data/secondlow_prospective_events.jsonl` | Prospective events append-only |

Any post-approval change to exposure definition, endpoint, or decision rules requires a new version with justification.

## 11. Optional Simpler Variant (v0.2 candidate)

**Single-condition exposure**: `purge_depth_atr` ≥ 1.0 only (drop Condition A).

Increases expected EXPOSED count and reduces conjunction complexity at the cost of a weaker theoretical story. Activate only as a new pre-registered version if power is prioritized over narrative strength.

---

## Amendment Log

| Version | Date | Change |
|---|---|---|
| 0.1 | 2026-07-06 | Initial amended draft — analysis universe locked to 21 PRE; implementation pins; Rule #1 tension documented; percentile bootstrap primary |

**Approval gate**: APPROVED 2026-07-06 by user. Sealed set unsealed for H-SECONDLOW-003 v0.1 only.

**Results:** `results/h_secondlow_003_v01/descriptive_report.json` · `descriptive_event_table.csv`