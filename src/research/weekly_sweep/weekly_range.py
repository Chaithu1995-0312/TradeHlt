"""weekly_range.py — Program 8: weekly accumulation range + sweep geometry.

Tests the ICT/CRT weekly liquidity theory: Monday+Tuesday form an accumulation range;
Wednesday-Friday is when a sweep of that range (a stop-hunt) resolves into the real
directional move. `crt_engine_v2.RangeDetector` has ZERO weekly memory (its SWEEP state is
purely intraday/local-range, see `crt_engine_v2.py:1017-1066`), so this module reimplements
the identical boundary-cross-then-close-back-inside geometry test against a WEEKLY range
instead — locally, not by importing the live spine (Hypothesis-Protocol isolation).

Every function here is pure and no-lookahead: it inspects only the `window` (or the
accumulation-bar subset of it) it is given, never anything outside. No config reads, no I/O.
Unit-testable with synthetic candle lists (see tests/research/test_weekly_sweep.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence

# SK-1 (2026-08-19): SP-001 now has ONE implementation. The module's original isolation note
# ("reimplement the small shared arithmetic locally; never import the live spine") is
# SUPERSEDED for the ARITHMETIC only — `structure.predicates` is a pure, config-free identity
# module, not the spine. The FOUNDING (this file's weekly calendar range) stays entirely
# local, which is the independence that made F-042 a genuinely new ontology.
from structure.predicates import swept_high as _swept_high, swept_low as _swept_low

if TYPE_CHECKING:  # avoid pulling the heavy crt_engine_v2 import at runtime
    from config_layer.crt_engine_v2 import Candle

# Python's datetime.weekday(): Monday=0 ... Sunday=6.
ACCUMULATION_WEEKDAYS = (0, 1)   # Monday, Tuesday — the range-forming bars
SWEEP_WEEKDAYS = (2, 3, 4)       # Wednesday, Thursday, Friday — the only days a sweep may fire


@dataclass(frozen=True)
class WeeklyRange:
    """The Monday+Tuesday accumulation range for one ISO week."""

    iso_year: int
    iso_week: int
    h_ref: float
    l_ref: float
    formed_at_index: int         # .index of the last accumulation bar used
    n_accumulation_bars: int     # bars actually used (holiday-shortened weeks are smaller)


@dataclass(frozen=True)
class WeeklySweepEvent:
    """A detected boundary-cross-then-close-back-inside sweep of a `WeeklyRange`."""

    boundary: str                # "HIGH" | "LOW"
    direction: str                # "short" | "long" — opposite the swept boundary
    sweep_price: float
    range: WeeklyRange
    bar_index: int


def _iso_week(bar: "Candle") -> tuple[int, int]:
    iso = bar.timestamp.isocalendar()
    return (iso[0], iso[1])


def _has_unexpected_gap(bars: Sequence["Candle"], max_intraweek_gap_minutes: float) -> bool:
    """True iff any consecutive-bar gap WITHIN `bars` exceeds the threshold.

    Purely local: only compares timestamps already present in `bars` (the accumulation
    bars), never anything outside. This catches an intraday data outage (e.g. a 3-hour
    dropout on an otherwise-normal Monday) that would still clear a raw bar-COUNT threshold
    while silently understating the true weekly high/low — distinct from, and a complement
    to, the whole-week holiday veto in `is_week_structurally_valid`.
    """
    ordered = list(bars)
    if len(ordered) < 2:
        return False
    for prev, cur in zip(ordered[:-1], ordered[1:]):
        delta_minutes = (cur.timestamp - prev.timestamp).total_seconds() / 60.0
        if delta_minutes > max_intraweek_gap_minutes:
            return True
    return False


def current_week_range(
    window: Sequence["Candle"],
    *,
    min_accumulation_bars: int,
    max_intraweek_gap_minutes: float | None = None,
) -> WeeklyRange | None:
    """Build the current ISO week's Mon+Tue accumulation range, or None if not (yet) valid.

    Pure; only inspects `window` (past+current bars, ending at the bar being evaluated).
    Returns None — never a partial/contaminated range — when:
      * the current bar's ISO week has no Tuesday bar yet. This is the RANGE-LOCK rule: the
        range is only considered formed once Tuesday's session has begun closing bars, so a
        sweep can only ever fire from Wednesday onward (matching the theory's own wording;
        no separate "is it Wednesday" gate is needed at the call site).
      * fewer than `min_accumulation_bars` Mon/Tue bars are present (a holiday-shortened or
        otherwise degenerate week — a conservative guard, not a silent partial range).
      * `max_intraweek_gap_minutes` is given and an unexpected intraday gap is found inside
        the Mon/Tue bars (see `_has_unexpected_gap`).
    """
    bars = list(window)
    if not bars:
        return None
    year, week = _iso_week(bars[-1])

    acc_bars = [
        b for b in bars
        if _iso_week(b) == (year, week) and b.timestamp.weekday() in ACCUMULATION_WEEKDAYS
    ]
    if not acc_bars:
        return None
    if not any(b.timestamp.weekday() == 1 for b in acc_bars):
        return None   # Tuesday hasn't closed yet this week — range not locked
    if len(acc_bars) < min_accumulation_bars:
        return None   # holiday-shortened / degenerate week
    if max_intraweek_gap_minutes is not None and _has_unexpected_gap(acc_bars, max_intraweek_gap_minutes):
        return None

    return WeeklyRange(
        iso_year=year,
        iso_week=week,
        h_ref=max(float(b.high) for b in acc_bars),
        l_ref=min(float(b.low) for b in acc_bars),
        formed_at_index=acc_bars[-1].index,
        n_accumulation_bars=len(acc_bars),
    )


def is_week_structurally_valid(window: Sequence["Candle"], weekly_mask, holidays) -> bool:
    """Veto a degenerate week (e.g. the whole Mon+Tue span is a broker holiday closure)
    using the already-derived per-instrument tradability mask
    (`data_ingestion.session_autoderive.derive_weekly_mask` / `is_tradable_by_mask`, computed
    ONCE in the driver script from the full corpus and passed down here — never recomputed
    inside this function). Does NOT redefine weekday semantics; it only vetoes weeks whose
    accumulation bars fall entirely on structurally non-tradable slots — a broker-calibrated
    complement to the raw `min_accumulation_bars` count guard in `current_week_range`.
    """
    from data_ingestion.session_autoderive import is_tradable_by_mask

    bars = list(window)
    if not bars:
        return False
    year, week = _iso_week(bars[-1])
    acc_bars = [
        b for b in bars
        if _iso_week(b) == (year, week) and b.timestamp.weekday() in ACCUMULATION_WEEKDAYS
    ]
    if not acc_bars:
        return False
    return any(is_tradable_by_mask(b.timestamp, weekly_mask, holidays) for b in acc_bars)


def _first_sweep_this_week(window: Sequence["Candle"], weekly_range: WeeklyRange, boundary: str) -> bool:
    """True iff no EARLIER Wed-Fri bar in `window` (excluding the current bar) already swept
    `boundary` against `weekly_range`. Re-derived from `window` alone on every call (no
    instance state) so the one-shot-per-boundary-per-week guard keeps the caller fully pure.
    """
    bars = list(window)
    if len(bars) < 2:
        return True
    for b in bars[:-1]:
        if _iso_week(b) != (weekly_range.iso_year, weekly_range.iso_week):
            continue
        if b.timestamp.weekday() not in SWEEP_WEEKDAYS:
            continue
        if boundary == "HIGH":
            if _swept_high(float(b.high), float(b.close), weekly_range.h_ref):
                return False
        else:
            if _swept_low(float(b.low), float(b.close), weekly_range.l_ref):
                return False
    return True


def detect_weekly_sweep(window: Sequence["Candle"], weekly_range: WeeklyRange) -> WeeklySweepEvent | None:
    """Boundary-cross-then-close-back-inside test, evaluated on `window[-1]` only.

    Mirrors `config_layer.crt_engine_v2.RangeDetector.detect_sweep`'s geometry
    (`swept_high = bar.high > h_ref and bar.close < h_ref`, symmetric for low) and its
    short-on-high-sweep / long-on-low-sweep convention, reimplemented here against a
    `WeeklyRange` rather than imported — this module stays isolated from the live spine
    per the Hypothesis Protocol.

    Weekday gating (only Wed/Thu/Fri may fire) and the one-shot-per-boundary-per-week guard
    (`_first_sweep_this_week`) are the CALLER's responsibility, keeping this a reusable,
    calendar-agnostic geometry primitive.
    """
    bars = list(window)
    if not bars:
        return None
    bar = bars[-1]
    swept_high = _swept_high(float(bar.high), float(bar.close), weekly_range.h_ref)
    swept_low = _swept_low(float(bar.low), float(bar.close), weekly_range.l_ref)

    if not swept_high and not swept_low:
        return None

    boundary = "HIGH" if swept_high else "LOW"
    direction = "short" if swept_high else "long"
    sweep_price = float(bar.high) if swept_high else float(bar.low)

    return WeeklySweepEvent(
        boundary=boundary,
        direction=direction,
        sweep_price=sweep_price,
        range=weekly_range,
        bar_index=bar.index,
    )
