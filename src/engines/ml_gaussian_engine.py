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
        # P0 name-anchored contract: live names in the order the model was trained.
        self._feature_schema_resolved: Optional[list] = None
        self._schema_alignment: Optional[str] = None

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
            if isinstance(_meta, dict):
                self._feature_schema_resolved = list(
                    _meta.get("feature_schema_resolved") or []
                )
                self._schema_alignment = _meta.get("schema_alignment")
            if not self._feature_schema_resolved:
                # Contract requires a resolved order — refuse rather than truncate.
                logger.warning(
                    "MLGaussianEngine: no feature_schema_resolved for version='%s' — "
                    "refusing load (name-anchored contract).",
                    active_version,
                )
                self._model = None
                self._scaler = None
                self._load_failed = True
                return

            # STORY-1.6: register under the *registry version id* used at compute().
            # load_gaussian_model registers under the model file path only.
            # Hash registration remains for telemetry; name-anchored extract is
            # the scoring authority (hash mismatch no longer forces 0.5 fallback).
            from features.feature_schema import FeatureSchemaRegistry
            _hash = None
            if isinstance(_meta, dict):
                _hash = _meta.get("feature_order_hash")
            if not _hash:
                try:
                    import json as _json
                    from training.trainer import MODELS_DIR
                    _bundle = _json.loads((MODELS_DIR / model_file).read_text(encoding="utf-8"))
                    _hash = _bundle.get("feature_order_hash")
                except Exception:
                    _hash = None
            if _hash:
                FeatureSchemaRegistry.register(active_version, str(_hash))
                logger.info(
                    "MLGaussianEngine: registered schema hash for version='%s' "
                    "(informational; scoring uses name-anchored order)",
                    active_version,
                )

            logger.info(
                "MLGaussianEngine: loaded model version='%s' n_features=%d "
                "alignment=%s resolved_dim=%d",
                active_version,
                model.n_features,
                self._schema_alignment,
                len(self._feature_schema_resolved),
            )

        except Exception as exc:
            logger.warning(
                "MLGaussianEngine: model load failed — %s. "
                "Will return 0.5 fallback on all compute() calls.", exc,
            )
            self._model = None
            self._scaler = None
            self._feature_schema_resolved = None
            self._schema_alignment = None
            self._load_failed = True

    def compute(self, input_data: dict, candle_idx: int = 0, direction: str = "long") -> dict:
        """
        Compute ML-based Gaussian score from a canonical feature dict.

        Pipeline (P0 name-anchored contract, 2026-07-22):
          1. Lazy model load (schema resolved at load)
          2. Build vector by **trained name order** (resolved live names) —
             never ambient extract + silent truncate
          3. If direction='short', mirror directional features in that order
          4. Require len(vec) == model.n_features (exact)
          5. Scale + predict_expected_rr + sigmoid map to score

        Returns dict with: score, reason, meta (on success)
        """
        _fallback = {"score": 0.5, "reason": "ml_gaussian_fallback"}

        if self._model is None and not self._load_failed:
            self._load_model()

        if self._model is None or self._load_failed:
            return _fallback

        if not self._feature_schema_resolved:
            return {
                "score": 0.5,
                "reason": "ml_gaussian_no_resolved_schema",
            }

        try:
            from features.gaussian_schema_contract import (
                GaussianSchemaError,
                extract_model_feature_vector,
            )

            try:
                vec = extract_model_feature_vector(
                    input_data, self._feature_schema_resolved
                )
            except GaussianSchemaError as gse:
                logger.warning(
                    "MLGaussianEngine: name-anchored extract failed — %s", gse
                )
                return {
                    "score": 0.5,
                    "reason": "ml_gaussian_schema_extract_failed",
                    "meta": {"error": str(gse)},
                }

            # Mirror directional features for short trades so the model (trained in
            # long perspective via --mirror-short-features) scores correctly.
            if direction == "short":
                try:
                    from core.model_registry import _mirror_features_for_short
                    vec = _mirror_features_for_short(
                        vec, self._feature_schema_resolved
                    )
                except Exception as _me:
                    logger.debug("MLGaussianEngine: short mirroring skipped — %s", _me)

            # P0 FAIL-CLOSED: exact width only — never silent truncate (schema v4).
            if len(vec) != self._model.n_features:
                logger.error(
                    "MLGaussianEngine: feature vector length %d != model.n_features %d. "
                    "Refusing silent truncate — returning 0.5 fallback.",
                    len(vec), self._model.n_features,
                )
                return {
                    "score": 0.5,
                    "reason": "ml_gaussian_dim_mismatch",
                    "meta": {
                        "got": len(vec),
                        "expected": self._model.n_features,
                    },
                }

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
                    "schema_alignment": self._schema_alignment,
                    "n_features": self._model.n_features,
                },
            }

        except Exception as exc:
            logger.warning(
                "MLGaussianEngine.compute() failed — %s. Returning 0.5 fallback.", exc
            )
            return _fallback