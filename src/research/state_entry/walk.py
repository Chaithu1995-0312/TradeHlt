"""EntryUnit -> R under the SEM-017 two-target object (MC-STATEENTRY labels + exits).

Two exit ARMS, one kernel (``research.oracle.multi_tp_walk``):

    close_only (PRIMARY)  every forward bar is fed with open=high=low=close plus
                          AdverseFill(model_gaps=True). A stop fires only when a bar CLOSES
                          at/through it and fills at that close (losses can exceed -1R); a
                          target fires only on a close at/through it and fills at the level.
                          No intrabar ordering is assumed.
    sl_first (REFERENCE)  real high/low, tie_break="production" (SL-first, F-088).

Two GEOMETRY arms: ``structural`` (the engine's own stop arithmetic) and ``fixed_atr``
(the oracle labeler's fixed_atr arm). Both are mirrored, not imported, so this module
stays a pure function of its inputs.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from research.indicators import atr as research_atr
from research.measurement.forward_walk import AdverseFill
from research.oracle.multi_tp_walk import TIE_BREAK_PRODUCTION, multi_tp_walk
from research.state_entry.extract import (
    ENTER_SWEEP,
    EXECUTION_AT_APPROVAL,
    EXECUTION_LEGACY,
    Bar,
    EntryUnit,
)

ARM_CLOSE_ONLY = "close_only"
ARM_SL_FIRST = "sl_first"
ARMS = (ARM_CLOSE_ONLY, ARM_SL_FIRST)
PRIMARY_ARM = ARM_CLOSE_ONLY

GEOM_STRUCTURAL = "structural"
GEOM_FIXED_ATR = "fixed_atr"
GEOMETRIES = (GEOM_STRUCTURAL, GEOM_FIXED_ATR)

HORIZONS = (4, 8, 16, 40, 96, 192, 480)
ATR_PERIOD = 14

# Kernel convention mirrored from the production trade (multi_tp_walk docstring).
_TRAIL_FRACTION = 0.5
# A close-only stop fills at the close; slippage is charged by the cost model, not here.
_CLOSE_ONLY_FILL = AdverseFill(stop_slippage=0.0, model_gaps=True)


@dataclass(frozen=True)
class Geometry:
    """Declared trade geometry. All fields come from the production config at run time."""

    sl_atr_buffer: float          # crt_engine.sl_atr_buffer
    tp1_mult: float               # crt_engine.tp1_atr_multiplier (R multiple)
    tp2_mult: float               # crt_engine.tp2_atr_multiplier (R multiple)
    fixed_sl_atr_mult: float      # sl_tp_comparison.legacy_sl_atr_mult
    partial_fraction: float       # execution_planner.partial_tp_fraction


@dataclass(frozen=True)
class Levels:
    entry: float
    sl: float
    tp1: float
    tp2: float
    atr_abs: float

    @property
    def risk(self) -> float:
        return abs(self.entry - self.sl)


def close_only_bars(bars: Sequence[Bar]) -> list[Bar]:
    """The PRIMARY arm's view of the corpus: every bar collapsed to its close."""
    return [Bar(timestamp=b.timestamp, open=b.close, high=b.close, low=b.close,
                close=b.close, index=b.index) for b in bars]


def atr_at(bars: Sequence[Bar], row: int) -> float:
    """Price-unit ATR at ``row`` from bars <= row only (causal)."""
    return research_atr(bars[max(0, row - ATR_PERIOD): row + 1], ATR_PERIOD)


