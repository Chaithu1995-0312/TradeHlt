"""
test_agent_plan_compiler.py
===========================
Tests for src/agent/plan_compiler.py — deterministic planning, no LLM.

Actual API:
  PlanCompiler.build(intent_key: str) -> Plan
  PlanCompiler.filter(plan, skip_tools: set) -> Plan
  Plan.intent_key, Plan.steps (List[ToolStep]), Plan.filter(skip)
  ToolStep.tool, ToolStep.default_args
  PLAN_REGISTRY: Dict[str, List[ToolStep]]  — 17 intents

Helper:
  _tools(plan) -> list[str]   — extracts tool names from Plan.steps in order
"""

import pytest
from agent.plan_compiler import PlanCompiler, Plan, PLAN_REGISTRY


def _tools(plan: Plan) -> list:
    """Extract ordered tool name list from a Plan."""
    return [s.tool for s in plan.steps]


# ─────────────────────────────────────────────────────────────────────────────
# Canonical intent → tool sequence tests
# ─────────────────────────────────────────────────────────────────────────────

def test_tune_and_promote_pipeline():
    """tune_and_promote: tuner → validator → promotion, in that order."""
    plan = PlanCompiler.build("tune_and_promote")
    tools = _tools(plan)
    assert "tuner.run_multi"                  in tools
    assert "validator.validate"               in tools
    assert "promotion.promote_from_checkpoint" in tools
    assert tools.index("tuner.run_multi") < tools.index("validator.validate") < tools.index(
        "promotion.promote_from_checkpoint"
    )


def test_backtest_only():
    """backtest_only: single step backtest.run_v2."""
    plan = PlanCompiler.build("backtest_only")
    assert _tools(plan) == ["backtest.run_v2"]


def test_governance_run_canonical_order():
    """governance_run: reflection.load_merge before meta_governor.dry_run before governance.run_loop."""
    plan  = PlanCompiler.build("governance_run")
    tools = _tools(plan)
    assert "reflection.load_merge" in tools
    assert "meta_governor.dry_run"  in tools
    assert "governance.run_loop"    in tools
    assert tools.index("reflection.load_merge") < tools.index("meta_governor.dry_run")
    assert tools.index("meta_governor.dry_run")  < tools.index("governance.run_loop")


def test_advise_signal_engine_first_veto_present():
    """advise_signal: engine.run must be first; advise.veto must be present."""
    plan  = PlanCompiler.build("advise_signal")
    tools = _tools(plan)
    assert tools[0] == "engine.run", f"engine.run must be first, got {tools[0]!r}"
    assert "advise.veto" in tools


def test_full_pipeline_contains_all_stages():
    """full_pipeline: includes tuner, validator, promotion, backtest, live_hook."""
    plan  = PlanCompiler.build("full_pipeline")
    tools = _tools(plan)
    for expected in (
        "tuner.run_multi",
        "validator.validate",
        "promotion.promote_from_checkpoint",
        "backtest.run_v2",
        "live_hook.dry_run",
    ):
        assert expected in tools, f"full_pipeline missing tool '{expected}'"


