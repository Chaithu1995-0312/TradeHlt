# Phase-1 Duplicate Formula Identity Closure (2026-07-10)

**Status:** `COMPLETE`

## Input binding

- require_phase1_frozen_candidate: **PASS**
- path: `data/mt5/XAUUSD_M15.csv`
- sha256: `4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56`
- rows: 47275
- corpus promoted: **false**

## Families closed

- BODY_RATIO
- DISPLACEMENT_RETEST
- SWING
- VOLATILITY_REGIME
- VOLUME

Identity count: **16**

## Exact duplicates removed from governed authority

- T-003 volume column overwrite
- TRUST_SWING_CAUSAL in-place mutation of centered swing columns
- TRUST_VOLREGIME_CAUSAL in-place mutation of volatility_regime column

## Ambiguous names eliminated

- volume (proxy no longer shares identity)
- swing_high / swing_low (bare name → legacy alias CENTERED only; causal has distinct names)
- volatility_regime (bare → legacy alias GLOBAL only; expanding/rolling distinct names)
- body_ratio (canonical is body_to_range_ratio; total_wick has distinct name)
- disp_strength / retest_depth historical CRT alias collisions (CH-002 emission + registry)

## Flags

```
{
  "PIT_REMEDIATION_STARTED": false,
  "MODEL_LINEAGE_STARTED": false,
  "MODEL_COMPATIBILITY_EVALUATED": false,
  "RETRAINING_PERFORMED": false,
  "ECONOMIC_CLAIMS_ALLOWED": false,
  "MODEL_ENABLEMENT_CHANGED": false,
  "MODEL_ARTIFACTS_CHANGED": false
}
```

## What this does not prove

- PIT/lookahead correctness is not closed
- All canonical formulas are not yet audited
- Full FeaturePipeline correctness is not proven
- Batch/runtime/live parity is not proven
- Model training lineage is not recovered
- Model compatibility is not evaluated
- No retraining performed
- No economic claims

## Next exact step

STOP FOR USER REVIEW. Do not begin PIT/lookahead remediation automatically.
