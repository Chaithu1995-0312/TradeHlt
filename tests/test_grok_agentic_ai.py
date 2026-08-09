"""
GrokAgenticAI — multi-agent registry, goals, recipes, OpsDoctor tools.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agent.goal import (
    SuccessCriterion,
    eval_all,
    eval_criterion,
    extract_metrics_from_result,
    merge_metrics,
    Observation,
)
from agent.grok_agentic import (
    INTENT_TO_SPECIALIST,
    PRODUCT_NAME,
    SPECIALISTS,
    build_goal,
    detect_specialist,
    strip_product_prefix,
)
from agent.plan_compiler import PLAN_REGISTRY, PlanCompiler
from agent.recipes.campaign_pipeline import campaign_next_tools, campaign_seed_steps
from agent.recipes.ops_diagnose import ops_seed_steps
from agent.tool_registry import REGISTRY


def test_product_name():
    assert PRODUCT_NAME == "GrokAgenticAI"
    assert "ops_doctor" in SPECIALISTS
    assert "campaign_runner" in SPECIALISTS
    assert "truth_janitor" in SPECIALISTS
    assert SPECIALISTS["ops_doctor"].display_name == "OpsDoctor"
    assert SPECIALISTS["campaign_runner"].display_name == "CampaignRunner"
    assert SPECIALISTS["truth_janitor"].display_name == "TruthJanitor"


def test_strip_ask_prefix():
    assert strip_product_prefix("Ask GrokAgenticAI diagnose BNB").lower().startswith("diagnose")
    assert strip_product_prefix("GrokAgenticAI: campaign for EURUSD").lower().startswith("campaign")
    assert strip_product_prefix("tune only") == "tune only"


def test_detect_specialists():
    assert detect_specialist("Ask GrokAgenticAI OpsDoctor why no trades") == "ops_doctor"
    assert detect_specialist("diagnose throughput drop") == "ops_doctor"
    assert detect_specialist("Ask GrokAgenticAI CampaignRunner tune until") == "campaign_runner"
    assert detect_specialist("run campaign for SOL") == "campaign_runner"
    assert detect_specialist("Ask GrokAgenticAI TruthJanitor hygiene") == "truth_janitor"
    assert detect_specialist("run construction protocol") == "truth_janitor"
    assert detect_specialist("doc drift check") == "truth_janitor"


def test_intent_maps():
    assert INTENT_TO_SPECIALIST["ops_diagnose"] == "ops_doctor"
    assert INTENT_TO_SPECIALIST["campaign_run"] == "campaign_runner"
    assert INTENT_TO_SPECIALIST["truth_janitor"] == "truth_janitor"


def test_build_goal_ops():
    g = build_goal("ops_doctor", "diagnose BNBUSDT", instruments=["BNBUSDT"])
    assert g.agent_name == PRODUCT_NAME
    assert g.specialist == "OpsDoctor"
    assert g.kind == "ops_diagnose"
    assert g.autonomy == "read_only"
    assert g.instruments == ["BNBUSDT"]


def test_criteria_eval():
    m = {"validation.decision": "APPROVE", "incident_pack": True}
    assert eval_criterion(SuccessCriterion("validation.decision", "eq", "APPROVE"), m)
    assert eval_all(
        [SuccessCriterion("incident_pack", "eq", True)],
        m,
    )


def test_plan_registry_has_specialist_seeds():
    assert "ops_diagnose" in PLAN_REGISTRY
    assert "campaign_run" in PLAN_REGISTRY
    assert "truth_janitor" in PLAN_REGISTRY
    ops = [s.tool for s in PlanCompiler.build("ops_diagnose").steps]
    assert ops[0] == "ops.throughput_snapshot"
    assert "ops.incident_pack" in ops
    camp = [s.tool for s in PlanCompiler.build("campaign_run").steps]
    assert camp[0] == "tuner.run_multi"
    assert "validator.validate" in camp
    truth = [s.tool for s in PlanCompiler.build("truth_janitor").steps]
    assert truth[0] == "truth.construction_check"
    assert truth[-1] == "truth.hygiene_pack"


def test_ops_tools_registered_readonly():
    for name in (
        "ops.throughput_snapshot",
        "ops.funnel_diagnose",
        "ops.fail_reasons",
    ):
        assert name in REGISTRY
        assert REGISTRY[name].write is False
    assert REGISTRY["ops.incident_pack"].write is True


def test_truth_tools_registered():
    for name in (
        "truth.construction_check",
        "truth.feature_math_lint",
        "truth.script_census",
        "truth.citation_floor",
    ):
        assert name in REGISTRY
        assert REGISTRY[name].write is False
    assert REGISTRY["truth.hygiene_pack"].write is True


def test_ops_seed_and_campaign_branch():
    steps = ops_seed_steps("BNBUSDT")
    assert len(steps) >= 4
    assert steps[-1].tool == "ops.incident_pack"

    seed = campaign_seed_steps(instruments="EURUSD")
    assert seed[0].tool == "tuner.run_multi"
    nxt = campaign_next_tools(
        "validator.validate",
        {"validation.decision": "REJECT"},
    )
    assert nxt is not None
    assert "tuner.run_multi" in nxt
    assert campaign_next_tools("validator.validate", {"validation.decision": "APPROVE"}) == []


def test_extract_metrics_validation():
    m = extract_metrics_from_result(
        "validator.validate",
        {"decision": "APPROVE", "fitness": 0.4},
    )
    assert m["validation.decision"] == "APPROVE"
    assert m["decision"] == "APPROVE"


def test_merge_observations():
    obs = [
        Observation(0, "ops.throughput_snapshot", "success", {"trade_like_signals": 1}),
        Observation(1, "ops.incident_pack", "success", {"incident_pack": True, "incident_path": "x"}),
    ]
    m = merge_metrics(obs)
    assert m["incident_pack"] is True
    assert m["n_steps"] == 2
    assert m["tools_run"][-1] == "ops.incident_pack"


def test_ops_throughput_handler_smoke():
    """Handler runs without network; returns status ok."""
    fn = REGISTRY["ops.throughput_snapshot"].handler
    out = fn(instrument="BNBUSDT", n=10)
    assert out["status"] == "ok"
    assert "logs" in out


def test_ops_incident_pack_writes_under_results(tmp_path, monkeypatch):
    """Incident pack writes under results/incidents (confirm path tested elsewhere)."""
    import agent.modes.ops_mode as om

    # Redirect repo root for this test to tmp
    monkeypatch.setattr(om, "_REPO", tmp_path)
    (tmp_path / "results").mkdir()
    out = om._incident_pack(instrument="BNBUSDT", notes="test pack", prior_json="{}")
    assert out["status"] == "ok"
    assert out["incident_pack"] is True
    path = tmp_path / out["incident_path"]
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["product"] == "GrokAgenticAI"
    assert payload["specialist"] == "OpsDoctor"


def test_intent_regex_ops_and_campaign():
    from agent.intent_router import IntentRouter

    router = IntentRouter(llm_chat_fn=MagicMock(), use_llm=False)
    r1 = router.classify("Ask GrokAgenticAI diagnose why no trades on BNBUSDT", [])
    assert r1["intent_key"] == "ops_diagnose"
    r2 = router.classify("run campaign for EURUSD", [])
    assert r2["intent_key"] == "campaign_run"
    r3 = router.classify("Ask GrokAgenticAI TruthJanitor run repo hygiene", [])
    assert r3["intent_key"] == "truth_janitor"


def test_build_goal_truth():
    g = build_goal("truth_janitor", "run hygiene")
    assert g.specialist == "TruthJanitor"
    assert g.kind == "truth_janitor"
    assert g.seed_intent == "truth_janitor"


def test_truth_hygiene_pack_writes(tmp_path, monkeypatch):
    import agent.modes.truth_mode as tm

    monkeypatch.setattr(tm, "_REPO", tmp_path)
    (tmp_path / "results").mkdir()
    out = tm._hygiene_pack(notes="p1 test", prior_json='{"passed": true}')
    assert out["status"] == "ok"
    assert out["hygiene_pack"] is True
    assert out["truth.complete"] is True
    path = tmp_path / out["hygiene_path"]
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["specialist"] == "TruthJanitor"
    assert payload["authority"] == "governance_hygiene_only"


def test_truth_seed_recipe():
    from agent.recipes.truth_janitor import truth_seed_steps

    tools = [s.tool for s in truth_seed_steps()]
    assert tools == [
        "truth.construction_check",
        "truth.feature_math_lint",
        "truth.script_census",
        "truth.citation_floor",
        "truth.hygiene_pack",
    ]
