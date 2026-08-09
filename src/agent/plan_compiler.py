"""
plan_compiler.py
─────────────────────────────────────────────────────────────────────────────
Deterministic intent → tool sequence mapping.

PlanCompiler.build(intent_key) looks up PLAN_REGISTRY and returns an ordered
Plan. The LLM is NOT involved here — this is pure Python dispatch.

PLAN_REGISTRY is the single source of truth for what steps each intent runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ToolStep:
    tool: str
    default_args: dict = field(default_factory=dict)


@dataclass
class Plan:
    intent_key: str
    steps: List[ToolStep]

    def filter(self, skip: set) -> "Plan":
        """Return a new Plan with steps whose tool name is not in skip."""
        return Plan(
            intent_key=self.intent_key,
            steps=[s for s in self.steps if s.tool not in skip],
        )


def _s(tool: str, **defaults) -> ToolStep:
    return ToolStep(tool=tool, default_args=defaults)


# ── Canonical intent → tool sequence map ─────────────────────────────────────
# All 14 intents. Steps are executed in order by AgentCore.
PLAN_REGISTRY: Dict[str, List[ToolStep]] = {
    # ── Pipeline mode ──────────────────────────────────────────────────────────
    "tune_only": [
        _s("tuner.run_multi"),
    ],
    "tune_and_validate": [
        _s("tuner.run_multi"),
        _s("validator.validate"),
    ],
    "tune_and_promote": [
        _s("tuner.run_multi"),
        _s("validator.validate"),
        _s("promotion.promote_from_checkpoint"),
    ],
    "validate_only": [
        _s("validator.validate"),
    ],
    "promote_only": [
        _s("promotion.promote_from_checkpoint"),
    ],
    "backtest_only": [
        _s("backtest.run_v2"),
    ],
    "full_pipeline": [
        _s("tuner.run_multi"),
        _s("validator.validate"),
        _s("promotion.promote_from_checkpoint"),
        _s("backtest.run_v2"),
        _s("live_hook.dry_run"),
    ],
    # ── Copilot mode ───────────────────────────────────────────────────────────
    "advise_signal": [
        _s("engine.run"),
        _s("fusion.explain"),
        _s("planner.plan"),
        _s("risk.check"),
        _s("advise.veto"),
    ],
    "veto_query": [
        _s("engine.run"),
        _s("fusion.explain"),
        _s("advise.veto"),
    ],
    "resize_query": [
        _s("engine.run"),
        _s("fusion.explain"),
        _s("advise.resize"),
    ],
    # ── Governance mode ────────────────────────────────────────────────────────
    "governance_inspect": [
        _s("reflection.load_merge"),
        _s("meta_governor.dry_run"),
    ],
    "governance_propose": [
        _s("reflection.load_merge"),
        _s("reflection.generate_prompt"),
        _s("meta_governor.dry_run"),
        _s("shadow.stage_candidate"),
    ],
    "governance_run": [
        _s("reflection.load_merge"),
        _s("meta_governor.dry_run"),
        _s("governance.run_loop"),
    ],
    # ── Cross-mode ─────────────────────────────────────────────────────────────
    "audit_inspect": [
        _s("audit.tail"),
    ],
    # ── Findings (cross-mode, on-demand post-run synthesis) ───────────────────
    "findings_synthesize": [
        _s("findings.synthesize"),
    ],
    "findings_recent": [
        _s("findings.list_recent", n=10),
    ],
    "findings_explain": [
        _s("findings.explain"),
    ],
    # ── GrokAgenticAI specialists (executed via GoalLoop; seeds for docs/tests) ─
    "ops_diagnose": [
        _s("ops.throughput_snapshot"),
        _s("ops.funnel_diagnose"),
        _s("ops.fail_reasons"),
        _s("collector.tail"),
        _s("ops.incident_pack"),
    ],
    "campaign_run": [
        _s("tuner.run_multi"),
        _s("validator.validate"),
        _s("backtest.run_v2"),
    ],
    "campaign_tune_validate": [
        _s("tuner.run_multi"),
        _s("validator.validate"),
    ],
    "truth_janitor": [
        _s("truth.construction_check"),
        _s("truth.feature_math_lint"),
        _s("truth.script_census"),
        _s("truth.citation_floor"),
        _s("truth.hygiene_pack"),
    ],
}

_ASK_PLAN = Plan(intent_key="ask_user", steps=[])


class PlanCompiler:
    @staticmethod
    def build(intent_key: str) -> Plan:
        """
        Return a deterministic Plan for the given intent_key.
        Returns a plan with intent_key='ask_user' and empty steps if unknown.
        Steps are fresh copies — default_args cannot leak between calls.
        """
        steps = PLAN_REGISTRY.get(intent_key)
        if steps is None:
            return _ASK_PLAN
        return Plan(
            intent_key=intent_key,
            steps=[ToolStep(tool=s.tool, default_args=dict(s.default_args)) for s in steps],
        )

    @staticmethod
    def filter(plan: Plan, skip_tools: set) -> Plan:
        """Remove steps matching any tool in skip_tools."""
        return plan.filter(skip_tools)
