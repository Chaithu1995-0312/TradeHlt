"""CampaignRunner seed + Mode-B branch table (metric → next tools)."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from agent.plan_compiler import ToolStep, _s


def campaign_seed_steps(
    *,
    include_promote: bool = False,
    include_backtest: bool = True,
    include_live_dry: bool = False,
    data_dir: str = "data/",
    instruments: str = "",
) -> List[ToolStep]:
    """Default campaign: tune → validate → optional promote → optional backtest."""
    steps: List[ToolStep] = [
        _s("tuner.run_multi", data_dir=data_dir, instruments=instruments),
        _s("validator.validate", data_dir=data_dir),
    ]
    if include_promote:
        steps.append(_s("promotion.promote_from_checkpoint", data_dir=data_dir))
    if include_backtest:
        # instrument CSV resolved later by ArgFiller / context
        steps.append(_s("backtest.run_v2"))
    if include_live_dry:
        steps.append(_s("live_hook.dry_run"))
    return steps


# (last_tool, decision_or_status) → next tools to append (once)
_BRANCHES: Dict[Tuple[str, str], List[str]] = {
    # Reject → one re-tune then re-validate (loop control in goal_loop)
    ("validator.validate", "REJECT"): ["tuner.run_multi", "validator.validate"],
    ("validator.validate", "APPROVE"): [],  # continue seed remainder
    ("tuner.run_multi", "error"): [],       # stop
    ("promotion.promote_from_checkpoint", "error"): [],
}


def campaign_next_tools(last_tool: str, metrics: dict) -> Optional[List[str]]:
    """
    Return extra tools to queue after an observation, or None for no branch.
    Empty list means "stop branching" (continue remaining seed / end).
    """
    decision = str(metrics.get("validation.decision") or metrics.get("decision") or "").upper()
    status = str(metrics.get("status") or "").lower()

    if last_tool == "validator.validate" and decision:
        key = (last_tool, decision)
        if key in _BRANCHES:
            return list(_BRANCHES[key])
    if status == "error":
        key = (last_tool, "error")
        if key in _BRANCHES:
            return list(_BRANCHES[key])
    return None
