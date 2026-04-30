"""
state.py
─────────────────────────────────────────────────────────────────────────────
AgentState — conversation memory, tool call log, pending confirmations.
Persisted to logs/agent_sessions/<session_id>.json after every turn.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional


def _new_session_id() -> str:
    ts = int(time.time() * 1000)
    return f"ses_{ts}"


@dataclass
class ToolCall:
    tool: str
    args: dict
    result: Any = None
    outcome: str = "pending"    # pending | success | fail | denied | refused
    latency_ms: int = 0
    error: Optional[str] = None


@dataclass
class AgentState:
    session_id: str = field(default_factory=_new_session_id)
    mode: Optional[Literal["pipeline", "copilot", "governance"]] = None
    intent_key: Optional[str] = None
    plan_id: Optional[str] = None
    messages: List[Dict[str, str]] = field(default_factory=list)
    tool_calls: List[ToolCall] = field(default_factory=list)
    pending_confirmations: List[dict] = field(default_factory=list)
    mode_context: Dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})

    def confirmed(self, tool_name: str) -> bool:
        """True if this tool was confirmed in the current turn."""
        return any(
            c.get("tool") == tool_name and c.get("confirmed")
            for c in self.pending_confirmations
        )

    def save(self, session_dir: str = "logs/agent_sessions") -> None:
        Path(session_dir).mkdir(parents=True, exist_ok=True)
        path = Path(session_dir) / f"{self.session_id}.json"
        with open(path, "w") as f:
            json.dump(self._to_dict(), f, indent=2, default=str)

    @classmethod
    def load(cls, session_id: str, session_dir: str = "logs/agent_sessions") -> "AgentState":
        path = Path(session_dir) / f"{session_id}.json"
        with open(path) as f:
            data = json.load(f)
        state = cls(session_id=data["session_id"])
        state.mode = data.get("mode")
        state.intent_key = data.get("intent_key")
        state.plan_id = data.get("plan_id")
        state.messages = data.get("messages", [])
        state.tool_calls = [ToolCall(**tc) for tc in data.get("tool_calls", [])]
        state.pending_confirmations = data.get("pending_confirmations", [])
        state.mode_context = data.get("mode_context", {})
        return state

    def _to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "mode": self.mode,
            "intent_key": self.intent_key,
            "plan_id": self.plan_id,
            "messages": self.messages,
            "tool_calls": [
                {
                    "tool": tc.tool,
                    "args": tc.args,
                    "outcome": tc.outcome,
                    "latency_ms": tc.latency_ms,
                    "error": tc.error,
                }
                for tc in self.tool_calls
            ],
            "pending_confirmations": self.pending_confirmations,
            "mode_context": self.mode_context,
        }
