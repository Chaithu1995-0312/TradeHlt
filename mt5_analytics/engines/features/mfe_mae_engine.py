"""
mfe_mae_engine — MFE/MAE in the trade's own R, via reused `horizon_excursion`.

Adapter trick (the highest-value reuse in the architecture): `horizon_excursion` normalizes
by `risk = sl_atr_mult·atr`. By building the research `Signal` with `atr = risk_distance`
and `sl_atr_mult = 1.0`, the returned `mfe_r`/`mae_r` are already in the trade's OWN R — no
excursion math is reimplemented. Exit-agnostic over the holding window; no-lookahead is
inherited from `horizon_excursion`'s own guard.
"""
from __future__ import annotations

from datetime import datetime

from research.contracts import Signal  # type: ignore
from research.measurement.forward_walk import horizon_excursion  # type: ignore

_NULL = {
    "mfe_r": None,
    "mae_r": None,
    "reached_0_5r": None,
    "reached_1r": None,
    "reached_1_5r": None,
    "reached_2r": None,
    "reached_3r": None,
    "favorable_first": None,
    "bars_to_first_1r": None,
}


def _entry_dt(episode) -> datetime:
    return datetime.fromisoformat(episode.entry_time.replace("Z", "+00:00"))


def partial(episode, window, entry_index: int, risk: float) -> dict:
    """Excursion partial. Returns null fields when risk is undefined or no forward bars."""
    future = list(window)[entry_index + 1:]
    if risk <= 0.0 or not future:
        return dict(_NULL)
    signal = Signal(
        instrument=episode.symbol,
        timestamp=_entry_dt(episode),
        entry_index=entry_index,
        direction=episode.direction,
        entry=episode.entry_vwap,
        sl_atr_mult=1.0,        # ⇒ risk == atr == risk_distance ⇒ mfe_r/mae_r in true R
        tp_atr_mult=1.0,
        atr=risk,
        meta={},
    )
    return horizon_excursion(signal, future, max_forward=len(future))
