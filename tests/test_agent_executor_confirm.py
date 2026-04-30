"""
test_agent_executor_confirm.py
==============================
Tests for src/agent/executor.py — confirm gate, path guard, allowlist.

API contract (actual executor.py):
  Executor(state, audit, write_tools_enabled=[])
  dispatch(tool_name: str, args: dict, confirmed: bool = False) -> Any
    Returns:
      PendingConfirmation  — write tool, not yet confirmed
      "REFUSED: <reason>"  — path guard, allowlist, or unknown tool
      tool result (any)    — success
  dispatch_denied(tool_name, args)  — records denied confirmation in state + audit

PendingConfirmation fields: .tool (str), .args (dict), .preview (str)
State confirmation: state.pending_confirmations list of {"tool": ..., "confirmed": True/False}
"""

import pytest
from unittest.mock import patch, MagicMock

from agent.executor import Executor, PendingConfirmation
from agent.state import AgentState
from agent.tool_registry import REGISTRY


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def _executor(write_tools_enabled=None):
    """Create an Executor with a fresh AgentState and a mock audit logger."""
    state = AgentState()
    audit = MagicMock()   # write_step() called by dispatch — mock absorbs all calls
    return Executor(state, audit, write_tools_enabled=write_tools_enabled or []), state, audit


# ─────────────────────────────────────────────────────────────────────────────
# 1. Read (non-write) tool runs inline without confirmation
# ─────────────────────────────────────────────────────────────────────────────

def test_read_tool_runs_inline():
    """Non-write tool (allowlist=True, write=False) must execute and return result."""
    executor, state, audit = _executor()

    original_handler = REGISTRY["backtest.run_v2"].handler
    REGISTRY["backtest.run_v2"].handler = lambda **kw: {"trades": 42}
    try:
        result = executor.dispatch(
            "backtest.run_v2",
            {"csv_path": "x.csv", "config_path": "y.json"},
        )
    finally:
        REGISTRY["backtest.run_v2"].handler = original_handler

    assert not isinstance(result, PendingConfirmation), (
        "Non-write tool must not return PendingConfirmation"
    )
    assert not (isinstance(result, str) and result.startswith("REFUSED:")), (
        "Non-write tool must not be refused"
    )
    assert result == {"trades": 42}


# ─────────────────────────────────────────────────────────────────────────────
# 2. Write tool without prior confirmation returns PendingConfirmation
# ─────────────────────────────────────────────────────────────────────────────

def test_write_tool_returns_pending_without_confirm():
    """Write tool dispatched without confirmed=True must return PendingConfirmation."""
    executor, state, _ = _executor(write_tools_enabled=["live_hook.enable"])

    result = executor.dispatch(
        "live_hook.enable",
        {"config_path": "configs/production/x.json"},
        confirmed=False,
    )

    assert isinstance(result, PendingConfirmation), (
        f"Expected PendingConfirmation, got {type(result).__name__}: {result!r}"
    )
    assert result.tool == "live_hook.enable"
    assert result.args == {"config_path": "configs/production/x.json"}


# ─────────────────────────────────────────────────────────────────────────────
# 3. Write tool executes after confirmed=True
# ─────────────────────────────────────────────────────────────────────────────

def test_write_tool_executes_after_confirm():
    """Write tool dispatched with confirmed=True must execute and return result."""
    executor, state, _ = _executor(write_tools_enabled=["live_hook.enable"])
    tool_name = "live_hook.enable"
    args      = {"config_path": "configs/production/x.json"}

    original = REGISTRY[tool_name].handler
    REGISTRY[tool_name].handler = lambda **kw: {"live_toggle": True}
    try:
        result = executor.dispatch(tool_name, args, confirmed=True)
    finally:
        REGISTRY[tool_name].handler = original

    assert not isinstance(result, PendingConfirmation)
    assert not (isinstance(result, str) and result.startswith("REFUSED:"))
    assert result == {"live_toggle": True}


# ─────────────────────────────────────────────────────────────────────────────
# 4. Write tool with path outside allowed roots is refused
# ─────────────────────────────────────────────────────────────────────────────

def test_path_outside_allowlist_refused():
    """
    Write tool with a path referencing src/ (outside configs/production/, logs/,
    results/) must be refused — even with confirmed=True.
    """
    executor, state, _ = _executor(write_tools_enabled=["live_hook.enable"])

    result = executor.dispatch(
        "live_hook.enable",
        {"config_path": "src/core/engine_runner.py"},
        confirmed=True,
    )

    assert isinstance(result, str), (
        f"Expected REFUSED string, got {type(result).__name__}: {result!r}"
    )
    assert result.startswith("REFUSED:"), (
        f"Expected 'REFUSED: ...' message, got: {result!r}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 5. Unknown tool is refused
# ─────────────────────────────────────────────────────────────────────────────

def test_unknown_tool_refused():
    """Tool name not in REGISTRY must be refused."""
    executor, state, _ = _executor()

    result = executor.dispatch("nonexistent.tool", {})

    assert isinstance(result, str)
    assert result.startswith("REFUSED:")
    assert "unknown tool" in result.lower() or "unknown" in result.lower()


# ─────────────────────────────────────────────────────────────────────────────
# 6. dispatch_denied records a denied entry in state.tool_calls
# ─────────────────────────────────────────────────────────────────────────────

def test_dispatch_denied_records_audit():
    """dispatch_denied must append a 'denied' ToolCall to state.tool_calls."""
    executor, state, audit = _executor(write_tools_enabled=["live_hook.enable"])
    tool_name = "live_hook.enable"
    args      = {"config_path": "configs/production/x.json"}

    executor.dispatch_denied(tool_name, args)

    assert len(state.tool_calls) == 1, (
        f"Expected 1 ToolCall after dispatch_denied, got {len(state.tool_calls)}"
    )
    tc = state.tool_calls[0]
    assert tc.tool    == tool_name
    assert tc.outcome == "denied"
    # audit.write_step must have been called
    audit.write_step.assert_called_once()
