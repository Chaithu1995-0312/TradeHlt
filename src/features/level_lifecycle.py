"""MKT-L01 level lifecycle: the single implementation of ACTIVE -> SWEPT / BROKEN.

Contract (configs/formulas/concept_contracts.yaml MKT-L01 lifecycle, MKT-E01 rule):
  * a level is tested from its `available_at` bar on (inclusive);
  * only ACTIVE levels are tested;
  * GP-04 pierce-and-reject (SP-001 `swept_high` / `swept_low`, strict) ends it SWEPT and is one
    MKT-E01 event; a bar that sweeps two levels is two events;
  * otherwise GP-02 (close strictly beyond the level) ends it BROKEN;
  * the contract has no EXPIRED rule, so a level never expires here.

Used by the feature pipeline (batch), the live FeatureStore (one `step` per bar, state carried
across bars) and `semantics.market.events.level_lifecycle` (which wraps it). Pure: no config, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

from structure.predicates import swept_high, swept_low

UPPER = "UPPER"
LOWER = "LOWER"


@dataclass(frozen=True)
class BookLevel:
    key: int
    price: float
    side: str            # UPPER | LOWER
    formed_at: int
    available_at: int


@dataclass(frozen=True)
class StepResult:
    swept: tuple = ()    # keys of levels swept on this bar (one MKT-E01 event each), activation order
    broken: tuple = ()   # keys of levels broken on this bar

    def sides(self, book: "LevelBook") -> set:
        return {book.levels[k].side for k in self.swept}


@dataclass
class LevelBook:
    """Levels in their lifecycle. `add` a level when (or before) it is known; `step` once per bar,
    in bar order. Levels are activated in (available_at, insertion) order."""

    levels: list = field(default_factory=list)       # key -> BookLevel
    _pending: list = field(default_factory=list)     # keys not yet available
    _active: list = field(default_factory=list)      # keys ACTIVE, activation order
    ended: dict = field(default_factory=dict)        # key -> ("SWEPT" | "BROKEN", bar)

    def add(self, price: float, side: str, *, formed_at: int, available_at: int) -> int:
        if side not in (UPPER, LOWER):
            raise ValueError(f"LevelBook: side {side!r}")
        key = len(self.levels)
        self.levels.append(BookLevel(key, float(price), side, int(formed_at), int(available_at)))
        self._pending.append(key)
        self._pending.sort(key=lambda j: (self.levels[j].available_at, j))
        return key

    def step(self, i: int, high: float, low: float, close: float) -> StepResult:
        while self._pending and self.levels[self._pending[0]].available_at <= i:
            self._active.append(self._pending.pop(0))
        swept, broken, keep = [], [], []
        for j in self._active:
            lvl = self.levels[j]
            if lvl.side == UPPER:
                is_swept, is_broken = swept_high(high, close, lvl.price), close > lvl.price
            else:
                is_swept, is_broken = swept_low(low, close, lvl.price), close < lvl.price
            if is_swept:
                swept.append(j)
                self.ended[j] = ("SWEPT", i)
            elif is_broken:
                broken.append(j)
                self.ended[j] = ("BROKEN", i)
            else:
                keep.append(j)
        self._active = keep
        return StepResult(tuple(swept), tuple(broken))


@dataclass
class LiveSweepState:
    """Per-bar FM-090..093 for a caller that sees one bar at a time (the live FeatureStore). Carries
    the LevelBook, the per-side event window (W = feature_pipeline.double_sweep_window) and the
    last-event bar, so a truncated OHLC buffer never resets consumption. Same lifecycle as
    `swing_level_sweeps` (parity: tests/test_e01_sweep_semantics.py)."""

    k: int
    window: int
    book: LevelBook = field(default_factory=LevelBook)
    bar: int = -1
    last_event: int | None = None
    _up: list = field(default_factory=list)
    _down: list = field(default_factory=list)

    def step(self, highs: Sequence[float], lows: Sequence[float], close: float,
             swing_high: bool, swing_low: bool) -> dict:
        """`highs`/`lows` = the OHLC history ending at this bar (only the last k+1 are read);
        `swing_high`/`swing_low` = this bar's FC1-A causal publication flags."""
        self.bar += 1
        i, k = self.bar, self.k
        if len(highs) > k:
            if swing_high:
                self.book.add(highs[-1 - k], UPPER, formed_at=i - k, available_at=i)
            if swing_low:
                self.book.add(lows[-1 - k], LOWER, formed_at=i - k, available_at=i)
        sides = self.book.step(i, highs[-1], lows[-1], close).sides(self.book)
        up, down = UPPER in sides, LOWER in sides
        self._up = (self._up + [up])[-self.window:]
        self._down = (self._down + [down])[-self.window:]
        if up or down:
            self.last_event = i
        return {
            "liquidity_sweep": 1.0 if up else (-1.0 if down else 0.0),           # FM-090
            "sweep_detected": 1.0 if (up or down) else 0.0,                       # FM-091
            "double_sweep": 1.0 if (any(self._up) and any(self._down)) else 0.0,  # FM-092
            "candles_since_sweep": 0.0 if self.last_event is None else float(i - self.last_event),  # FM-093
        }


def swing_level_sweeps(high: Sequence[float], low: Sequence[float], close: Sequence[float],
                       swing_high: Sequence[float], swing_low: Sequence[float], *, k: int):
    """Per-bar MKT-E01 events on swing_pivot(k) levels, by side.

    `swing_high[i] == 1` means a pivot high formed at i-k is published at bar i (FC1-A causal), so
    the level is `high[i-k]` with available_at = i; the same for lows. Returns int8 arrays
    (up, down): 1 where at least one UPPER / LOWER level was swept on that bar.
    """
    h = np.asarray(high, dtype=float)
    lo = np.asarray(low, dtype=float)
    c = np.asarray(close, dtype=float)
    sh = np.asarray(swing_high)
    sl = np.asarray(swing_low)
    n = len(c)
    book = LevelBook()
    up = np.zeros(n, dtype=np.int8)
    down = np.zeros(n, dtype=np.int8)
    for i in range(n):
        if sh[i] == 1 and i - k >= 0:
            book.add(h[i - k], UPPER, formed_at=i - k, available_at=i)
        if sl[i] == 1 and i - k >= 0:
            book.add(lo[i - k], LOWER, formed_at=i - k, available_at=i)
        sides = book.step(i, h[i], lo[i], c[i]).sides(book)
        up[i] = UPPER in sides
        down[i] = LOWER in sides
    return up, down
