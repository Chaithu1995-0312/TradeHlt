"""TRS-01 thesis. Born on the MKT-E04 bar, or not at all.

A sweep with no directional displacement is an episode, not a failed thesis (D2-1).
FAILED / SPENT / EXPIRED record the thesis lifecycle. They do not close a position.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional, Sequence

from semantics import geometry as gp
from semantics.identity import parameterization_id
from semantics.market.events import clock_rollovers, extension_reach, sweep
from semantics.market.levels import Level, extension
from semantics.trading.roles import Invalidation, breach, make_invalidation
from semantics.types import Bar, Bias

THESIS = "TRS-01"

ACTIVE = "ACTIVE"
FAILED = "FAILED"
SPENT = "SPENT"
EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class Thesis:
    """TRS-01. available_at advances when a later bar is an input of the status."""

    concept_id: str
    parameterization_id: str
    available_at: int
    direction: Bias
    founding: str
    sweep_bar: int
    born_at: int
    invalidation: Optional[Invalidation]
    status: str = ACTIVE
    terminal_at: Optional[int] = None
    retrace_fraction: float = 0.0
    extension_fib: float = 0.0
    move_start: float = 0.0
    move_end: float = 0.0
    clock: str = ""


def form_thesis(
    sweep_bar: Bar,
    level: Level,
    displacement_bar: Bar,
    *,
    retrace_fraction: float,
    extension_fib: float,
    clock: str,
) -> Optional[Thesis]:
    """None unless events.sweep fires and GP-06 confirms it on the displacement bar.

    The displacement move, shared by the invalidation retracement and the spent
    extension, runs from the sweep's reference price to the displacement close
    (MKT-E04: away from the sweep).
    """
    event = sweep(sweep_bar, level)
    if event is None or event.implied_bias is None or event.reference_price is None:
        return None
    if displacement_bar.index < event.bar:
        return None
    if not gp.directional_impulse(displacement_bar, event.reference_price, event.implied_bias):
        return None
    founding = str(event.reference)
    born = displacement_bar.index
    invalidation = make_invalidation(
        event.reference_price, displacement_bar.close, retrace_fraction, formed_at=born,
    )
    pid = parameterization_id(THESIS, {"founding": founding}, ("founding",))
    return Thesis(
        THESIS, pid, born, event.implied_bias, founding, event.bar, born, invalidation,
        ACTIVE, None, float(retrace_fraction), float(extension_fib),
        float(event.reference_price), float(displacement_bar.close), clock,
    )


def _terminal(thesis: Thesis, status: str, bar: int) -> Thesis:
    return replace(thesis, status=status, terminal_at=bar, available_at=max(thesis.available_at, bar))


def mark_failed(thesis: Thesis, bar: Bar) -> Thesis:
    """FAILED on MKT-E10. Sets the thesis status only; it does not close a position (D2-2)."""
    if thesis.status != ACTIVE or thesis.invalidation is None:
        return thesis
    event = breach(thesis.invalidation, bar, thesis.direction)
    if event is None:
        return thesis
    return _terminal(thesis, FAILED, event.bar)


def mark_spent(thesis: Thesis, bar: Bar) -> Thesis:
    """SPENT on MKT-E11 (GP-03). A spent move is not an invalidation."""
    if thesis.status != ACTIVE:
        return thesis
    level = extension(
        thesis.move_start, thesis.move_end, thesis.extension_fib,
        anchor="displacement", formed_at=thesis.born_at, available_at=thesis.born_at,
    )
    event = extension_reach(bar, level, thesis.direction)
    if event is None:
        return thesis
    return _terminal(thesis, SPENT, event.bar)


def mark_expired(thesis: Thesis, clock_ids: Sequence[str]) -> Thesis:
    """EXPIRED on the first MKT-E12 at or after the thesis is born."""
    if thesis.status != ACTIVE:
        return thesis
    for event in clock_rollovers(clock_ids, clock=thesis.clock):
        if event is not None and event.bar >= thesis.born_at:
            return _terminal(thesis, EXPIRED, event.bar)
    return thesis
