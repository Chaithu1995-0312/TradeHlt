"""SEM-015 TIMEOUT net-R path shared by economic probes."""
from __future__ import annotations

from typing import Optional

from research.costs import ComponentCostModel
from research.probes.horizon import close_at_horizon


def net_r(
    corpus: list[dict],
    bar_index: int,
    direction: str,
    atr: float,
    cost_model: ComponentCostModel,
    horizon: int,
) -> Optional[float]:
    gross = close_at_horizon(corpus, bar_index, direction, atr, horizon)
    if gross is None:
        return None
    side = "long" if direction == "LONG" else "short"
    cost_r = cost_model.cost_price(exit_kind="TIMEOUT", direction=side, nights_held=0) / atr
    return gross - cost_r
