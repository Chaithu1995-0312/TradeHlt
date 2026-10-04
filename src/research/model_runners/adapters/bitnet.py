"""BitNet hard-reject gate adapter (off-spine observe; does not flip use_bitnet)."""
from __future__ import annotations

from typing import Any

from bitnet.bitnet_inference import bitnet_score
from bitnet.defaults import LEGACY6_KEYS
from research.model_runners.contracts import ModelContract
from research.model_runners.substrate import BarContext, require_feature_keys


class BitNetAdapter:
    def __init__(self, *, contract: ModelContract, prod_config: dict[str, Any]):
        self.contract = contract
        # bitnet_score loads composition/model.json via production façade — no CLI artifact.
        # Document prod flag without mutating it.
        from research.model_runners.require_config import require_section, require_key

        crt = require_section(prod_config, "crt_engine")
        use_bitnet = require_key(crt, "use_bitnet", path="crt_engine")
        thr = require_key(crt, "bitnet_main_threshold", path="crt_engine")
        self._threshold = float(thr)
        self._use_bitnet_prod = bool(use_bitnet)
        self.config_sections_read = ["crt_engine"]
        self.config_keys_read = [
            "crt_engine.use_bitnet",
            "crt_engine.bitnet_main_threshold",
        ]
        self.artifact_info = {
            "path": "model.json",
            "serve": "bitnet.bitnet_inference.bitnet_score",
            "use_bitnet_prod": self._use_bitnet_prod,
            "bitnet_main_threshold": self._threshold,
            "note": "observe-only; does not enable production gate",
        }

    def score_bar(self, bar: BarContext) -> dict[str, Any]:
        require_feature_keys(bar.features, LEGACY6_KEYS)
        feat = {k: float(bar.features[k]) for k in LEGACY6_KEYS}
        # CRT serve aliases if present (FM-027/028)
        if "displacement_retrace" in bar.features:
            feat["displacement_retrace"] = float(bar.features["displacement_retrace"])
        if "displacement_atr_ratio" in bar.features:
            feat["displacement_atr_ratio"] = float(bar.features["displacement_atr_ratio"])
        confidence = float(bitnet_score(feat))
        return {
            "score": confidence,
            "confidence": confidence,
            "threshold": self._threshold,
            "would_reject": bool(confidence < self._threshold),
            "use_bitnet_prod": self._use_bitnet_prod,
            "feature_keys_used": list(LEGACY6_KEYS),
            "semantic": "bitnet_hard_reject_confidence",
        }
