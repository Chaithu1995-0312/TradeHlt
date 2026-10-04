"""
governance_mode.py — Governance Meta-reasoner tool registrations
─────────────────────────────────────────────────────────────────────────────
Tools: governance.run_loop, reflection.load_merge, reflection.generate_prompt,
       meta_governor.dry_run, shadow.stage_candidate, audit.tail

Only governance.run_loop is write=True (may promote via ShadowPromotionGate).
All others are read-only or write to scratch files only.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from ..tool_registry import register_tool

logger = logging.getLogger("GovernanceMode")


# ── reflection.load_merge ──────────────────────────────────────────────────────

@register_tool(
    name="reflection.load_merge",
    description="Load and merge collector.jsonl + trades CSV into a reflection dataset. Returns row count.",
    write=False,
    args_schema={
        "collector_log": {"type": "str", "required": False, "desc": "Path to collector.jsonl (default: logs/collector.jsonl)"},
        "trades_csv":    {"type": "str", "required": False, "desc": "Path to trades CSV (default: logs/trades.csv)"},
    },
)
def _reflection_load_merge(
    collector_log: str = "logs/collector.jsonl",
    trades_csv: str = "logs/trades.csv",
) -> dict:
    try:
        from governance.reflection_buffer_advanced import ReflectionBuffer
        rb   = ReflectionBuffer()
        rows = rb.load_and_merge(collector_log=collector_log, trades_csv=trades_csv)
        count = len(rows) if hasattr(rows, "__len__") else -1
        return {"status": "ok", "rows": count}
    except Exception as exc:
        logger.error("reflection.load_merge: %s", exc)
        return {"status": "error", "error": str(exc)}


# ── reflection.generate_prompt ─────────────────────────────────────────────────

@register_tool(
    name="reflection.generate_prompt",
    description="Generate meta-governor prompt from reflection data. Writes logs/meta_prompt.txt (scratch).",
    write=False,
    args_schema={
        "collector_log": {"type": "str", "required": False, "desc": "Path to collector.jsonl"},
        "trades_csv":    {"type": "str", "required": False, "desc": "Path to trades CSV"},
    },
)
def _reflection_generate_prompt(
    collector_log: str = "logs/collector.jsonl",
    trades_csv: str = "logs/trades.csv",
) -> dict:
    try:
        from governance.reflection_buffer_advanced import ReflectionBuffer
        rb = ReflectionBuffer()
        rb.load_and_merge(collector_log=collector_log, trades_csv=trades_csv)
        prompt = rb.generate_prompt_payload() if hasattr(rb, "generate_prompt_payload") else ""
        Path("logs/meta_prompt.txt").write_text(str(prompt))
        return {"status": "ok", "prompt_length": len(str(prompt))}
    except Exception as exc:
        logger.error("reflection.generate_prompt: %s", exc)
        return {"status": "error", "error": str(exc)}


# ── meta_governor.dry_run ──────────────────────────────────────────────────────

@register_tool(
    name="meta_governor.dry_run",
    description="Run MetaGovernorExecutor inference and preview proposed config patch (no write).",
    write=False,
    args_schema={
        "collector_log": {"type": "str", "required": False, "desc": "Path to collector.jsonl"},
        "trades_csv":    {"type": "str", "required": False, "desc": "Path to trades CSV"},
    },
)
def _meta_governor_dry_run(
    collector_log: str = "logs/collector.jsonl",
    trades_csv: str = "logs/trades.csv",
) -> dict:
    try:
        from governance.bitnet_governance_executor import MetaGovernorExecutor
        from governance.reflection_buffer_advanced import ReflectionBuffer
        rb = ReflectionBuffer()
        rb.load_and_merge(collector_log=collector_log, trades_csv=trades_csv)
        prompt = rb.generate_prompt_payload() if hasattr(rb, "generate_prompt_payload") else ""
        mge    = MetaGovernorExecutor()
        raw    = mge.run_inference(str(prompt)) if hasattr(mge, "run_inference") else ""
        patch  = mge.extract_and_validate_config(raw) if hasattr(mge, "extract_and_validate_config") else {}
        return {"status": "ok", "proposed_patch": patch, "raw_preview": str(raw)[:300]}
    except Exception as exc:
        logger.error("meta_governor.dry_run: %s", exc)
        return {"status": "error", "error": str(exc)}


# ── shadow.stage_candidate ─────────────────────────────────────────────────────

@register_tool(
    name="shadow.stage_candidate",
    description="Stage a config patch in ShadowPromotionGate for shadow validation (writes candidate.json scratch — no prod mutation).",
    write=False,
    args_schema={
        "patch_json": {"type": "str", "required": True, "desc": "JSON dict of config param changes to stage"},
    },
)
def _shadow_stage(patch_json: str) -> dict:
    try:
        patch = json.loads(patch_json)
        from governance.shadow_promotion_gate import ShadowPromotionGate
        gate = ShadowPromotionGate()
        result = gate.stage_candidate(patch) if hasattr(gate, "stage_candidate") else {}
        return result if isinstance(result, dict) else {"status": "ok", "patch": patch}
    except Exception as exc:
        logger.error("shadow.stage_candidate: %s", exc)
        return {"status": "error", "error": str(exc)}


# ── governance.run_loop ─────────────────────────────────────────────────────────

@register_tool(
    name="governance.run_loop",
    description="Run the full governance loop (reflection → meta-governor → shadow validate → conditional promotion). WRITE — may promote config.",
    write=True,
    args_schema={
        "collector_log": {"type": "str", "required": False, "desc": "Path to collector.jsonl"},
        "trades_csv":    {"type": "str", "required": False, "desc": "Path to trades CSV"},
        "baseline_pnl":  {"type": "float", "required": False, "desc": "Baseline PnL threshold for promotion gate"},
    },
)
def _governance_run_loop(
    collector_log: str = "logs/collector.jsonl",
    trades_csv: str = "logs/trades.csv",
    baseline_pnl: float = 0.0,
) -> dict:
    try:
        from governance.orchestrator import GovernanceOrchestrator
        orch   = GovernanceOrchestrator()
        result = orch.run(
            collector_log=collector_log,
            trades_csv=trades_csv,
            baseline_pnl=baseline_pnl,
        ) if hasattr(orch, "run") else {}
        return result if isinstance(result, dict) else {"status": "ok"}
    except Exception as exc:
        logger.error("governance.run_loop: %s", exc)
        return {"status": "error", "error": str(exc)}


# ── audit.tail ─────────────────────────────────────────────────────────────────

@register_tool(
    name="audit.tail",
    description="Return the last N entries from logs/governance_audit.jsonl.",
    write=False,
    args_schema={
        "n": {"type": "int", "required": False, "desc": "Number of lines (default: 20)"},
    },
)
def _audit_tail(n: int = 20) -> dict:
    try:
        log_path = Path("logs/governance_audit.jsonl")
        if not log_path.exists():
            return {"status": "ok", "lines": [], "note": "governance_audit.jsonl not found"}
        with open(log_path) as f:
            lines = f.readlines()
        tail = []
        for line in lines[-n:]:
            try:
                tail.append(json.loads(line))
            except json.JSONDecodeError:
                tail.append({"raw": line.strip()})
        return {"status": "ok", "count": len(tail), "lines": tail}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
