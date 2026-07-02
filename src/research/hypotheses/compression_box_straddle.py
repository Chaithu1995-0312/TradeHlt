"""compression_box_straddle.py — Program-9 Stage-2 economic consumer (transition family).

The SOLE permitted Stage-2 consumer of Program 9 (pre-reg D7,
docs/research/preregistration-program-9.md). F-040 proved the expansion forecast is real
but a spot DIRECTIONAL consumer cannot express its long-volatility payoff. This
hypothesis is the non-directional construction: on the FIRST bar of an M5 COMPRESSION
run, arm a both-sided stop-entry straddle at the compression box edges — long stop above
the box high, short stop below the box low, first touch wins, other side cancelled (OCO).
Payoff ≈ long volatility: it profits iff the forecast expansion actually leaves the box,
in either direction.

It is genuinely NEW, not the falsified `compression_breakout`:
  * `compression_breakout` (Program 4b) requires the CURRENT bar to already break the box
    in a specific direction — a directional close-through entry (Stage-2 FAIL, F-040).
  * `compression_box_straddle` emits at the COMPRESSION bar itself with direction "oco";
    the side is decided later, intrabar, by the first edge touch — no directional bet at
    detect time, and no lookahead (the fill is simulated by `forward_walk_oco`, D1–D3).

Flows through the IDENTICAL frozen machinery (forward_walk_oco delegates every filled
straddle's exit to the unchanged forward_walk intrabar_fixed + CostModel + the M4
QualificationGate). Per the Authority Ladder it earns NO authority unless the gate
PROMOTEs it. Pure, no-lookahead: detect() reads only `window`.
"""

from __future__ import annotations

from typing import Sequence

from research.candle_state.encoder import VOL_COMPRESSION, CandleStateEncoder
from research.contracts import Signal
from research.indicators import atr
from research.registry import register_hypothesis


@register_hypothesis
class CompressionBoxStraddle:
    name = "compression_box_straddle"
    family = "transition"
    economic_rationale = (
        "volatility cycle / transition, non-directional: a low-volatility COMPRESSION "
        "regime stores energy and forward expansion is forecastable (F-040 Stage-1), but "
        "the DIRECTION of the release is not (F-019/F-020). A both-sided stop-entry "
        "straddle at the box edges is the long-volatility construction that monetizes "
        "expansion without a directional bet — Program-9 sole Stage-2 consumer (D7)."
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

        # Precondition (pre-reg D4): the CURRENT bar is a COMPRESSION state AND the
        # previous bar was NOT — fire only on the first bar of a compression run, so
        # consecutive compression bars never arm overlapping straddles.
        if self.encoder.encode(bars).vol != VOL_COMPRESSION:
            return []
        if self.encoder.encode(bars[:-1]).vol == VOL_COMPRESSION:
            return []

        box = bars[-self.compression_lookback:]
        box_high = max(float(b.high) for b in box)
        box_low = min(float(b.low) for b in box)
        if not box_high > box_low:
            return []
        bar = bars[-1]

        return [Signal(
            instrument=ctx.get("instrument", "UNKNOWN"), timestamp=bar.timestamp,
            entry_index=bar.index, direction="oco",
            entry=(box_high + box_low) / 2.0,   # telemetry only; real entry = touched edge
            sl_atr_mult=self.sl_atr_mult, tp_atr_mult=self.tp_atr_mult, atr=a,
            meta={"compression_lookback": self.compression_lookback,
                  "box_high": round(box_high, 6), "box_low": round(box_low, 6)},
        )]
