"""The Phase-1 state machine, implemented literally.

    IDLE -> BULK_FOUND -> WAIT_FOR_MANIPULATION -> MANIPULATION_DETECTED -> ALERT

The specification draws exactly these five states, so they exist as five states rather
than being collapsed into a boolean. Every transition is recorded, so "the machine ran"
is an observation in the artifact and not a claim in prose.

BRIDGE RULINGS ENCODED HERE (drift log Record 5, 2026-08-28)
------------------------------------------------------------
* After ``ALERT`` the monitor returns to ``WAIT_FOR_MANIPULATION``. The parent range
  remains the reference object and alerts on every later qualifying candle.
* There is NO expiry. The specification says "any later candle may qualify" and names
  no TTL, so none is invented; a parent stays armed to the end of the corpus.
* Every supplied parent is monitored independently and in parallel. Monitors never
  interact and never retire one another.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Iterable, Sequence

from research.sujan_manipulation.geometry import ManipulationEvent, detect_manipulation
from research.sujan_manipulation.parent import Bar, ParentBulkCandle, parent_range


class Phase1State(Enum):
    IDLE = "IDLE"
    BULK_FOUND = "BULK_FOUND"
    WAIT_FOR_MANIPULATION = "WAIT_FOR_MANIPULATION"
    MANIPULATION_DETECTED = "MANIPULATION_DETECTED"
    ALERT = "ALERT"


#: The declared Phase-1 path, in order. Used by the trace assertions.
PHASE1_PATH = (
    Phase1State.IDLE,
    Phase1State.BULK_FOUND,
    Phase1State.WAIT_FOR_MANIPULATION,
    Phase1State.MANIPULATION_DETECTED,
    Phase1State.ALERT,
)


@dataclass(frozen=True)
class StateTransition:
    parent_timestamp: datetime
    from_state: Phase1State
    to_state: Phase1State
    bar_index: int | None
    bar_timestamp: datetime | None


class ParentMonitor:
    """Monitors ONE supplied parent bulk candle for the frozen manipulation event."""

    def __init__(self, parent: ParentBulkCandle) -> None:
        self.parent = parent
        self.range = parent_range(parent)
        self.state = Phase1State.IDLE
        self.trace: list[StateTransition] = []
        self.alerts: list[ManipulationEvent] = []

    # ── internals ────────────────────────────────────────────────────────
    def _to(self, state: Phase1State, bar: Bar | None = None) -> None:
        self.trace.append(
            StateTransition(
                parent_timestamp=self.parent.timestamp,
                from_state=self.state,
                to_state=state,
                bar_index=None if bar is None else bar.index,
                bar_timestamp=None if bar is None else bar.timestamp,
            )
        )
        self.state = state

    # ── public ───────────────────────────────────────────────────────────
    def arm(self) -> None:
        """IDLE -> BULK_FOUND -> WAIT_FOR_MANIPULATION."""
        if self.state is not Phase1State.IDLE:
            raise RuntimeError(f"monitor already armed (state={self.state.value})")
        self._to(Phase1State.BULK_FOUND)
        self._to(Phase1State.WAIT_FOR_MANIPULATION)

    def step(self, bar: Bar) -> ManipulationEvent | None:
        """Feed one candle. Returns the alert if this candle qualifies."""
        if self.state is not Phase1State.WAIT_FOR_MANIPULATION:
            raise RuntimeError(f"monitor is not waiting (state={self.state.value})")
        event = detect_manipulation(bar, self.range)
        if event is None:
            return None
        self._to(Phase1State.MANIPULATION_DETECTED, bar)
        self._to(Phase1State.ALERT, bar)
        self.alerts.append(event)
        # Bridge ruling: the parent range remains the reference object.
        self._to(Phase1State.WAIT_FOR_MANIPULATION, bar)
        return event


@dataclass
class ManipulationRunner:
    """Runs every supplied parent in parallel over one bar stream. No expiry."""

    monitors: list[ParentMonitor] = field(default_factory=list)

    @classmethod
    def from_parents(cls, parents: Sequence[ParentBulkCandle]) -> "ManipulationRunner":
        runner = cls(monitors=[ParentMonitor(p) for p in parents])
        for monitor in runner.monitors:
            monitor.arm()
        return runner

    def run(self, bars: Iterable[Bar]) -> list[ManipulationEvent]:
        """Stream bars in order. Detection at bar i sees only bar i — no lookahead."""
        events: list[ManipulationEvent] = []
        for bar in bars:
            for monitor in self.monitors:
                event = monitor.step(bar)
                if event is not None:
                    events.append(event)
        return events

    @property
    def trace(self) -> list[StateTransition]:
        out: list[StateTransition] = []
        for monitor in self.monitors:
            out.extend(monitor.trace)
        return out
