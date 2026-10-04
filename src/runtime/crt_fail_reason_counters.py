"""
CRT try_* fail-reason counters — OBSERVATION_ONLY.

Default-off. Implements the same record_guard interface as baseline trace hooks
so existing StateMachine._trace_guard call sites feed counts without re-evaluating
guards or altering control flow.

TASK_CLASS = OBSERVATION_ONLY
(see docs/governance/TASK_CLASSIFICATION_BEHAVIOR_POLICY.md)
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class CRTFailReasonCounters:
    """Aggregate pass/fail counts for instrumented CRT guards.

    Attach to CRTEngine via::

        counters = CRTFailReasonCounters()
        engine.baseline_trace = counters   # duck-typed; only record_guard used
        counters.enabled = True

    Or set ``engine.sm.trace_hooks = counters`` with ``enabled=True`` around
    process_candle (process_candle will overwrite sm.trace_hooks from baseline_trace
    when baseline_trace is set and enabled).
    """

    enabled: bool = False
    # (guard_id, failure_reason|PASS) -> count
    counts: Counter = field(default_factory=Counter)
    # (from_state, candidate_to_state, failure_reason|PASS) -> count
    edge_counts: Counter = field(default_factory=Counter)
    evaluations: int = 0
    warnings: list[str] = field(default_factory=list)

    # Compatibility with CRTBaselineTraceHooks fields used by process_candle
    state_before: Optional[str] = None
    state_after: Optional[str] = None
    snapshot_before: dict = field(default_factory=dict)
    snapshot_after: dict = field(default_factory=dict)
    action: dict = field(default_factory=dict)
    events_at_start: int = 0
    guards: list = field(default_factory=list)
    crt_inputs: list = field(default_factory=list)
    config_reads: list = field(default_factory=list)
    exceptions: list = field(default_factory=list)

    def reset_bar(self) -> None:
        """No per-bar reset of aggregates — counters are run-level."""
        self.state_before = None
        self.state_after = None
        self.action = {}

    def record_guard(
        self,
        *,
        guard_id: str,
        guard_name: str = "",
        source_location: str = "",
        from_state: str = "",
        candidate_to_state: str = "",
        result: bool = False,
        operator: str = "",
        operands: Optional[list] = None,
        thresholds: Optional[list] = None,
        short_circuit_status: str = "NONE",
        failure_reason: Optional[str] = None,
        **_: Any,
    ) -> None:
        if not self.enabled:
            return
        try:
            self.evaluations += 1
            key_reason = "PASS" if result else (failure_reason or "UNKNOWN_FAIL")
            self.counts[(guard_id, key_reason)] += 1
            self.edge_counts[(from_state, candidate_to_state, key_reason)] += 1
        except Exception as exc:  # never alter engine path
            self.warnings.append(f"record_guard_failed:{exc}")

    def as_dict(self) -> dict:
        by_guard: dict[str, dict[str, int]] = {}
        for (gid, reason), n in sorted(self.counts.items()):
            by_guard.setdefault(gid, {})[reason] = n
        by_edge: dict[str, dict[str, int]] = {}
        for (fr, to, reason), n in sorted(self.edge_counts.items()):
            ek = f"{fr}->{to}"
            by_edge.setdefault(ek, {})[reason] = n
        return {
            "enabled": self.enabled,
            "evaluations": self.evaluations,
            "by_guard_id": by_guard,
            "by_edge": by_edge,
            "raw_counts": [
                {"guard_id": g, "reason": r, "count": n}
                for (g, r), n in sorted(self.counts.items(), key=lambda x: (-x[1], x[0]))
            ],
            "warnings": list(self.warnings),
        }
