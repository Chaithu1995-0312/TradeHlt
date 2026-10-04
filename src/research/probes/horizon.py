"""Hold-to-horizon gross R scoring shared by economic probes."""
from __future__ import annotations

from typing import Optional


def close_at_horizon(
    corpus: list[dict],
    bar_index: int,
    direction: str,
    atr: float,
    horizon: int,
) -> Optional[float]:
    """gross_R for a hold-to-horizon, no-TP/SL object. None if the window is truncated."""
    future = corpus[bar_index + 1: bar_index + 1 + horizon]
    if len(future) < horizon:
        return None
    entry = corpus[bar_index + 1]["open"]
    exit_price = future[-1]["close"]
    sign = 1.0 if direction == "LONG" else -1.0
    return sign * (exit_price - entry) / atr
