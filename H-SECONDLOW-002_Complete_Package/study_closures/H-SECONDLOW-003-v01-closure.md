# Study Closure Note — H-SECONDLOW-003 v0.1

**Date:** 2026-07-06  
**Verdict:** ARCHIVE_OR_MODIFY

## What was learned?

- On 21 sealed PRE events with conjunction (-1.5 / 1.0), median `close_disp_atr` was **negative** for EXPOSED (n=5) vs Reference (n=16); primary median diff ≈ **-1.95 ATR**; bootstrap 95% CI crossed zero.
- Corpus substitution matters: xlsx discovery story does not carry to MT5 canonical prices.
- Rule #1 (≥12 EXPOSED) failed as expected — study correctly classified as descriptive stop, not inconclusive.

## What surprised us?

- Effect direction was opposite the archived xlsx forensic narrative despite similar detector geometry.
- Holdout split (6 events) contained zero EXPOSED — internal validation not evaluable.

## What should we do differently next time?

- Pre-register **before** any threshold mining; use single-condition first.
- Use tiered decision framework; do not use universal ≥12 EXPOSED gate on ~20 event pools.
- Do not unseal for metric/regime rescue variants on the same 21 events.