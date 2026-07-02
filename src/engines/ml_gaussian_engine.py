"""
ml_gaussian_engine.py
=====================
ML-based Gaussian engine using a trained GaussianNBModel (32-dim).

Selected via config["gaussian_impl"] (Config-First §6.5 — config is the single
source of truth; the GAUSSIAN_IMPL env var was removed):
  gaussian_impl=ml        → MLGaussianEngine (this file)
  gaussian_impl=heuristic → HeuristicGaussianEngine (default)

Fail-open doctrine:
  Any exception during model load or inference returns
  {"score": 0.5, "reason": "ml_gaussian_fallback"} — never raises.
"""

from __future__ import annotations

import logging
import math
from typing import Optional

logger = logging.getLogger(__name__)


class MLGaussianEngine:
    """
    ML-based Gaussian scoring engine backed by GaussianNBModel (32-dim).

    Model is loaded lazily on first compute() call (or eagerly if preload=True).

    Parameters
    ----------
    config  : dict — engine configuration
    preload : bool — if True, load model at __init__ time
    """

    def __init__(self, config: dict, preload: bool = False):
        self.config = config
        self._model = None
        self._scaler = None
        self._model_version: Optional[str] = None
        self._load_failed: bool = False

        if preload:
            self._load_model()

    def _load_model(self) -> None:
        """
        Load GaussianNBModel + StandardScaler from the active registry entry.
        Sets self._load_failed = True on any exception (fail-open).
        """
        try:
            import os
            from core.model_registry import GaussianModelRegistry
            from training.trainer import load_gaussian_model

            registry = GaussianModelRegistry()

            # Instrument-aware lookup: GAUSSIAN_INSTRUMENT env var takes priority,
            # then config["instrument"] key, then legacy EURUSD fallback.
            _instrument = os.getenv("GAUSSIAN_INSTRUMENT") or (
                self.config.get("instrument") if isinstance(self.config, dict) else None
            )
            active_version = (
                registry.get_active_version(_instrument) if _instrument else None
            ) or registry.get_active_gaussian()

            if _instrument and active_version:
                logger.info(
                    "MLGaussianEngine: instrument-aware lookup '%s' → version '%s'",
                    _instrument, active_version,
                )

            if active_version is None:
                logger.warning(
                    "MLGaussianEngine: no active Gaussian model in registry. "
                    "Falling back to 0.5."
                )
                self._load_failed = True
                return

            reg_data = registry._load()
            entry = reg_data.get(active_version, {})
            model_file = entry.get("model_file", f"{active_version}.json")

            # Strip leading "models/" prefix: load_gaussian_model prepends MODELS_DIR
            # internally, so passing a path already rooted at "models/" doubles it.
            from pathlib import Path as _Path
            _mf = _Path(model_file)
            if _mf.parts and _mf.parts[0].lower() == "models":
                model_file = str(_Path(*_mf.parts[1:]))

            model, scaler, _meta = load_gaussian_model(model_file)

            self._model = model
            self._scaler = scaler
            self._model_version = active_version
            self._load_failed = False

            # STORY-1.6: register the model's stored feature ordering so the
            # inference-time check_compatibility() guard has a hash to compare.
            # Otherwise the in-memory registry is empty at live inference (it is
            # only populated by trainer.py at train time) and every model would
            # be treated as unregistered.
            if isinstance(_meta, dict) and _meta.get("feature_order_hash"):
                from features.feature_schema import FeatureSchemaRegistry
                FeatureSchemaRegistry.register(active_version, _meta["feature_order_hash"])

            logger.info(
                "MLGaussianEngine: loaded model version='%s' n_features=%d",
                active_version, model.n_features,
            )

        except Exception as exc:
            logger.warning(
                "MLGaussianEngine: model load failed — %s. "
                "Will return 0.5 fallback on all compute() calls.", exc,
            )
            self._model = None
            self._scaler = None
            self._load_failed = True

    def compute(self, input_data: dict, candle_idx: int = 0, direction: str = "long") -> dict:
        """
        Compute ML-based score from 35-dim canonical feature dict.

        Pipeline:
          1. Lazy model load
          2. Extract 35-dim vector via dataset_builder.extract_feature_vector()
          3. If direction='short', mirror directional features to long perspective
             (must match the mirroring applied during training with --mirror-short-features)
          4. Validate dimension matches model.n_features
          5. Scale with self._scaler.transform_one()
          6. Call self._model.predict_expected_rr(scaled)
          7. Map expected_rr → score via sigmoid: 1 / (1 + exp(-expected_rr))

        Returns dict with: score, reason, meta (on success)
        """
        _fallback = {"score": 0.5, "reason": "ml_gaussian_fallback"}

        if self._model is None and not self._load_failed:
            self._load_model()

        if self._model is None or self._load_failed:
            return _fallback

        try:
            from features.dataset_builder import extract_feature_vector
            vec = extract_feature_vector(input_data)

            # Mirror directional features for short trades so the model (trained in
            # long perspective via --mirror-short-features) scores correctly.
            if direction == "short":
                try:
                    from core.model_registry import _mirror_features_for_short
                    from features.feature_schema import CANONICAL_FEATURE_ORDER
                    vec = _mirror_features_for_short(vec, CANONICAL_FEATURE_ORDER)
                except Exception as _me:
                    logger.debug("MLGaussianEngine: short mirroring skipped — %s", _me)

            # STORY-1.6 schema-corruption guard: when the registry reports the
            # model's stored feature ordering differs from the runtime ordering
            # AND the lengths are equal, truncation cannot fix it (same shape,
            # different meaning) — fall back to neutral rather than scoring on
            # misaligned features. The len>n_features case below is a legitimate
            # v3.0→v2.0 migration and is handled by truncation as before.
            from features.feature_schema import FeatureSchemaRegistry
            if (len(vec) == self._model.n_features
                    and not FeatureSchemaRegistry.check_compatibility(self._model_version)):
                logger.warning(
                    "MLGaussianEngine: schema incompatibility for model_version=%s "
                    "(equal length, order mismatch / unregistered) — returning 0.5 fallback.",
                    self._model_version,
                )
                return _fallback

            if len(vec) > self._model.n_features:
                # Schema migration: pipeline produces v3.0 (38-dim) but model was
                # trained on v2.0 (35-dim). Truncate silently — backward compat.
                logger.debug(
                    "MLGaussianEngine: truncating vector %d → %d (schema migration).",
                    len(vec), self._model.n_features,
                )
                vec = vec[:self._model.n_features]
            if len(vec) != self._model.n_features:
                logger.error(
                    "MLGaussianEngine: feature vector length %d != model.n_features %d. "
                    "Returning 0.5 fallback.", len(vec), self._model.n_features,
                )
                return _fallback

            scaled = self._scaler.transform_one(vec)
            expected_rr, confidence, probs = self._model.predict_expected_rr(scaled)

            score = 1.0 / (1.0 + math.exp(-expected_rr))
            score = max(0.0, min(1.0, score))

            return {
                "score": round(score, 4),
                "reason": "ml_gaussian",
                "meta": {
                    "expected_rr":   round(expected_rr, 4),
                    "confidence":    round(confidence, 4),
                    "model_version": self._model_version,
                },
            }

        except Exception as exc:
            logger.warning(
                "MLGaussianEngine.compute() failed — %s. Returning 0.5 fallback.", exc
            )
            return _fallback