"""
integrity_events.py
===================
Canonical integrity-event telemetry spine.

Single public function ``emit_integrity_event`` appends a machine-readable
JSON record to ``logs/integrity_events.jsonl``. Used across the trading
system to make corruption, schema drift, and fail-closed branches visible
without breaking runtime.

Contract
--------
- Append-only JSONL at logs/integrity_events.jsonl
- One JSON object per line: {ts, event, severity, source, payload}
- NEVER raises — logging failure falls back to stderr print, then is swallowed
- No dependency on event_fabric — kept intentionally lighter than
  engine_telemetry.py so it can be imported from any layer (including
  scripts/) without pulling in optional infra.

Severity levels
---------------
INFO     — observability / lifecycle
WARNING  — recoverable integrity issue (e.g. unknown session, legacy schema)
ERROR    — non-recoverable for the current operation (e.g. incomplete trade)
CRITICAL — system-wide invariant violation (e.g. feature_dim mismatch)
"""
from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

_LOG_PATH = Path("logs/integrity_events.jsonl")
_logger = logging.getLogger("IntegrityEvents")


class Severity:
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


_VALID_SEVERITIES = {Severity.INFO, Severity.WARNING, Severity.ERROR, Severity.CRITICAL}


def emit_integrity_event(
    event_type: str,
    severity: str,
    source: str,
    payload: dict,
) -> None:
    """Append one integrity event to logs/integrity_events.jsonl.

    Parameters
    ----------
    event_type : str
        Canonical event name (e.g. "REPLAY_MISMATCH", "JSONL_CORRUPTION").
    severity : str
        One of INFO / WARNING / ERROR / CRITICAL. Unknown values are coerced to WARNING.
    source : str
        Short identifier of the emitting module (e.g. "trade_replay_validator").
    payload : dict
        Arbitrary JSON-serializable detail. Non-dicts are wrapped as {"raw": str(...)}.

    Notes
    -----
    This function NEVER raises. If JSONL append fails (disk full, permission
    denied, etc.) the failure is debug-logged and falls back to stderr.
    """
    try:
        sev = severity if severity in _VALID_SEVERITIES else Severity.WARNING
        if not isinstance(payload, dict):
            payload = {"raw": str(payload)}
        record = {
            "ts":       time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event":    str(event_type),
            "severity": sev,
            "source":   str(source),
            "payload":  payload,
        }
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str, ensure_ascii=False) + "\n")
    except Exception as exc:  # noqa: BLE001
        try:
            _logger.debug("integrity_events: write failed: %s", exc)
            print(
                f"[integrity_events:FALLBACK] {event_type} {severity} {source} {payload}",
                file=sys.stderr,
            )
        except Exception:
            pass


__all__ = ["emit_integrity_event", "Severity"]
