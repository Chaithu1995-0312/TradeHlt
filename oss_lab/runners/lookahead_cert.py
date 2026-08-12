"""Lookahead certification design + scaffold.

Design (Phase 8): future-mutation test.

  Run A: original data
  Run B: identical data through time T; different data after T

Require features[T], states[T], context[T], shape[T], CRT[T], testimony[T],
decision[T], entry[T] identical. If future mutation changes any pre-T output:
LOOKAHEAD = FAIL; record first divergent timestamp and object.

This module implements the *protocol object* and a pure-function probe helper
for adapters that can emit bar-indexed snapshots. Full CRT/feature re-run is
NOT wired here — reuse existing production/research paths when authorized.

Do not accept documentation claims as proof.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Optional, Sequence


@dataclass
class LookaheadProbeResult:
    status: str  # PASS | FAIL | NOT_RUN | UNKNOWN
    cut_timestamp: Optional[str] = None
    first_divergent_timestamp: Optional[str] = None
    first_divergent_object: Optional[str] = None
    compared_objects: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    authority: str = "RESEARCH_LAB_ONLY"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Objects that must remain identical for all t <= T under future mutation.
DEFAULT_OBJECTS = (
    "features",
    "states",
    "context",
    "shape",
    "crt",
    "testimony",
    "decision",
    "entry",
)


def compare_snapshots(
    run_a: Sequence[dict[str, Any]],
    run_b: Sequence[dict[str, Any]],
    *,
    cut_timestamp: str,
    timestamp_key: str = "timestamp",
    objects: Sequence[str] = DEFAULT_OBJECTS,
) -> LookaheadProbeResult:
    """Compare bar snapshots for all rows with timestamp <= cut.

    Each snapshot is a dict with timestamp_key and optional object keys.
    Values compared with == (JSON-serializable equality).
    """
    by_a = {str(r[timestamp_key]): r for r in run_a if timestamp_key in r}
    by_b = {str(r[timestamp_key]): r for r in run_b if timestamp_key in r}
    # Only rows at or before cut
    keys = sorted(k for k in by_a if k <= cut_timestamp)
    compared: list[str] = []
    for ts in keys:
        if ts not in by_b:
            return LookaheadProbeResult(
                status="FAIL",
                cut_timestamp=cut_timestamp,
                first_divergent_timestamp=ts,
                first_divergent_object="row_missing_in_run_b",
                compared_objects=compared,
                notes=["row present in A missing in B before cut"],
            )
        a, b = by_a[ts], by_b[ts]
        for obj in objects:
            if obj not in a and obj not in b:
                continue
            compared.append(f"{ts}:{obj}")
            if a.get(obj) != b.get(obj):
                return LookaheadProbeResult(
                    status="FAIL",
                    cut_timestamp=cut_timestamp,
                    first_divergent_timestamp=ts,
                    first_divergent_object=obj,
                    compared_objects=compared,
                    notes=["future mutation changed pre-cut output"],
                )
    return LookaheadProbeResult(
        status="PASS",
        cut_timestamp=cut_timestamp,
        compared_objects=compared,
        notes=["all pre-cut objects identical under future mutation"],
    )


def not_run(reason: str) -> LookaheadProbeResult:
    return LookaheadProbeResult(status="NOT_RUN", notes=[reason])
