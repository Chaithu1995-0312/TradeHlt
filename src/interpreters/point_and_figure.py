"""
point_and_figure.py — PNF-v1, the FIRST real interpreter (Plan 5). Shadow / measure-only.

Point & Figure is a price-only, time-agnostic chart: prices are quantized to a box grid
and grouped into alternating columns (X = up, O = down). PNF-v1 emits exactly two signals:
  • DOUBLE_TOP_BREAKOUT  → LONG  (an X column tops one box above the prior X column's top)
  • DOUBLE_BOTTOM_BREAKDOWN → SHORT (an O column bottoms one box below the prior O column)

FROZEN experiment definition (owner directive — NO sweep, NO optimization, NO other patterns):
  box = 0.5 × ATR(20) · 3-box reversal · double-top / double-bottom only.
Identity is **PNF-v1** (name='pnf' + version()='1' ⇒ trace_id 'PNF-v1-…'); a future PNF-v2 is
version()='2' and cannot overwrite this experiment's history.

Pure / deterministic / no-lookahead: columns are rebuilt from the window's closes only; a signal
fires ONLY when the breakout completes on the window's LAST bar. The interpreter claims no edge —
it is run through the existing adapter → forward_walk → QualificationGate chain to be measured
honestly (REJECT is an acceptable, valuable verdict).
"""

from __future__ import annotations

import math
from typing import Sequence, Tuple

from config_layer.crt_engine_v2 import Candle, Direction
from research.indicators import atr

from interpreters.contract import BaseInterpreter, EventKind, InterpreterEvent


def _pnf_signals(closes: Sequence[float], box: float, reversal: int):
    """Build P&F columns from `closes` and return [(bar_idx, EventKind, magnitude_boxes)].

    Pure: a function of (closes, box, reversal) only. A double-top/bottom is recorded at the
    bar where the current column's extreme first passes the PRIOR same-direction column's extreme.
    """
    out: list[tuple[int, EventKind, int]] = []
    if box <= 0 or len(closes) < 2:
        return out

    def bidx(p: float) -> int:
        return math.floor(p / box)

    direction: str | None = None          # 'X' (up) | 'O' (down) | None (not yet established)
    col_top = col_bottom = bidx(closes[0])
    prev_x_top: int | None = None         # top of the last COMPLETED X column
    prev_o_bottom: int | None = None      # bottom of the last COMPLETED O column

    for i in range(1, len(closes)):
        b = bidx(closes[i])
        if direction is None:
            if b > col_top:
                direction, col_top = "X", b
            elif b < col_bottom:
                direction, col_bottom = "O", b
        elif direction == "X":
            if b > col_top:
                col_top = b
                if prev_x_top is not None and col_top > prev_x_top:
                    out.append((i, EventKind.DOUBLE_TOP_BREAKOUT, col_top - prev_x_top))
            elif b <= col_top - reversal:           # 3-box reversal → flip to O
                prev_x_top = col_top                 # this X column is now the prior X
                direction, col_bottom = "O", b
        else:  # direction == "O"
            if b < col_bottom:
                col_bottom = b
                if prev_o_bottom is not None and col_bottom < prev_o_bottom:
                    out.append((i, EventKind.DOUBLE_BOTTOM_BREAKDOWN, prev_o_bottom - col_bottom))
            elif b >= col_bottom + reversal:        # 3-box reversal → flip to X
                prev_o_bottom = col_bottom
                direction, col_top = "X", b
    return out


class PointAndFigureInterpreter(BaseInterpreter):
    """PNF-v1 — frozen. See module docstring. No parameter sweep; if REJECTed, freeze."""

    name = "pnf"                          # trace_id ⇒ 'PNF-v1-…'
    family = "interpreter"                # candidate (not a control)
    FROZEN_ID = "PNF-v1"
    economic_rationale = (
        "point_and_figure double-top/double-bottom breakout: a column of demand (X) exceeding the "
        "prior demand peak (or supply O breaking the prior trough) is the classic P&F continuation "
        "signal. Measured shadow-only to test whether it carries a standalone edge vs controls."
    )

    def __init__(self, *, box_atr_frac: float = 0.5, atr_period: int = 20, reversal: int = 3,
                 sl_atr_mult: float = 1.0, tp_atr_mult: float = 2.0):
        # FROZEN config — do NOT sweep these. (Defaults ARE the experiment.)
        self.box_atr_frac = float(box_atr_frac)
        self.atr_period = int(atr_period)
        self.reversal = int(reversal)
        self.sl_atr_mult = float(sl_atr_mult)
        self.tp_atr_mult = float(tp_atr_mult)
        self._last_explain: dict = {"observation": "no signal", "reasoning": "", "unknowns": []}

    def version(self) -> str:
        return "1"                        # PNF-v1; bump to "2" for a NEW ontology, never a tweak

    def _observe(self, window: Sequence[Candle], features: dict,
                 ctx: dict) -> Tuple[list[InterpreterEvent], float]:
        if len(window) < self.atr_period + 1:
            return [], 0.0
        a = atr(window, self.atr_period)
        box = self.box_atr_frac * a
        if box <= 0:
            return [], 0.0

        closes = [c.close for c in window]
        signals = _pnf_signals(closes, box, self.reversal)
        if not signals:
            return [], 0.0

        last_idx = len(window) - 1
        # Fire ONLY if a breakout completed on the current (last) bar — no-lookahead.
        fired = [s for s in signals if s[0] == last_idx]
        if not fired:
            return [], 0.0
        _, kind, mag = fired[-1]

        direction = Direction.LONG if kind is EventKind.DOUBLE_TOP_BREAKOUT else Direction.SHORT
        conf = min(mag / max(self.reversal, 1), 1.0)     # bounded ∈ [0,1]; ≥ ~1 box at breakout
        bar = window[-1]
        self._last_explain = {
            "observation": f"{kind.value} (mag={mag} boxes, box={box:.6f})",
            "reasoning": f"P&F {('X' if direction is Direction.LONG else 'O')}-column passed the "
                         f"prior {'top' if direction is Direction.LONG else 'bottom'}",
            "unknowns": [],
        }
        ev = InterpreterEvent(
            kind=kind,
            confidence=conf,
            strength=conf,
            direction=direction,
            entry=bar.close,
            sl_atr_mult=self.sl_atr_mult,
            tp_atr_mult=self.tp_atr_mult,
            atr=a,
            meta={"box": box, "reversal": self.reversal, "mag_boxes": mag},
        )
        return [ev], conf

    def explain(self) -> dict:
        return dict(self._last_explain)
