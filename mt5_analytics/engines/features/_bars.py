"""
_bars — the candle value object + window builder shared by every feature sub-engine.

`Bar` carries exactly the `.high/.low/.close/.index` interface that `forward_walk`,
`horizon_excursion`, `research.indicators.atr`, and `RegimeLabeler` all consume, so one
type satisfies the whole layer. `build_window` re-indexes a bar sequence 0..n-1 (so a
bar's `.index` equals its position — the no-lookahead guard compares `bar.index >
entry_index`) and locates the entry bar (the last bar opening at or before entry).
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass, replace
from typing import Sequence


@dataclass(frozen=True)
class Bar:
    index: int
    time: int            # epoch seconds — M15 bar open time
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


def build_window(bars: Sequence[Bar], entry_time_epoch: int) -> tuple[list[Bar], int]:
    """Return (re-indexed window, entry_index).

    `entry_index` = index of the bar that *contains* the entry (the last bar whose open
    time ≤ entry_time). Falls back to 0 when entry precedes the window. The window is
    re-indexed 0..n-1 so `Bar.index` equals list position (required by the forward-walk
    no-lookahead guard).
    """
    ordered = sorted(bars, key=lambda b: b.time)
    indexed = [replace(b, index=i) for i, b in enumerate(ordered)]
    if not indexed:
        return [], 0
    times = [b.time for b in indexed]
    pos = bisect.bisect_right(times, entry_time_epoch) - 1
    return indexed, max(0, pos)
