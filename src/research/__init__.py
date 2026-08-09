"""Edge Discovery Program — behavior-agnostic research platform.

Two sub-pipelines with different, deliberately different coupling to the live spine:

  - Edge-discovery / hypothesis pipeline (this package's original scope — see
    docs/implementation_plan + the Phase-0 plan). Imports the proven primitives
    (Candle, CandleLoader, forward-walk simulation) but runs its own
    hypothesis -> measure -> qualify -> promote loop, fully decoupled from the
    live CRT spine.

  - model_runners/ observation pipeline (research.model_runners.adapters —
    "call production engines only"). This one DELIBERATELY imports live engines
    (core.decision_engine.DecisionEngine, core.engine_runner.{detect_regime,
    breakout_engine,trap_engine}, core.gate_intelligence.compute_crt_levels,
    core.fusion_engine.{FusionEngine,FusionConfig,GaussianAdapter}) so research
    measures what production actually runs, not a parallel reimplementation that
    could silently diverge from it (the F-037 failure mode: research measured a
    different stack than live for months, unnoticed). OBSERVATION_ONLY — no
    promote, retrain, or production wire-up from this path either.

CORRECTED 2026-07-29: this docstring previously stated a single blanket rule —
"MUST NOT import the live execution path (core.engine_runner / ...)" — which was
already false in code (model_runners/ imports core.engine_runner and more) before
this correction, and was never mechanically enforced. The rule that actually
matters, and the one enforced below, is narrower and still holds without
exception for BOTH sub-pipelines: research may observe and score via live
engines, but must NEVER acquire the power to promote or validate-for-promotion.
So the forbidden set is the promotion/validation AUTHORITY only:
governance.promotion_manager (PromotionManager) and
config_layer.config_validator (ConfigValidator). Enforced by
scripts/governance/scan_runtime_boundary.py (authority_imports_in_source) and
tests/test_runtime_boundary.py — prose alone is how the old rule silently drifted
out of sync with the code for as long as it did.
"""
