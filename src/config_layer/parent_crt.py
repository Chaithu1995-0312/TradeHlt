"""parent_crt.py — CH-htfcrt-parent-candle-smc-v1 (2026-08-15, user-authorized): the
parent-timeframe 3-candle CRT construct.

Classifies a stream of CALENDAR-TRUE parent candles (from
`features.parent_candle.ParentCandleBuilder`, any of H4/D1/W1/MN1) into the 3-candle CRT
narrative:

    C1 (RANGE_C1)         — the reference parent candle; its own high/low become h_ref/l_ref.
    C2 (MANIPULATION_C2)  — sweeps C1's boundary and closes back inside (parent-scale sweep).
    C3 (DISTRIBUTION_C3)  — a directional impulse away from the swept side, confirming C2's
                             sweep was a real manipulation and not noise.

Uses the NEW `CRTState` members added by this same program (`state_identity.py`) and their
DISJOINT `VALID_TRANSITIONS` sub-graph:

    RANGE_C1        -> [MANIPULATION_C2, RANGE_C1]
    MANIPULATION_C2 -> [DISTRIBUTION_C3, RANGE_C1]
    DISTRIBUTION_C3 -> [RANGE_C1]

`ParentCRTTrack.on_parent_close` consumes exactly ONE newly-closed parent candle per call and
advances the sub-graph by exactly one edge — either the forward edge (sweep found / impulse
confirmed) or the reset self-loop/back-edge (RANGE_C1 self-loop, or back to RANGE_C1 from C2/C3)
— which is what makes this a genuine, VALID_TRANSITIONS-conformant state machine rather than a
batch re-classification of a 3-candle window. On every reset, the just-arrived candle becomes
the NEW C1 (a rolling reference), never a stale one.

ISOLATION (why the geometry is REIMPLEMENTED, not imported, from crt_engine_v2's
RangeDetector.detect_sweep / StateMachine.try_sweep_to_displacement's directional contract):
mirrors the `research.weekly_sweep.weekly_range` precedent — this module tests the SAME
boundary-cross-then-close-back-inside sweep geometry and the SAME F-074 directional-impulse
contract, but against a PARENT-scale range, not the M15 execution range. Reimplementing keeps
this module a pure, independently-testable classifier that cannot be silently perturbed by an
unrelated M15-engine change, and keeps the M15 engine free of any parent-timeframe coupling
beyond the single defaulted `parent_state` keyword on `CRTEngine.process_candle`.

NO-LOOKAHEAD: `on_parent_close` only ever receives a candle the caller already knows is CLOSED
(the caller is expected to be driven off `ParentCandleBuilder.push()`'s return value, exactly
as `HTFBuilder`/`ParentCandleBuilder` already guarantee). This module holds no independent
clock and never peeks ahead.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from config_layer.state_identity import CRTState, Direction
# SK-1 (2026-08-19): SP-001/SP-002 single implementation. The parent-scale FOUNDING
# (ParentRange, below) stays local — only the arithmetic is shared.
from structure.predicates import (
    directional_impulse as _directional_impulse,
    swept_high as _swept_high,
    swept_low as _swept_low,
)

if TYPE_CHECKING:
    from config_layer.crt_engine_v2 import Candle


@dataclass(frozen=True)
class ParentRange:
    """The reference range formed by the current C1 parent candle."""

    h_ref: float
    l_ref: float
    formed_at_index: int   # C1 candle's own .index


@dataclass(frozen=True)
class ParentSweepEvent:
    """A detected boundary-cross-then-close-back-inside sweep of a `ParentRange` (the C2
    "manipulation" candle)."""

    direction: Direction   # LONG (low swept) or SHORT (high swept)
    price: float
    candle_index: int


class ParentCRTTrack:
    """Streams closed parent candles and classifies them into RANGE_C1 / MANIPULATION_C2 /
    DISTRIBUTION_C3. One instance per parent timeframe (H4, D1, W1, MN1 — each timeframe's
    3-candle narrative is independent; do not share one instance across timeframes)."""

    def __init__(self) -> None:
        self._state: CRTState = CRTState.RANGE_C1
        self._range: Optional[ParentRange] = None
        self._sweep: Optional[ParentSweepEvent] = None

    @property
    def state(self) -> CRTState:
        return self._state

    @property
    def range(self) -> Optional[ParentRange]:
        return self._range

    @property
    def sweep(self) -> Optional[ParentSweepEvent]:
        return self._sweep

    @property
    def bias(self) -> Direction:
        """The parent-CRT's directional bias for the M15 bridge (`process_candle`'s
        `parent_state` keyword). NONE unless DISTRIBUTION_C3 has actually been reached — a
        MANIPULATION_C2 sweep alone does not set a bias. A swept range is not a confirmed
        narrative until the impulse away from it has also confirmed (F-074 at parent scale).
        Distinct from Stage-3 ObjectiveStatus (htf_state.py)."""
        if self._state == CRTState.DISTRIBUTION_C3 and self._sweep is not None:
            return self._sweep.direction
        return Direction.NONE

    def on_parent_close(self, parent: "Candle") -> CRTState:
        """Feed exactly one newly-closed parent candle. Returns the resulting state.

        Advances the disjoint C1/C2/C3 sub-graph by exactly one legal edge per call —
        never more than one transition per candle, matching how the M15 engine's own
        `process_candle` advances its state machine one bar at a time."""
        if self._range is None:
            # First candle this track has ever seen -> establishes the initial C1.
            self._become_c1(parent)
            return self._state

        if self._state == CRTState.RANGE_C1:
            sweep = self._detect_parent_sweep(parent, self._range)
            if sweep is not None:
                self._sweep = sweep
                self._state = CRTState.MANIPULATION_C2
            else:
                # RANGE_C1 -> RANGE_C1 self-loop: roll the reference forward.
                self._become_c1(parent)
            return self._state

        if self._state == CRTState.MANIPULATION_C2:
            assert self._sweep is not None and self._range is not None
            if self._directional_impulse_confirmed(parent, self._sweep):
                self._state = CRTState.DISTRIBUTION_C3
            else:
                # MANIPULATION_C2 -> RANGE_C1: sweep didn't confirm; restart from here.
                self._become_c1(parent)
            return self._state

        if self._state == CRTState.DISTRIBUTION_C3:
            # DISTRIBUTION_C3 -> RANGE_C1 is the ONLY legal edge (VALID_TRANSITIONS) —
            # the narrative always restarts fresh from the candle after distribution.
            self._become_c1(parent)
            return self._state

        raise AssertionError(f"ParentCRTTrack: unreachable state {self._state!r}")   # pragma: no cover

    # ── internals — reimplemented geometry, isolated from crt_engine_v2 (see module doc) ──

    def _become_c1(self, candle: "Candle") -> None:
        self._range = ParentRange(h_ref=candle.high, l_ref=candle.low, formed_at_index=candle.index)
        self._state = CRTState.RANGE_C1
        self._sweep = None

    def _detect_parent_sweep(self, candle: "Candle", rng: ParentRange) -> Optional[ParentSweepEvent]:
        """Boundary-cross-then-close-back-inside, at parent scale. Mirrors
        `RangeDetector.detect_sweep`'s geometry (crt_engine_v2.py) exactly, reimplemented
        against a `ParentRange` rather than the M15 engine's `Range`."""
        swept_high = _swept_high(candle.high, candle.close, rng.h_ref)
        swept_low = _swept_low(candle.low, candle.close, rng.l_ref)
        if not swept_high and not swept_low:
            return None
        direction = Direction.SHORT if swept_high else Direction.LONG
        price = candle.high if swept_high else candle.low
        return ParentSweepEvent(direction=direction, price=price, candle_index=candle.index)

    def _directional_impulse_confirmed(self, candle: "Candle", sweep: ParentSweepEvent) -> bool:
        """The F-074 directional displacement contract, reimplemented at parent scale:
        LONG (low swept) needs a bullish close above the sweep price; SHORT (high swept)
        needs a bearish close below it. Unsigned/energy-only impulses do not qualify —
        matching `try_sweep_to_displacement`'s CH-directional-displacement-contract
        (crt_engine_v2.py, user-authorized 2026-08-13)."""
        if sweep.direction == Direction.LONG:
            return _directional_impulse(candle.open, candle.close, sweep.price, is_long=True)
        if sweep.direction == Direction.SHORT:
            return _directional_impulse(candle.open, candle.close, sweep.price, is_long=False)
        return False
