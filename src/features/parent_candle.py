"""parent_candle.py — CH-htfcrt-parent-candle-smc-v1: real, calendar-true HTF parent candles.

Distinct from (and NOT a replacement for) `runtime.backtest_v2.HTFBuilder`. `HTFBuilder` is a
COUNT-based reset clock — it flips `current_htf_id` every N M15 bars and (pre-this-program)
performed zero OHLC aggregation; its window boundaries are stream-offset dependent, not
calendar-aligned. `ParentCandleBuilder` here is CALENDAR-based: it streams one child candle at
a time and emits a genuine parent `Candle` (real open/high/low/close/volume) the moment the
next calendar period's first child arrives, for any rule `features.calendar_periods` supports
(H1, H4, D1, W1, MN1— the hour-grid rules are duplicated there rather than imported from
`research.resample`; see that module's LAYERING note for why).

These two builders answer different questions and must not be conflated:
  * `HTFBuilder.parent_candle` (added by this same program, see backtest_v2.py) — "what did the
    engine's existing reset window look like as a candle" — cheap, zero-risk, still count-based.
  * `ParentCandleBuilder` (this module) — "what did the real, calendar-true H4/D1/W1/MN1 candle
    look like" — the object the 3-candle parent-CRT track (config_layer.parent_crt) is built on.

NO-LOOKAHEAD (non-negotiable, adversarially tested — see tests/test_parent_candle_builder.py):
the in-progress period's accumulator is never exposed. `parent_candle` / `parent_history` only
ever return CLOSED periods — the same discipline `resample.py` and `weekly_range.py` already
enforce, extended to a streaming (incremental push) API instead of a batch one, because the
3-candle CRT track (Phase 2) needs to classify state on every new M15 bar, not just once per
finished research run.
"""

from __future__ import annotations

from collections import deque
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from features.calendar_periods import ALL_PERIOD_RULES, period_key, period_start

if TYPE_CHECKING:
    from config_layer.crt_engine_v2 import Candle

#: re-exported for callers that want the accepted-rule list without importing calendar_periods.
SUPPORTED_RULES = ALL_PERIOD_RULES


def _aggregate(children: list, timestamp, index: int) -> "Candle":
    """Shared OHLC aggregation — identical contract to `resample._emit` /
    `calendar_periods._emit` (open=first, high=max, low=min, close=last,
    volume=Decimal-exact sum). Defined once here rather than importing either sibling's
    private helper, matching the `weekly_sweep` isolation precedent (reimplement the small
    shared arithmetic locally instead of reaching into another module's underscored API).
    """
    from config_layer.crt_engine_v2 import Candle

    vol = sum((Decimal(str(c.volume)) for c in children), Decimal(0))
    return Candle(
        timestamp=timestamp,
        open=children[0].open,
        high=max(c.high for c in children),
        low=min(c.low for c in children),
        close=children[-1].close,
        volume=float(vol),
        index=index,
    )


class ParentCandleBuilder:
    """Streams M15 (or any finer-grid) candles and emits closed parent candles for `rule`.

    `keep` controls how many trailing closed parents are retained in `parent_history` — the
    3-candle CRT track needs `keep >= 3` (C1/C2/C3); anything requiring only the latest parent
    can use the default of 1 cheaply (a single-slot ring, no extra memory).
    """

    def __init__(self, rule: str, keep: int = 1):
        if rule not in SUPPORTED_RULES:
            raise ValueError(f"ParentCandleBuilder: unsupported rule '{rule}' (expected one of {SUPPORTED_RULES})")
        self.rule = rule
        self._keep = max(1, int(keep))
        self._buffer: list = []
        self._cur_key = None
        self._history: deque = deque(maxlen=self._keep)
        self._period_idx = 0

    def push(self, candle) -> bool:
        """Feed one child candle (must arrive in chronological order — same contract as
        `resample.resample`/`HTFBuilder.push`). Returns True iff this push closed a period
        (a new parent candle is now the most recent entry in `parent_history`)."""
        key = period_key(candle.timestamp, self.rule)
        if self._cur_key is None:
            self._cur_key = key
            self._buffer = [candle]
            return False
        if key != self._cur_key:
            parent = _aggregate(self._buffer, period_start(self._cur_key, self.rule), self._period_idx)
            self._history.append(parent)
            self._period_idx += 1
            self._cur_key = key
            self._buffer = [candle]
            return True
        self._buffer.append(candle)
        return False

    @property
    def parent_candle(self) -> Optional["Candle"]:
        """The most recently CLOSED parent candle, or None before the first close.

        Never the in-progress accumulator — that would be the lookahead leak this module
        exists to avoid. `self._buffer` is intentionally private and unexposed."""
        return self._history[-1] if self._history else None

    @property
    def parent_history(self) -> "list[Candle]":
        """Up to `keep` most recently CLOSED parent candles, oldest first. Defensive copy."""
        return list(self._history)
