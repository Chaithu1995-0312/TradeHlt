# Volatility Regime Semantic Adjudication FC-0.5

**Verdict:** `SEPARATE_LOCAL_VOLATILITY_CONTEXT_FEATURE`

Selected implementation intent: {
  "feature_rename_candidate": "volatility_context or atr_percentile_tercile",
  "math": "rolling causal ATR percentile rank, N=200 unless FC-1 design revises N",
  "legacy_global_rank": "preserve under LEGACY only"
}

Rejected: {
  "GLOBAL": "non-causal; fails prefix invariance",
  "EXPANDING_as_named_regime": "causal but long-memory / early unstable; still not latent Regime Detection",
  "ROLLING_keeping_name_regime": "math OK but ontology collision with Regime Detection"
}

Empirical candidate stats in JSON twin.
