# Study Closure Note — Depth & Regime Descriptive Studies

**Date:** 2026-07-06  
**Verdict:** DESCRIPTIVE COMPLETE — no hypothesis promoted

## What was learned?

- **Depth:** Regime-normalized depth is 93% collinear with baseline; lowest-low depth is wrong geometry for second-low purges (often negative).
- **Regime:** Deep breaks (depth ≥ 1.0) skew to expanded vol (mean ATR14/ATR100 ≈ 1.31); Parkinson ratio redundant with ATR ratio (r ≈ 0.86).
- Regime as **normalizer** is not supported; **filter** (compressed vol only) is the only honest future framing on prospective data.

## What surprised us?

- Calendar-day second_low on full MT5 yields zero events — trading-day ladder is mandatory.
- xlsx vs MT5 price level differs ~100 USD at shared timestamps — feeds are not interchangeable.

## What should we do differently next time?

- Run depth/regime descriptives **before** any outcome prereg if alternatives are considered.
- Cap alternative metrics at 2–3 pre-specified; no post-hoc picking on sealed set.
- Pause outcome work until `secondlow_prospective_events.jsonl` has material count.