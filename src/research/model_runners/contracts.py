"""Model catalog — all audit models; phase marks implement status."""
from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet


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


MODEL_CATALOG: dict[str, ModelContract] = {
    "rr": ModelContract(
        model_id="rr",
        entry_point="engines.rr_engine.RREngine.compute",
        input_mode="ohlc",
        spine_active=True,
        requires_artifact_cli=False,
        required_feature_keys=frozenset({"high", "low", "close"}),
        phase=1,
        audit_status="CERTIFIED",
        description="Candle polarity index (live fusion RR slot)",
        runnable=True,
    ),
    "gaussian": ModelContract(
        model_id="gaussian",
        entry_point="engines.heuristic_gaussian_engine.HeuristicGaussianEngine.compute",
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
    ),
    "zone_gate": ModelContract(
        model_id="zone_gate",
        entry_point="engines.zone_cluster_score.score_zone_cluster",
        input_mode="features",
        spine_active=True,
        requires_artifact_cli=False,
        required_feature_keys=frozenset(),
        phase=1,
        audit_status="REDUNDANT",
        description="Production zone cluster score (hard path)",
        runnable=True,
    ),
    "crt_score": ModelContract(
        model_id="crt_score",
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
                "candles_since_retest",
                "sweep_detected",
            }
        ),
        phase=1,
        audit_status="CONDITIONAL",
        description="Fusion CRT scorer (compute_scores path; not full FSM)",
        runnable=True,
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
                "candles_since_retest",
                "double_sweep",
            }
        ),
        phase=3,
        audit_status="DORMANT",
        description="BitNet hard-reject confidence (observe; use_bitnet stays prod value)",
        runnable=True,
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
    ),
    "rr_trained": ModelContract(
        model_id="rr_trained",
        entry_point="config_layer.rr.rr_pattern_miner.NanoInferenceEngine",
        input_mode="features",
        spine_active=False,
        requires_artifact_cli=True,
        required_feature_keys=frozenset(),
        phase=3,
        audit_status="OFF_SPINE",
        description="Trained RR NanoInference (v3 map); not live polarity",
        runnable=True,
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
    ),
    "gaussian_ml": ModelContract(
        model_id="gaussian_ml",
        entry_point="training.trainer.load_gaussian_model + NB predict",
        input_mode="features",
        spine_active=False,
        requires_artifact_cli=True,
        required_feature_keys=frozenset(),
        phase=3,
        audit_status="EXPERIMENTAL",
        description=(
            "Offline GaussianNB — requires --artifact; "
            "NOT gated by engine_runner.gaussian_impl"
        ),
        runnable=True,
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
