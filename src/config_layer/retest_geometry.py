"""retest_geometry.py — the ONE EXPANSION->RETEST geometry test (STORY-83.11a).

Extracted from ``StateMachine.try_expansion_to_retest`` (crt_engine_v2.py) so the CRT engine and
the CRTStateResolver call the same rule instead of each holding a copy. User rule 2026-09-28:
reusing an authority is correct when the meaning matches; only a second copy is a defect. The
resolver's RETEST node declares this meaning ("This is the CRT engine's EXPANSION->RETEST
transition point", market_crt_states.yaml).

The test, from EXPANSION with an active range:
  * depth_abs = LONG ``close - l_ref`` / otherwise ``h_ref - close``   (distance from the swept edge)
  * depth_abs >= retest_min_depth_atr_fraction * atr                    ([IC-007] floor)
  * depth_abs <= max(retest_depth_max * range_size, retest_atr_depth_fraction * atr)   ([PATCH 5])
  * FM-028 displacement_atr_ratio <= max_displacement_strength          ([PATCH 7]; skipped when the
    displacement candle range is unknown or atr <= 0, exactly as the engine skips it)

Pure: no state, no I/O, no side effects. Callers own tracing/telemetry. The FM-028 ratio goes
through the registered callable (features.fm_resolve), the same identity the engine uses.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from features.fm_resolve import bind_phase2_crt_callables

_FM028 = bind_phase2_crt_callables()["FM-028"]

#: Failure reasons — the engine's existing trace ``failure_reason`` strings, unchanged.
FAIL_DEPTH_BELOW_MIN = "depth_below_min"
FAIL_DEPTH_ABOVE_CEILING = "depth_above_ceiling"
FAIL_OVEREXTENDED_DISPLACEMENT = "overextended_displacement"


@dataclass(frozen=True)
class RetestGeometry:
    depth_abs: float
    min_depth: float
    static_ceiling: float
    atr_ceiling: float
    adaptive_ceiling: float
    displacement_atr_ratio: Optional[float]   # None = strength check skipped (engine semantics)
    failure_reason: Optional[str]             # None = retest geometry passes

    @property
    def passed(self) -> bool:
        return self.failure_reason is None


def evaluate_retest_geometry(
    *,
    is_long: bool,
    close: float,
    h_ref: float,
    l_ref: float,
    atr: float,
    displacement_range: Optional[float],
    displacement_atr: float,
    retest_depth_max: float,
    retest_atr_depth_fraction: float,
    retest_min_depth_atr_fraction: float,
    max_displacement_strength: float,
) -> RetestGeometry:
    """Evaluate the EXPANSION->RETEST geometry. Checks run in the engine's order.

    ``atr`` drives the depth band; ``displacement_atr`` drives the FM-028 ratio. The engine passes
    ``state.atr_abs`` for both (its only call site passes ``self.state.atr_abs`` as ``atr``), kept
    as two arguments so the extraction cannot change which value feeds which check.
    """
    static_ceiling = retest_depth_max * (h_ref - l_ref)
    atr_ceiling = retest_atr_depth_fraction * atr if atr > 0 else static_ceiling
    adaptive_ceiling = max(static_ceiling, atr_ceiling)
    depth_abs = (close - l_ref) if is_long else (h_ref - close)
    min_depth = retest_min_depth_atr_fraction * atr if atr > 0 else 0.0

    ratio: Optional[float] = None
    if displacement_range is not None and displacement_atr > 0:
        ratio = _FM028(displacement_range, displacement_atr)

    if depth_abs < min_depth:
        reason: Optional[str] = FAIL_DEPTH_BELOW_MIN
    elif depth_abs > adaptive_ceiling:
        reason = FAIL_DEPTH_ABOVE_CEILING
    elif ratio is not None and ratio > max_displacement_strength:
        reason = FAIL_OVEREXTENDED_DISPLACEMENT
    else:
        reason = None

    return RetestGeometry(
        depth_abs=depth_abs,
        min_depth=min_depth,
        static_ceiling=static_ceiling,
        atr_ceiling=atr_ceiling,
        adaptive_ceiling=adaptive_ceiling,
        displacement_atr_ratio=ratio,
        failure_reason=reason,
    )
