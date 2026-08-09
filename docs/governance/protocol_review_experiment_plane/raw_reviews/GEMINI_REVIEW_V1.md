# Independent Technical Review — Gemini (adversarial)

**Protocol:** `MSIP_WHOLE_REPRESENTATION_PREREGISTRATION_V1`  
**Review date:** 2026-07-14  
**Reviewer label:** Gemini (independent adversarial)  
**Archive note:** Full session text preserved in session prompt; this file is the normalized governance archive of verdict + findings.

```text
REVIEW_STATUS = FAIL
FREEZE_RECOMMENDATION = FREEZE_BLOCKED
```

## Executive verdict (condensed)

Prereg identifies falsifiable estimand M2−M1 and blocks H-017/H-018 partition mining, but has critical mechanical flaws: temporal nested CV ignores outcome horizon overlap (h=8); global null month-permutation destroys R₈ autocorrelation; M1 `bars_since_range_entry` missingness undefined. Freeze blocked until leakage and exchangeability defects resolved.

## Blocking findings

| Reviewer id | RF-id | Domain | Severity |
|-------------|-------|--------|----------|
| BF-01 | RF-GEM-001 | TEMPORAL VALIDATION | CRITICAL |
| BF-02 | RF-GEM-002 | GLOBAL NULL | CRITICAL |
| BF-03 | RF-GEM-003 | SUPPORT / MISSINGNESS | MAJOR |

### BF-01 — Temporal leakage (→ RF-GEM-001)

- **Problem:** Unmitigated temporal leakage between contiguous folds due to overlapping forward horizons.
- **Evidence in protocol:** “Fold k trains on all bars strictly before fold k’s start” + primary h=8.
- **Reviewer proposed fix:** Embargo/purge ≥ h−1 bars (inner + outer).
- **PREP note:** Do **not** auto-adopt h−1; derive purge from exact R₈ indexing (`close[t+h]/close[t]−1`).

### BF-02 — Global null exchangeability (→ RF-GEM-002)

- **Problem:** Month-contained permutation of R₈ destroys autocorrelation of 8-bar forward returns → anti-conservative null / Type-I risk.
- **Evidence:** `block_permute_R8_within_train_calendar_month_full_nested_procedure`.
- **Reviewer proposed fix:** Circular shift with offset > h, or block perm with block size > h.
- **PREP note:** Design hypothesis required; do not auto-adopt a single proposed null.

### BF-03 — M1 missingness (→ RF-GEM-003)

- **Problem:** `bars_since_range_entry if trackable else omit with missingness rule` — rule undefined.
- **Required:** Exact mathematical missingness handler (no performance-based imputation).

## Non-blocking (registered as recommendations)

| Reviewer topic | RF-id | Notes |
|----------------|-------|-------|
| Categorical encoding for Ridge | RF-GEM-NB-01 | one-hot vs ordinal |
| HP selection biases against M2 | RF-GEM-NB-02 | overlaps DeepSeek B1 (primary cluster owner RF-DS-001) |
| Optional independent HP tuning | (see RF-DS-001) | |

## Required protocol amendments (reviewer list)

1. §7.1/§7.2 purge/embargo for h  
2. §8 null that preserves R₈ dependence  
3. §2 M1 missingness rule  

## Freeze decision

**FREEZE_BLOCKED.** Re-review required after BF-01/BF-02 (BF-03 mechanical fix may not need full re-review per Gemini).
