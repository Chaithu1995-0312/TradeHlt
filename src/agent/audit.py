"""
audit.py
─────────────────────────────────────────────────────────────────────────────
Append-only JSONL audit logger with two output streams:

  logs/agent_audit.jsonl      — per-step tool calls + session summaries
  logs/agent_intent_log.jsonl — session summaries only (feedback loop seed)

Per-step record:
  {ts, session_id, plan_id, step_index, mode, intent_key,
   tool, args_hash, result_hash, write, confirmed, outcome, latency_ms, error}

Session summary record:
  {ts, session_id, plan_id, intent, intent_key, mode, plan_steps,
   outcome, metrics, write_confirmed, total_latency_ms}
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, List, Optional

logger = logging.getLogger("AgentAudit")

_DEFAULT_AUDIT_LOG  = "logs/agent_audit.jsonl"
_DEFAULT_INTENT_LOG = "logs/agent_intent_log.jsonl"


def _sha256_short(obj: Any) -> str:
    canonical = json.dumps(obj, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _append(path: str, record: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


class AuditLogger:
    def __init__(
        self,
        audit_path: str = _DEFAULT_AUDIT_LOG,
        intent_path: str = _DEFAULT_INTENT_LOG,
    ):
        self.audit_path  = audit_path
        self.intent_path = intent_path

    def write_step(
        self,
        *,
        session_id: str,
        plan_id: Optional[str],
        step_index: int,
        mode: Optional[str],
        intent_key: Optional[str],
        tool: str,
        args: dict,
        result: Any,
        write: bool,
        confirmed: Optional[bool],
        outcome: str,
        latency_ms: int,
        error: Optional[str] = None,
    ) -> None:
        record = {
            "ts": _now_iso(),
            "session_id": session_id,
            "plan_id": plan_id,
            "step_index": step_index,
            "mode": mode,
            "intent_key": intent_key,
            "tool": tool,
            "args_hash": _sha256_short(args),
            "result_hash": _sha256_short(result) if result is not None else None,
            "write": write,
            "confirmed": confirmed,
            "outcome": outcome,
            "latency_ms": latency_ms,
            "error": error,
        }
        _append(self.audit_path, record)

    def write_session_summary(
        self,
        *,
        session_id: str,
        plan_id: Optional[str],
        intent: str,
        intent_key: Optional[str],
        mode: Optional[str],
        plan_steps: List[str],
        outcome: str,
        metrics: dict,
        write_confirmed: bool,
        total_latency_ms: int,
    ) -> None:
        record = {
            "ts": _now_iso(),
            "session_id": session_id,
            "plan_id": plan_id,
            "intent": intent,
            "intent_key": intent_key,
            "mode": mode,
            "plan_steps": plan_steps,
            "outcome": outcome,
            "metrics": metrics,
            "write_confirmed": write_confirmed,
            "total_latency_ms": total_latency_ms,
        }
        _append(self.audit_path, record)
        _append(self.intent_path, record)
        logger.debug("Session summary: %s → %s (%dms)", session_id, outcome, total_latency_ms)
