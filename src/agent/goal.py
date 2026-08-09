"""
goal.py — AgentGoal contracts for GrokAgenticAI
─────────────────────────────────────────────────────────────────────────────
Goal-oriented campaign objects. Meeting success criteria means the *campaign*
completed — it does NOT grant production / promotion authority (§6.5).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal, Optional


GoalKind = Literal[
    "ops_diagnose",
    "campaign_pipeline",
    "campaign_research",
    "training_refresh",
    "data_hygiene",
    "truth_janitor",
    "multi_llm_handoff",
]

Autonomy = Literal[
    "read_only",
    "confirm_writes",
    "preapproved_writes",
]

CriterionOp = Literal["eq", "ne", "gte", "lte", "contains", "exists"]


@dataclass
class SuccessCriterion:
    metric: str
    op: CriterionOp
    value: Any = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AgentGoal:
    goal_id: str
    kind: GoalKind
    objective: str
    agent_name: str = "GrokAgenticAI"
    specialist: str = ""  # e.g. OpsDoctor, CampaignRunner
    instruments: List[str] = field(default_factory=list)
    success: List[SuccessCriterion] = field(default_factory=list)
    fail_fast: List[SuccessCriterion] = field(default_factory=list)
    autonomy: Autonomy = "confirm_writes"
    preapproved_tools: List[str] = field(default_factory=list)
    max_steps: int = 12
    max_wall_s: int = 3600
    seed_intent: Optional[str] = None
    measurement_contract_id: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


@dataclass
class Observation:
    step_index: int
    tool: str
    outcome: Literal["success", "fail", "denied", "refused", "pending"]
    metrics: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    raw_status: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


def _get_nested(metrics: Dict[str, Any], key: str) -> Any:
    """Support dotted keys: validation.decision"""
    if key in metrics:
        return metrics[key]
    cur: Any = metrics
    for part in key.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def eval_criterion(crit: SuccessCriterion, metrics: Dict[str, Any]) -> bool:
    """Pure predicate — no I/O."""
    val = _get_nested(metrics, crit.metric)
    op = crit.op
    if op == "exists":
        return val is not None
    if val is None:
        return False
    if op == "eq":
        return val == crit.value
    if op == "ne":
        return val != crit.value
    if op == "gte":
        try:
            return float(val) >= float(crit.value)
        except (TypeError, ValueError):
            return False
    if op == "lte":
        try:
            return float(val) <= float(crit.value)
        except (TypeError, ValueError):
            return False
    if op == "contains":
        return crit.value in val if val is not None else False
    return False


def merge_metrics(observations: List[Observation]) -> Dict[str, Any]:
    """Later observations overwrite earlier keys; also keep last tool names."""
    out: Dict[str, Any] = {}
    tools: List[str] = []
    for obs in observations:
        tools.append(obs.tool)
        out.update(obs.metrics)
        if obs.error:
            out["last_error"] = obs.error
        out["last_tool"] = obs.tool
        out["last_outcome"] = obs.outcome
    out["tools_run"] = tools
    out["n_steps"] = len(observations)
    return out


def eval_any(criteria: List[SuccessCriterion], metrics: Dict[str, Any]) -> bool:
    if not criteria:
        return False
    return any(eval_criterion(c, metrics) for c in criteria)


def eval_all(criteria: List[SuccessCriterion], metrics: Dict[str, Any]) -> bool:
    if not criteria:
        return False
    return all(eval_criterion(c, metrics) for c in criteria)


def extract_metrics_from_result(tool: str, result: Any) -> Dict[str, Any]:
    """Normalize tool results into flat-ish metrics for criteria / branching."""
    metrics: Dict[str, Any] = {"tool": tool}
    if not isinstance(result, dict):
        metrics["raw_type"] = type(result).__name__
        return metrics
    metrics.update({k: v for k, v in result.items() if not str(k).startswith("_")})
    # Common ValidationReport shapes
    decision = result.get("decision") or (result.get("report") or {}).get("decision")
    if decision is not None:
        metrics["validation.decision"] = decision
        metrics["decision"] = decision
    if "status" in result:
        metrics["status"] = result["status"]
    if result.get("status") == "error":
        metrics["error"] = result.get("error", "error")
    # Incident pack
    if "incident_path" in result:
        metrics["incident_path"] = result["incident_path"]
        metrics["incident_pack"] = True
    return metrics