def test_governance_inspect_preflight_present():
    """governance_inspect: reflection.load_merge must precede meta_governor.dry_run."""
    plan  = PlanCompiler.build("governance_inspect")
    tools = _tools(plan)
    assert "reflection.load_merge" in tools
    assert tools.index("reflection.load_merge") < tools.index("meta_governor.dry_run"), (
        "reflection.load_merge must precede meta_governor.dry_run in governance_inspect"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Determinism — LLM cannot reorder (pure Python lookup)
# ─────────────────────────────────────────────────────────────────────────────

def test_same_intent_key_always_returns_same_tools():
    """Determinism invariant: same intent_key → same tool list every call."""
    plan_a = PlanCompiler.build("tune_and_promote")
    plan_b = PlanCompiler.build("tune_and_promote")
    assert _tools(plan_a) == _tools(plan_b)


def test_build_returns_fresh_copies_no_mutation_leak():
    """Mutations to one plan's steps must not affect subsequent builds."""
    plan_a = PlanCompiler.build("backtest_only")
    plan_a.steps.clear()          # mutate first plan in-place
    plan_b = PlanCompiler.build("backtest_only")
    assert len(plan_b.steps) == 1, (
        "Mutation of a previously built Plan must not affect PLAN_REGISTRY"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Unknown intent_key → ask_user plan
# ─────────────────────────────────────────────────────────────────────────────

def test_unknown_intent_key_returns_ask_user_plan():
    """build() with an unrecognised key must return the ask_user sentinel plan."""
    plan = PlanCompiler.build("totally_unknown_intent_xyz")
    assert plan.intent_key == "ask_user"
    assert len(plan.steps) == 0, (
        "ask_user sentinel plan must have no steps"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Plan.filter / PlanCompiler.filter
# ─────────────────────────────────────────────────────────────────────────────

def test_filter_removes_specified_tools():
    """filter() must drop steps whose tool is in the skip set."""
    plan     = PlanCompiler.build("tune_and_promote")
    filtered = PlanCompiler.filter(plan, {"validator.validate"})
    tools    = _tools(filtered)
    assert "validator.validate"               not in tools
    assert "tuner.run_multi"                  in tools
    assert "promotion.promote_from_checkpoint" in tools


def test_filter_empty_skip_returns_all_steps():
    plan     = PlanCompiler.build("advise_signal")
    filtered = PlanCompiler.filter(plan, set())
    assert _tools(filtered) == _tools(plan)


def test_filter_all_tools_returns_empty_steps():
    plan  = PlanCompiler.build("backtest_only")
    skip  = {s.tool for s in plan.steps}
    empty = PlanCompiler.filter(plan, skip)
    assert len(empty.steps) == 0


def test_filter_preserves_intent_key():
    plan     = PlanCompiler.build("tune_and_promote")
    filtered = PlanCompiler.filter(plan, {"validator.validate"})
    assert filtered.intent_key == plan.intent_key


# ─────────────────────────────────────────────────────────────────────────────
# PLAN_REGISTRY exhaustiveness
# ─────────────────────────────────────────────────────────────────────────────

_EXPECTED_INTENTS = {
    # Pipeline
    "tune_only", "tune_and_validate", "tune_and_promote",
    "validate_only", "promote_only", "backtest_only", "full_pipeline",
    # Copilot
    "advise_signal", "veto_query", "resize_query",
    # Governance
    "governance_inspect", "governance_propose", "governance_run",
    # Cross-mode
    "audit_inspect",
    # Findings / post-run synthesis
    "findings_synthesize", "findings_recent", "findings_explain",
}


def test_plan_registry_contains_all_expected_intents():
    """PLAN_REGISTRY must register every expected intent exactly once."""
    missing = _EXPECTED_INTENTS - set(PLAN_REGISTRY)
    assert not missing, f"PLAN_REGISTRY missing intents: {missing}"


def test_plan_registry_no_empty_step_lists():
    """Every registered intent must have at least one ToolStep."""
    empty = [k for k, v in PLAN_REGISTRY.items() if not v]
    assert not empty, f"PLAN_REGISTRY intents with no steps: {empty}"


def test_all_registry_tools_are_strings():
    """Every ToolStep.tool value must be a non-empty string."""
    bad = [
        (intent, i, s.tool)
        for intent, steps in PLAN_REGISTRY.items()
        for i, s in enumerate(steps)
        if not isinstance(s.tool, str) or not s.tool
    ]
    assert not bad, f"Non-string or empty tool names found: {bad}"


# ─────────────────────────────────────────────────────────────────────────────
# Findings / post-run synthesis intents
# ─────────────────────────────────────────────────────────────────────────────

def test_findings_synthesize_single_step():
    """findings_synthesize: single step findings.synthesize."""
    plan = PlanCompiler.build("findings_synthesize")
    assert _tools(plan) == ["findings.synthesize"]


def test_findings_recent_default_n():
    """findings_recent: single step findings.list_recent with default n=10."""
    plan = PlanCompiler.build("findings_recent")
    assert _tools(plan) == ["findings.list_recent"]
    step = plan.steps[0]
    assert step.default_args.get("n") == 10, (
        f"findings.list_recent must default n=10, got {step.default_args!r}"
    )


def test_findings_explain_single_step():
    """findings_explain: single step findings.explain."""
    plan = PlanCompiler.build("findings_explain")
    assert _tools(plan) == ["findings.explain"]
