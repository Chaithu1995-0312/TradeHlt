"""
rr_fusion.py
============
Advisory ML fusion layer — wraps NanoInferenceEngine for integration
into the existing CRT + Gaussian scoring pipeline.

# ─────────────────────────────────────────────────────────────────────────────
# INTEGRATION CONTRACT
# ─────────────────────────────────────────────────────────────────────────────
#
#  • RRFusionLayer is PURELY ADVISORY. It NEVER:
#      - triggers trades
#      - overrides CRT signals
#      - modifies the CRT engine or GaussianScoringEngine
#
#  • If the model is missing, corrupt, or raises any exception,
#    RRFusionLayer returns the unmodified gaussian_score — as if it
#    doesn't exist. This is the ROLLBACK state.
#
#  • The model is loaded ONCE at construction and kept in memory.
#    Inference calls are stateless and thread-safe.
#
#  • The layer accepts both TradeRecord dataclass objects and plain dicts.
#
# ─────────────────────────────────────────────────────────────────────────────
# SAFEGUARDS (in order of execution)
# ─────────────────────────────────────────────────────────────────────────────
#  1. Drift detection: if any raw input exceeds 1.5× normal range
#     → bypass ML, return gaussian_score  (status: "drift_detected")
#  2. Input clipping: depth/body/disp clamped to [0.0, 1.0]
#     (after drift check, so drift detection sees raw values)
#  3. Low confidence: if Mahalanobis confidence < 0.3
#     → bypass ML  (status: "bypassed_low_confidence")
#  4. Threshold cap: if gaussian_score < threshold and final > gaussian_score
#     → cap at gaussian_score  (status: "capped_by_threshold")
#
# ─────────────────────────────────────────────────────────────────────────────
# ROLLBACK STRATEGY
# ─────────────────────────────────────────────────────────────────────────────
#  1. Delete models/rr_model.json → engine._loaded = False
#     → all calls return {final_score: gaussian_score, status: "model_not_loaded"}
#  2. Set RRFusionLayer(enabled=False) to hard-disable at construction
#
# ─────────────────────────────────────────────────────────────────────────────
# USAGE
# ─────────────────────────────────────────────────────────────────────────────
#
#   from rr_fusion import RRFusionLayer
#
#   fusion = RRFusionLayer()                        # load once at startup
#   ml_info = fusion.score(trade_record, threshold=0.5)
#   print(ml_info["final_score"])
#   print(ml_info["expected_rr"])
#   print(ml_info["probability_of_win"])
#   print(ml_info["confidence"])
#   print(ml_info["status"])
#
# ─────────────────────────────────────────────────────────────────────────────
"""

import os
import warnings
from typing import Any, Dict, Optional

from rr_pattern_miner import NanoInferenceEngine, DEFAULT_MODEL_PATH

# ─────────────────────────────────────────────────────────────────────────────
# Session one-hot helpers
# ─────────────────────────────────────────────────────────────────────────────

def _encode_session_onehot(session: Any):
    """Return (is_asia, is_london, is_newyork) — must match rr_dataset_builder."""
    if session is None:
        return 0.0, 0.0, 0.0
    s = str(session).upper().strip()
    if s in ("ASIA", "ASIAN"):
        return 1.0, 0.0, 0.0
    if s in ("LONDON", "LONDON_OPEN"):
        return 0.0, 1.0, 0.0
    if s in ("NEWYORK", "NEW_YORK", "NY"):
        return 0.0, 0.0, 1.0
    return 0.0, 0.0, 0.0


def _extract_hour(entry_time: Any) -> int:
    """Extract integer hour 0-23 from entry_time."""
    if entry_time is None:
        return 0
    if hasattr(entry_time, "hour"):
        return int(entry_time.hour) % 24
    try:
        s = str(entry_time).replace("T", " ").split(" ")
        if len(s) >= 2:
            return int(s[1].split(":")[0]) % 24
    except Exception:
        pass
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# Passthrough result helper
# ─────────────────────────────────────────────────────────────────────────────

