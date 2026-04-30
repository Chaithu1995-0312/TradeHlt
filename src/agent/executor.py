"""
executor.py
─────────────────────────────────────────────────────────────────────────────
Executor — dispatches tool calls from the agent loop.

Safety layers (applied in order):
  1. Allowlist check — tool must be in REGISTRY with allowlist=True, or
     explicitly listed in write_tools_enabled config.
  2. Path guard — write tool args must not reference paths outside the
     allowed write roots (configs/production/, logs/, results/).
  3. Confirm gate — write=True tools return PendingConfirmation until the
     operator responds y/N via the CLI.

Audit records written for every dispatch (success, fail, denied, refused).
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any, List, Optional, Set

logger = logging.getLogger("AgentExecutor")

_WRITE_ROOTS = [
    re.compile(r"^configs[/\\]production[/\\]"),
    re.compile(r"^logs[/\\]"),
    re.compile(r"^results[/\\]"),
]


def _path_allowed(path: str) -> bool:
    return any(p.match(path.replace("\\", "/")) for p in _WRITE_ROOTS)


@dataclass
class PendingConfirmation:
    tool: str
    args: dict
    preview: str


class Executor:
    def __init__(
        self,
        state: Any,
        audit: Any,
        write_tools_enabled: Optional[List[str]] = None,
    ):
        self.state = state
        self.audit = audit
        self._write_enabled: Set[str] = set(write_tools_enabled or [])
        self._step_index = 0

    def dispatch(self, tool_name: str, args: dict, confirmed: bool = False) -> Any:
        """
        Dispatch a tool call.

        Returns:
          - PendingConfirmation  if write=True and not confirmed
          - "REFUSED: <reason>"  if path guard or allowlist blocks
          - tool result (any)    on success
        """
        from agent.tool_registry import REGISTRY
        from agent.state import ToolCall

        if tool_name not in REGISTRY:
            return self._refuse(tool_name, args, f"unknown tool '{tool_name}'")

        spec = REGISTRY[tool_name]

        # 1. Allowlist check for non-default tools
        if not spec.allowlist and tool_name not in self._write_enabled:
            return self._refuse(tool_name, args, "not in write_tools_enabled config")

        # 2. Path guard on write tools
        if spec.write:
            for v in args.values():
                if isinstance(v, str) and ("/" in v or "\\" in v):
                    if not _path_allowed(v):
                        return self._refuse(
                            tool_name, args,
                            f"path '{v}' outside allowed write roots (configs/production/, logs/, results/)"
                        )

        # 3. Confirm gate
        if spec.write and not confirmed:
            preview = (
                f"  Tool   : {spec.name}\n"
                f"  Args   : {args}\n"
                f"  Impact : {spec.description}\n"
                f"  [WRITE — requires confirmation]"
            )
            return PendingConfirmation(tool=tool_name, args=args, preview=preview)

        # 4. Execute
        t0 = time.monotonic()
        result, outcome, error = None, "success", None
        try:
            result = spec.handler(**args)
        except Exception as exc:
            outcome, error = "fail", str(exc)
            logger.error("Tool %s failed: %s", tool_name, exc)
        latency_ms = int((time.monotonic() - t0) * 1000)

        tc = ToolCall(tool=tool_name, args=args, result=result,
                      outcome=outcome, latency_ms=latency_ms, error=error)
        self.state.tool_calls.append(tc)
        self.audit.write_step(
            session_id=self.state.session_id,
            plan_id=self.state.plan_id,
            step_index=self._step_index,
            mode=self.state.mode,
            intent_key=self.state.intent_key,
            tool=tool_name,
            args=args,
            result=result,
            write=spec.write,
            confirmed=confirmed if spec.write else None,
            outcome=outcome,
            latency_ms=latency_ms,
            error=error,
        )
        self._step_index += 1
        return result

    def dispatch_denied(self, tool_name: str, args: dict) -> None:
        """Record a denied write-tool confirmation in state + audit."""
        from agent.tool_registry import REGISTRY
        from agent.state import ToolCall

        spec = REGISTRY.get(tool_name)
        tc = ToolCall(tool=tool_name, args=args, outcome="denied")
        self.state.tool_calls.append(tc)
        self.audit.write_step(
            session_id=self.state.session_id,
            plan_id=self.state.plan_id,
            step_index=self._step_index,
            mode=self.state.mode,
            intent_key=self.state.intent_key,
            tool=tool_name,
            args=args,
            result=None,
            write=True,
            confirmed=False,
            outcome="denied",
            latency_ms=0,
        )
        self._step_index += 1

    def _refuse(self, tool_name: str, args: dict, reason: str) -> str:
        from agent.state import ToolCall
        logger.warning("Refusing '%s': %s", tool_name, reason)
        tc = ToolCall(tool=tool_name, args=args, outcome="refused", error=reason)
        self.state.tool_calls.append(tc)
        self.audit.write_step(
            session_id=self.state.session_id,
            plan_id=self.state.plan_id,
            step_index=self._step_index,
            mode=self.state.mode,
            intent_key=self.state.intent_key,
            tool=tool_name,
            args=args,
            result=None,
            write=True,
            confirmed=False,
            outcome="refused",
            latency_ms=0,
            error=reason,
        )
        self._step_index += 1
        return f"REFUSED: {reason}"
