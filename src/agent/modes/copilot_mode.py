"""
copilot_mode.py — Live Signal Co-pilot tool registrations
─────────────────────────────────────────────────────────────────────────────
All tools in this mode are read-only. The copilot NEVER places or cancels
trades. UltronRiskGate remains the final pre-execution authority.

Tools: engine.run, fusion.explain, planner.plan, risk.check,
       advise.veto, advise.resize, collector.tail
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from ..tool_registry import register_tool

logger = logging.getLogger("CopilotMode")


# ── engine.run ─────────────────────────────────────────────────────────────────

@register_tool(
    name="engine.run",
    description="Run the CRT engine stack (CRT+Gaussian+ZoneGate+RR) on a feature dict. Returns EngineRunnerResult.",
    write=False,
    args_schema={
        "instrument": {"type": "str", "required": True,  "desc": "Trading instrument"},
        "features":   {"type": "str", "required": False, "desc": "JSON feature dict (uses last cached state if omitted)"},
    },
)
def _engine_run(instrument: str, features: str = "") -> dict:
    try:
        from core.engine_runner import EngineRunner
        from config_layer.production_config import get_prod_config
        cfg    = get_prod_config(instrument)
        runner = EngineRunner(cfg)
        feat   = json.loads(features) if features else {}
        result = runner.run(feat, context={"instrument": instrument})
        return result if isinstance(result, dict) else {"status": "ok", "result": str(result)}
    except Exception as exc:
        logger.error("engine.run: %s", exc)
        return {"status": "error", "error": str(exc)}


# ── fusion.explain ─────────────────────────────────────────────────────────────

@register_tool(
    name="fusion.explain",
    description="Return per-component scores and fusion result for the last engine run.",
    write=False,
    args_schema={
        "instrument": {"type": "str", "required": True,  "desc": "Trading instrument"},
        "engine_result": {"type": "str", "required": False, "desc": "JSON engine result (uses last if omitted)"},
    },
)
def _fusion_explain(instrument: str, engine_result: str = "") -> dict:
    try:
        from core.fusion_engine import FusionEngine
        from config_layer.production_config import get_prod_config
        cfg    = get_prod_config(instrument)
        fe     = FusionEngine(cfg)
        er     = json.loads(engine_result) if engine_result else {}
        result = fe.compute(er, cfg) if hasattr(fe, "compute") else {}
        return result if isinstance(result, dict) else {"status": "ok", "fusion": str(result)}
    except Exception as exc:
        logger.error("fusion.explain: %s", exc)
        return {"status": "error", "error": str(exc)}


# ── planner.plan ───────────────────────────────────────────────────────────────

@register_tool(
    name="planner.plan",
    description="Generate a trade plan (entry, SL, TP, RR, TTL) from a decision signal.",
    write=False,
    args_schema={
        "instrument":    {"type": "str",  "required": True,  "desc": "Trading instrument"},
        "decision_json": {"type": "str",  "required": False, "desc": "JSON decision dict"},
        "features_json": {"type": "str",  "required": False, "desc": "JSON feature dict"},
    },
)
def _planner_plan(instrument: str, decision_json: str = "", features_json: str = "") -> dict:
    try:
        from config_layer.execution_planner import ExecutionPlannerV1_2
        from config_layer.production_config import get_prod_config
        cfg      = get_prod_config(instrument)
        decision = json.loads(decision_json) if decision_json else {}
        features = json.loads(features_json) if features_json else {}
        planner  = ExecutionPlannerV1_2(cfg)
        plan     = planner.plan(decision, features, cfg)
        return plan if isinstance(plan, dict) else {"status": "ok", "plan": str(plan)}
    except Exception as exc:
        logger.error("planner.plan: %s", exc)
        return {"status": "error", "error": str(exc)}


# ── risk.check ─────────────────────────────────────────────────────────────────

@register_tool(
    name="risk.check",
    description="Run UltronRiskGate on a candidate trade. Returns gate decision dict.",
    write=False,
    args_schema={
        "instrument":  {"type": "str", "required": True,  "desc": "Trading instrument"},
        "trade_json":  {"type": "str", "required": False, "desc": "JSON trade plan dict"},
    },
)
def _risk_check(instrument: str, trade_json: str = "") -> dict:
    try:
        from core.ultron_risk_gate import UltronRiskGate
        from config_layer.production_config import get_prod_config
        cfg   = get_prod_config(instrument)
        gate  = UltronRiskGate(cfg)
        trade = json.loads(trade_json) if trade_json else {}
        result = gate.check_trade(trade) if hasattr(gate, "check_trade") else {}
        return result if isinstance(result, dict) else {"status": "ok"}
    except Exception as exc:
        logger.error("risk.check: %s", exc)
        return {"status": "error", "error": str(exc)}


# ── advise.veto ────────────────────────────────────────────────────────────────

@register_tool(
    name="advise.veto",
    description="Agent-internal: LLM reasons over component scores and returns TAKE|VETO|RESIZE advice.",
    write=False,
    args_schema={
        "scores_json":  {"type": "str", "required": True, "desc": "JSON dict with crt, gaussian, zone_gate, rr, fusion scores"},
        "instrument":   {"type": "str", "required": False, "desc": "Instrument name (for context)"},
    },
)
def _advise_veto(scores_json: str, instrument: str = "") -> dict:
    try:
        from config_layer.llama_gate import llm_chat
        scores = json.loads(scores_json)
        scores_text = "\n".join(f"  {k}: {v}" for k, v in scores.items())
        messages = [
            {
                "role": "system",
                "content": (
                    "You are the CRT signal co-pilot. You only advise — you never trade.\n"
                    "Review the component scores and identify the weakest element.\n"
                    "Output ONLY JSON: "
                    '{"action": "TAKE|VETO|RESIZE", "factor": <0.0-1.5>, '
                    '"why": "<≤25 words explaining the decision>"}'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Instrument: {instrument or 'unknown'}\n"
                    f"Component scores:\n{scores_text}\n\n"
                    "What is your advice?"
                ),
            },
        ]
        raw = llm_chat(messages, max_tokens=128, temperature=0.3)
        from agent.tool_planner import _extract_json
        parsed = _extract_json(raw) if raw else None
        if parsed:
            return {
                "action": parsed.get("action", "TAKE"),
                "factor": float(parsed.get("factor", 1.0)),
                "why":    parsed.get("why", ""),
            }
        return {"action": "TAKE", "factor": 1.0, "why": "LLM unavailable — defaulting to TAKE"}
    except Exception as exc:
        logger.error("advise.veto: %s", exc)
        return {"action": "TAKE", "factor": 1.0, "why": f"error: {exc}"}


# ── advise.resize ──────────────────────────────────────────────────────────────

@register_tool(
    name="advise.resize",
    description="Suggest a position size multiplier [0.0, 1.5] based on fusion scores. Advisory only.",
    write=False,
    args_schema={
        "scores_json": {"type": "str", "required": True, "desc": "JSON dict with fusion and component scores"},
    },
)
def _advise_resize(scores_json: str) -> dict:
    try:
        scores = json.loads(scores_json)
        fusion = float(scores.get("fusion", scores.get("final_score", 0.5)))
        # Simple heuristic: scale factor by fusion quality
        if fusion >= 0.75:
            factor = 1.0
        elif fusion >= 0.6:
            factor = 0.75
        elif fusion >= 0.5:
            factor = 0.5
        else:
            factor = 0.0
        return {
            "suggested_factor": factor,
            "fusion_score": fusion,
            "note": "Apply multiplier to base position size. Operator applies manually.",
        }
    except Exception as exc:
        return {"suggested_factor": 0.5, "error": str(exc)}


# ── collector.tail ─────────────────────────────────────────────────────────────

@register_tool(
    name="collector.tail",
    description="Return the last N lines from logs/collector.jsonl as a list of dicts.",
    write=False,
    args_schema={
        "n": {"type": "int", "required": False, "desc": "Number of lines (default: 20)"},
    },
)
def _collector_tail(n: int = 20) -> dict:
    try:
        log_path = Path("logs/collector.jsonl")
        if not log_path.exists():
            return {"status": "ok", "lines": [], "note": "collector.jsonl not found"}
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
