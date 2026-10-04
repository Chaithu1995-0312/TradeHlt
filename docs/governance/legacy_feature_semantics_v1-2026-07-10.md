# LEGACY_FEATURE_SEMANTICS_V1

| Field | Value |
|---|---|
| Freeze id | `LEGACY_FEATURE_SEMANTICS_V1` |
| Machine twin | [`legacy_feature_semantics_v1-2026-07-10.json`](legacy_feature_semantics_v1-2026-07-10.json) |
| Fingerprint | [`legacy_feature_output_fingerprint_xauusd-2026-07-10.json`](legacy_feature_output_fingerprint_xauusd-2026-07-10.json) |
| Program | Feature Pipeline Closure FC-0 |

## Authority

This freeze is **descriptive only**.

**Not:** VALIDATED · APPROVED · AUTHORITATIVE · ECONOMICALLY_ADMISSIBLE.

It captures production-default FeaturePipeline semantics **before** FC-1 remediation so shadow replay can compare LEGACY vs CANONICAL without losing history.

## What is frozen

- Implementation content hashes (`feature_pipeline`, `candle_math`, `derived_math`, `feature_schema`, `market_ontology.yaml`)
- Ordered 38 `CANONICAL_FEATURES` + schema hashes
- Default env semantic flags (unset = leaking swing / global vol regime)
- PASS-A defect verdicts A–D
- Deterministic float32 output fingerprint on frozen XAUUSD Phase-1 candidate

## Regeneration

```text
python scripts/analysis/legacy_feature_fingerprint.py --write
python scripts/analysis/legacy_feature_fingerprint.py --check
```

Do not edit the fingerprint by hand.
