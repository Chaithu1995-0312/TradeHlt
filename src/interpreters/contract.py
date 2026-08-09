"""
contract.py — the Interpreter Contract (frozen Schema 1.0).

An **Interpreter** is an event/feature producer (Level 4): it OBSERVES a window and
emits `InterpreterEvent`s + a reading-level confidence. It is a different economic
object from a research `Hypothesis` (which emits trades). Interpreters feed FUSION;
they are MEASURED by being bridged to a `Hypothesis` (see `adapter.py`) and run
through the existing `forward_walk` + `QualificationGate` — there is NO new oracle.

Hard invariants (frozen — do not extend the contract surface):
  • Pure / deterministic / no-lookahead: `observe(window, …)` is a pure function of
    `window` (which ends at the current bar). Same window → identical reading,
    including `trace_id` and `observation_time` (both derived from the last bar —
    never wall-clock).
  • Identity-blind boundary: downstream (adapter/fusion) consumes only
    events / confidence / strength / unknowns — never `name`/`family`/`meta` or the
    concrete class. `meta` is OPAQUE telemetry, forbidden for any decision.
  • Core required (`observe`/events/`confidence`), rest defaulted by
    `BaseInterpreter` (`unknowns=[]`, `failure_conditions={}`, `version()="1.0"`,
    `explain()` telemetry-only). The base VALIDATES every reading (never trust
    subclasses): confidence & strength ∈ [0,1], `kind` ∈ EventKind, `direction` ∈
    {Direction, None}, non-empty trace_id, present observation_time.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Optional, Protocol, Sequence, Tuple, runtime_checkable

from config_layer.crt_engine_v2 import Candle, Direction   # reuse frozen enum/value-object

logger = logging.getLogger("CRT.Interpreter")

# The CONTRACT version — distinct from an interpreter's implementation `version()`.
# Bump only when the reading/event shape changes; many implementation versions
# (PNF-v7, Wyckoff-v3) conform to one schema.
SCHEMA_VERSION = "1.0"


class EventKind(Enum):
    """Contract-level event taxonomy (drift guard — no stringly-typed kinds).
    Future interpreters extend this enum (+ a test); `BaseInterpreter` rejects any
    non-member kind. `OBSERVATION` = a non-directional context reading."""
    BREAKOUT = "BREAKOUT"
    REVERSAL = "REVERSAL"
    SPRING = "SPRING"
    CATAPULT = "CATAPULT"
    OBSERVATION = "OBSERVATION"
    # Plan 5 — Point & Figure (the designed extension point; +a test in test_point_and_figure).
    DOUBLE_TOP_BREAKOUT = "DOUBLE_TOP_BREAKOUT"
    DOUBLE_BOTTOM_BREAKDOWN = "DOUBLE_BOTTOM_BREAKDOWN"


class InterpreterError(ValueError):
    """Raised when an interpreter produces a reading that violates the contract."""


@dataclass(frozen=True)
class InterpreterEvent:
    """One observation event. `confidence` = how sure; `strength` = how powerful
    (orthogonal). Entry geometry is optional — present only on directional events
    the adapter can turn into a trade Signal. `meta` is OPAQUE (telemetry only)."""
    kind: EventKind
    confidence: float
    strength: float
    direction: Optional[Direction] = None
    entry: Optional[float] = None
    sl_atr_mult: Optional[float] = None
    tp_atr_mult: Optional[float] = None
    atr: Optional[float] = None
    meta: Mapping[str, Any] = field(default_factory=dict)

    @property
    def is_directional(self) -> bool:
        """True iff this event carries a full directional trade geometry (so the
        adapter can emit a Signal). Non-directional events feed fusion as context."""
        return (
            self.direction is not None and self.entry is not None
            and self.sl_atr_mult is not None and self.tp_atr_mult is not None
            and self.atr is not None
        )


@dataclass(frozen=True)
class InterpreterReading:
    """The pure output of `observe()`. Carries the owner's five capabilities as
    fields (events/confidence/unknowns/failure_conditions) + provenance."""
    events: list[InterpreterEvent]
    confidence: float
    trace_id: str                 # hierarchical: {NAME}-v{version}-{YYYYMMDD-HHMMSS}
    observation_time: datetime    # window's LAST bar timestamp (deterministic)
    schema_version: str = SCHEMA_VERSION
    unknowns: list[str] = field(default_factory=list)
    failure_conditions: dict = field(default_factory=dict)


@runtime_checkable
class Interpreter(Protocol):
    """Behavior-agnostic plugin contract. Mirrors the research `Hypothesis` purity."""
    name: str
    family: str
    economic_rationale: str

    def observe(self, window: Sequence[Candle], features: dict, ctx: dict) -> InterpreterReading: ...

    def explain(self) -> dict: ...   # telemetry/explainability ONLY — never a decision input


def _require_unit(value: float, label: str) -> None:
    if not (0.0 <= float(value) <= 1.0):
        raise InterpreterError(f"{label}={value} outside [0,1]")


class BaseInterpreter:
    """Reduce boilerplate + enforce the contract. Subclasses implement `_observe`
    returning `(events, confidence)`; the base wraps it into a validated, provenance-
    stamped `InterpreterReading`. `unknowns`/`failure_conditions`/`version`/`explain`
    are overridable hooks with safe defaults (Q3: core-required, rest-defaulted)."""

    name: str = "base"
    family: str = "base"
    economic_rationale: str = ""
    schema_version: str = SCHEMA_VERSION

    # ── hooks (override as needed) ───────────────────────────────────────────
    def version(self) -> str:
        """Implementation version (distinct from `schema_version`). Default '1.0'."""
        return "1.0"

    def _observe(self, window: Sequence[Candle], features: dict,
                 ctx: dict) -> Tuple[list[InterpreterEvent], float]:
        raise NotImplementedError

    def unknowns(self, window: Sequence[Candle], features: dict, ctx: dict) -> list[str]:
        return []

    def failure_conditions(self, window: Sequence[Candle], features: dict, ctx: dict) -> dict:
        return {}

    def explain(self) -> dict:
        """Telemetry-only narration. NEVER consumed by adapter/fusion/decision."""
        return {"observation": "", "reasoning": "", "unknowns": []}

    # ── final pipeline (do not override) ─────────────────────────────────────
    def _trace_id(self, ts: datetime) -> str:
        # Deterministic from the bar time (no mutable counter) → same window yields
        # the same trace_id (replay-safe). seq component = the bar's HHMMSS.
        return f"{self.name.upper()}-v{self.version()}-{ts.strftime('%Y%m%d-%H%M%S')}"

    def observe(self, window: Sequence[Candle], features: dict, ctx: dict) -> InterpreterReading:
        if not window:
            raise InterpreterError(f"{self.name}: empty window — cannot observe")
        events, confidence = self._observe(window, features, ctx)
        ts = window[-1].timestamp     # deterministic, last bar — never wall-clock
        reading = InterpreterReading(
            events=list(events),
            confidence=float(confidence),
            trace_id=self._trace_id(ts),
            observation_time=ts,
            schema_version=self.schema_version,
            unknowns=list(self.unknowns(window, features, ctx)),
            failure_conditions=dict(self.failure_conditions(window, features, ctx)),
        )
        self._validate(reading)
        return reading

    def _validate(self, reading: InterpreterReading) -> None:
        """The contract's teeth — never trust subclasses."""
        _require_unit(reading.confidence, "reading.confidence")
        if not reading.trace_id:
            raise InterpreterError("empty trace_id")
        if reading.observation_time is None:
            raise InterpreterError("missing observation_time")
        for ev in reading.events:
            if not isinstance(ev.kind, EventKind):
                raise InterpreterError(f"event.kind not an EventKind: {ev.kind!r}")
            if ev.direction is not None and not isinstance(ev.direction, Direction):
                raise InterpreterError(f"event.direction not Direction|None: {ev.direction!r}")
            _require_unit(ev.confidence, "event.confidence")
            _require_unit(ev.strength, "event.strength")
