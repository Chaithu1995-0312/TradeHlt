# CRT State Resolver Validation Report

> Generated: 2026-07-24T12:45:08.775077

## Reference source

CRT engine dwell counts from XAUUSD M15 (`state_distribution` in engine
summary). Resolver counts are **bar-level predicate + transition graph**
classifications — not expected to match byte-for-byte (engine has soft-confirm,
score threshold, session filter, and HTF reset logic beyond feature predicates).

Reference total: **47,202** bar-dwells

## Dataset: `synthetic`

- **Total bars resolved:** 5,000
- **Transitions:** 382
- **States within 10% of reference:** 0/9

| State | Resolver | % | Reference | Δ | Rel. match | Within 10% |
|-------|----------|---|-----------|---|------------|------------|
| RANGE | 4,180 | 83.60% | 35,159 | -30,979 | 11.9% | ✗ |
| SWEEP | 646 | 12.92% | 6,995 | -6,349 | 9.2% | ✗ |
| EXPANSION | 157 | 3.14% | 4,605 | -4,448 | 3.4% | ✗ |
| DISPLACEMENT | 0 | 0.00% | 373 | -373 | 0.0% | ✗ |
| SHADOW_PENDING | 0 | 0.00% | 43 | -43 | 0.0% | ✗ |
| RETEST | 0 | 0.00% | 17 | -17 | 0.0% | ✗ |
| EXECUTION | 0 | 0.00% | 5 | -5 | 0.0% | ✗ |
| RESOLUTION | 0 | 0.00% | 5 | -5 | 0.0% | ✗ |
| EXPIRED | 17 | 0.34% | 0 | +17 | 0.0% | ✗ |

### Funnel (resolver vs engine)

| Stage | Resolver | Reference | Conversion (resolver) |
|-------|----------|-----------|----------------------|
| RANGE | 4,180 | 35,159 | — |
| SWEEP | 646 | 6,995 | 15.45% |
| DISPLACEMENT | 0 | 373 | 0.00% |
| EXPANSION | 157 | 4,605 | 24.30% |
| RETEST | 0 | 17 | 0.00% |
| EXECUTION | 0 | 5 | 0.00% |

### State Sequence (first 20 bars)
```
RANGE → SWEEP → SWEEP → SWEEP → SWEEP → RANGE → RANGE → RANGE → SWEEP → SWEEP → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE
```

### Interpretation notes

- **RANGE/SWEEP** should be in the same order of magnitude if
  `liquidity_sweep` / `sweep_detected` match the engine's sweep geometry.
- **DISPLACEMENT/EXPANSION/RETEST** diverge when predicates use feature-pipeline
  flags (`displacement_flag`, `retest_flag`) that are *similar but not identical*
  to CRT engine gates (`body_ratio>=0.70`, EMA retest band, expansion ATR distance).
- **EXECUTION** requires `session ∈ {LONDON,NEWYORK,OVERLAP}` + retest + trend +
  neutral RSI — still under-counts vs engine because score/soft-confirm are not
  feature-state predicates.
- **SHADOW_PENDING / EXPIRED / RESOLUTION** are memory states; feature-only
  resolution cannot fully reproduce HTF-reset and trade-lifecycle logic.

