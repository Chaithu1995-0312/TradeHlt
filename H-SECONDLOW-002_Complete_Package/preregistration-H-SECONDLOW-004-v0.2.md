# H-SECONDLOW-004 v0.2 — Pre-Registration (DRAFT)

**Status:** APPROVED (2026-07-07)  
**Date:** 2026-07-07
**Hypothesis ID:** H-SECONDLOW-004  
**Version:** 0.2  
**Predecessor:** H-SECONDLOW-003 v0.1 (ARCHIVE_OR_MODIFY) · relaxation diagnostic R2

---

## Data Use Declaration

- [x] Descriptive use on historical 36 events: **ALLOWED** (count-only completed; no outcomes)
- [ ] Outcome analysis on sealed 21 PRE: **FORBIDDEN** for this hypothesis
- [x] Outcome analysis on prospective ledger: **PRIMARY PATH**

**Corpus:** `data/XAUUSD_M15.csv` · hash `de2ca73224cb46a4`
**Detector:** `src/research/secondlow_v1/detector.py` (20d trading-day ladder, 120min independence — unchanged from v1 pin)

---

## Simplest Version First

H-SECONDLOW-003 tested a conjunction (pre-2h weakness **and** depth). The count diagnostic
(2026-07-07) showed the conjunction is the primary EXPOSED limiter; relaxing depth alone (R1)
adds almost nothing (+1 on 36). **v0.2 drops Condition A** and tests depth-only exposure —
the simplest version that still expresses “meaningful second-low break” (depth ≥ 1.0 ATR).

We are **not** testing R5 (OR logic), R3 (shorter lookback), or R4 (spacing change) in this
hypothesis. Those require separate IDs if pursued.

---

## Research Question

On POST_DISCOVERY independent second-low purge events (prospective ledger), does a purge
with **purge_depth_atr ≥ 1.0** produce systematically positive `close_disp_atr` at +120 minutes
relative to shallower purges on the same detector population?

---

## Analysis Universe (Locked)

**Primary population:** Independent second-low purge events appended to
`data/secondlow_prospective_events.jsonl` with `post_window_complete: true`, detected on the
canonical MT5 corpus **after** user approval of this prereg.

- **Excluded:** All 21 sealed PRE timestamps (no outcome analysis on sealed set).
- **Excluded:** Discovery-window events (2026-04-17 → 2026-05-22).
- **Excluded:** Historical PRE events on MT5 before prospective ledger start — descriptive counts only.

Outcome-linked analysis begins only when ≥1 prospective event with complete +120m window exists.

---

## Exposure Definition (Pre-Specified, Not Mined)

**EXPOSED if:** `purge_depth_atr` ≥ **1.0**

**Reference group:** All prospective independent events with `purge_depth_atr` < 1.0

No conjunction. No pre-2h filter. No PARTIAL arm.

| Field | Definition |
|---|---|
| ATR | True-range rolling mean, period 14 (`compute_true_range_atr`) |
| `purge_depth_atr` | `(second_low_20d − purge_low) / atr_at_purge` |
| `pre_2h_return_atr` | Computed for reporting only — **not** used for exposure |
| Post window | Exactly 8 M15 bars (+120 min) with +15 min continuity from purge bar |

**Threshold justification (pre-data):** 1.0 ATR carried from H-SECONDLOW-003 Condition B
without re-tuning; count diagnostic showed R1 (0.75) adds no material frequency gain.

---

## Primary Endpoint

`close_disp_atr` at exactly +120 minutes (close of the 8th bar after purge).

---

## Primary Estimand

Median(`close_disp_atr` | EXPOSED) − Median(`close_disp_atr` | Reference)

**Secondary (reporting only):**

- Proportion positive in each group
- Bootstrap percentile 95% CI on median difference (5000 resamples, seed **42**)

---

## Event Rate Planning

| Field | Value |
|---|---|
| Historical independent rate/year | ~15–20 |
| Historical EXPOSED rate (depth ≥ 1.0 on 36 ind.) | 9 / 36 (25%) |
| Expected EXPOSED in first 12mo prospective | ~4–6 (low power) |
| `minimum_events_for_decision` | **8** prospective EXPOSED |
| Study tier if below minimum | Tier 1 — Descriptive / Learning Only |

---

## Regime / Depth Role

- [x] No regime adjustment in v0.2
- [ ] Regime as filter — deferred to future hypothesis if prospective data warrants

Depth threshold is the sole exposure dimension.

---

## Holdout Strategy

- [x] **Prospective only** (`secondlow_prospective_events.jsonl`)
- [ ] Internal split on historical data — **not used**

Chronological OOS: all POST_DISCOVERY events after prereg approval.

---

## Sequential Update Protocol (v1.1)

Attach [`prospective-sequential-update-protocol-v1.md`](prospective-sequential-update-protocol-v1.md).

| Checklist item | Value |
|---|---|
| Appendix version | ≥ 1.1 |
| `starting_prior` | **A** — fresh N(0, 2²) on mean-diff Bayes track |
| Carry-forward from H-SECONDLOW-003 | **No** (exposure definition changed) |
| Update cadence | ≥3 prospective events with ≥1 EXPOSED, or monthly |
| Tier unlock | F-TIER* **and** B-TIER* both required |
| Log paths | `secondlow_prospective_events.jsonl`, `secondlow_prospective_update_log.jsonl` |

### Decision Rules (Summary)

| Rule | Criterion |
|---|---|
| **Stop** | F-STOP and/or B-STOP per protocol §6.2 |
| **Continue** | WATCH (F-WATCH / B-WATCH) |
| **Shadow candidate** | F-TIER3 **and** B-TIER3 (n_prospective_EXPOSED ≥ 15) |
| **Archive** | STOP triggered + user closure note |

---

## Risk of Overfitting

**Level:** Low  
**Justification:** Single pre-declared threshold (1.0 ATR) chosen before prospective outcomes;
exposure is one-dimensional; no historical outcome mining on sealed 21; detector bytecode unchanged.

---

## Power & Precision Expectations

- v0.2 adds only +1 EXPOSED vs H-SECONDLOW-003 conjunction on historical 36 events — a
  **reality check**, not a frequency solution.
- Value is an unbiased prospective stream under a simpler, auditable exposure rule.
- Wide CIs expected until n_prospective_EXPOSED ≥ 8.

---

## Data Provenance

| Artifact | Role |
|---|---|
| `data/XAUUSD_M15.csv` | Canonical OHLCV |
| `data/secondlow_prospective_events.jsonl` | Primary analysis universe |
| `data/sealed_evaluation_set_v1.json` | **Not used** for outcomes in this study |
| `results/relaxation_count_diagnostic/` | Motivation only (count-only) |

---

## Forbidden Without New Version

- Adding pre-2h condition back after seeing prospective results
- Threshold sweep on depth (0.75, 1.25, etc.) on accumulated prospective data
- Mixing sealed 21 outcomes into tier gates
- Combining R4 spacing or R3 lookback into this hypothesis

---

## Approval Gate

**APPROVED 2026-07-07** — prospective outcome analysis authorized on ledger events only.

---

## Amendment Log

| Version | Date | Change |
|---|---|---|
| 0.2 | 2026-07-07 | Initial draft — depth-only single condition, prospective-primary, prior A, protocol v1.1 |
| 0.2 | 2026-07-07 | APPROVED — first prospective dual-track update authorized |