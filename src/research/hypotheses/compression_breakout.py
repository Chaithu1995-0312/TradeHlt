"""compression_breakout.py — Program-4b Stage-2 economic consumer (transition family).

The non-directional Stage-1 gate asks "does a compression state predict forward expansion?".
This hypothesis is the ONLY thing that may convert a Stage-1 survivor into an economic claim:
after a low-volatility COMPRESSION regime, take the FIRST range break in the break direction —
the standard "energy stored → expansion leg" construction.

It is a genuinely NEW trigger, NOT the falsified `expansion_breakout`:
  * `expansion_breakout` fires when the CURRENT bar is itself a strong expansion bar closing
    beyond a lookback range (no regime precondition).
  * `compression_breakout` fires only when the bar BEFORE the break was a COMPRESSION state
    (a volatility-cycle precondition) and the current bar breaks the compression range.

It flows through the IDENTICAL frozen machinery (forward_walk intrabar_fixed + CostModel + the
M4 QualificationGate) as every other hypothesis — promotion stays expectancy-first. Per the
Authority Ladder it earns NO authority unless the gate PROMOTEs it. Pure, no-lookahead: detect()
reads only `window`.
"""

from __future__ import annotations

from typing import Sequence

from research.candle_state.encoder import VOL_COMPRESSION, CandleStateEncoder
from research.contracts import Signal
from research.indicators import atr
from research.registry import register_hypothesis


@register_hypothesis
class CompressionBreakout:
    name = "compression_breakout"
    family = "transition"
    economic_rationale = (
        "volatility cycle / transition: a low-volatility COMPRESSION regime stores energy; the "
        "first range break after compression tends to initiate an expansion leg. Program-4b "
        "economic consumer of the non-directional compression->expansion transition signal."
    )

    def __init__(self, compression_lookback: int = 5, sl_atr_mult: float = 1.0,
                 tp_atr_mult: float = 2.0, atr_period: int = 14,
                 encoder: CandleStateEncoder | None = None):
        self.compression_lookback = compression_lookback
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.atr_period = atr_period
        self.encoder = encoder or CandleStateEncoder(atr_period=atr_period)

    def detect(self, window: Sequence, features: dict, ctx: dict) -> list[Signal]:
        bars = list(window)
        if len(bars) < self.compression_lookback + 2:
            return []
        a = atr(bars, self.atr_period)
        if a <= 0:
            return []

        setup = bars[:-1]                       # everything up to the bar before the break
        # Precondition: the bar immediately before the break is a COMPRESSION state.
        if self.encoder.encode(setup).vol != VOL_COMPRESSION:
            return []

        comp = setup[-self.compression_lookback:]
        comp_high = max(float(b.high) for b in comp)
        comp_low = min(float(b.low) for b in comp)
        bar = bars[-1]

        if float(bar.close) > comp_high:
            direction = "long"
        elif float(bar.close) < comp_low:
            direction = "short"
        else:
            return []

        return [Signal(
            instrument=ctx.get("instrument", "UNKNOWN"), timestamp=bar.timestamp,
            entry_index=bar.index, direction=direction, entry=float(bar.close),
            sl_atr_mult=self.sl_atr_mult, tp_atr_mult=self.tp_atr_mult, atr=a,
            meta={"compression_lookback": self.compression_lookback,
                  "comp_high": round(comp_high, 6), "comp_low": round(comp_low, 6)},
        )]
