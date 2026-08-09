"""
goal_loop.py — GrokAgenticAI goal execution
─────────────────────────────────────────────────────────────────────────────
Runs a specialist AgentGoal under existing Executor fences:

  seed recipe → dispatch (allowlist / path / confirm) → observe →
  Mode-B branch (campaign) → success / fail_fast / max_steps stop

LLM never chooses arbitrary tools (Mode D forbidden).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .goal import (
    AgentGoal,
    Observation,
    eval_all,
    eval_any,
    extract_metrics_from_result,
    merge_metrics,
)
from .grok_agentic import SPECIALISTS, get_specialist
from .plan_compiler import ToolStep
from .recipes.campaign_pipeline import campaign_next_tools, campaign_seed_steps
from .recipes.ops_diagnose import ops_seed_steps
from .recipes.truth_janitor import truth_seed_steps

logger = logging.getLogger("GrokAgenticAI.GoalLoop")


@dataclass
class GoalResult:
    goal: AgentGoal
    observations: List[Observation] = field(default_factory=list)
    success_met: bool = False
    fail_fast_met: bool = False
    outcome: str = "no_op"
    metrics: Dict[str, Any] = field(default_factory=dict)
    write_confirmed: bool = False
    summary: str = ""
    steps_run: List[str] = field(default_factory=list)


ConfirmFn = Callable[[str, dict, str], bool]  # tool, args, preview → confirmed?
DispatchFn = Callable[[str, dict, bool], Any]
DeniedFn = Callable[[str, dict], None]
FillArgsFn = Callable[[str, dict, dict], dict]  # tool, schema, defaults → filled args or clarify


class GoalLoop:
    def __init__(
        self,
        *,
        dispatch: DispatchFn,
        dispatch_denied: DeniedFn,
        fill_args: FillArgsFn,
        confirm_fn: Optional[ConfirmFn] = None,
        get_tool_schema: Callable[[str], Optional[dict]],
    ):
        self._dispatch = dispatch
        self._dispatch_denied = dispatch_denied
        self._fill_args = fill_args
        self._confirm_fn = confirm_fn
        self._get_tool_schema = get_tool_schema

    def run(self, goal: AgentGoal) -> GoalResult:
        t0 = time.monotonic()
        steps = self._seed_steps(goal)
        observations: List[Observation] = []
        write_confirmed = False
        re_tune_budget = 1  # CampaignRunner: at most one REJECT→retune cycle
        result = GoalResult(goal=goal)

        # Allowlist for specialist
        allow: Optional[Set[str]] = None
        for key, spec in SPECIALISTS.items():
            if spec.display_name == goal.specialist or spec.seed_intent == goal.seed_intent:
                if spec.enforce_allowlist:
                    allow = set(spec.tool_allowlist)
                break

        i = 0
        while i < len(steps) and len(observations) < goal.max_steps:
            if time.monotonic() - t0 > goal.max_wall_s:
                logger.warning("goal %s wall-clock exceeded", goal.goal_id)
                break

            step = steps[i]
            i += 1

            if allow is not None and step.tool not in allow:
                observations.append(
                    Observation(
                        step_index=len(observations),
                        tool=step.tool,
                        outcome="refused",
                        metrics={"status": "refused", "error": "outside specialist allowlist"},
                        error="outside specialist allowlist",
                    )
                )
                continue

            schema = self._get_tool_schema(step.tool) or {}
            filled = self._fill_args(step.tool, schema, dict(step.default_args))
            if filled.get("clarify"):
                result.outcome = "clarify"
                result.summary = str(filled["clarify"])
                result.observations = observations
                return result

            args = filled.get("args", dict(step.default_args))
            # Inject instruments from goal when useful
            if goal.instruments and "instrument" in (schema or {}) and not args.get("instrument"):
                args["instrument"] = goal.instruments[0]
            if goal.instruments and "instruments" in args and not args.get("instruments"):
                args["instruments"] = " ".join(goal.instruments)

            print(f"  [{goal.specialist or 'GrokAgenticAI'}] step {len(observations)+1} {step.tool}...", end=" ", flush=True)

            out = self._dispatch(step.tool, args, False)

            # PendingConfirmation duck-type
            if type(out).__name__ == "PendingConfirmation" or (
                hasattr(out, "preview") and hasattr(out, "tool")
            ):
                preview = getattr(out, "preview", str(out))
                print(f"\n{preview}")
                confirmed = False
                if goal.autonomy == "preapproved_writes" and step.tool in goal.preapproved_tools:
                    confirmed = True
                    print("  preapproved write.")
                elif self._confirm_fn:
                    confirmed = self._confirm_fn(step.tool, args, preview)
                else:
                    ans = input("  Confirm? y/N: ").strip().lower()
                    confirmed = ans == "y"

                if confirmed:
                    write_confirmed = True
                    out = self._dispatch(step.tool, args, True)
                    print("  confirmed.")
                else:
                    self._dispatch_denied(step.tool, args)
                    print("  denied.")
                    observations.append(
                        Observation(
                            step_index=len(observations),
                            tool=step.tool,
                            outcome="denied",
                            metrics={"status": "denied"},
                        )
                    )
                    result.outcome = "denied"
                    break
            elif isinstance(out, str) and out.startswith("REFUSED:"):
                print(f"\n  {out}")
                observations.append(
                    Observation(
                        step_index=len(observations),
                        tool=step.tool,
                        outcome="refused",
                        metrics={"status": "refused", "error": out},
                        error=out,
                    )
                )
                break
            else:
                print("done")

            outcome = "success"
            err = None
            if isinstance(out, dict) and out.get("status") == "error":
                outcome = "fail"
                err = str(out.get("error", "error"))

            metrics = extract_metrics_from_result(step.tool, out)
            # Propagate goal context for incident pack
            if goal.instruments:
                metrics.setdefault("instrument", goal.instruments[0])
            obs = Observation(
                step_index=len(observations),
                tool=step.tool,
                outcome=outcome,  # type: ignore[arg-type]
                metrics=metrics,
                error=err,
                raw_status=str(metrics.get("status", "")),
            )
            observations.append(obs)

            merged = merge_metrics(observations)
            if goal.fail_fast and eval_any(goal.fail_fast, merged):
                # Don't fail-fast on expected validator REJECT (branch handles it)
                if not (
                    step.tool == "validator.validate"
                    and str(merged.get("validation.decision", "")).upper() == "REJECT"
                ):
                    result.fail_fast_met = True
                    result.outcome = "fail_fast"
                    break

            # Mode-B campaign branches (REJECT → one retune cycle)
            if goal.kind == "campaign_pipeline":
                extra = campaign_next_tools(step.tool, metrics)
                if extra is not None and extra:
                    if "tuner.run_multi" in extra:
                        if re_tune_budget <= 0:
                            print("  [CampaignRunner] re-tune budget exhausted — stopping")
                            result.outcome = "reject_exhausted"
                            break
                        re_tune_budget -= 1
                        inst_s = " ".join(goal.instruments)
                        tail: List[ToolStep] = [
                            ToolStep(
                                tool="tuner.run_multi",
                                default_args={"data_dir": "data/", "instruments": inst_s},
                            ),
                            ToolStep(
                                tool="validator.validate",
                                default_args={"data_dir": "data/"},
                            ),
                        ]
                        if goal.context.get("include_promote"):
                            tail.append(
                                ToolStep(
                                    tool="promotion.promote_from_checkpoint",
                                    default_args={"data_dir": "data/"},
                                )
                            )
                        if goal.context.get("include_backtest", True):
                            tail.append(ToolStep(tool="backtest.run_v2", default_args={}))
                        steps = steps[:i] + tail

            merged_now = merge_metrics(observations)
            if goal.success and eval_all(goal.success, merged_now):
                result.success_met = True
                result.outcome = "success"
                break

            # Soft success: ops incident pack written
            if goal.kind == "ops_diagnose" and metrics.get("incident_pack"):
                result.success_met = True
                result.outcome = "success"
                break

            # Soft success: truth hygiene pack written
            if goal.kind == "truth_janitor" and metrics.get("hygiene_pack"):
                result.success_met = True
                result.outcome = "success"
                break

        result.observations = observations
        result.metrics = merge_metrics(observations)
        result.write_confirmed = write_confirmed
        result.steps_run = [o.tool for o in observations]
        if result.outcome in ("no_op",):
            if not observations:
                result.outcome = "no_op"
            elif all(o.outcome == "success" for o in observations):
                result.outcome = "success"
                # Ops complete flag
                if goal.kind == "ops_diagnose":
                    result.metrics["ops.complete"] = True
                    result.success_met = True
                if goal.kind == "truth_janitor":
                    result.metrics["truth.complete"] = True
                    result.success_met = True
            elif any(o.outcome == "success" for o in observations):
                result.outcome = "partial"
            else:
                result.outcome = "fail"

        result.summary = self._summary(goal, result)
        return result

    def _seed_steps(self, goal: AgentGoal) -> List[ToolStep]:
        inst = goal.instruments[0] if goal.instruments else ""
        instruments_str = " ".join(goal.instruments)
        if goal.kind == "ops_diagnose" or goal.seed_intent == "ops_diagnose":
            return ops_seed_steps(instrument=inst)
        if goal.kind == "truth_janitor" or goal.seed_intent == "truth_janitor":
            return truth_seed_steps()
        if goal.kind == "campaign_pipeline" or goal.seed_intent in (
            "campaign_run",
            "campaign_tune_validate",
        ):
            include_promote = bool(goal.context.get("include_promote", False))
            include_backtest = bool(goal.context.get("include_backtest", True))
            # "promote" in objective
            obj = (goal.objective or "").lower()
            if "promot" in obj:
                include_promote = True
            if "skip backtest" in obj or "no backtest" in obj:
                include_backtest = False
            return campaign_seed_steps(
                include_promote=include_promote,
                include_backtest=include_backtest,
                instruments=instruments_str,
            )
        # Fallback empty
        return []

    @staticmethod
    def _summary(goal: AgentGoal, result: GoalResult) -> str:
        brand = goal.agent_name or "GrokAgenticAI"
        specialist = goal.specialist or "agent"
        chain = " → ".join(result.steps_run) if result.steps_run else "(none)"
        bits = [
            f"{brand}/{specialist} goal={goal.goal_id}",
            f"outcome={result.outcome}",
            f"success_met={result.success_met}",
            f"steps=[{chain}]",
        ]
        if result.metrics.get("incident_path"):
            bits.append(f"incident={result.metrics['incident_path']}")
        if result.metrics.get("hygiene_path"):
            bits.append(f"hygiene={result.metrics['hygiene_path']}")
        if result.metrics.get("validation.decision"):
            bits.append(f"validation={result.metrics['validation.decision']}")
        if result.metrics.get("last_error"):
            bits.append(f"error={result.metrics['last_error']}")
        return " | ".join(bits)
