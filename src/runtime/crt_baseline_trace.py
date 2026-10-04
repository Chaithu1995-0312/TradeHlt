"""
crt_baseline_trace.py — optional, behavior-preserving CRT baseline observation.

Default-off. When disabled / hooks is None, CRT takes no extra work beyond a
single attribute check at instrumented points.

Does NOT recompute features, re-evaluate guards, or mutate CRT control flow.
Authority: research/governance observation only (§6.5).
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

TRACE_SCHEMA_VERSION = "1.0.0"


def _jsonable(v: Any) -> Any:
    if v is None or isinstance(v, (str, int, bool)):
        return v
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return {"__nonfinite__": True, "repr": repr(v)}
        return v
    if hasattr(v, "name"):  # Enum
        try:
            return v.name
        except Exception:
            pass
    if hasattr(v, "isoformat"):
        try:
            return v.isoformat()
        except Exception:
            pass
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _jsonable(val) for k, val in v.items()}
    if dataclasses.is_dataclass(v) and not isinstance(v, type):
        return _jsonable(asdict(v))
    return repr(v)


@dataclass
class OperandRec:
    name: str
    runtime_value: Any
    source_class: str
    source_name: str
    source_location: str
    feature_id: Optional[str] = None
    formula_id: Optional[str] = None
    config_key: Optional[str] = None
    provenance_status: str = "PROVEN"


@dataclass
class ThresholdRec:
    name: str
    runtime_value: Any
    config_key: Optional[str]
    config_source: str
    read_location: str


@dataclass
class GuardRec:
    evaluation_order: int
    guard_id: str
    guard_name: str
    source_location: str
    from_state: str
    candidate_to_state: str
    operands: list[OperandRec] = field(default_factory=list)
    operator: str = ""
    thresholds: list[ThresholdRec] = field(default_factory=list)
    result: bool = False
    short_circuit_status: str = "NONE"
    failure_reason: Optional[str] = None


class CRTBaselineTraceHooks:
    """Attached to CRTEngine / StateMachine when tracing is active for a bar."""

    def __init__(self) -> None:
        self.enabled: bool = False
        self._guard_order: int = 0
        self.guards: list[GuardRec] = []
        self.events_at_start: int = 0
        self.state_before: Optional[str] = None
        self.state_after: Optional[str] = None
        self.snapshot_before: dict = {}
        self.snapshot_after: dict = {}
        self.action: dict = {}
        self.crt_inputs: list[dict] = []
        self.config_reads: list[dict] = []
        self.warnings: list[str] = []
        self.exceptions: list[str] = []

    def reset_bar(self) -> None:
        self._guard_order = 0
        self.guards = []
        self.crt_inputs = []
        self.config_reads = []
        self.warnings = []
        self.exceptions = []
        self.state_before = None
        self.state_after = None
        self.snapshot_before = {}
        self.snapshot_after = {}
        self.action = {}

    def record_guard(
        self,
        *,
        guard_id: str,
        guard_name: str,
        source_location: str,
        from_state: str,
        candidate_to_state: str,
        result: bool,
        operator: str = "",
        operands: Optional[list[dict]] = None,
        thresholds: Optional[list[dict]] = None,
        short_circuit_status: str = "NONE",
        failure_reason: Optional[str] = None,
    ) -> None:
        if not self.enabled:
            return
        self._guard_order += 1
        ops = [
            OperandRec(**{**o, "runtime_value": _jsonable(o.get("runtime_value"))})
            if isinstance(o, dict)
            else o
            for o in (operands or [])
        ]
        ths = [
            ThresholdRec(**{**t, "runtime_value": _jsonable(t.get("runtime_value"))})
            if isinstance(t, dict)
            else t
            for t in (thresholds or [])
        ]
        self.guards.append(
            GuardRec(
                evaluation_order=self._guard_order,
                guard_id=guard_id,
                guard_name=guard_name,
                source_location=source_location,
                from_state=from_state,
                candidate_to_state=candidate_to_state,
                operands=ops,  # type: ignore[arg-type]
                operator=operator,
                thresholds=ths,  # type: ignore[arg-type]
                result=result,
                short_circuit_status=short_circuit_status,
                failure_reason=failure_reason,
            )
        )
        # collect inputs/config from operands/thresholds
        for o in operands or []:
            if not isinstance(o, dict):
                continue
            self.crt_inputs.append(
                {
                    "name": o.get("name"),
                    "runtime_value": _jsonable(o.get("runtime_value")),
                    "source_class": o.get("source_class"),
                    "source_name": o.get("source_name"),
                    "source_location": o.get("source_location"),
                    "formula_id": o.get("formula_id"),
                    "feature_id": o.get("feature_id"),
                    "config_key": o.get("config_key"),
                    "provenance_status": o.get("provenance_status", "PROVEN"),
                }
            )
        for t in thresholds or []:
            if not isinstance(t, dict):
                continue
            self.config_reads.append(
                {
                    "config_key": t.get("config_key"),
                    "effective_value": _jsonable(t.get("runtime_value")),
                    "name": t.get("name"),
                    "config_source": t.get("config_source"),
                    "read_location": t.get("read_location"),
                }
            )


def snapshot_engine_state(state: Any) -> dict:
    """Minimal authoritative CRT state surface for reconstruction."""
    cs = getattr(state, "current_state", None)
    se = getattr(state, "sweep_event", None)
    ar = getattr(state, "active_range", None)
    dc = getattr(state, "displacement_candle", None)
    rc = getattr(state, "retest_candle", None)
    return {
        "current_state": cs.name if cs is not None else None,
        "current_candle_index": getattr(state, "current_candle_index", None),
        # Direct access, no getattr default: atr_abs is a non-optional field, so a default
        # could only mask a rename. ABSOLUTE atr (NOT the close-relative FM-041 `atr`).
        "atr": state.atr_abs,
        "direction": getattr(getattr(state, "direction", None), "name", None)
        or getattr(getattr(state, "direction", None), "value", None),
        "ema_fast_val": getattr(state, "ema_fast_val", None),
        "ema_slow_val": getattr(state, "ema_slow_val", None),
        "evaluating_soft_conf": getattr(state, "evaluating_soft_conf", None),
        "soft_conf_candles": getattr(state, "soft_conf_candles", None),
        "cached_features": dict(getattr(state, "cached_features", None) or {}),
        "sweep_event": None
        if se is None
        else {
            "price": getattr(se, "price", None),
            "direction": getattr(getattr(se, "direction", None), "value", None),
            "candle_index": getattr(se, "candle_index", None),
            "double_confirmed": getattr(se, "double_confirmed", None),
        },
        "active_range": None
        if ar is None
        else {
            "h_ref": getattr(ar, "h_ref", None),
            "l_ref": getattr(ar, "l_ref", None),
            "size": getattr(ar, "size", None),
            "session": getattr(ar, "session", None),
            "htf_candle_id": getattr(ar, "htf_candle_id", None),
        },
        "displacement_candle_index": getattr(dc, "index", None) if dc is not None else None,
        "retest_candle_index": getattr(rc, "index", None) if rc is not None else None,
        "_displacement_entry_idx": getattr(state, "_displacement_entry_idx", None),
        "_expansion_entry_idx": getattr(state, "_expansion_entry_idx", None),
        "_came_from_shadow": getattr(state, "_came_from_shadow", None),
        "pending_displacement_ttl": getattr(state, "pending_displacement_ttl", None),
        "active_trade": None
        if not getattr(state, "active_trade", None)
        else {
            "id": getattr(state.active_trade, "id", None),
            "status": getattr(state.active_trade, "status", None),
            "direction": getattr(getattr(state.active_trade, "direction", None), "value", None),
        },
        "transition_log_len": len(getattr(state, "transition_log", None) or []),
    }


def build_bar_record(
    *,
    identity: dict,
    raw_bar: dict,
    canonical_features: dict,
    hooks: CRTBaselineTraceHooks,
    effective_config: dict,
    events_emitted: list,
    output_classification: str,
) -> dict:
    guards = []
    for g in hooks.guards:
        guards.append(
            {
                "evaluation_order": g.evaluation_order,
                "guard_id": g.guard_id,
                "guard_name": g.guard_name,
                "source_location": g.source_location,
                "from_state": g.from_state,
                "candidate_to_state": g.candidate_to_state,
                "operands": [asdict(o) if dataclasses.is_dataclass(o) else o for o in g.operands],
                "operator": g.operator,
                "thresholds": [asdict(t) if dataclasses.is_dataclass(t) else t for t in g.thresholds],
                "result": g.result,
                "short_circuit_status": g.short_circuit_status,
                "failure_reason": g.failure_reason,
            }
        )

    true_guards = [g for g in guards if g.get("result") is True]
    selected = None
    transition_selected = False
    if hooks.state_before != hooks.state_after:
        transition_selected = True
        selected = {
            "transition_selected": True,
            "from_state": hooks.state_before,
            "to_state": hooks.state_after,
            "selection_location": "CRTEngine.process_candle / StateMachine",
            "winning_guard_id": true_guards[-1]["guard_id"] if true_guards else None,
            "selection_reason": (hooks.action or {}).get("action"),
        }
    else:
        selected = {
            "transition_selected": False,
            "from_state": hooks.state_before,
            "to_state": hooks.state_after,
            "selection_location": "CRTEngine.process_candle",
            "winning_guard_id": None,
            "selection_reason": (hooks.action or {}).get("action"),
        }

    missing = []
    for k, ok in [
        ("raw_bar", bool(raw_bar)),
        ("canonical_features", bool(canonical_features.get("feature_count") == 38)),
        ("state_before", hooks.state_before is not None),
        ("state_after", hooks.state_after is not None),
    ]:
        if not ok:
            missing.append(k)

    nonfinite = []
    vals = canonical_features.get("values_by_name") or {}
    for name, v in vals.items():
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            nonfinite.append(name)
        if isinstance(v, dict) and v.get("__nonfinite__"):
            nonfinite.append(name)

    status = "COMPLETE"
    if missing or nonfinite:
        status = "PARTIAL"
    if hooks.exceptions:
        status = "FAILED"

    unknown_prov = [
        i for i in hooks.crt_inputs if i.get("provenance_status") == "UNKNOWN"
    ]

    return {
        "trace_identity": identity,
        "raw_bar": raw_bar,
        "canonical_features": canonical_features,
        "crt_inputs": {"inputs": hooks.crt_inputs},
        "effective_config": effective_config,
        "state_transition": {
            "state_before": hooks.state_before,
            "state_after": hooks.state_after,
            "state_changed": hooks.state_before != hooks.state_after,
            "persistent_state_snapshot_before": hooks.snapshot_before,
            "persistent_state_snapshot_after": hooks.snapshot_after,
            "guards_evaluated": guards,
            "selected_transition": selected,
            "action": hooks.action,
        },
        "outputs": {
            "returned_value": hooks.action,
            "events_emitted": events_emitted,
            "trade_output": (hooks.snapshot_after or {}).get("active_trade"),
            "rejection": None
            if "REJECT" not in str((hooks.action or {}).get("action", "")).upper()
            and "FILTER" not in str((hooks.action or {}).get("action", "")).upper()
            else hooks.action,
            "diversion": None
            if (hooks.action or {}).get("action") not in ("RESET", "SWEEP_EXPIRED", "SHADOW_LEAK", "EXPANSION_EXPIRED")
            else hooks.action,
            "output_classification": output_classification,
        },
        "integrity": {
            "trace_complete": status == "COMPLETE",
            "raw_bar_complete": "raw_bar" not in missing,
            "canonical_feature_complete": "canonical_features" not in missing,
            "canonical_feature_count": canonical_features.get("feature_count"),
            "crt_input_provenance_complete": len(unknown_prov) == 0,
            "effective_config_complete": bool(effective_config),
            "state_before_captured": hooks.state_before is not None,
            "guards_complete": True,  # all observed evaluation points recorded
            "state_after_captured": hooks.state_after is not None,
            "outputs_complete": bool(hooks.action is not None),
            "missing_fields": missing,
            "unknown_provenance": unknown_prov,
            "nonfinite_features": nonfinite,
            "exceptions": hooks.exceptions,
            "warnings": hooks.warnings,
            "status": status,
            "evaluated_guard_count": len(guards),
            "true_guard_count": len(true_guards),
        },
    }


def classify_output(action: dict) -> str:
    a = str((action or {}).get("action") or "NONE")
    if a == "NONE":
        return "NO_OUTPUT"
    if "TRADE_OPENED" in a or a.startswith("TRADE_"):
        if "OPENED" in a:
            return "TRADE_OPENED"
        return "TRADE_EVENT"
    if "REJECT" in a or a == "FILTER_REJECTED":
        return "REJECTED"
    if a in ("RESET", "SWEEP_EXPIRED", "SHADOW_LEAK", "EXPANSION_EXPIRED", "EXPANSION_TTL_RESET"):
        return "DIVERTED"
    if a in (
        "SWEEP_DETECTED",
        "DISPLACEMENT_CONFIRMED",
        "EXPANSION_CONFIRMED",
        "RETEST_CONFIRMED",
        "SHADOW_SWEEP_DETECTED",
        "SHADOW_EXPANSION_CONFIRMED",
        "BEGIN_SOFT_CONF",
    ):
        return "TRADE_CANDIDATE" if "RETEST" in a or "DISPLACEMENT" in a or "EXPANSION" in a else "STATE_EVENT"
    return "STATE_EVENT"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_meta(root: Path) -> dict:
    import subprocess

    def run(args: list[str]) -> str:
        try:
            r = subprocess.run(args, cwd=str(root), capture_output=True, text=True, check=True)
            return r.stdout.strip()
        except Exception:
            return "UNKNOWN"

    commit = run(["git", "rev-parse", "HEAD"])
    dirty = run(["git", "status", "--porcelain"])
    return {
        "repository_commit": commit,
        "dirty_worktree_status": "DIRTY" if dirty else "CLEAN",
        "dirty_worktree_detail_lines": len(dirty.splitlines()) if dirty and dirty != "UNKNOWN" else 0,
    }
