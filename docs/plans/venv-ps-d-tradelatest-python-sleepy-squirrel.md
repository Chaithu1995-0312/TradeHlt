> Created: 2026-05-07 · Updated: 2026-05-07 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Plan: Fix fusion log pairing failure → recover valid training records

## Context

Running `validate_logs('logs/EURUSD_fusion.jsonl')` returns only 199 paired records (minimum is 500+). The log has 38,333 lines with 19,138 ENTRY records for only 199 unique `trade_id` values — each trade_id appears ~96× because the backtest was run multiple times appending to the same log file.

**The critical bug**: `dataset_validator.py` Pass 1 does `entries[tid] = rec` on every ENTRY event, so it **keeps the LAST occurrence** of each trade_id. The last occurrence always has all-zero features (later backtest runs wrote zero-padded entries). The first occurrence (line 0, 2, 4…) has valid non-zero features. Result: 199 pairs are formed but all have zero-feature vectors — technically valid (zeros are floats), so they pass `validate_vector()` and slip into training data silently.

**Two fixes needed:**
1. Keep the **FIRST** ENTRY for each `trade_id` (not last) — recovers the valid features
2. Add a **zero-feature guard** — reject any ENTRY where all 35 feature values are 0.0

This is a surgical 2-line + 1-block change to `dataset_validator.py`. No other files need touching.

---

## Critical files

- `src/features/dataset_validator.py` — the only file to edit
  - Line with the overwrite bug: `entries[tid] = rec` (inside `if event == "ENTRY":` block, Pass 1)
  - `validate_vector()` call in Pass 2 (lines 183–191) — add zero-vector check before this

---

## Implementation

### Fix 1 — Keep first ENTRY per trade_id (`dataset_validator.py`, Pass 1)

**Old** (inside `if event == "ENTRY":` block):
```python
if tid:
    entries[tid] = rec
```

**New**:
```python
if tid and tid not in entries:   # keep first occurrence, discard duplicates
    entries[tid] = rec
```

### Fix 2 — Reject all-zero feature vectors (`dataset_validator.py`, Pass 2)

Add this guard immediately **before** the `feature_dict_to_vector()` call (after `feature_dict = entry.get("features", {})`):

```python
# Reject zero-padded entries written by incomplete backtest runs
if feature_dict and all(v == 0.0 for v in feature_dict.values()):
    rpt.skipped_bad_features += 1
    rpt.warnings.append(f"trade_id={tid[:8]}… all-zero feature vector, skipped")
    continue
```

---

## Expected outcome after fix

- Pass 1 keeps line 0/2/4… (the original valid entries) for each of the 199 trade_ids
- Zero-vector guard catches any that still slip through
- `valid_for_training` should reach ≥199 with real features (up from effectively ~0 useful records)
- Still below the 500 recommendation — user will need to run backtests on additional instruments (GBPUSD, etc.) or a longer CSV date range to reach 500+

---

## Verification

```bash
# After fix, re-run validation — check valid_for_training count and that warnings no longer show all-zero records
python -c "
from src.features.dataset_validator import validate_logs
from src.features.dataset_builder import build_dataset
records, report = validate_logs('logs/EURUSD_fusion.jsonl')
print('Valid records:', report.valid_for_training)
# Spot-check a feature vector — should be non-zero
if records:
    print('Sample features (first 5 values):', list(records[0]['feature_vec'])[:5])
build_dataset(records, output_path='data/training.json')
"

# Then re-run training
python scripts/training/train_pipeline.py tradenet --data data/training.json --output results/tradenet_result.json
```
