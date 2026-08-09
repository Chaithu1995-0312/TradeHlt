"""Live RREngine (candle polarity) adapter."""
from __future__ import annotations

from typing import Any

from engines.rr_engine import RREngine
from research.model_runners.contracts import ModelContract
from research.model_runners.substrate import BarContext, require_feature_keys


class RRPolarityAdapter:
    def __init__(self, *, contract: ModelContract, prod_config: dict[str, Any]):
        self.contract = contract
        # RREngine scoring uses high/low/close only; no production scoring section.
        # Pass empty config — engine min_rr is unused for polarity math.
        self._engine = RREngine({})
        self.config_sections_read: list[str] = []
        self.config_keys_read: list[str] = []
        self.artifact_info: dict[str, Any] | None = None
        _ = prod_config  # config not required for polarity path

    def score_bar(self, bar: BarContext) -> dict[str, Any]:
        require_feature_keys(bar.features, ("high", "low", "close"))
        native = self._engine.compute(
            {
                "high": float(bar.features["high"]),
                "low": float(bar.features["low"]),
                "close": float(bar.features["close"]),
            }
        )
        if not isinstance(native, dict):
            raise TypeError(f"RREngine.compute must return dict, got {type(native)}")
        return native
