"""
audit — append-only lifecycle chain (Phase 6.5).

Persists run/verification summaries to `audit/*.jsonl` (never mutated), mirroring the
repo's `promotion_log.jsonl` discipline. Gives the analytics layer its own audit trail
without touching MT5 truth. Payloads are the `to_audit_dict()` of `RunSummary` /
`VerificationReport` — designed for exactly this, so no transformation is needed.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

from ..analytics_config import _require, load_config
from utils.jsonl_writer import append_jsonl  # type: ignore

# kind -> audit file
_FILES = {
    "rebuild_run": "rebuild_runs.jsonl",
    "daemon_event": "daemon_events.jsonl",
    "verification_run": "verification_runs.jsonl",
    "coverage_run": "coverage_runs.jsonl",
}


def append_audit(kind: str, payload: dict, *, cfg: "dict | None" = None) -> dict:
    """Append `{timestamp_utc, kind, **payload}` to the audit file for `kind`."""
    cfg = cfg or load_config()
    audit_root = Path(str(_require(cfg, "audit_root")))
    fname = _FILES.get(kind, f"{kind}.jsonl")
    line = {
        "timestamp_utc": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "kind": kind,
        **payload,
    }
    append_jsonl(audit_root / fname, line)
    return line
