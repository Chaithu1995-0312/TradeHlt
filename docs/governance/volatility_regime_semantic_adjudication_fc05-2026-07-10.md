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

---

## Addendum 2026-07-11 — N=200 CONFIRMED structural (FC1-D shipped without revision)

The FC-0.5 verdict left the window open ("N=200 unless FC-1 design revises N"). FC1-D
(`CH-fc1d-volregime-causal`) shipped N=200 as structural for FEAT-VOLATILITY_REGIME_ROLLING_CAUSAL_RANK;
this addendum records the confirming criteria (audit finding A7 — the design note was owed):

1. **Semantic fit** — the adjudicated meaning is *local ATR-percentile context* (NOT latent
   Regime Detection): 200 M15 bars ≈ 2.1 trading days — a genuinely local window; expanding
   (long-memory) was rejected for exactly this reason, so a large N would re-import the
   rejected semantic.
2. **PIT safety** — trailing rolling rank; prefix-invariant (enforced by
   `tests/test_fc1d_volregime_causal.py`).
3. **Warmup** — `min_periods=1`: early bars rank within a short window (self-referential
   terciles); acceptable for a context feature, stated here explicitly rather than hidden.
4. **F-029/F-030 evidence context** — global vs expanding vs rolling were byte-identical on
   ledgers (A/B/C, crypto majors) and vol-LEVEL conditioning is economically non-consumable
   (F-030), so no measured consumer discriminates N today; N carries structural-identity
   authority only, no economic authority (§6.5).
5. **Revision trigger** — a measured consumer demonstrating ΔG001 sensitivity to window
   adaptivity. Until then N=200 is frozen with the identity (changing N = new identity version,
   not a knob sweep).
