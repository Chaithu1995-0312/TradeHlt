"""
ml_gaussian_engine.py
=====================
ML-based Gaussian engine using a trained GaussianNBModel (32-dim).

Selected via environment variable:
  GAUSSIAN_IMPL=ml        → MLGaussianEngine (this file)
  GAUSSIAN_IMPL=heuristic → HeuristicGaussianEngine (default)

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
            from core.model_registry import GaussianModelRegistry
            from training.trainer import load_gaussian_model

            registry = GaussianModelRegistry()
            active_version = registry.get_active_gaussian()

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

            model, scaler, _meta = load_gaussian_model(model_file)

            self._model = model
            self._scaler = scaler
            self._model_version = active_version
            self._load_failed = False

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

    def compute(self, input_data: dict, candle_idx: int = 0) -> dict:
        """
        Compute ML-based score from 32-dim canonical feature dict.

        Pipeline:
          1. Lazy model load
          2. Extract 32-dim vector via dataset_builder.extract_feature_vector()
          3. Validate dimension matches model.n_features
          4. Scale with self._scaler.transform_one()
          5. Call self._model.predict_expected_rr(scaled)
          6. Map expected_rr → score via sigmoid: 1 / (1 + exp(-expected_rr))

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