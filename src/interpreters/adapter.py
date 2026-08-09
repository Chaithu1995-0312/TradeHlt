"""
adapter.py — the ONLY bridge from an Interpreter to the research measurement stack.

`InterpreterHypothesis` wraps any `Interpreter` as a research `Hypothesis` (implements
`detect() -> list[Signal]`), so an interpreter is measured by the UNCHANGED
`forward_walk` + `QualificationGate` (the reused oracle) — no parallel measurement
code, no `InterpreterOracle`. Mirrors `hypotheses/spine_hypothesis.py`.

IDENTITY-BLIND (frozen invariant): `detect()` builds Signals from ONLY the reading's
directional events (direction + entry geometry). It never branches on the interpreter's
identity/type or on `event.meta`. `name`/`family`/`economic_rationale` are carried as
labels for qualification telemetry (the M4.7 rationale gate), not as decision inputs.
Confidence/strength/trace_id ride along in `Signal.meta` as provenance only.
"""

from __future__ import annotations

from typing import Sequence

from research.contracts import Signal

from interpreters.contract import Interpreter


class InterpreterHypothesis:
    """Adapt one `Interpreter` to the `Hypothesis` Protocol (behavior-agnostic)."""

    def __init__(self, interpreter: Interpreter, *, family: str = "interpreter"):
        self._interp = interpreter
        # Labels for the research registry / M4.7 rationale gate (telemetry, not
        # decisions). Reading them here does not violate identity-blindness, which is
        # about detect()'s SIGNAL logic — that uses only events (see below).
        self.name = f"interp:{getattr(interpreter, 'name', 'unknown')}"
        self.family = family
        self.economic_rationale = getattr(interpreter, "economic_rationale", "")

    def detect(self, window: Sequence, features: dict, ctx: dict) -> list[Signal]:
        if not window:
            return []
        bar = window[-1]
        idx = getattr(bar, "index", None)
        if idx is None:
            return []

        reading = self._interp.observe(window, features, ctx)
        instrument = ctx.get("instrument", "UNKNOWN")

        signals: list[Signal] = []
        for ev in reading.events:
            # Identity-blind: only directional events with full geometry become trades.
            if not ev.is_directional:
                continue
            signals.append(Signal(
                instrument=instrument,
                timestamp=bar.timestamp,
                entry_index=idx,
                direction=ev.direction.value.lower(),   # Direction enum → "long"/"short"
                entry=float(ev.entry),
                sl_atr_mult=float(ev.sl_atr_mult),
                tp_atr_mult=float(ev.tp_atr_mult),
                atr=float(ev.atr),
                meta={                                    # provenance only (telemetry)
                    "event_kind": ev.kind.value,
                    "confidence": ev.confidence,
                    "strength": ev.strength,
                    "trace_id": reading.trace_id,
                    "schema_version": reading.schema_version,
                },
            ))
        return signals
