"""
intent_router.py
─────────────────────────────────────────────────────────────────────────────
IntentRouter — classifies NL input into {mode, intent_key, confidence}.

Classification order:
  1. Regex patterns from intent_patterns.json (fast, deterministic)
  2. LLM classification via llm_chat if regex confidence < floor
  3. Falls back to intent_key="ask_user" if neither succeeds

The LLM only picks intent_key — it never selects tools or execution order.
That is PlanCompiler's job.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .tool_planner import _extract_json

logger = logging.getLogger("IntentRouter")

# intent_key → [mode, [regex patterns]]  (loaded from intent_patterns.json)
_PATTERNS_PATH = "src/agent/prompts/intent_patterns.json"

# All valid intent keys per mode (for LLM classifier prompt)
_MODE_INTENTS: Dict[str, List[str]] = {
    "pipeline": [
        "tune_only", "tune_and_validate", "tune_and_promote",
        "validate_only", "promote_only", "backtest_only", "full_pipeline",
    ],
    "copilot": ["advise_signal", "veto_query", "resize_query"],
    "governance": ["governance_inspect", "governance_propose", "governance_run"],
    "cross": ["audit_inspect"],
}

_ALL_INTENT_KEYS = [k for keys in _MODE_INTENTS.values() for k in keys]

_LLM_SYSTEM = (
    "You are an intent classifier for a CRT trading automation agent.\n"
    "Map the user's request to exactly ONE intent_key from this list:\n"
    "{INTENT_LIST}\n"
    "  ask_user: cannot classify\n\n"
    'Respond ONLY with JSON: {"intent_key": "<key>", "confidence": <0.0-1.0>}'
)


class IntentRouter:
    def __init__(
        self,
        llm_chat_fn: Callable,
        patterns_path: str = _PATTERNS_PATH,
        use_llm: bool = True,
        confidence_floor: float = 0.6,
    ):
        self._llm_chat = llm_chat_fn
        self._use_llm = use_llm
        self._floor = confidence_floor
        self._patterns: dict = {}
        self._load_patterns(patterns_path)

    def _load_patterns(self, path: str) -> None:
        try:
            with open(path) as f:
                self._patterns = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            logger.warning("IntentRouter: cannot load patterns (%s) — regex disabled", exc)

    def classify(self, user_input: str, conversation: List[dict]) -> dict:
        """
        Returns: {"mode": str | None, "intent_key": str, "confidence": float}
        intent_key == "ask_user" means unclassified.
        """
        # 1. Regex (no LLM)
        result = self._regex_classify(user_input)
        if result and result["confidence"] >= self._floor:
            logger.debug("regex → %s (%.2f)", result["intent_key"], result["confidence"])
            return result

        # 2. LLM
        if self._use_llm:
            result = self._llm_classify(user_input, conversation)
            if result and result["confidence"] >= self._floor:
                logger.debug("llm → %s (%.2f)", result["intent_key"], result["confidence"])
                return result

        return {"mode": None, "intent_key": "ask_user", "confidence": 0.0}

    def _regex_classify(self, text: str) -> Optional[dict]:
        import re
        text_lower = text.lower()
        for intent_key, entry in self._patterns.items():
            mode = entry.get("mode")
            for pattern in entry.get("patterns", []):
                if re.search(pattern, text_lower):
                    return {"mode": mode, "intent_key": intent_key, "confidence": 0.85}
        return None

    def _llm_classify(self, user_input: str, conversation: List[dict]) -> Optional[dict]:
        intent_list = "\n".join(f"  {k}" for k in _ALL_INTENT_KEYS)
        system = _LLM_SYSTEM.replace("{INTENT_LIST}", intent_list)

        messages = [{"role": "system", "content": system}]
        messages.extend(conversation[-2:])
        messages.append({"role": "user", "content": user_input})

        from config_layer.llama_gate import llm_chat
        raw = llm_chat(messages, max_tokens=64, temperature=0.0)
        if not raw:
            return None

        parsed = _extract_json(raw)
        if not parsed:
            return None

        intent_key = parsed.get("intent_key", "ask_user")
        if intent_key not in _ALL_INTENT_KEYS and intent_key != "ask_user":
            logger.warning("LLM returned unknown intent_key '%s', using ask_user", intent_key)
            intent_key = "ask_user"

        confidence = float(parsed.get("confidence", 0.5))
        mode = next(
            (m for m, keys in _MODE_INTENTS.items() if intent_key in keys),
            None
        )
        if mode == "cross":
            mode = None

        return {"mode": mode, "intent_key": intent_key, "confidence": confidence}
