"""Model catalog — all audit models; phase marks implement status.

Phase 0 model-registry join (2026-09-23, design plan:
docs/implementation_plan/dont-read-codebase-yet-lovely-clarke.md). MODEL_CATALOG is the hub —
the only surface bound to code (entry_point / required_feature_keys / spine_active). Seven new
fields join it to the other two declarative surfaces (docs/governance/miar_registry.json,
active_models.yaml) via one semantic_id, so the same model can no longer carry three different
names across three files with nothing checking they agree (the rr / candle_commitment / rr_model
collision that motivated this). Verified by tests/test_model_registry_join.py.

This is a DATA-ONLY addition. No runner reads the seven new fields; runtime behaviour is
unchanged. Declaring a semantic_id/authority here grants NO production authority — only
measured ΔG001 does (CLAUDE.md §6.5 Authority Ladder). `authority` here mirrors what a model
already does in production (spine_active + EXPECTED_ENGINES membership + any historical shadow
measurement); it does not grant anything new.

Tier vocabulary (semantic_id prefix, distinct from feature-DAG L0-L6 and layer_trace L0-L9 —
see the plan's "naming collision" section):
    M0  spine-family engine   — a single scoring/state engine, wired or dormant
    M1  block specialist      — Phase 3, not yet built (19-block ensemble)
    M2  state specialist      — Phase 3, not yet built
    M3  temporal tracker      — Phase 3, not yet built
    M4  arbiter / fusion      — combines other models' votes into one decision
    M9  orchestration         — runs the pipeline; not itself a vote

`authority` derivation rule (mechanical, not per-row judgment):
    FUSION_VOTE — model_id's engine is one of core.engine_runner.EXPECTED_ENGINES
                  ({"crt","ema_momentum_kernel","feature_cluster_similarity","candle_commitment"}) — the four fusion-completeness votes.
    SPINE       — spine_active=True but not an EXPECTED_ENGINES vote (runs live, not a fusion
                  input/veto in its own right).
    SHADOW      — spine_active=False but historically measured via a shadow A/B (bitnet, F-055).
    NONE        — spine_active=False, no shadow measurement (dormant/experimental/dead).
    VETO        — reserved; no current catalog row is a standalone hard-veto distinct from its
                  FUSION_VOTE/SPINE role (feature_cluster_similarity's F-041 hard-gate behaviour is folded into
                  its FUSION_VOTE row, not split into a second row).

`scale_type` — `"composite"` is for models whose return is a structured/multi-field object with
no single dominant scalar (a plan, a decision, an orchestrator dict); everything else names the
type of its one dominant signal.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Optional


@dataclass(frozen=True)
class ModelContract:
    model_id: str
    entry_point: str
    input_mode: str  # features | ohlc | candles | compose | blocked
    spine_active: bool
    requires_artifact_cli: bool
    required_feature_keys: FrozenSet[str]
    phase: int  # 1=runnable live, 2=runnable compose/sm, 3=off-spine, 9=blocked catalog
    audit_status: str
    description: str
    runnable: bool
    # ---- Phase 0 model-registry join fields (2026-09-23) — see module docstring ----
    semantic_id: str  # "M{tier}_{BLOCK}_{FAMILY}_{ARM}" — unique, tests/test_model_registry_join.py
    tier: str  # one of M0/M1/M2/M3/M4/M9 — see module docstring
    miar_id: Optional[str]  # docs/governance/miar_registry.json entries[].id, or None
    miar_absent_reason: Optional[str]  # required when miar_id is None
    active_models_key: Optional[str]  # active_models.yaml top-level or dotted key, or None
    active_models_absent_reason: Optional[str]  # required when active_models_key is None
    serve_domain: str  # ALL_BARS | CRT_STATE:<X> | TRADE_OPENED | RETEST_ONLY | OFFLINE | COMPOSE
    scale_type: str  # score | tail_prob | calibrated_prob | regression | gate_bool | categorical | composite
    authority: str  # NONE | SHADOW | FUSION_VOTE | VETO | SPINE — see module docstring
    trained_on_schema: Optional[str]  # e.g. "38dim_legacy" / "39dim_v4" / "48dim"; None = untrained


MODEL_CATALOG: dict[str, ModelContract] = {
    "candle_commitment": ModelContract(
        model_id="candle_commitment",
        entry_point="engines.candle_commitment.CandleCommitment.compute",
        input_mode="ohlc",
        spine_active=True,
        requires_artifact_cli=False,
        required_feature_keys=frozenset({"high", "low", "close"}),
        phase=1,
        audit_status="CERTIFIED",
        description="Candle polarity index (live fusion RR slot)",
        runnable=True,
        semantic_id="M0_SPINE_RR_POLARITY",
        tier="M0",
        miar_id="candle_commitment",
        miar_absent_reason=None,
        active_models_key="rr_model",
        active_models_absent_reason=None,
        serve_domain="ALL_BARS",
        scale_type="score",
        authority="FUSION_VOTE",  # EXPECTED_ENGINES member ("rr")
        trained_on_schema=None,  # untrained — pure OHLC arithmetic
    ),
    "ema_momentum_kernel": ModelContract(
        model_id="ema_momentum_kernel",
        entry_point="engines.ema_momentum_kernel.EmaMomentumKernel.compute",
        input_mode="features",
        spine_active=True,
        requires_artifact_cli=False,
        required_feature_keys=frozenset(
            {"ema_fast", "ema_slow", "momentum_score"}
        ),
        phase=1,
        audit_status="FLAWED",
        description="Live heuristic Gaussian kernel (F-060)",
        runnable=True,
        semantic_id="M0_SPINE_GAUSSIAN_HEURISTIC",
        tier="M0",
        miar_id="ema_momentum_kernel",
        miar_absent_reason=None,
        active_models_key="ema_momentum_kernel",
        active_models_absent_reason=None,
        serve_domain="ALL_BARS",
        scale_type="score",
        authority="FUSION_VOTE",  # EXPECTED_ENGINES member ("ema_momentum_kernel")
        trained_on_schema=None,  # unparameterised kernel (F-060) — no mu/sigma ever loaded
    ),
    "feature_cluster_similarity": ModelContract(
        model_id="feature_cluster_similarity",
        entry_point="engines.zone_cluster_score.score_zone_cluster",
        input_mode="features",
        spine_active=True,
        requires_artifact_cli=False,
        required_feature_keys=frozenset(),
        phase=1,
        audit_status="REDUNDANT",
        description="Production zone cluster score (hard path)",
        runnable=True,
        semantic_id="M0_SPINE_ZONE_GATE_CLUSTER",
        tier="M0",
        miar_id="feature_cluster_similarity",
        miar_absent_reason=None,
        active_models_key="feature_cluster_similarity",
        active_models_absent_reason=None,
        serve_domain="ALL_BARS",
        scale_type="score",
        authority="FUSION_VOTE",  # EXPECTED_ENGINES member ("feature_cluster_similarity"); F-041's hard-gate
        # behaviour (feature_cluster_similarity_mode=hard) is this same row's production role, not a separate veto row.
        trained_on_schema=None,  # geometric zone registry, not a trained artifact
    ),
    "crt_structure_rule_score": ModelContract(
        model_id="crt_structure_rule_score",
        entry_point="engines.crt_engine.compute",
        input_mode="features",
        spine_active=True,
        requires_artifact_cli=False,
        required_feature_keys=frozenset(
            {
                "body_ratio",
                "disp_strength",
                "atr",
                "retest_depth",
                "double_sweep",
                "candles_since_sweep",
                "sweep_detected",
            }
        ),
        phase=1,
        audit_status="CONDITIONAL",
        description="Fusion CRT scorer (compute_scores path; not full FSM)",
        runnable=True,
        semantic_id="M0_SPINE_CRT_FUSION_SCORER",
        tier="M0",
        miar_id="crt",  # shared with crt_state_machine — MIAR's "crt" primary_code lists both
        miar_absent_reason=None,
        active_models_key="crt",  # shared with crt_state_machine
        active_models_absent_reason=None,
        serve_domain="ALL_BARS",
        scale_type="score",
        authority="FUSION_VOTE",  # EXPECTED_ENGINES member ("crt")
        trained_on_schema=None,
    ),
    "fusion_compute": ModelContract(
        model_id="fusion_compute",
        entry_point="core.fusion_engine.FusionEngine.compute",
        input_mode="compose",
        spine_active=True,
        requires_artifact_cli=False,
        required_feature_keys=frozenset(),
        phase=2,
        audit_status="CONDITIONAL",
        description="Four live engines → FusionEngine.compute only",
        runnable=True,
        semantic_id="M4_ARBITER_FUSION_COMPUTE",
        tier="M4",
        miar_id="decision_fusion",  # primary_code lists fusion_engine.py, decision_engine.py, engine_runner.py
        miar_absent_reason=None,
        active_models_key=None,
        active_models_absent_reason="fusion weights live under engine_runner/fusion_engine config sections, not a dedicated active_models.yaml top-level key",
        serve_domain="COMPOSE",
        scale_type="composite",  # returns {final_score, scores, missing_engines, feature_cluster_similarity_dead, ...}
        authority="SPINE",  # combines the 4 FUSION_VOTE rows; not itself one of them
        trained_on_schema=None,
    ),
    "bitnet": ModelContract(
        model_id="bitnet",
        entry_point="bitnet.bitnet_inference.bitnet_score",
        input_mode="features",
        spine_active=False,
        requires_artifact_cli=False,
        required_feature_keys=frozenset(
            {
                "body_ratio",
                "retest_depth",
                "disp_strength",
                "atr",
                "candles_since_sweep",
                "double_sweep",
            }
        ),
        phase=3,
        audit_status="DORMANT",
        description="BitNet hard-reject confidence (observe; use_bitnet stays prod value)",
        runnable=True,
        semantic_id="M0_SPINE_BITNET_LEGACY6",
        tier="M0",
        miar_id="bitnet",
        miar_absent_reason=None,
        active_models_key="bitnet",
        active_models_absent_reason=None,
        serve_domain="RETEST_ONLY",  # CRT RETEST -> approve_with_soft_conf, per crt_engine_v2.py:2176
        scale_type="score",  # MIAR: "never claim probability without calibration"
        authority="SHADOW",  # F-055 shadow A/B measured it; use_bitnet stays false in production
        trained_on_schema="38dim_legacy",  # CONTRACT-B/R2.5 bundles; legacy-6 encoder itself is
        # schema-independent (6 hand-picked keys, not canonical-vector-bound)
    ),
    "tradenet": ModelContract(
        model_id="tradenet",
        entry_point="training.trade_net_v2.TradeNetV2.predict",
        input_mode="features",
        spine_active=False,
        requires_artifact_cli=True,
        required_feature_keys=frozenset(),
        phase=3,
        audit_status="UNWIRED",
        description="TradeNet v2 multi-head (requires --artifact)",
        runnable=True,
        semantic_id="M0_SPINE_TRADENET_MULTIHEAD",
        tier="M0",
        miar_id="tradenet",
        miar_absent_reason=None,
        active_models_key="tradenet",
        active_models_absent_reason=None,
        serve_domain="OFFLINE",
        scale_type="composite",  # TradeNetV2.predict returns dict of multiple named heads (self._heads)
        authority="NONE",  # F-005: fusion neural slot is a permanent stub, zero spine consumption
        trained_on_schema="48dim",  # TRADENET_SCHEMA v3.0, n_features=48; v5.0-vs-v6.0 not
        # distinguished by the artifact itself (dim unchanged across that rename, F-107)
    ),
    "rr_trained": ModelContract(
        model_id="rr_trained",
        entry_point="config_layer.rr.rr_trained.NanoInferenceEngine",
        input_mode="features",
        spine_active=False,
        requires_artifact_cli=True,
        required_feature_keys=frozenset(),
        phase=3,
        audit_status="OFF_SPINE",
        description="Trained RR NanoInference (v3 map); not live polarity",
        runnable=True,
        semantic_id="M0_SPINE_RR_TRAINED_NANO",
        tier="M0",
        miar_id="rr_trained",
        miar_absent_reason=None,
        active_models_key="rr_model",  # rr_model's own prose covers "rr_fusion disabled"; no
        # separate nested key exists (unlike gaussian's trained_registry.v4_mirrored)
        active_models_absent_reason=None,
        serve_domain="RETEST_ONLY",
        scale_type="score",  # confidence-gated NanoInferenceEngine.predict (F-044 rank-27 Mahalanobis)
        authority="NONE",  # engine_runner.rr_fusion.enabled: false
        trained_on_schema="39dim_v4",  # widest artifact on disk (docs/implementation_plan
        # /pure-chatgpt-model-response-cozy-pie.md §1); no 48-dim artifact exists
    ),
    "crt_state_machine": ModelContract(
        model_id="crt_state_machine",
        entry_point="config_layer.crt_engine_v2.CRTEngine.process_candle",
        input_mode="candles",
        spine_active=True,
        requires_artifact_cli=False,
        required_feature_keys=frozenset(),
        phase=2,
        audit_status="CONDITIONAL",
        description="Full 9-state CRT FSM (sequential candles)",
        runnable=True,
        semantic_id="M0_SPINE_CRT_STATE_MACHINE",
        tier="M0",
        miar_id="crt",  # shared with crt_structure_rule_score
        miar_absent_reason=None,
        active_models_key="crt",  # shared with crt_structure_rule_score
        active_models_absent_reason=None,
        serve_domain="ALL_BARS",
        scale_type="categorical",  # drives CRTState, a 9(+3 parent-CRT)-member enum, not a scalar
        authority="SPINE",  # foundational to the whole spine; not itself a FUSION_VOTE row
        trained_on_schema=None,
    ),
    "envelope": ModelContract(
        model_id="envelope",
        entry_point="research.envelope_offline.shadow.predict_heads",
        input_mode="features",
        spine_active=False,
        requires_artifact_cli=True,
        required_feature_keys=frozenset(),
        phase=3,
        audit_status="EXPERIMENTAL",
        description="EnvelopeNet 4 heads (requires --artifact bundle dir); 38-dim legacy vector",
        runnable=True,
        semantic_id="M0_SPINE_ENVELOPE_MFE_MAE",
        tier="M0",
        miar_id=None,
        miar_absent_reason="DESIGN_ONLY per miar_registry.json design_only_concepts."
        "envelope_post_entry_continuous_bounds — no production MIAR owner row (no wired "
        "consumer, decision_weight conceptually 0, no measured G001)",
        active_models_key="envelope",
        active_models_absent_reason=None,
        serve_domain="OFFLINE",
        scale_type="regression",  # 4 independent joblib heads: y_mfe_r/y_mae_r_heat/y_holding_bars/y_time_to_mfe
        authority="NONE",
        trained_on_schema="38dim_legacy",
    ),
    "nb_outcome_classifier": ModelContract(
        model_id="nb_outcome_classifier",
        entry_point="training.trainer.load_gaussian_model + NB predict",
        input_mode="features",
        spine_active=False,
        requires_artifact_cli=True,
        required_feature_keys=frozenset(),
        phase=3,
        audit_status="EXPERIMENTAL",
        description=(
            "Offline GaussianNB — requires --artifact; "
            "not a fusion slot (slot is EmaMomentumKernel)"
        ),
        runnable=True,
        semantic_id="M0_SPINE_GAUSSIAN_ML_NB",
        tier="M0",
        miar_id="nb_outcome_classifier",
        miar_absent_reason=None,
        active_models_key="ema_momentum_kernel.trained_registry.entries.v4_mirrored",  # dotted path — nested key
        active_models_absent_reason=None,
        serve_domain="ALL_BARS",
        scale_type="score",  # NB posteriors are not reliably calibrated; MIAR nb_outcome_classifier intent
        # forbids probability framing regardless of variant
        authority="NONE",  # config-gated off; M4 (E0/E1/E2) returned 0 PROMOTE, REGISTRY_ACTIVE != ECONOMIC_AUTHORITY
        trained_on_schema="38dim_legacy",  # Gaussian_v4_mirrored_38dim, per the governance doc's own name
    ),
    "regime": ModelContract(
        model_id="regime",
        entry_point="core.engine_runner.detect_regime",
        input_mode="features",
        spine_active=True,
        requires_artifact_cli=False,
        required_feature_keys=frozenset(
            {"ema_spread", "momentum_score", "volatility_ratio"}
        ),
        phase=1,
        audit_status="CONDITIONAL",
        description="Regime label (MIAR §3.12); F-061 flags trend-pin degeneracy",
        runnable=True,
        semantic_id="M0_SPINE_REGIME_DETECTOR",
        tier="M0",
        miar_id="regime",
        miar_absent_reason=None,
        active_models_key=None,
        active_models_absent_reason="no dedicated active_models.yaml section for this engine_runner-internal helper",
        serve_domain="ALL_BARS",
        scale_type="categorical",  # detect_regime returns a label ("trend"/"chop"/...), not a score
        authority="SPINE",  # spine_active, not an EXPECTED_ENGINES fusion vote
        trained_on_schema=None,
    ),
    "trap": ModelContract(
        model_id="trap",
        entry_point="core.engine_runner.trap_engine",
        input_mode="features",
        spine_active=True,
        requires_artifact_cli=False,
        required_feature_keys=frozenset(
            {"sweep_detected", "disp_strength", "trend_bias"}
        ),
        phase=1,
        audit_status="CERTIFIED",
        description="Dual-engine trap/deception voter (MIAR §3.10)",
        runnable=True,
        semantic_id="M0_SPINE_TRAP_VOTER",
        tier="M0",
        miar_id="trap",
        miar_absent_reason=None,
        active_models_key=None,
        active_models_absent_reason="no dedicated active_models.yaml section for this engine_runner-internal helper",
        serve_domain="ALL_BARS",
        scale_type="score",  # trap_engine(): dict with a dominant continuous "score" 0-1 (+ direction)
        authority="SPINE",
        trained_on_schema=None,
    ),
    "breakout": ModelContract(
        model_id="breakout",
        entry_point="core.engine_runner.breakout_engine",
        input_mode="features",
        spine_active=True,
        requires_artifact_cli=False,
        required_feature_keys=frozenset(
            {"trend_bias", "momentum_score", "ema_spread"}
        ),
        phase=1,
        audit_status="CONDITIONAL",
        description="Dual-engine breakout voter (MIAR §3.11); F-061 saturation risk",
        runnable=True,
        semantic_id="M0_SPINE_BREAKOUT_VOTER",
        tier="M0",
        miar_id="breakout",
        miar_absent_reason=None,
        active_models_key=None,
        active_models_absent_reason="no dedicated active_models.yaml section for this engine_runner-internal helper",
        serve_domain="ALL_BARS",
        scale_type="score",  # F-061: breakout_engine score pinned at ~1.0 on saturated bars — confirms continuous scalar
        authority="SPINE",
        trained_on_schema=None,
    ),
    "decision": ModelContract(
        model_id="decision",
        entry_point="core.decision_engine.DecisionEngine.evaluate",
        input_mode="compose",
        spine_active=True,
        requires_artifact_cli=False,
        required_feature_keys=frozenset(),
        phase=2,
        audit_status="CONDITIONAL",
        description=(
            "Stage-4 approval (MIAR §3.14): fusion_compute -> DecisionEngine. "
            "Static thresholds only (no AcceptanceController)"
        ),
        runnable=True,
        semantic_id="M4_ARBITER_DECISION_APPROVAL",
        tier="M4",
        miar_id="decision_fusion",  # shared with fusion_compute — same primary_code list
        miar_absent_reason=None,
        active_models_key=None,
        active_models_absent_reason="fusion weights live under engine_runner/fusion_engine config sections, not a dedicated active_models.yaml top-level key",
        serve_domain="COMPOSE",
        scale_type="composite",  # APPROVE/REJECT structured return (example-service.py convention)
        authority="SPINE",
        trained_on_schema=None,
    ),
    "execution_plan": ModelContract(
        model_id="execution_plan",
        entry_point="config_layer.execution_planner.ExecutionPlannerV1_2.plan",
        input_mode="compose",
        spine_active=True,
        requires_artifact_cli=False,
        required_feature_keys=frozenset({"high", "low", "atr"}),
        phase=2,
        audit_status="CONDITIONAL",
        description=(
            "Stage-5 executable trade plan (MIAR §3.13): mirrors live_engine_hook "
            ":860-926 — plan() -> compute_crt_levels -> SL/TP -> geometric RR -> "
            "position size. Stops at the trade plan; UltronRiskGate NOT invoked."
        ),
        runnable=True,
        semantic_id="M4_ARBITER_EXECUTION_PLAN",
        tier="M4",
        miar_id="execution_intent",
        miar_absent_reason=None,
        active_models_key=None,
        active_models_absent_reason="no dedicated active_models.yaml section; planner config lives under execution_planner production-config, not this descriptive mirror",
        serve_domain="COMPOSE",
        scale_type="composite",  # entry/SL/TP1/TP2/RR/TTL structured ExecutionPlan
        authority="SPINE",
        trained_on_schema=None,
    ),
    "llm_gate": ModelContract(
        model_id="llm_gate",
        entry_point="core.fusion_engine.FusionEngine.evaluate",
        input_mode="blocked",
        spine_active=False,
        requires_artifact_cli=False,
        required_feature_keys=frozenset(),
        phase=9,
        audit_status="FAILED",
        description="LLM gate dead — no llm_fn on EngineRunner; evaluate() unused",
        runnable=False,
        semantic_id="M9_ORCH_LLM_GATE",
        tier="M9",
        miar_id=None,
        miar_absent_reason="dead code (no llm_fn wired to EngineRunner) — no MIAR entry covers an unreachable evaluate() path",
        active_models_key=None,
        active_models_absent_reason="dead code, no descriptive mirror maintained for an unreachable path",
        serve_domain="OFFLINE",
        scale_type="composite",
        authority="NONE",
        trained_on_schema=None,
    ),
    "strategies": ModelContract(
        model_id="strategies",
        entry_point="strategies.strategy_orchestrator.StrategyOrchestrator",
        input_mode="blocked",
        spine_active=False,
        requires_artifact_cli=False,
        required_feature_keys=frozenset(),
        phase=9,
        audit_status="DEPRECATED",
        description="S1-S10 sidecar; not on live spine",
        runnable=False,
        semantic_id="M9_ORCH_STRATEGIES_SIDECAR",
        tier="M9",
        miar_id=None,
        miar_absent_reason="deprecated sidecar, not on the live spine — no MIAR intent owns it",
        active_models_key="strategies",
        active_models_absent_reason=None,
        serve_domain="OFFLINE",
        scale_type="composite",
        authority="NONE",
        trained_on_schema=None,
    ),
    "engine_runner": ModelContract(
        model_id="engine_runner",
        entry_point="core.engine_runner.EngineRunner.run",
        input_mode="blocked",
        spine_active=True,
        requires_artifact_cli=False,
        required_feature_keys=frozenset(),
        phase=9,
        audit_status="ORCHESTRATOR",
        description="Full orchestrator — use backtest, not single-model runner",
        runnable=False,
        semantic_id="M9_ORCH_ENGINE_RUNNER",
        tier="M9",
        miar_id="decision_fusion",  # primary_code explicitly lists engine_runner.py alongside fusion/decision
        miar_absent_reason=None,
        active_models_key="engine_runner",
        active_models_absent_reason=None,
        serve_domain="COMPOSE",
        scale_type="composite",
        authority="SPINE",  # runs live; not itself a vote/veto
        trained_on_schema=None,
    ),
}


def list_models() -> list[ModelContract]:
    return [MODEL_CATALOG[k] for k in sorted(MODEL_CATALOG)]


def list_runnable() -> list[ModelContract]:
    return [m for m in list_models() if m.runnable]


def get_contract(model_id: str) -> ModelContract:
    if model_id not in MODEL_CATALOG:
        known = ", ".join(sorted(MODEL_CATALOG))
        raise KeyError(f"unknown model_id={model_id!r}. Known: {known}")
    return MODEL_CATALOG[model_id]
