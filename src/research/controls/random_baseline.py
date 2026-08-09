"""random_baseline.py — null controls: random entries.

Answers "does anything beat noise?" Two parametrized variants are registered:
  * uniform 50/50 long-short
  * biased 70/30 long  (does a directional tilt alone explain an apparent edge?)

Direction is deterministic given (seed, instrument, entry_index) so runs are
reproducible regardless of call order. A real hypothesis must beat these in the
qualification gate (M4).
"""

from __future__ import annotations

import random
from typing import Sequence

from research.contracts import Signal
from research.indicators import atr


class RandomBaseline:
    family = "control"
    economic_rationale = "null control — random entries; a real edge MUST beat this"

    def __init__(self, name: str = "random_uniform", long_prob: float = 0.5, *,
                 seed: int = 42, stride: int = 1,
                 sl_atr_mult: float = 1.0, tp_atr_mult: float = 2.0, atr_period: int = 14):
        self.name = name
        self.long_prob = long_prob
        self.seed = seed
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
        instrument = ctx.get("instrument", "UNKNOWN")
        rng = random.Random(f"{self.seed}:{instrument}:{bar.index}")
        direction = "long" if rng.random() < self.long_prob else "short"
        return [Signal(
            instrument=instrument, timestamp=bar.timestamp, entry_index=bar.index,
            direction=direction, entry=float(bar.close),
            sl_atr_mult=self.sl_atr_mult, tp_atr_mult=self.tp_atr_mult, atr=a,
            meta={"control": "random", "long_prob": self.long_prob},
        )]
