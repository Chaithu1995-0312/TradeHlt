# PIT Phase C — Canonical FeaturePipeline Certification Gate

_Date: 2026-07-11 · ACTIVE_VERSION=`v2_multi_2026_04` · sequence: Phase A (F-051, centered
swings) → FC1-A → FC1-D (Phase B, volatility regime) → **Phase C (this gate)**._

## Certification statement

**The 38-column canonical FeaturePipeline is certified PIT-CLEAN at the prefix-invariance
level.** Empirically (not statically): running the pipeline on strict prefixes of the corpus
reproduces the full-corpus values **bit-for-bit on every shared timestamp for all 38
production columns, with zero tail exclusion** — bar *t* uses only information ≤ *t*.

Evidence (`docs/governance/pit_phaseC_feature_certification-2026-07-11.{json,md}`):

| Arm | Cuts | Result |
|---|---|---|
| BNBUSDT_M15 (29,922 bars) | 50%, 75% | 38/38 PREFIX_INVARIANT, 0 mismatched bars |
| synthetic (1,200 bars) | 60% | 38/38 PREFIX_INVARIANT, 0 mismatched bars |
| global-fit AST scan | — | exactly 1 unwindowed rank site = research-only `volatility_regime_global_batch`; empirically proven not to reach production columns |
| batch↔online structure parity | — | all 10 structure dims incl. liquidity (FC1-A tests, strengthened 2026-07-11) |

**Permanent floor:** `tests/test_pit_prefix_invariance.py` — synthetic prefix-vs-full equality
for all 38 columns on every pytest run + a regression tripwire on new full-frame rank/quantile
sites. Future dependence cannot silently re-enter without a red floor.

## Explicit scope (what this does and does not certify)

- **Certifies**: temporal correctness of the production feature computation — no future
  dependence, no global-fit dependence in production columns, deterministic warmup behavior
  (NaN warmup rows are DROPPED by `finalize()`, never filled with synthetic values).
- **Does NOT certify**: economic value of any feature (F-019…F-045 nulls stand); artifact
  admissibility — `models/rr_model.json` and `models/zone_registry.json` remain
  **PIT_UNCLEAN** (centered_swings + global_batch_volatility_regime training era,
  `models/*.provenance.json`); live feeder completeness beyond the FeatureStore-computed dims
  (feeder-supplied dims are pass-through by contract).
- **Grants no authority** (§6.5): PIT-clean is a correctness precondition, not evidence of edge.

## Residual (tracked, not blockers to this gate)

1. Model training-lineage recovery (the review's post-Phase-C step): any retrain of
   structure-/regime-sensitive artifacts must use causal-era datasets and revalidate
   (provenance operational rule).
2. `FU-CRT-MOVE-MISWIRE` (gate-ON behavior phase, post-PIT).
3. Live feeder contract: dims the feeder supplies (EMA/ATR/RSI/etc.) are validated but not
   re-derived by FeatureStore; their PIT properties are the feeder's contract.

## Verdict

Per the review sequence: **"one bug-free canonical FeaturePipeline" (PIT/prefix sense) is now
declared** — model training-lineage recovery may begin, against a settled canonical semantics.
