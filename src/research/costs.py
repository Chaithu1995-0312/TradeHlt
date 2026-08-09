"""costs.py — conservative flat cost model for the falsification phase (M1–M6).

The purpose of M1–M6 is *falsification, not execution realism*. A simple model that
slightly OVER-penalizes is strictly preferable to a sophisticated one that under-
estimates and manufactures false edges. We therefore apply a flat round-trip haircut:

    round_trip = entry (0.05%) + exit (0.05%) + slippage_reserve (0.02%) = 0.12% = 12 bps

applied symmetrically to every trade. `forward_walk` stays pure GROSS geometry; the cost
is converted to R units and subtracted by `EdgeAggregator` so every gate qualifies on
NET RR. Cost-model evolution (see plan): M1–M6 flat → M7 observed → M8 per-symbol.
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_ROUND_TRIP_BPS = 12.0   # 0.12%


@dataclass(frozen=True)
class CostModel:
    """Flat round-trip cost expressed in basis points of entry price."""

    round_trip_bps: float = DEFAULT_ROUND_TRIP_BPS

    def cost_r(self, entry: float, risk_distance: float) -> float:
        """Round-trip cost expressed in R units (= cost_price / risk_distance).

        risk_distance is the 1R price distance (sl_atr_mult * atr). A trade risking a
        small distance relative to price pays proportionally more cost in R terms —
        which correctly penalizes tight-stop / high-churn hypotheses.
        """
        if risk_distance <= 0:
            raise ValueError(f"CostModel.cost_r: non-positive risk_distance ({risk_distance})")
        cost_price = (self.round_trip_bps / 10_000.0) * entry
        return cost_price / risk_distance

    def net_rr(self, gross_rr: float, entry: float, risk_distance: float) -> float:
        """Net an outcome's gross R by the round-trip cost."""
        return gross_rr - self.cost_r(entry, risk_distance)


# Canonical instances.
DEFAULT_COST_MODEL = CostModel()                  # 12 bps — used everywhere by default
ZERO_COST = CostModel(round_trip_bps=0.0)          # for pure-geometry math tests only
