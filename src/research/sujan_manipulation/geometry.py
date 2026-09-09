"""SUJAN_MANIPULATION_RESEARCH_PHASE_1 primitives (SEM-033). Research only.

Phase 1 is DETECTION ONLY. There is no entry, no target, no stop, no outcome, no
economic reading anywhere in this package.

The frozen definitions (human bridge, 2026-08-28 — drift log Record 5):

    Parent Range   Range High = parent candle HIGH, Range Low = parent candle LOW.
                   Full wick-to-wick extent. Body-only interpretations are REJECTED.

    Manipulation   A LATER candle that
                     (1) purges the parent range high OR the parent range low, AND
                     (2) closes back INSIDE the parent range.

WHAT THIS MODULE DELIBERATELY DOES NOT CONTAIN
----------------------------------------------
No ATR, no volatility measure, no percentage, no body ratio, no displacement, no
threshold of any kind. It reads OHLC and two levels. The spec forbids converting a
visual concept into a magnitude rule, and nothing here does.

Purge arithmetic is IMPORTED from SP-001 (``structure.predicates``), never re-derived
locally — local re-derivation is the named FC-FEATURE-NAME-COLLISION failure class.
What SP-001 does NOT own is the FOUNDING (which level counts as liquidity); that is
supplied by the caller and, in this package, is UNRESOLVED by design. See ``parent.py``.

THE LITERAL "CLOSES BACK INSIDE" READING
----------------------------------------
SP-001 ``swept_high`` already asserts ``high > ref and close < ref`` — closed back past
the PURGED side. The bridge ruled (Record 5) that the spec's words mean FULLY inside:
``range_low < close < range_high``. So each predicate adds ONE conjunct against the
opposite boundary. A candle that purges the high and closes BELOW the range low is NOT
manipulation under this reading.

The looser SP-001-only reading is preserved, not discarded: every emitted event carries
``bar_high`` / ``bar_low`` / ``bar_close`` / ``range_high`` / ``range_low``, so the
alternative reading is fully re-derivable from the artifact without a re-run.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from structure.predicates import swept_high, swept_low

from research.sujan_manipulation.parent import Bar, ParentRange

#: The alert kind named by the Phase-1 specification.
ALERT_KIND = "SUJAN_MANIPULATION_DETECTED"


class ManipulationSide(Enum):
    """Which boundary was purged.

    ``HIGH_SWEEP`` / ``LOW_SWEEP`` are the two values the Phase-1 spec names.

    ``BOTH`` is a THIRD value authorised by the human bridge 2026-08-28 (drift log
    Record 5) for the case the spec did not cover: an outside candle that purges the
    high AND the low and still closes fully inside. It is not a mechanical proxy and
    not an interpretation — it is the honest label for a case the frozen definition
    admits but the enum did not enumerate.
    """

    HIGH_SWEEP = "HIGH_SWEEP"
    LOW_SWEEP = "LOW_SWEEP"
    BOTH = "BOTH"


@dataclass(frozen=True)
class ManipulationEvent:
    """One ``SUJAN_MANIPULATION_DETECTED`` alert.

    The first three fields are the REQUIRED OUTPUT of the Phase-1 specification. The
    rest are provenance: they let a reader re-derive the predicate — including the
    alternative close-back-inside reading — without re-running anything.
    """

    parent_timestamp: datetime
    manipulation_timestamp: datetime
    side: ManipulationSide
    # ── provenance below this line ─────────────────────────────────────────
    parent_index: int
    manipulation_index: int
    range_high: float
    range_low: float
    bar_high: float
    bar_low: float
    bar_close: float


def purged_high_closed_inside(bar: Bar, rng: ParentRange) -> bool:
    """Purged the range HIGH and closed fully back inside the range.

    ``swept_high`` supplies ``bar.high > rng.high and bar.close < rng.high`` (SP-001,
    strict on both sides). The added conjunct is the literal "inside the parent range".
    """
    return swept_high(bar.high, bar.close, rng.high) and bar.close > rng.low


def purged_low_closed_inside(bar: Bar, rng: ParentRange) -> bool:
    """Purged the range LOW and closed fully back inside the range. Mirror of the above."""
    return swept_low(bar.low, bar.close, rng.low) and bar.close < rng.high


def detect_manipulation(bar: Bar, rng: ParentRange) -> ManipulationEvent | None:
    """The frozen Phase-1 predicate. ``None`` when the bar does not qualify.

    ``bar`` must be strictly LATER than the parent candle — "a later candle" in the
    specification. The parent can never manipulate its own range, and a bar at or
    before the parent is rejected here rather than silently allowed.
    """
    if bar.index <= rng.parent_index:
        return None

    high_purge = purged_high_closed_inside(bar, rng)
    low_purge = purged_low_closed_inside(bar, rng)

    if high_purge and low_purge:
        side = ManipulationSide.BOTH
    elif high_purge:
        side = ManipulationSide.HIGH_SWEEP
    elif low_purge:
        side = ManipulationSide.LOW_SWEEP
    else:
        return None

    return ManipulationEvent(
        parent_timestamp=rng.parent_timestamp,
        manipulation_timestamp=bar.timestamp,
        side=side,
        parent_index=rng.parent_index,
        manipulation_index=bar.index,
        range_high=rng.high,
        range_low=rng.low,
        bar_high=bar.high,
        bar_low=bar.low,
        bar_close=bar.close,
    )
