"""Live HeuristicGaussianEngine adapter (spine gaussian slot)."""
from __future__ import annotations

from typing import Any

from engines.heuristic_gaussian_engine import HeuristicGaussianEngine
from features.feature_schema import CANONICAL_FEATURES
from research.model_runners.contracts import ModelContract
from research.model_runners.require_config import require_key, require_section
from research.model_runners.substrate import BarContext, require_feature_keys


class GaussianAdapter:
    def __init__(
        self,
        *,
        contract: ModelContract,
        prod_config: dict[str, Any],
        instrument: str,
    ):
        self.contract = contract
        if not instrument:
            raise ValueError("instrument is required for gaussian adapter")

        er = require_section(prod_config, "engine_runner")
        impl = require_key(er, "gaussian_impl", path="engine_runner")
        if impl != "heuristic":
            raise RuntimeError(
                f"gaussian model_id requires engine_runner.gaussian_impl='heuristic'; "
                f"got {impl!r}. Use a separate model_id for ML path (Phase 3)."
            )

        # Pass instrument explicitly — do not rely on engine's internal instrument default.
        engine_cfg: dict[str, Any] = {"instrument": instrument}
        self._engine = HeuristicGaussianEngine(engine_cfg, instrument=instrument)
        self.config_sections_read = ["engine_runner"]
        self.config_keys_read = ["engine_runner.gaussian_impl"]
        self.artifact_info = None

    @property
    def engine(self) -> HeuristicGaussianEngine:
        """Public accessor for the wrapped live engine (R5).

        ``fusion_compute`` must hand the same engine instance to
        ``core.fusion_engine.GaussianAdapter``; it previously reached in via
        ``._engine``, which coupled it to this class's private layout.
        """
        return self._engine

    def score_bar(self, bar: BarContext) -> dict[str, Any]:
        require_feature_keys(
            bar.features, ("ema_fast", "ema_slow", "momentum_score")
        )
        # Engine asserts full canonical feature count.
        if len(bar.features) < len(CANONICAL_FEATURES):
            raise ValueError(
                f"gaussian requires full canonical feature dict "
                f"(have {len(bar.features)}, need >= {len(CANONICAL_FEATURES)})"
            )
        # Convert Mapping to plain dict for engine
        feat = {k: float(bar.features[k]) for k in bar.features}
        native = self._engine.compute(feat)
        if not isinstance(native, dict):
            raise TypeError(
                f"HeuristicGaussianEngine.compute must return dict, got {type(native)}"
            )
        return native
