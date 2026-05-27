"""
findings_mode.py — Post-run findings tool registrations
─────────────────────────────────────────────────────────────────────────────
Tools: findings.synthesize, findings.list_recent, findings.explain

These wrap ``agent.findings_synthesizer`` and append-to-JSONL writes are
path-guarded by Executor (logs/ root is whitelisted in executor.py).

findings.synthesize is write=True because it appends a new line to
logs/agent_findings.jsonl, so it inherits the confirm-gate just like
every other write tool in pipeline_mode.
"""

from __future__ import annotations

import logging

from ..tool_registry import register_tool

logger = logging.getLogger("FindingsMode")


# ── findings.synthesize ──────────────────────────────────────────────────────

@register_tool(
    name="findings.synthesize",
    description="Synthesize a Groq-backed finding for one CRT run. Appends logs/agent_findings.jsonl.",
    write=True,
    args_schema={
        "run_id": {"type": "str", "required": True, "desc": "Run ID (8+ hex chars) from logs/control_plane or results/{INSTR}/"},
    },
)
def _findings_synthesize(run_id: str) -> dict:
    from agent.findings_synthesizer import synthesize_finding
    return synthesize_finding(run_id)


# ── findings.list_recent ─────────────────────────────────────────────────────

@register_tool(
    name="findings.list_recent",
    description="Return the most recent N findings (read-only). Default N=10.",
    write=False,
    args_schema={
        "n": {"type": "int", "required": False, "desc": "Number of findings to return (default 10, max 200)"},
    },
)
def _findings_list_recent(n: int = 10) -> list[dict]:
    from agent.findings_synthesizer import list_recent
    n = max(1, min(int(n or 10), 200))
    return list_recent(limit=n)


# ── findings.explain ─────────────────────────────────────────────────────────

@register_tool(
    name="findings.explain",
    description="Return the latest finding for one run_id (read-only).",
    write=False,
    args_schema={
        "run_id": {"type": "str", "required": True, "desc": "Run ID prefix (>=8 chars)"},
    },
)
def _findings_explain(run_id: str) -> dict | None:
    from agent.findings_synthesizer import explain
    return explain(run_id)
