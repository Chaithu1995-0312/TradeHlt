"""expansion_breakout.py — continuation behavior (hypothesis #1, NOT privileged).

A strong expansion bar that closes beyond the recent range is taken as a continuation
signal in the bar's direction. This is just one plugin among many; it flows through the
identical measurement/qualification machinery as every other behavior (incl. its
opposite, mean_reversion).
"""

from __future__ import annotations

from typing import Sequence

from research.contracts import Signal
from research.indicators import atr
from research.registry import register_hypothesis


@register_hypothesis
class ExpansionBreakout:
    name = "expansion_breakout"
    family = "continuation"
    economic_rationale = (
        "under-reaction / trend persistence: a strong expansion bar breaking recent "
        "structure tends to continue as momentum participants pile in"
    )

    def __init__(self, lookback: int = 5, body_ratio_min: float = 0.5,
                 sl_atr_mult: float = 1.0, tp_atr_mult: float = 2.0, atr_period: int = 14):
        self.lookback = lookback
        self.body_ratio_min = body_ratio_min
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.atr_period = atr_period

    def detect(self, window: Sequence, features: dict, ctx: dict) -> list[Signal]:
        if len(window) < self.lookback + 2:
            return []
        bar = window[-1]
        a = atr(window, self.atr_period)
        if a <= 0:
            return []
        prior = window[-(self.lookback + 1):-1]
        prior_high = max(float(b.high) for b in prior)
        prior_low = min(float(b.low) for b in prior)

        if bar.is_bullish and bar.close > prior_high and bar.body_ratio >= self.body_ratio_min:
            direction = "long"
        elif (not bar.is_bullish) and bar.close < prior_low and bar.body_ratio >= self.body_ratio_min:
            direction = "short"
        else:
            return []

        return [Signal(
            instrument=ctx.get("instrument", "UNKNOWN"), timestamp=bar.timestamp,
            entry_index=bar.index, direction=direction, entry=float(bar.close),
            sl_atr_mult=self.sl_atr_mult, tp_atr_mult=self.tp_atr_mult, atr=a,
            meta={"body_ratio": round(bar.body_ratio, 4), "lookback": self.lookback},
        )]
