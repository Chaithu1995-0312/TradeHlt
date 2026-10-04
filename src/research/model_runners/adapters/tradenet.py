"""TradeNet v2 observe adapter (UNWIRED on spine; requires --artifact)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from research.model_runners.contracts import ModelContract
from research.model_runners.require_config import sha256_file
from research.model_runners.substrate import BarContext
from training.trade_net_v2 import TradeNetV2


class TradeNetAdapter:
    def __init__(
        self,
        *,
        contract: ModelContract,
        prod_config: dict[str, Any],
        artifact: Path,
        instrument: str,
    ):
        self.contract = contract
        _ = prod_config
        if not artifact.is_file():
            raise FileNotFoundError(f"TradeNet artifact missing: {artifact}")
        # Fail closed on schema dim before TradeNetV2 silent missing-mode.
        import json

        from features.feature_schema import CANONICAL_FEATURE_DIM

        envelope = json.loads(artifact.read_text(encoding="utf-8"))
        if "feature_dim" not in envelope:
            raise KeyError(f"TradeNet envelope missing feature_dim: {artifact}")
        env_dim = int(envelope["feature_dim"])
        if env_dim != CANONICAL_FEATURE_DIM:
            raise RuntimeError(
                f"TradeNet schema_mismatch: envelope feature_dim={env_dim} != "
                f"CANONICAL_FEATURE_DIM={CANONICAL_FEATURE_DIM} ({artifact}). "
                "Refuse silent truncate/pad."
            )
        self._model = TradeNetV2(model_path=artifact, instrument=instrument)
        if self._model._mode == "missing":
            raise RuntimeError(
                f"TradeNetV2 failed to load artifact {artifact} "
                f"(mode=missing after dim check passed)."
            )
        self.config_sections_read = []
        self.config_keys_read = []
        self.artifact_info = {
            "path": str(artifact),
            "sha256": sha256_file(artifact),
            "mode": self._model._mode,
            "schema_version": self._model.schema_version,
            "spine_active": False,
        }

    def score_bar(self, bar: BarContext) -> dict[str, Any]:
        feat = {k: float(bar.features[k]) for k in bar.features}
        pred = self._model.predict(feat)
        if pred is None:
            raise RuntimeError("TradeNetV2.predict returned None")
        if not isinstance(pred, dict):
            raise TypeError(f"TradeNetV2.predict must return dict, got {type(pred)}")
        # Ensure primary score key for stats
        out = dict(pred)
        if "score" not in out and "tradenet_score" in out:
            out["score"] = out["tradenet_score"]
        return out
