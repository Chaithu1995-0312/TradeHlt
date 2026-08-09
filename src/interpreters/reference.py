"""
reference.py — proof-of-contract interpreters. NOT real interpreters.

`NullInterpreter` emits nothing (the no-event baseline). `ConstantDirectionInterpreter`
emits one directional event on a fixed cadence (the interpreter analog of the research
`AlwaysLong` control). They exist ONLY to prove the contract + adapter round-trip
through `forward_walk` + `QualificationGate`. Real interpreters (P&F/Wyckoff/…) come in
later plans and must satisfy the same `Interpreter` contract.
"""

from __future__ import annotations

from typing import Sequence, Tuple

from config_layer.crt_engine_v2 import Candle, Direction
from research.indicators import atr, sma

from interpreters.contract import (
    BaseInterpreter, EventKind, InterpreterEvent,
)


class NullInterpreter(BaseInterpreter):
    """Emits no events, neutral confidence. The no-signal baseline."""
    name = "null"
    family = "control"
    economic_rationale = "null baseline: emits no events (contract floor)."

    def _observe(self, window: Sequence[Candle], features: dict,
                 ctx: dict) -> Tuple[list[InterpreterEvent], float]:
        return [], 0.0

    def explain(self) -> dict:
        return {"observation": "no events", "reasoning": "null baseline", "unknowns": []}


class ConstantDirectionInterpreter(BaseInterpreter):
    """Emits one directional BREAKOUT event every `cadence` bars (by bar index),
    fixed SL/TP ATR multiples — the interpreter analog of the `AlwaysLong` control.
    Deterministic: geometry is a pure function of the window's last bar + window ATR."""
    family = "control"
    economic_rationale = (
        "constant-direction control: a fixed-direction breakout every N bars; "
        "exists to anchor the interpreter→adapter→qualification round-trip, not as an edge."
    )

    def __init__(self, direction: Direction = Direction.LONG, *, cadence: int = 5,
                 sl_atr_mult: float = 1.0, tp_atr_mult: float = 2.0, atr_period: int = 14):
        self.direction = direction
        self.cadence = max(1, int(cadence))
        self.sl_atr_mult = float(sl_atr_mult)
        self.tp_atr_mult = float(tp_atr_mult)
        self.atr_period = int(atr_period)
        self.name = f"const_{direction.value.lower()}"

    def _observe(self, window: Sequence[Candle], features: dict,
                 ctx: dict) -> Tuple[list[InterpreterEvent], float]:
        bar = window[-1]
        idx = getattr(bar, "index", None)
        if idx is None or idx % self.cadence != 0:
            return [], 0.0          # non-directional silence between cadence bars
        a = atr(window, self.atr_period)
        if a <= 0:
            a = 1.0                 # degenerate window → unit ATR (still a valid trade geometry)
        ev = InterpreterEvent(
            kind=EventKind.BREAKOUT,
            confidence=1.0,
            strength=0.5,
            direction=self.direction,
            entry=bar.close,
            sl_atr_mult=self.sl_atr_mult,
            tp_atr_mult=self.tp_atr_mult,
            atr=a,
            meta={"cadence": self.cadence},
        )
        return [ev], 1.0

    def explain(self) -> dict:
        return {
            "observation": f"constant {self.direction.value} breakout every {self.cadence} bars",
            "reasoning": "control interpreter — no economic edge claimed",
            "unknowns": [],
        }


class MovingAverageCrossInterpreter(BaseInterpreter):
    """The simplest *realistic* reference interpreter — a fast/slow SMA cross.

    NOT chosen for edge (MA crosses are weak); chosen because it is deterministic,
    explainable, and exercises every contract surface (EventKind/Direction reuse,
    trace_id, observation_time, explain(), meta opacity, adapter, qualification)
    WITHOUT P&F complexity. Plan 4 proves the end-to-end chain on real data; the
    expected verdict is NOT PROMOTE — a working chain is the win, not an edge.

    Pure / deterministic / no-lookahead: reads only `window`. Emits one directional
    `BREAKOUT` event on the bar where the fast SMA crosses the slow SMA; otherwise no
    events (non-directional silence). Geometry uses the window ATR (SpineHypothesis
    convention); confidence/strength are bounded functions of the MA separation.
    """
    family = "control"
    economic_rationale = (
        "moving-average cross reference: fast SMA crossing slow SMA; exists to prove "
        "the interpreter→adapter→forward_walk→QualificationGate chain on real data, "
        "not as a claimed edge."
    )

    def __init__(self, *, fast_period: int = 10, slow_period: int = 30,
                 sl_atr_mult: float = 1.0, tp_atr_mult: float = 2.0, atr_period: int = 14):
        if fast_period >= slow_period:
            raise ValueError("fast_period must be < slow_period")
        self.fast_period = int(fast_period)
        self.slow_period = int(slow_period)
        self.sl_atr_mult = float(sl_atr_mult)
        self.tp_atr_mult = float(tp_atr_mult)
        self.atr_period = int(atr_period)
        self.name = f"ma_cross_{fast_period}_{slow_period}"
        self._last_explain: dict = {
            "observation": "no cross yet", "reasoning": "", "unknowns": [],
        }

    def _observe(self, window: Sequence[Candle], features: dict,
                 ctx: dict) -> Tuple[list[InterpreterEvent], float]:
        # Need the slow window on BOTH the current and previous bar to detect a cross.
        if len(window) < self.slow_period + 1:
            return [], 0.0

        prev_fast = sma(window[:-1], self.fast_period)
        prev_slow = sma(window[:-1], self.slow_period)
        cur_fast = sma(window, self.fast_period)
        cur_slow = sma(window, self.slow_period)

        crossed_up = prev_fast <= prev_slow and cur_fast > cur_slow
        crossed_down = prev_fast >= prev_slow and cur_fast < cur_slow
        if not (crossed_up or crossed_down):
            return [], 0.0

        bar = window[-1]
        a = atr(window, self.atr_period)
        if a <= 0:
            a = 1.0
        sep = abs(cur_fast - cur_slow) / a          # MA separation in ATR units
        conf = min(sep, 1.0)                          # bounded ∈ [0,1]
        direction = Direction.LONG if crossed_up else Direction.SHORT
        self._last_explain = {
            "observation": f"{'up' if crossed_up else 'down'} cross "
                           f"(fast={cur_fast:.6f} slow={cur_slow:.6f})",
            "reasoning": f"SMA{self.fast_period} crossed "
                         f"{'above' if crossed_up else 'below'} SMA{self.slow_period}",
            "unknowns": [],
        }
        ev = InterpreterEvent(
            kind=EventKind.BREAKOUT,
            confidence=conf,
            strength=conf,                           # for a MA cross, separation ⇒ both
            direction=direction,
            entry=bar.close,
            sl_atr_mult=self.sl_atr_mult,
            tp_atr_mult=self.tp_atr_mult,
            atr=a,
            meta={"fast": cur_fast, "slow": cur_slow, "sep_atr": sep},
        )
        return [ev], conf

    def explain(self) -> dict:
        return dict(self._last_explain)
