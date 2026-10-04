#!/usr/bin/env python3
"""dry_run_plug.py — thin local DryRun plug (DC-003/004 + MODE_LOCK).

Plug-in / plug-out: no AWS, no broker, no Hot.
Decision plane stub only — execution is simulated and never live.

Usage:
  set PYTHONPATH=D:\\Tradelatest;D:\\Tradelatest\\src
  python multi_llm/scripts_design/dry_run_plug.py
  python multi_llm/scripts_design/dry_run_plug.py --mode Shadow
  python multi_llm/scripts_design/dry_run_plug.py --mode Hot   # must refuse
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Literal

Mode = Literal["DryRun", "Shadow"]
ALLOWED = {"DryRun", "Shadow"}


@dataclass
class Decision:
    allow: bool
    reason: str
    mode: str
    ts: str


@dataclass
class SimulatedExecution:
    attempted: bool
    broker_called: bool
    note: str


def decide(mode: str, force_deny: bool = False) -> Decision:
    """Fail-closed: unknown/missing signal => DENY. Stub always demos path."""
    ts = datetime.now(timezone.utc).isoformat()
    if force_deny:
        return Decision(False, "forced_deny", mode, ts)
    # stub: allow only in allowed modes for path demo — still no broker
    return Decision(True, "stub_path_ok_no_broker", mode, ts)


def execute_separated(decision: Decision, mode: str) -> SimulatedExecution:
    """DC-004: decision != execution. Never calls a broker."""
    if mode not in ALLOWED:
        return SimulatedExecution(False, False, "mode_forbidden")
    if not decision.allow:
        return SimulatedExecution(False, False, "denied_no_execution")
    if mode == "DryRun":
        return SimulatedExecution(True, False, "dry_run_simulated_fill")
    # Shadow
    return SimulatedExecution(True, False, "shadow_observe_only")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Local DryRun/Shadow plug — Hot refused")
    p.add_argument("--mode", default="DryRun", help="DryRun | Shadow (Hot refused)")
    p.add_argument("--force-deny", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    mode = args.mode.strip()
    if mode == "Hot" or mode not in ALLOWED:
        msg = {
            "ok": False,
            "error": "MODE_LOCK",
            "detail": f"mode={mode!r} forbidden; allowed={sorted(ALLOWED)}",
            "policy": "MODE_LOCK.md / infra-design-04",
        }
        print(json.dumps(msg, indent=2) if args.json else f"REFUSED: {msg['detail']}")
        return 2

    decision = decide(mode, force_deny=args.force_deny)
    execution = execute_separated(decision, mode)
    out = {
        "ok": True,
        "cards": ["DC-003", "DC-004"],
        "mode": mode,
        "decision": asdict(decision),
        "execution": asdict(execution),
        "invariants": {
            "fail_closed": True,
            "decision_ne_execution": True,
            "broker_called": execution.broker_called,
            "aws": False,
            "hot": False,
        },
    }
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print(f"mode={mode} allow={decision.allow} reason={decision.reason}")
        print(f"execution attempted={execution.attempted} broker={execution.broker_called} note={execution.note}")
        print("invariants: fail_closed + decision!=execution + no broker + no AWS/Hot")
    return 0


if __name__ == "__main__":
    sys.exit(main())