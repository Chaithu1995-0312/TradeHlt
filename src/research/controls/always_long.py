"""always_long.py — the anti-drift control.

Answers the most dangerous question in crypto research: *does the apparent edge merely
capture the market's structural upward drift?* In a bull market everything long looks
smart. A candidate hypothesis must beat always-long in the qualification gate (M4) — so
`PF 1.15` vs always-long `PF 1.14` correctly resolves to REJECT.
"""

from __future__ import annotations

from typing import Sequence

from research.contracts import Signal
from research.indicators import atr


class AlwaysLong:
    name = "always_long"
    family = "control"
    economic_rationale = "structural drift control — captures market beta; not a real edge"

    def __init__(self, *, stride: int = 1, sl_atr_mult: float = 1.0,
                 tp_atr_mult: float = 2.0, atr_period: int = 14):
        self.stride = stride
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.atr_period = atr_period

    def detect(self, window: Sequence, features: dict, ctx: dict) -> list[Signal]:
        bar = window[-1]
        if self.stride > 1 and (bar.index % self.stride) != 0:
            return []
        a = atr(window, self.atr_period)
        if a <= 0:
            return []
        return [Signal(
            instrument=ctx.get("instrument", "UNKNOWN"), timestamp=bar.timestamp,
            entry_index=bar.index, direction="long", entry=float(bar.close),
            sl_atr_mult=self.sl_atr_mult, tp_atr_mult=self.tp_atr_mult, atr=a,
            meta={"control": "always_long"},
        )]
