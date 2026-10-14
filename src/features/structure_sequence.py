"""Swing-sequence states — FM-121 higher_low, FM-122 lower_high, FM-123 sideways.

These classify an already-published causal swing series. They are not the one-bar pierce
events FM-055 higher_high / FM-056 lower_low (this bar's extreme versus the previous
published swing price), and they are not MKT-E08.

On a confirmation bar the new price is last_swing_*_price (the pivot). The previous price
is that series shifted one bar. The comparison is strict. The result stays until the next
confirmation of the same kind. Before the second swing of a side the state is 0. sideways
is 0 until both sides have two published swings; an unknown sequence is not called sideways.
"""
from __future__ import annotations

import numpy as np


def swing_sequence_states(swing_high, swing_low, last_swing_high_price, last_swing_low_price):
    """Return int8 arrays (higher_low, lower_high, sideways), each 0 or 1, never NaN."""
    sh = np.asarray(swing_high)
    sl = np.asarray(swing_low)
    last_h = np.asarray(last_swing_high_price, dtype=float)
    last_l = np.asarray(last_swing_low_price, dtype=float)
    n = len(sl)
    if not (len(sh) == len(last_h) == len(last_l) == n):
        raise ValueError("swing_sequence_states: arrays must share one length")

    higher_low = np.zeros(n, dtype=np.int8)
    lower_high = np.zeros(n, dtype=np.int8)
    sideways = np.zeros(n, dtype=np.int8)
    seq_hh = seq_hl = seq_lh = seq_ll = False
    highs_known = lows_known = False

    for i in range(n):
        if i > 0 and sl[i] == 1:
            new, old = last_l[i], last_l[i - 1]
            if np.isfinite(new) and np.isfinite(old):
                seq_hl = bool(new > old)
                seq_ll = bool(new < old)
                lows_known = True
        if i > 0 and sh[i] == 1:
            new, old = last_h[i], last_h[i - 1]
            if np.isfinite(new) and np.isfinite(old):
                seq_hh = bool(new > old)
                seq_lh = bool(new < old)
                highs_known = True
        if lows_known and seq_hl:
            higher_low[i] = 1
        if highs_known and seq_lh:
            lower_high[i] = 1
        if highs_known and lows_known:
            up = seq_hh and bool(higher_low[i])
            down = bool(lower_high[i]) and seq_ll
            if not up and not down:
                sideways[i] = 1
    return higher_low, lower_high, sideways
