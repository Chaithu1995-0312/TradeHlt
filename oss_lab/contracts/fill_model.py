"""Fill model is a declared experimental variable — never silent."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class FillModelDeclaration:
    fill_model_id: str
    data_resolution: str
    order_type: str
    fill_policy: str
    slippage_model: str
    queue_model: str
    liquidity_model: str
    partial_fill_policy: str
    price_priority: str
    volume_assumptions: str
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["notes"] = list(self.notes)
        return d


# Declared Tradelatest research defaults (descriptive; not production authority).
TRADLATEST_RESEARCH_INTRABAR = FillModelDeclaration(
    fill_model_id="TL-FILL-INTRABAR-FIXED-V1",
    data_resolution="M15_OHLC",
    order_type="market_at_bar_open_or_signal_price",
    fill_policy="intrabar_fixed_sl_before_tp",
    slippage_model="flat_round_trip_bps_research_cost_model",
    queue_model="NOT_APPLICABLE",
    liquidity_model="infinite_at_bar",
    partial_fill_policy="NOT_APPLICABLE_full_fill_assumed",
    price_priority="SL_before_TP_same_bar",
    volume_assumptions="unit_size_no_market_impact",
    notes=(
        "Mirrors research.measurement.forward_walk + research.costs.CostModel.",
        "Spine uses seeded ATR-fraction slippage — deliberately different; see provenance.",
    ),
)