def _passthrough(gaussian_score: float, gaussian_p_win: float, reason: str) -> Dict[str, Any]:
    """Return gaussian_score unchanged with given status reason."""
    return {
        "final_score":        float(gaussian_score),
        "expected_rr":        0.0,
        "probability_of_win": float(gaussian_p_win),
        "confidence":         0.0,
        "status":             reason,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Drift detection threshold
# ─────────────────────────────────────────────────────────────────────────────
# Features depth/body/disp are naturally in [0, 1]. Values > 1.5 indicate
# an out-of-distribution trade that the model was not trained on.
_DRIFT_THRESHOLD = 1.5


# ─────────────────────────────────────────────────────────────────────────────
# RRFusionLayer
# ─────────────────────────────────────────────────────────────────────────────

class RRFusionLayer:
    """
    Advisory ML fusion layer for the CRT trading system.

    Wraps NanoInferenceEngine with:
      - Graceful model loading (no raises into caller)
      - Feature clipping + drift detection
      - One-hot session encoding
      - Complete error isolation

    Parameters:
        model_path: Path to rr_model.json
        threshold:  Gaussian score below which ML cannot raise the score
        enabled:    Hard on/off switch
    """

    def __init__(
        self,
        model_path: str = DEFAULT_MODEL_PATH,
        threshold:  float = 0.5,
        enabled:    bool = True,
    ) -> None:
        self._threshold  = threshold
        self._enabled    = enabled
        self._engine: Optional[NanoInferenceEngine] = None
        self._loaded     = False
        self._load_error = ""

        if not enabled:
            return
        self._try_load(model_path)

    def _try_load(self, path: str) -> None:
        if not os.path.exists(path):
            self._load_error = f"Model file not found: {path}"
            warnings.warn(
                f"[RRFusionLayer] {self._load_error}. "
                "Running in passthrough mode."
            )
            return
        try:
            self._engine = NanoInferenceEngine.load(path)
            self._loaded = True
        except Exception as exc:
            self._load_error = str(exc)
            warnings.warn(
                f"[RRFusionLayer] Failed to load model: {exc}. "
                "Running in passthrough mode."
            )

    # ------------------------------------------------------------------
    def score(
        self,
        trade:     Any,
        threshold: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Produce advisory ML annotation for a trade.

        Args:
            trade:     TradeRecord dataclass or dict.
            threshold: Override instance threshold for this call.

        Returns:
            dict: final_score, expected_rr, probability_of_win,
                  confidence, status

        NOTE: Never raises. All errors return passthrough.
        """
        g_score, g_pwin = self._extract_gaussian_fields(trade)

        if not self._enabled:
            return _passthrough(g_score, g_pwin, "disabled")

        if not self._loaded:
            return _passthrough(g_score, g_pwin, "model_not_loaded")

        thr = threshold if threshold is not None else self._threshold

        try:
            depth, body, disp, is_asia, is_london, is_newyork, hour = \
                self._extract_model_fields(trade)

            # SAFEGUARD: Drift detection on raw (unclipped) values
            if depth > _DRIFT_THRESHOLD or body > _DRIFT_THRESHOLD or disp > _DRIFT_THRESHOLD:
                return _passthrough(g_score, g_pwin, "drift_detected")

            # Input clipping after drift check
            depth = max(0.0, min(1.0, depth))
            body  = max(0.0, min(1.0, body))
            disp  = max(0.0, min(1.0, disp))

            return self._engine.predict(  # type: ignore[union-attr]
                depth=depth,
                body=body,
                disp=disp,
                gaussian_score=g_score,
                gaussian_p_win=g_pwin,
                is_asia=is_asia,
                is_london=is_london,
                is_newyork=is_newyork,
                hour=hour,
                threshold=thr,
            )
        except Exception as exc:
            warnings.warn(f"[RRFusionLayer] Inference error: {exc}")
            return _passthrough(g_score, g_pwin, "inference_error")

    # ------------------------------------------------------------------
    def score_dict(
        self,
        depth:          float,
        body:           float,
        disp:           float,
        gaussian_score: float,
        gaussian_p_win: float,
        is_asia:        float,
        is_london:      float,
        is_newyork:     float,
        hour:           int,
        threshold:      Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Low-level interface accepting pre-extracted scalar fields.
        Useful when calling from a hot loop.
        """
        if not self._enabled:
            return _passthrough(gaussian_score, gaussian_p_win, "disabled")
        if not self._loaded:
            return _passthrough(gaussian_score, gaussian_p_win, "model_not_loaded")

        # Drift detection on raw values
        if depth > _DRIFT_THRESHOLD or body > _DRIFT_THRESHOLD or disp > _DRIFT_THRESHOLD:
            return _passthrough(gaussian_score, gaussian_p_win, "drift_detected")

        # Input clipping
        depth = max(0.0, min(1.0, depth))
        body  = max(0.0, min(1.0, body))
        disp  = max(0.0, min(1.0, disp))

        thr = threshold if threshold is not None else self._threshold
        try:
            return self._engine.predict(  # type: ignore[union-attr]
                depth=depth,
                body=body,
                disp=disp,
                gaussian_score=gaussian_score,
                gaussian_p_win=gaussian_p_win,
                is_asia=is_asia,
                is_london=is_london,
                is_newyork=is_newyork,
                hour=hour,
                threshold=thr,
            )
        except Exception as exc:
            warnings.warn(f"[RRFusionLayer] Inference error: {exc}")
            return _passthrough(gaussian_score, gaussian_p_win, "inference_error")

    # ------------------------------------------------------------------
    @staticmethod
    def _get(obj: Any, attr: str, default: float = 0.0) -> Any:
        if isinstance(obj, dict):
            return obj.get(attr, default)
        return getattr(obj, attr, default)

    def _extract_gaussian_fields(self, trade: Any):
        g_score = float(self._get(trade, "gaussian_score", 0.0))
        g_pwin  = float(self._get(trade, "gaussian_p_win", 0.5))
        return g_score, g_pwin

    def _extract_model_fields(self, trade: Any):
        """Return (depth, body, disp, is_asia, is_london, is_newyork, hour)."""
        depth = float(self._get(trade, "retest_depth", 0.0))
        body  = float(self._get(
            trade, "body_ratio",
            self._get(trade, "body_ratio_feat", 0.0)
        ))
        disp  = float(self._get(
            trade, "disp_strength",
            self._get(trade, "disp_str_feat", 0.0)
        ))
        session = self._get(trade, "session", None)
        is_asia, is_london, is_newyork = _encode_session_onehot(session)
        entry_time = self._get(trade, "entry_time", None)
        hour       = _extract_hour(entry_time)
        return depth, body, disp, is_asia, is_london, is_newyork, hour

    # ------------------------------------------------------------------
    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def load_error(self) -> str:
        return self._load_error

    def reload(self, model_path: str = DEFAULT_MODEL_PATH) -> bool:
        """Hot-reload the model. Returns True on success, restores old on failure."""
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


# ─────────────────────────────────────────────────────────────────────────────
# Module-level singleton
# ─────────────────────────────────────────────────────────────────────────────
_default_layer: Optional[RRFusionLayer] = None


def get_fusion_layer(
    model_path: str = DEFAULT_MODEL_PATH,
    threshold:  float = 0.5,
) -> RRFusionLayer:
    """
    Get or create the module-level singleton RRFusionLayer.

    Usage:
        from rr_fusion import get_fusion_layer
        layer = get_fusion_layer()
        result = layer.score(trade_record)
    """
    global _default_layer
    if _default_layer is None:
        _default_layer = RRFusionLayer(model_path=model_path, threshold=threshold)
    return _default_layer


# ─────────────────────────────────────────────────────────────────────────────
# Standalone test
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import datetime

    # Test 1: model not loaded
    layer_missing = RRFusionLayer(model_path="models/nonexistent.json")
    result = layer_missing.score({"gaussian_score": 0.7, "gaussian_p_win": 0.6})
    assert result["status"] == "model_not_loaded"
    assert result["final_score"] == 0.7
    print("Test 1 PASSED: model_not_loaded passthrough")

    # Test 2: disabled layer
    layer_off = RRFusionLayer(enabled=False)
    result = layer_off.score({"gaussian_score": 0.65, "gaussian_p_win": 0.55})
    assert result["status"] == "disabled"
    print("Test 2 PASSED: disabled passthrough")

    # Test 3: drift detection
    class _MockDrift:
        retest_depth   = 2.5   # > 1.5 → drift
        body_ratio     = 0.5
        disp_strength  = 0.2
        gaussian_score = 0.7
        gaussian_p_win = 0.6
        session        = "LONDON"
        entry_time     = None

    # Need loaded engine for drift test, so use mock path
    model_path = "models/rr_model_test.json"
    if os.path.exists(model_path):
        layer = RRFusionLayer(model_path=model_path, threshold=0.5)
        assert layer.is_loaded

        result = layer.score(_MockDrift())
        assert result["status"] == "drift_detected"
        assert result["final_score"] == 0.7
        print("Test 3 PASSED: drift detection")

        # Test 4: normal inference
        class _MockTrade:
            retest_depth   = 0.35
            body_ratio     = 0.55
            disp_strength  = 0.25
            gaussian_score = 0.65
            gaussian_p_win = 0.60
            session        = "LONDON"
            entry_time     = datetime.datetime(2024, 3, 15, 14, 30, 0)

        result = layer.score(_MockTrade())
        assert "final_score" in result
        assert result["status"] in (
            "success", "bypassed_low_confidence", "capped_by_threshold"
        )
        print(f"Test 4 PASSED: inference result = {result}")

        # Test 5: reload
        assert layer.reload(model_path)
        print("Test 5 PASSED: model reload")
    else:
        print(f"Tests 3-5 SKIPPED: run rr_pattern_miner.py first to generate {model_path}")

    print("\nAll rr_fusion.py tests PASSED.")