"""
entry_tracker — price-path shape over the holding window (pure, per-episode).

Records peak/trough prices, bars-to-peak / bars-to-worst, and whether the trade went
adverse before it peaked ("did winners first go negative"). This unlocks later
breakeven / trailing-stop / exit studies without touching the feature purity invariant.
Direction-aware; no-lookahead by construction (only bars strictly after entry).
"""
from __future__ import annotations

from .features._bars import Bar  # noqa: F401  (type clarity)
from .position_reconstructor import LONG  # reuse the canonical direction token

_NULL = {
    "path_peak_price": None,
    "path_trough_price": None,
    "bars_to_peak": None,
    "bars_to_max_adverse": None,
    "went_adverse_first": None,
}


def partial(episode, window, entry_index: int) -> dict:
    future = list(window)[entry_index + 1:]
    if not future:
        return dict(_NULL)

    entry = episode.entry_vwap
    is_long = episode.direction == LONG

    best_fav = None        # most favorable excursion (price units, >= 0 ideal)
    worst_adv = None       # most adverse excursion (<= 0 ideal)
    bars_to_peak = None
    bars_to_worst = None
    first_adverse_bar = None
    peak_price = None
    trough_price = None

    for i, bar in enumerate(future, start=1):
        hi, lo = float(bar.high), float(bar.low)
        if is_long:
            fav, adv = hi - entry, lo - entry
            fav_px, adv_px = hi, lo
        else:
            fav, adv = entry - lo, entry - hi
            fav_px, adv_px = lo, hi

        if best_fav is None or fav > best_fav:
            best_fav, bars_to_peak, peak_price = fav, i, fav_px
        if worst_adv is None or adv < worst_adv:
            worst_adv, bars_to_worst, trough_price = adv, i, adv_px
        if first_adverse_bar is None and adv < 0.0:
            first_adverse_bar = i

    went_adverse_first = (
        first_adverse_bar is not None
        and bars_to_peak is not None
        and first_adverse_bar <= bars_to_peak
    )
    return {
        "path_peak_price": round(float(peak_price), 10),
        "path_trough_price": round(float(trough_price), 10),
        "bars_to_peak": bars_to_peak,
        "bars_to_max_adverse": bars_to_worst,
        "went_adverse_first": bool(went_adverse_first),
    }
