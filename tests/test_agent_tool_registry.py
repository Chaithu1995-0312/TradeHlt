"""Tests for src/agent/tool_registry.py"""
import pytest
from agent.tool_registry import REGISTRY, register_tool, get_schema_text, ToolSpec


def test_all_pipeline_tools_registered():
    expected = [
        "tuner.run_multi", "validator.validate", "promotion.promote_from_checkpoint",
        "backtest.run_v2", "live_hook.dry_run", "live_hook.enable",
    ]
    for tool in expected:
        assert tool in REGISTRY, f"Missing pipeline tool: {tool}"


def test_all_copilot_tools_registered():
    expected = ["engine.run", "fusion.explain", "planner.plan", "risk.check",
                "advise.veto", "advise.resize", "collector.tail"]
    for tool in expected:
        assert tool in REGISTRY, f"Missing copilot tool: {tool}"


def test_all_governance_tools_registered():
    expected = ["governance.run_loop", "reflection.load_merge", "reflection.generate_prompt",
                "meta_governor.dry_run", "shadow.stage_candidate", "audit.tail"]
    for tool in expected:
        assert tool in REGISTRY, f"Missing governance tool: {tool}"


def test_write_tools_correctly_flagged():
    write_tools = ["tuner.run_multi", "promotion.promote_from_checkpoint",
                   "live_hook.enable", "governance.run_loop"]
    for t in write_tools:
        assert REGISTRY[t].write is True, f"{t} should be write=True"

    read_tools = ["validator.validate", "backtest.run_v2", "engine.run",
                  "fusion.explain", "advise.veto", "reflection.load_merge"]
    for t in read_tools:
        assert REGISTRY[t].write is False, f"{t} should be write=False"


def test_tool_schema_text_generates():
    schema = get_schema_text()
    assert "tuner.run_multi" in schema
    assert "validator.validate" in schema


def test_register_tool_decorator():
    """Dynamic registration via decorator."""
    @register_tool(name="test.temp_tool", write=False, description="temp")
    def _temp():
        return "ok"

    assert "test.temp_tool" in REGISTRY
    spec = REGISTRY["test.temp_tool"]
    assert spec.write is False
    assert spec.description == "temp"
    assert spec.handler() == "ok"

    # Cleanup
    del REGISTRY["test.temp_tool"]


def test_toolspec_has_required_fields():
    """Every ToolSpec must expose name, description, write, allowlist, handler, args_schema."""
    spec = REGISTRY["validator.validate"]
    assert isinstance(spec.name,        str)  and spec.name
    assert isinstance(spec.description, str)
    assert isinstance(spec.write,       bool)
    assert isinstance(spec.allowlist,   bool)
    assert callable(spec.handler)
    assert isinstance(spec.args_schema, dict)