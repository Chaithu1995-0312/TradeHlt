"""
engine_telemetry.py
===================
Structured observability wrapper for all engines.

Two public classes:

EngineTelemetry
    Wraps one engine inference call. Measures latency via a context manager
    (TelemetrySpan), then emits a canonical ENGINE_TELEMETRY event to
    logs/engine_telemetry.jsonl.

DecisionLineage
    Records the causal chain for one execution decision:
      feature snapshot → engine outputs → risk reductions → final decision.
    Writes a single DECISION_LINEAGE event to logs/decision_lineage.jsonl.
    Essential for debugging emergent behaviour: nobody loses the thread of
    why a decision was made even after hundreds of model updates.

All writes use make_event_envelope() from events.event_fabric so every record
carries (event_id, generation, schema_hash, timestamp, parent_event_id).
Writes are fail-open: logging failures are caught and debug-logged, never raised.
"""
from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("EngineTelemetry")

_ENGINE_TELEMETRY_LOG  = Path("logs/engine_telemetry.jsonl")
_DECISION_LINEAGE_LOG  = Path("logs/decision_lineage.jsonl")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _append_jsonl(path: Path, record: dict) -> None:
    """Append one JSON record to a JSONL file. Fail-open (debug-log on error)."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except Exception as exc:
        logger.debug("engine_telemetry: write failed (non-blocking): %s", exc)


def _make_envelope(event_type: str, source: str, payload: dict,
                   instrument: str = "", parent_event_id: str = "") -> dict:
    """Wrap payload in canonical event envelope (fail-open on import error)."""
    try:
        from events.event_fabric import make_event_envelope  # noqa: PLC0415
        return make_event_envelope(
            event_type=event_type,
            instrument=instrument,
            source=source,
            payload=payload,
            parent_event_id=parent_event_id,
        )
    except Exception:
        # Fallback envelope (no generation counter, no schema hash)
        return {
            "event_type":      event_type,
            "source":          source,
            "instrument":      instrument,
            "timestamp":       time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "parent_event_id": parent_event_id,
            "payload":         payload,
        }


# ── TelemetrySpan ─────────────────────────────────────────────────────────────

class TelemetrySpan:
    """Context manager that measures wall-clock latency in milliseconds."""

    def __init__(self) -> None:
        self._start: float = 0.0
        self.latency_ms: float = 0.0

    def __enter__(self) -> "TelemetrySpan":
        self._start = time.monotonic()
        return self

    def __exit__(self, *_: Any) -> None:
        self.latency_ms = (time.monotonic() - self._start) * 1000.0


# ── EngineTelemetry ───────────────────────────────────────────────────────────

class EngineTelemetry:
    """
    Observability wrapper for one engine.

    Usage:
        tel = EngineTelemetry("gaussian")
        with tel.record() as span:
            result = engine.compute(features)
        tel.emit(result, cluster_id=3)

    Parameters
    ----------
    engine_name : str
        Human-readable engine identifier (e.g. "gaussian", "zone_gate", "rr").
    emit_to_log : bool
        If True (default), append to logs/engine_telemetry.jsonl on each emit().
    """

    def __init__(self, engine_name: str, emit_to_log: bool = True) -> None:
        self._name     = engine_name
        self._emit     = emit_to_log
        self._span     = TelemetrySpan()

    @contextmanager
    def record(self):  # type: ignore[override]
        """
        Context manager: wrap engine inference and capture latency.
        latency_ms is available via the yielded span after the block exits.
        """
        span = TelemetrySpan()
        self._span = span
        with span:
            yield span

    def emit(
        self,
        result: dict,
        cluster_id: Optional[int] = None,
        input_summary: Optional[dict] = None,
        failure_mode: Optional[str] = None,
        instrument: str = "",
        parent_event_id: str = "",
    ) -> dict:
        """
        Emit a structured ENGINE_TELEMETRY record.

        Extracts score and confidence from common result-dict conventions.
        Returns the emitted record dict (useful in tests).
        """
        # Score extraction: try several common keys in priority order
        score = float(
            result.get("score",
            result.get("final_score",
            result.get("capital_quality_score",
            result.get("opportunity_score", 0.0))))
        )
        confidence = float(
            result.get("confidence",
            result.get("allocation_confidence",
            result.get("cluster_confidence", 0.0)))
        )

        payload = {
            "engine_name":   self._name,
            "score":         round(score, 4),
            "confidence":    round(confidence, 4),
            "latency_ms":    round(self._span.latency_ms, 2),
            "cluster_id":    cluster_id,
            "failure_mode":  failure_mode or result.get("reason"),
            "input_summary": input_summary or {},
        }

        record = _make_envelope(
            event_type="ENGINE_TELEMETRY",
            source=self._name,
            payload=payload,
            instrument=instrument,
            parent_event_id=parent_event_id,
        )

        if self._emit:
            _append_jsonl(_ENGINE_TELEMETRY_LOG, record)

        return record


# ── DecisionLineage ───────────────────────────────────────────────────────────

class DecisionLineage:
    """
    Causal trace for one execution decision.

    Records the full causal chain:
      feature snapshot → engine outputs → risk reductions → final decision.
    Written as a single DECISION_LINEAGE event to logs/decision_lineage.jsonl.

    Usage:
        lineage = DecisionLineage(decision_id="a1b2c3", instrument="ETHUSDT")
        lineage.set_features(feature_dict)
        lineage.add_engine("gaussian", gaussian_result)
        lineage.add_engine("zone",     zone_result)
        lineage.add_engine("rr",       rr_result)
        lineage.set_decision("ACCEPT", risk_reduction=0.0, reason="all gates passed")
        lineage.flush()  # writes one JSON line to logs/decision_lineage.jsonl

    Parameters
    ----------
    decision_id  : str — short unique id for this decision cycle
    instrument   : str — instrument symbol (e.g. "ETHUSDT")
    parent_event_id : str — event_id of the DECISION_SNAPSHOT that spawned this
    """

    def __init__(
        self,
        decision_id: str,
        instrument: str = "",
        parent_event_id: str = "",
    ) -> None:
        self._id             = decision_id
        self._instrument     = instrument
        self._parent_ev_id   = parent_event_id
        self._ts             = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        self._features: dict = {}
        self._engines:  list = []
        self._decision       = ""
        self._risk_reduction = 0.0
        self._reason         = ""

    def set_features(self, features: dict) -> None:
        """Store a numeric-only snapshot of the feature dict (for lineage audit)."""
        self._features = {
            k: round(float(v), 6)
            for k, v in features.items()
            if isinstance(v, (int, float))
        }

    def add_engine(self, name: str, result: dict) -> None:
        """Append one engine's output summary to the causal chain."""
        self._engines.append({
            "engine": name,
            "score":  float(
                result.get("score",
                result.get("final_score",
                result.get("capital_quality_score", 0.0)))
            ),
            "passed": bool(result.get("passed", True)),
            "reason": str(result.get("reason", result.get("reject_reason", ""))),
        })

    def set_decision(
        self,
        decision: str,
        risk_reduction: float = 0.0,
        reason: str = "",
    ) -> None:
        """Record the final decision and any risk reduction applied."""
        self._decision       = decision
        self._risk_reduction = risk_reduction
        self._reason         = reason

    def flush(self) -> None:
        """
        Write causal lineage record to logs/decision_lineage.jsonl.
        Fail-open: exceptions are debug-logged and swallowed.
        """
        payload = {
            "decision_id":      self._id,
            "feature_snapshot": self._features,
            "engine_outputs":   self._engines,
            "decision":         self._decision,
            "risk_reduction":   self._risk_reduction,
            "reason":           self._reason,
        }
        record = _make_envelope(
            event_type="DECISION_LINEAGE",
            source="DecisionLineage",
            payload=payload,
            instrument=self._instrument,
            parent_event_id=self._parent_ev_id,
        )
        _append_jsonl(_DECISION_LINEAGE_LOG, record)
