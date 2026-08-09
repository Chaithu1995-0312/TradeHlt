"""Fusion CRT scorer adapter — engines.crt_engine.compute → compute_scores."""
from __future__ import annotations

from typing import Any

from engines.crt_engine import compute as crt_compute
from research.model_runners.contracts import ModelContract
from research.model_runners.require_config import require_section
from research.model_runners.substrate import BarContext, require_feature_keys


class CrtScoreAdapter:
    def __init__(self, *, contract: ModelContract, prod_config: dict[str, Any]):
        self.contract = contract
        crt = require_section(prod_config, "crt_engine")
        if "score_component_weights" not in crt:
            raise KeyError(
                "missing production config: crt_engine.score_component_weights"
            )
        raw = crt["score_component_weights"]
        if not isinstance(raw, (list, tuple)) or len(raw) != 4:
            raise ValueError(
                "crt_engine.score_component_weights must be a 4-tuple, "
                f"got {raw!r}"
            )
        weights: list[float] = []
        for c in raw:
            if isinstance(c, bool) or not isinstance(c, (int, float)):
                raise ValueError(
                    f"crt_engine.score_component_weights entries must be numeric, got {c!r}"
                )
            fv = float(c)
            if fv != fv or fv < 0.0:  # NaN check without math import
                raise ValueError(
                    f"crt_engine.score_component_weights must be finite non-negative, got {c!r}"
                )
            weights.append(fv)
        self._weights = tuple(weights)
        self.config_sections_read = ["crt_engine"]
        self.config_keys_read = ["crt_engine.score_component_weights"]
        self.artifact_info = None

    def score_bar(self, bar: BarContext) -> dict[str, Any]:
        keys = (
            "body_ratio",
            "disp_strength",
            "atr",
            "retest_depth",
            "double_sweep",
            "candles_since_retest",
            "sweep_detected",
        )
        require_feature_keys(bar.features, keys)
        feat = {
            "body_ratio": float(bar.features["body_ratio"]),
            "disp_strength": float(bar.features["disp_strength"]),
            "atr": float(bar.features["atr"]),
            "retest_depth": float(bar.features["retest_depth"]),
            "double_sweep": float(bar.features["double_sweep"]),
            "candles_since_retest": float(bar.features["candles_since_retest"]),
            "sweep_detected": float(bar.features["sweep_detected"]),
        }
        trade_id = f"offline:{bar.bar_index}"
        native = crt_compute(
            trade_id,
            feat,
            context={"score_component_weights": self._weights},
        )
        if not isinstance(native, dict):
            raise TypeError(f"crt_engine.compute must return dict, got {type(native)}")
        return native
