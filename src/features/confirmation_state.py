"""FM-128 wait_for_next_candle — a decision state, not a feature column.

The confirmation card says: find the level, wait for the next candle, then enter.
The same bar that prints the pattern is not the entry. A gap expires the pending setup.
A close equal to the open confirms neither side. If both a long and a short setup are
armed, the side of the close wins.

Balanced doji is indecision and itself needs confirmation, so doji_material does not arm
this state. The card's "look at many candles" has no numeric count; this identity does
not invent a window.
"""
from __future__ import annotations

import numpy as np

# Prior-bar flags that arm the pending setup. doji_material is intentionally absent.
LONG_ARM = ("hammer", "pin_lower", "dragonfly_doji", "engulfing_bull", "morning_star")
SHORT_ARM = ("shooting_star", "pin_upper", "gravestone_doji", "engulfing_bear")


def armed_setups(flags: dict) -> tuple[bool, bool]:
    """(setup_long, setup_short) from one bar's pattern flags."""
    setup_long = any(bool(flags.get(name)) for name in LONG_ARM)
    setup_short = any(bool(flags.get(name)) for name in SHORT_ARM)
    return setup_long, setup_short


def wait_for_next_candle(setup_long, setup_short, contiguous, open_, close) -> int:
    """Confirm a setup that was armed on the previous bar.

    Returns +1 long, -1 short, or 0. `contiguous` is false across a session or weekend
    gap, which expires the pending setup. This function does not read the current bar's
    pattern: the caller passes the previous bar's setups.
    """
    if not contiguous:
        return 0
    if close > open_ and setup_long:
        return 1
    if close < open_ and setup_short:
        return -1
    return 0


def wait_for_next_series(long_flags, short_flags, contiguous, open_, close) -> np.ndarray:
    """Per-bar state. Bar i confirms the setups on bar i-1 when the two bars are contiguous."""
    long_flags = np.asarray(long_flags)
    short_flags = np.asarray(short_flags)
    contiguous = np.asarray(contiguous, dtype=bool)
    open_ = np.asarray(open_, dtype=float)
    close = np.asarray(close, dtype=float)
    n = len(close)
    out = np.zeros(n, dtype=np.int8)
    for i in range(1, n):
        out[i] = wait_for_next_candle(
            bool(long_flags[i - 1]), bool(short_flags[i - 1]),
            bool(contiguous[i]), float(open_[i]), float(close[i]),
        )
    return out
