"""mean_reversion.py — the OPPOSITE behavior, shipped at M2 to prove no continuation bias.

Price stretched far from its moving average is taken as a reversion signal AGAINST the
stretch. This exists to demonstrate that the architecture privileges no behavior: it
implements the identical Hypothesis interface and runs through the identical pipeline as
expansion_breakout. If continuation is real, this should fail to qualify — and vice
versa. The platform earns no edge from *believing* in either.
"""

from __future__ import annotations

from typing import Sequence

from research.contracts import Signal
from research.indicators import atr, sma
from research.registry import register_hypothesis


@register_hypothesis
class MeanReversion:
    name = "mean_reversion"
    family = "mean_reversion"
    economic_rationale = (
        "liquidity exhaustion / profit-taking: price stretched far from its mean tends "
        "to revert as the move runs out of marginal buyers/sellers"
    )

    def __init__(self, ma_period: int = 20, stretch_z: float = 1.5,
                 sl_atr_mult: float = 1.0, tp_atr_mult: float = 2.0, atr_period: int = 14):
        self.ma_period = ma_period
        self.stretch_z = stretch_z
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.atr_period = atr_period

    def detect(self, window: Sequence, features: dict, ctx: dict) -> list[Signal]:
        if len(window) < self.ma_period + 1:
            return []
        bar = window[-1]
        a = atr(window, self.atr_period)
        if a <= 0:
            return []
        mean = sma(window, self.ma_period)
        dist = bar.close - mean

        if dist > self.stretch_z * a:
            direction = "short"        # stretched up -> revert down
        elif dist < -self.stretch_z * a:
            direction = "long"         # stretched down -> revert up
        else:
            return []

        return [Signal(
            instrument=ctx.get("instrument", "UNKNOWN"), timestamp=bar.timestamp,
            entry_index=bar.index, direction=direction, entry=float(bar.close),
            sl_atr_mult=self.sl_atr_mult, tp_atr_mult=self.tp_atr_mult, atr=a,
            meta={"stretch_atr": round(dist / a, 4) if a else 0.0, "ma_period": self.ma_period},
        )]
