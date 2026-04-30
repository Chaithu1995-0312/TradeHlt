"""
tool_planner.py — ArgFiller
─────────────────────────────────────────────────────────────────────────────
Uses the LLM to fill missing required args for a single ToolStep.
The LLM is NOT asked to pick tools or decide order — only to extract
parameter values from the conversation context.

LLM response contract:
  {"args": {"param": "value", ...}, "clarify": null}
  {"args": {}, "clarify": "Which instrument should I tune?"}
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("ArgFiller")

_SYSTEM_PROMPT = (
    "You are an argument extractor for a trading automation tool. "
    "Given a tool's required parameters and the recent conversation, "
    "extract or infer the argument values from context. "
    "Respond ONLY with valid JSON: "
    '{\"args\": {\"param\": \"value\"}, \"clarify\": null} '
    "If a required argument cannot be inferred, set clarify to a short question."
)


def _extract_json(text: str) -> Optional[dict]:
    """Extract first balanced JSON object from text. Handles trailing commas."""
    depth, start = 0, -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                fragment = text[start: i + 1]
                try:
                    return json.loads(fragment)
                except json.JSONDecodeError:
                    cleaned = re.sub(r",\s*([}\]])", r"\1", fragment)
                    try:
                        return json.loads(cleaned)
                    except Exception:
                        return None
    return None


class ArgFiller:
    """
    Fills missing required args for a ToolStep via one LLM call.
    If all required args are already present, returns immediately (no LLM call).
    """

    def __init__(self, llm_chat_fn: Callable):
        self._llm_chat = llm_chat_fn

    def fill(
        self,
        tool_name: str,
        args_schema: dict,
        current_args: dict,
        conversation: List[dict],
    ) -> Dict[str, Any]:
        """
        Returns {"args": dict, "clarify": str | None}.
        "args"    : merged current_args + LLM-filled values
        "clarify" : question to surface to user (if LLM can't infer an arg)
        """
        required_missing = [
            k for k, v in args_schema.items()
            if v.get("required") and k not in current_args
        ]
        if not required_missing:
            return {"args": current_args, "clarify": None}

        schema_lines = "\n".join(
            f"  {k}: {v.get('type','any')} — {v.get('desc','')}"
            for k, v in args_schema.items()
            if k in required_missing
        )
        user_msg = (
            f"Tool: {tool_name}\n"
            f"Missing required arguments:\n{schema_lines}\n\n"
            "Extract these from the conversation. "
            'Respond ONLY with JSON: {"args": {...}, "clarify": null}'
        )

        messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
        messages.extend(conversation[-4:])
        messages.append({"role": "user", "content": user_msg})

        raw = self._llm_chat(messages, max_tokens=128, temperature=0.0)
        if not raw:
            logger.warning("ArgFiller: empty LLM response for '%s'", tool_name)
            return {"args": current_args, "clarify": None}

        parsed = _extract_json(raw)
        if not parsed:
            logger.warning("ArgFiller: JSON parse failed for '%s': %s", tool_name, raw[:80])
            return {"args": current_args, "clarify": None}

        merged = {**current_args, **parsed.get("args", {})}
        return {"args": merged, "clarify": parsed.get("clarify")}
