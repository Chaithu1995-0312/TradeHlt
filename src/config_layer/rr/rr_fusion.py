"""
rr_fusion.py
Advisory RR fusion layer using canonical 24-feature validation.
"""

import logging
import os
import warnings
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

from config_layer.rr.rr_pattern_miner import NanoInferenceEngine, DEFAULT_MODEL_PATH
from features.feature_pipeline import build_feature_vector
from features.feature_schema import CANONICAL_FEATURES
from features.schema_validator import validate_features, validate_feature_values

from features.feature_schema import (
    GAUSSIAN_SCHEMA, TRADENET_SCHEMA, SCHEMA_VERSION,
    validate_vector,
)

try:
    try:
        from config_layer.production_config import get_prod_section as _get_section
    except ImportError:
        from production_config import get_prod_section as _get_section  # standalone script path
    _DRIFT_THRESHOLD: float = _get_section("rr_model").get("drift_threshold", 1.5)
except Exception:
    _DRIFT_THRESHOLD: float = 1.5


def _passthrough(gaussian_score: float, gaussian_p_win: float, reason: str) -> Dict[str, Any]:
    return {
        "final_score": float(gaussian_score),
        "expected_rr": 0.0,
        "probability_of_win": float(gaussian_p_win),
        "confidence": 0.0,
        "status": reason,
    }


def _empty_canonical_features() -> dict:
    return {k: 0.0 for k in CANONICAL_FEATURES}


class RRFusionLayer:
    def __init__(
        self,
        model_path: str = DEFAULT_MODEL_PATH,
        threshold: float = 0.5,
        enabled: bool = True,
    ) -> None:
        self._threshold = threshold
        self._enabled = enabled
        self._engine: Optional[NanoInferenceEngine] = None
        self._loaded = False
        self._load_error = ""

        if not enabled:
            return
        self._try_load(model_path)

    def _try_load(self, path: str) -> None:
        if not os.path.exists(path):
            self._load_error = f"Model file not found: {path}"
            warnings.warn(f"[RRFusionLayer] {self._load_error}. Running in passthrough mode.")
            return
        try:
            self._engine = NanoInferenceEngine.load(path)
            self._loaded = True
        except Exception as exc:
            self._load_error = str(exc)
            warnings.warn(f"[RRFusionLayer] Failed to load model: {exc}. Running in passthrough mode.")

    @staticmethod
    def _get(obj: Any, attr: str, default: float = 0.0) -> Any:
        if isinstance(obj, dict):
            return obj.get(attr, default)
        return getattr(obj, attr, default)

    def _extract_gaussian_fields(self, trade: Any):
        g_score = float(self._get(trade, "gaussian_score", 0.0))
        g_pwin = float(self._get(trade, "gaussian_p_win", 0.5))
        return g_score, g_pwin

    def _extract_canonical_features(self, trade: Any) -> dict:
        trade_dict = trade if isinstance(trade, dict) else vars(trade) if hasattr(trade, "__dict__") else {}

        nested = trade_dict.get("features")
        if isinstance(nested, dict):
            validate_features(nested, CANONICAL_FEATURES)
            validate_feature_values(nested)
            return nested

        top_level = {k: trade_dict.get(k) for k in CANONICAL_FEATURES}
        validate_features(top_level, CANONICAL_FEATURES)
        validate_feature_values(top_level)
        return top_level

    def score(
        self,
        trade: Any,
        threshold: Optional[float] = None,
    ) -> Dict[str, Any]:
        g_score, g_pwin = self._extract_gaussian_fields(trade)

        if not self._enabled:
            return _passthrough(g_score, g_pwin, "disabled")

        if not self._loaded:
            return _passthrough(g_score, g_pwin, "model_not_loaded")

        thr = threshold if threshold is not None else self._threshold

        try:
            features = self._extract_canonical_features(trade)
            depth = float(features["retest_depth"])
            body = float(features["body_ratio"])
            disp = float(features["disp_strength"])

            if depth > _DRIFT_THRESHOLD or body > _DRIFT_THRESHOLD or disp > _DRIFT_THRESHOLD:
                logger.warning(
                    "RRFusionLayer: feature drift detected (depth=%.3f body=%.3f disp=%.3f "
                    "threshold=%.1f) — RR model bypassed, falling back to Gaussian.",
                    depth, body, disp, _DRIFT_THRESHOLD,
                )
                # Audit-trail emit so TrainingTrigger._drift_gate_open() and
                # post-hoc forensics see this in logs/integrity_events.jsonl.
                # Wrapped: import failure must not break the hot-path fallback.
                try:
                    from utils.integrity_events import emit_integrity_event
                    emit_integrity_event(
                        "RR_BYPASS", "WARNING", "rr_fusion",
                        {"depth": depth, "body": body, "disp": disp,
                         "threshold": _DRIFT_THRESHOLD},
                    )
                except Exception:
                    pass
                return _passthrough(g_score, g_pwin, "drift_detected")

            vector = build_feature_vector(features)
            return self._engine.predict(  # type: ignore[union-attr]
                features=vector,
                gaussian_score=g_score,
                gaussian_p_win=g_pwin,
                threshold=thr,
            )
        except Exception as exc:
            warnings.warn(f"[RRFusionLayer] Inference error: {exc}")
            return _passthrough(g_score, g_pwin, "inference_error")

    def score_dict(
        self,
        depth: float,
        body: float,
        disp: float,
        gaussian_score: float,
        gaussian_p_win: float,
        is_asia: float,
        is_london: float,
        is_newyork: float,
        hour: int,
        threshold: Optional[float] = None,
    ) -> Dict[str, Any]:
        if not self._enabled:
            return _passthrough(gaussian_score, gaussian_p_win, "disabled")
        if not self._loaded:
            return _passthrough(gaussian_score, gaussian_p_win, "model_not_loaded")

        if depth > _DRIFT_THRESHOLD or body > _DRIFT_THRESHOLD or disp > _DRIFT_THRESHOLD:
            return _passthrough(gaussian_score, gaussian_p_win, "drift_detected")

        features = _empty_canonical_features()
        features["retest_depth"] = float(depth)
        features["body_ratio"] = float(body)
        features["disp_strength"] = float(disp)

        thr = threshold if threshold is not None else self._threshold
        try:
            vector = build_feature_vector(features)
            return self._engine.predict(  # type: ignore[union-attr]
                features=vector,
                gaussian_score=float(gaussian_score),
                gaussian_p_win=float(gaussian_p_win),
                threshold=thr,
            )
        except Exception as exc:
            warnings.warn(f"[RRFusionLayer] Inference error: {exc}")
            return _passthrough(gaussian_score, gaussian_p_win, "inference_error")

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def load_error(self) -> str:
        return self._load_error

    def reload(self, model_path: str = DEFAULT_MODEL_PATH) -> bool:
        old_engine = self._engine
        old_loaded = self._loaded
        self._engine = None
        self._loaded = False
        self._try_load(model_path)
        if not self._loaded:
            self._engine = old_engine
            self._loaded = old_loaded
            return False
        return True


def score_trade(
    trade_record: Any,
    model_path: str = DEFAULT_MODEL_PATH,
    threshold: float = 0.5,
) -> Dict[str, Any]:
    layer = RRFusionLayer(model_path=model_path, threshold=threshold)
    return layer.score(trade_record)

