"""
core/types.py
Canonical TypedDict contracts for the execution spine.

These types are the authoritative interface definitions.  Every module that
produces or consumes spine data MUST conform to these shapes.  Import from
here — do NOT duplicate inline dicts in other modules.

Spine:
    EngineInput  → EngineRunner.run()    → EngineRunnerOutput
    EngineRunnerOutput  → ExecutionPlannerV1_2.plan()  → TradePlan
    TradePlan           → UltronRiskGate.evaluate()    → GateResult
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict, Required


# ──────────────────────────────────────────────────────────────────────────────
# 1. EngineRunner.run() — INPUT
# ──────────────────────────────────────────────────────────────────────────────

class EngineContext(TypedDict, total=False):
    """context dict passed to EngineRunner.run()."""
    symbol:    Required[str]    # e.g. "EURUSD"
    timeframe: Required[str]    # e.g. "M15"
    session:   str              # "london" | "newyork" | "asian"
    regime:    str              # from RegimeClassifier.classify()
    candle_idx: int
    fusion_weights: Dict[str, float]  # from ConfigRouter (optional override)


# ──────────────────────────────────────────────────────────────────────────────
# 2. EngineRunner.run() — OUTPUT
# ──────────────────────────────────────────────────────────────────────────────

class EngineScores(TypedDict, total=False):
    crt:                float
    gaussian:           float
    zone_gate:          float
    rr:                 float
    strategy_consensus: float   # 5th engine — StrategyOrchestrator consensus


class FusionSummary(TypedDict, total=False):
    final_score:      float
    normalized_score: float
    missing_engines:  List[str]
    zone_gate_dead:   bool


class EngineRunnerOutput(TypedDict, total=False):
    """Return value of EngineRunner.run()."""
    decision:           Required[str]   # "execute" | "reject"
    final_score:        float           # 0–1
    regime:             str
    selected_engine:    Optional[str]
    selected_direction: int             # 1=BUY, -1=SELL, 0=none
    dual_score:         float
    gate_reason:        str
    reject_stage:       str             # "none" | "adapter" | "completeness" | "fusion" | "regime" | "decision"
    reason:             str
    engine_scores:      EngineScores
    fusion:             FusionSummary
    record_id:          Optional[str]   # UUID linking to Collector entry


# ──────────────────────────────────────────────────────────────────────────────
# 3. ExecutionPlannerV1_2.plan() — OUTPUT
# ──────────────────────────────────────────────────────────────────────────────

class TradePlan(TypedDict, total=False):
    """Return value of ExecutionPlannerV1_2.plan()."""
    decision:     Required[str]         # "execute" | "skip"
    trade_intent: Optional[str]         # "BUY" | "SELL" | None
    entry_price:  float
    sl_price:     float
    tp_price:     float
    rr_ratio:     float
    sl_inr:       float
    tp_inr:       float
    lot_size:     float
    ttl_bars:     int
    risk_percent: float


# ──────────────────────────────────────────────────────────────────────────────
# 4. UltronRiskGate.evaluate() — OUTPUT
# ──────────────────────────────────────────────────────────────────────────────

class GateResult(TypedDict, total=False):
    """Return value of UltronRiskGate.evaluate()."""
    decision:           Required[str]   # "APPROVE" | "REJECT"
    reason:             str
    risk_mult:          float           # 0.0–1.0
    allocated_risk_pct: float
    account_balance:    float
    daily_loss_pct:     float
    trades_today:       int
    open_positions:     int


# ──────────────────────────────────────────────────────────────────────────────
# 5. Contract enforcement helpers
# ──────────────────────────────────────────────────────────────────────────────

class SpineContractError(RuntimeError):
    """Raised when a spine contract is violated at runtime."""


def assert_approve_before_order(gate_result: Dict[str, Any]) -> None:
    """
    Call this immediately before any MT5Bridge.place_order() invocation.
    Raises SpineContractError if gate_result does not carry APPROVE.
    """
    if gate_result.get("decision") != "APPROVE":
        raise SpineContractError(
            f"MT5Bridge.place_order() called without UltronRiskGate APPROVE. "
            f"gate_result['decision'] = {gate_result.get('decision')!r}"
        )


def assert_engine_runner_output(result: Dict[str, Any]) -> None:
    """Lightweight sanity check that a dict looks like EngineRunnerOutput."""
    decision = result.get("decision", "")
    if decision not in ("execute", "reject"):
        raise SpineContractError(
            f"EngineRunnerOutput.decision must be 'execute' or 'reject', got {decision!r}"
        )
