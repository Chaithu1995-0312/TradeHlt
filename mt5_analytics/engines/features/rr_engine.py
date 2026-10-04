"""
rr_engine — per-episode realized R (NO aggregation).

Realized R is computed directly: `(exit_vwap − entry_vwap)·dir / risk` — never via the
model-based RRFusionLayer. The risk basis is `|entry_vwap − SL|` when the order's stop is
known (from `history_orders_get`), else an ATR-at-entry fallback. Portfolio rollups
(expectancy/PF/win-rate) are explicitly OUT of the feature layer — they live in analytics/.
"""
from __future__ import annotations

from ...schemas.position_episode_v1_0 import LONG


def risk_distance(
    episode, sl_price: "float | None" = None, *, atr_value: "float | None" = None
) -> float:
    """Risk in price units: |entry − SL| if SL given & positive, else ATR fallback, else 0."""
    if sl_price is not None:
        rd = abs(episode.entry_vwap - float(sl_price))
        if rd > 0.0:
            return rd
    if atr_value is not None and atr_value > 0.0:
        return float(atr_value)
    return 0.0


def realized_r(episode, risk: float) -> "float | None":
    """Signed realized R; None when risk is undefined (no SL and no ATR)."""
    if risk <= 0.0:
        return None
    dir_sign = 1.0 if episode.direction == LONG else -1.0
    return round((episode.exit_vwap - episode.entry_vwap) * dir_sign / risk, 6)


def partial(episode, risk: float) -> dict:
    """Per-episode RR partial dict."""
    return {
        "risk_distance": round(risk, 10) if risk > 0.0 else None,
        "realized_r": realized_r(episode, risk),
    }