def unit_levels(unit: EntryUnit, bars: Sequence[Bar], geom: str, g: Geometry) -> Optional[Levels]:
    """Entry/SL/TP1/TP2 for one unit under one geometry, or None when the engine's
    inverted-SL guard would refuse it (or ATR cannot be computed)."""
    is_long = unit.direction == "long"
    sign = 1.0 if is_long else -1.0
    entry = unit.entry_price
    atr_abs = unit.engine_atr if unit.engine_atr else atr_at(bars, unit.entry_row)
    if not atr_abs > 0:
        return None

    if unit.entry_kind == EXECUTION_LEGACY and geom == GEOM_STRUCTURAL:
        # The engine's own levels, untouched: the parity object (F-088 / F-110).
        sl, tp1, tp2 = unit.engine_levels
        return Levels(entry, sl, tp1, tp2, atr_abs)

    if geom == GEOM_FIXED_ATR:
        sl = entry - sign * g.fixed_sl_atr_mult * atr_abs
    elif unit.entry_kind == EXECUTION_AT_APPROVAL:
        sl = unit.engine_levels[0]        # the engine's stop level; only the fill moves
    elif unit.entry_kind == ENTER_SWEEP or unit.displacement_row is None:
        sc = bars[unit.sweep_row]         # sl_anchor="sweep_extreme" arithmetic
        sl = (sc.low - g.sl_atr_buffer * atr_abs) if is_long else (sc.high + g.sl_atr_buffer * atr_abs)
    else:
        dc = bars[unit.displacement_row]  # sl_anchor="displacement" arithmetic (active)
        sl = (dc.low - g.sl_atr_buffer * atr_abs) if is_long else (dc.high + g.sl_atr_buffer * atr_abs)

    if (is_long and sl >= entry) or ((not is_long) and sl <= entry):
        return None
    risk = abs(entry - sl)
    return Levels(entry, sl, entry + sign * g.tp1_mult * risk, entry + sign * g.tp2_mult * risk, atr_abs)


def walk_unit(unit: EntryUnit, levels: Levels, bars: Sequence[Bar], *, arm: str,
              horizon: int, partial_fraction: float):
    """One multi_tp_walk over the ``horizon`` bars strictly after the entry bar.

    ``bars`` must already be the arm's view (``close_only_bars`` for the primary arm).
    Returns None when the corpus has fewer than ``horizon`` forward bars.
    """
    start = unit.entry_row + 1
    future = bars[start: start + horizon]
    if len(future) < horizon:
        return None
    return multi_tp_walk(
        levels.entry, unit.direction, levels.sl, levels.tp1, levels.tp2, future,
        partial_fraction=partial_fraction,
        tie_break=TIE_BREAK_PRODUCTION,
        trail_fraction=_TRAIL_FRACTION,
        max_forward=horizon,
        adverse_fill=_CLOSE_ONLY_FILL,
        entry_index=unit.entry_row,
    )


def walk_all(units: Sequence[EntryUnit], bars: Sequence[Bar], g: Geometry, cost_model, *,
             horizons: Sequence[int] = HORIZONS, arms: Sequence[str] = ARMS,
             geometries: Sequence[str] = GEOMETRIES) -> tuple[list[dict], dict]:
    """Every unit x geometry x horizon x arm -> one row. Returns (rows, drop counts)."""
    views = {ARM_CLOSE_ONLY: close_only_bars(bars), ARM_SL_FIRST: list(bars)}
    rows: list[dict] = []
    drops: dict[str, int] = {}
    for u in units:
        for geom in geometries:
            lv = unit_levels(u, bars, geom, g)
            if lv is None:
                drops[f"inverted_or_no_atr_{geom}"] = drops.get(f"inverted_or_no_atr_{geom}", 0) + 1
                continue
            for arm in arms:
                for h in horizons:
                    o = walk_unit(u, lv, views[arm], arm=arm, horizon=h,
                                  partial_fraction=g.partial_fraction)
                    if o is None:
                        k = f"insufficient_forward_h{h}"
                        drops[k] = drops.get(k, 0) + 1
                        continue
                    cost_r = cost_model.cost_r(lv.entry, lv.risk, exit_kind=o.exit_kind,
                                               direction=u.direction)
                    rows.append({
                        "entry_kind": u.entry_kind,
                        "direction": u.direction,
                        "geometry": geom,
                        "arm": arm,
                        "horizon": h,
                        "entry_row": u.entry_row,
                        "entry_ts": u.event_ts,
                        "setup_sweep_row": u.setup_sweep_row,
                        "hour": bars[u.entry_row].timestamp.hour,
                        "entry": lv.entry,
                        "sl": lv.sl,
                        "tp1": lv.tp1,
                        "tp2": lv.tp2,
                        "atr_abs": lv.atr_abs,
                        "sl_atr": lv.risk / lv.atr_abs,
                        "outcome": o.outcome,
                        "exit_kind": o.exit_kind,
                        "duration": o.duration_candles,
                        "y_gross": o.rr_gross,
                        "cost_r": cost_r,
                        "y_net": o.rr_gross - cost_r,
                    })
    return rows, drops
