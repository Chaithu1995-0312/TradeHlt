"""Uncapped ATR excursion via governed forward_walk (from p001 probe)."""
from __future__ import annotations

from typing import Optional

from research.contracts import Signal
from research.measurement.forward_walk import forward_walk

UNREACHABLE_ATR_MULT = 1e9


class Bar:
    """Minimal bar for forward_walk (reads .high/.low/.close/.index only)."""

    __slots__ = ("high", "low", "close", "index")

    def __init__(self, high: float, low: float, close: float, index: int) -> None:
        self.high, self.low, self.close, self.index = high, low, close, index


def excursion(corpus: list[dict], i: int, atr: float, horizon: int) -> Optional[dict]:
    """Uncapped (up, down) excursion in ATR units over bars i+1 .. i+horizon.

    Returns None when the window is truncated by corpus end (reported, never silently short).
    """
    future = corpus[i + 1: i + 1 + horizon]
    if len(future) < horizon:
        return None
    entry = corpus[i + 1]["open"]

    sig = Signal(
        instrument="XAUUSD", timestamp=corpus[i]["ts"], entry_index=i, direction="long",
        entry=entry, sl_atr_mult=UNREACHABLE_ATR_MULT, tp_atr_mult=UNREACHABLE_ATR_MULT, atr=atr,
    )
    bars = [Bar(b["high"], b["low"], b["close"], b["index"]) for b in future]
    oc = forward_walk(sig, bars, max_forward=horizon, exit_model="intrabar_fixed")
    if oc.outcome != "TIMEOUT":
        raise AssertionError(
            f"forward_walk exited ({oc.outcome}) despite unreachable barriers at bar {i} -- the "
            "excursion object is not what this probe declares. Refusing to report."
        )

    # Independent naive twin (F-088 certification pattern): a private max/min, computed without
    # the kernel, must agree to 1e-10 or the reuse is not the object it claims to be.
    twin_up = max(b["high"] for b in future) - entry
    twin_down = entry - min(b["low"] for b in future)
    if abs(oc.mfe - twin_up) > 1e-10 or abs(-oc.mae - twin_down) > 1e-10:
        raise AssertionError(
            f"twin certification FAILED at bar {i}: kernel up={oc.mfe} down={-oc.mae} vs "
            f"naive up={twin_up} down={twin_down}"
        )

    spans_gap = any(
        future[k + 1]["ts"] - future[k]["ts"] > GAP_THRESHOLD for k in range(len(future) - 1)
    ) or (future[0]["ts"] - corpus[i]["ts"] > GAP_THRESHOLD)

    return {
        "up": oc.mfe / atr,
        "down": twin_down / atr,
        "spans_gap": spans_gap,
    }


_Bar = Bar
