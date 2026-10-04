"""session_autoderive.py — learn a provider's tradable session from the data itself.

The hardcoded session calendar (`dataset_integrity._is_tradable`: Sun-22:00 open / Fri-21:00
close / 21:00 break) is the textbook GMT-FX week. Real brokers differ — e.g. IC Markets serves
Mon-00:00 → Fri-24:00 with no Sunday session and no daily break. Hardcoding one calendar per
broker is brittle; instead we DERIVE the tradable weekly mask from each series' own modal
presence pattern.

A weekly slot = (weekday, minute_of_day). A slot is "tradable" if a bar appears there in at least
`presence_min` of the weeks that weekday occurs at all. So:
  * weekend / overnight slots the broker never serves  → present in ~0% of weeks → NON-tradable.
  * normal trading slots                               → present in ~100% of weeks → tradable.
  * a one-off hole on a normal slot (corruption)       → still tradable in the mask → FLAGGED.
  * a market holiday (a normal slot absent that day)   → still tradable in the mask → FLAGGED
    unless the date is in the reviewed `holidays` list (the irregular-closure escape hatch).

This is provider-agnostic and self-calibrating: weekends/sessions are learned, only genuine
irregular closures (holidays) need an explicit list. Pure stdlib, deterministic.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Iterable

# A weekly slot identity: (weekday 0-6, minute-of-day 0-1439).
WeeklySlot = tuple[int, int]


def _slot(dt: datetime) -> WeeklySlot:
    return (dt.weekday(), dt.hour * 60 + dt.minute)


def derive_weekly_mask(
    timestamps: Iterable[datetime], *, presence_min: float = 0.5,
) -> frozenset[WeeklySlot]:
    """Set of (weekday, minute_of_day) slots the provider NORMALLY trades.

    For each slot, presence ratio = (distinct ISO weeks with a bar at that slot) / (distinct ISO
    weeks in which that weekday appears at all). A slot is tradable iff ratio >= presence_min. The
    weekday-specific denominator makes partial first/last weeks harmless.
    """
    slot_weeks: dict[WeeklySlot, set] = defaultdict(set)
    weekday_weeks: dict[int, set] = defaultdict(set)
    for dt in timestamps:
        iso = dt.isocalendar()
        wk = (iso[0], iso[1])
        slot_weeks[_slot(dt)].add(wk)
        weekday_weeks[dt.weekday()].add(wk)

    mask: set[WeeklySlot] = set()
    for slot, weeks in slot_weeks.items():
        denom = len(weekday_weeks[slot[0]]) or 1
        if len(weeks) / denom >= presence_min:
            mask.add(slot)
    return frozenset(mask)


def is_tradable_by_mask(dt: datetime, mask: frozenset[WeeklySlot], holidays) -> bool:
    """A timestamp is tradable iff its weekly slot is in the learned mask AND its date is not a
    reviewed holiday. `holidays` is a set/list of `YYYY-MM-DD` strings (empty ⇒ none)."""
    if holidays and dt.date().isoformat() in holidays:
        return False
    return _slot(dt) in mask
