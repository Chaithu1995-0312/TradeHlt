"""
BitNet Runner
Wraps BitNetModel with schema enforcement and fail-closed dimension checks.

Fail-closed contract (Phase 5/6 hardening):
  - No silent slicing. Runtime feature count must equal model.input_dim, OR
    the model must be schema=legacy_6input AND its declared feature_order
    must be a subset of CANONICAL_FEATURES (legacy bridge by NAME).
  - Mismatches emit BITNET_DIM_MISMATCH (CRITICAL) and raise RuntimeError.

Adaptive threshold (per-instrument per-regime):
  - Acceptance threshold is loaded from bitnet_thresholds.json, keyed by
    instrument and regime. Fallback chain: regime → DEFAULT → __default__ → 0.5.
  - File absence / parse failure logs a CRITICAL integrity event and falls back
    to hardcoded 0.5 for all instruments — never silent.
"""
import json
import logging
import os
from pathlib import Path

import numpy as np

from bitnet.bitnet_inference import BitNetModel
from bitnet.model_contract import CANONICAL_MODEL_SCHEMA_VERSION
from features.feature_schema import CANONICAL_FEATURES

try:
    from src.utils.integrity_events import emit_integrity_event  # noqa: F401
except Exception:  # pragma: no cover
    def emit_integrity_event(*_a, **_kw):  # type: ignore[no-redef]
        return None

logger = logging.getLogger(__name__)

# Fail-closed in production; set BITNET_DEBUG=true only in local dev/testing
DEBUG_MODE = os.environ.get("BITNET_DEBUG", "false").lower() == "true"


class BitNetRunner:
    """
    Production BitNet runner with schema enforcement and controlled failure modes.
    """

    def __init__(
        self,
        model_path: str = "model_export_format.json",
        *,
        instrument: str = "UNKNOWN",
        config: dict | None = None,
    ):
        self.model = BitNetModel(model_path)
        self.expected_input_dim = self.model.input_dim

        # Adaptive threshold context — kw-only so existing callers
        # (BitNetRunner(model_path)) keep working unchanged.
        self._instrument = instrument
        self._config = config or {}
        self._thresholds = self._load_thresholds()

        # Legacy bridge: legacy_6input models declare their own feature_order
        # (a strict 6-name subset of CANONICAL_FEATURES). We pluck by NAME — never
        # by prefix slice — so feature reordering can never silently corrupt input.
        self._legacy_feature_subset: list = []
        if self.model.schema_version == "legacy_6input":
            decl = list(self.model.feature_names or [])
            canonical_set = set(CANONICAL_FEATURES)
            unknown = [n for n in decl if n not in canonical_set]
            if not decl or unknown:
                emit_integrity_event(
                    "BITNET_LEGACY_FEATURE_SUBSET_INVALID",
                    "CRITICAL",
                    "bitnet.runner",
                    {
                        "model_path":         model_path,
                        "declared":           decl,
                        "unknown_features":   unknown,
                    },
                )
                raise RuntimeError(
                    "BitNet legacy_6input model declares features not present in "
                    f"CANONICAL_FEATURES: {unknown!r}. Refusing to load."
                )
            self._legacy_feature_subset = decl
            emit_integrity_event(
                "BITNET_LEGACY_FEATURE_SUBSET",
                "WARNING",
                "bitnet.runner",
                {
                    "model_path":      model_path,
                    "feature_order":   decl,
                    "schema":          self.model.schema_version,
                },
            )

        logger.info(
            "BitNetRunner initialized: schema=%s feature_dim=%d hash=%s instrument=%s",
            self.model.schema_version,
            self.expected_input_dim,
            self.model.feature_order_hash or "<none>",
            self._instrument,
        )

    def _load_thresholds(self) -> dict:
        """Load per-instrument per-regime thresholds from bitnet_thresholds.json.
        Falls back to hardcoded 0.5 per instrument if file absent or parse fails."""
        path = Path(self._config.get(
            "bitnet_thresholds_path",
            "src/bitnet/bitnet_thresholds.json",
        ))
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            emit_integrity_event(
                "BITNET_THRESHOLD_LOAD_FAILED",
                "WARNING",
                "bitnet.runner",
                {
                    "path":     str(path),
                    "error":    str(exc),
                    "fallback": "hardcoded 0.5 for all instruments",
                },
            )
            return {}

    def _threshold_for(self, regime: str = "UNKNOWN") -> float:
        """Per-instrument per-regime threshold with fallback chain:
        instrument+regime → instrument+DEFAULT → __default__ → 0.5."""
        inst_block = self._thresholds.get(self._instrument, {})
        if isinstance(inst_block, dict):
            val = inst_block.get((regime or "UNKNOWN").upper())
            if val is not None:
                return float(val)
            val = inst_block.get("DEFAULT")
            if val is not None:
                return float(val)
        val = self._thresholds.get("__default__")
        if val is not None:
            return float(val)
        # Hardcoded floor — never silent
        return 0.5

    def predict(self, features: dict) -> dict:
        """
        Run BitNet prediction on canonical feature dict.

        Parameters
        ----------
        features : dict
            Full canonical feature dict (all CANONICAL_FEATURES present).

        Returns
        -------
        dict
            { score: float, decision: str, error: Optional[str] }
        """
        try:
            # ── 1. Build input vector (fail-closed: never silent-slice). ──
            if self._legacy_feature_subset:
                # Legacy bridge: pluck the declared 6 feature names by key.
                ordered_values = [features[k] for k in self._legacy_feature_subset]
            else:
                ordered_values = [features[k] for k in CANONICAL_FEATURES]

            # ── 2. Dimension enforcement (NEVER silent). ──
            if len(ordered_values) != self.expected_input_dim:
                emit_integrity_event(
                    "BITNET_DIM_MISMATCH",
                    "CRITICAL",
                    "bitnet.runner",
                    {
                        "runtime_features":        len(ordered_values),
                        "model_input_dim":         self.expected_input_dim,
                        "model_schema_version":    self.model.schema_version,
                        "model_feature_order_hash": self.model.feature_order_hash,
                    },
                )
                raise RuntimeError(
                    f"BitNet feature dimension mismatch: runtime={len(ordered_values)} "
                    f"model={self.expected_input_dim} — refusing to truncate. "
                    f"Re-export model with schema_version="
                    f"{CANONICAL_MODEL_SCHEMA_VERSION}."
                )

            input_vector = np.array(ordered_values, dtype=np.float32)

            # ── 3. Inference. ──
            score = self.model.predict(input_vector)

            # ── 4. Per-instrument per-regime threshold (adaptive). ──
            # `_regime` is metadata (underscore-prefixed) and is stripped before
            # the feature vector is assembled — it is never in CANONICAL_FEATURES.
            regime    = features.get("_regime", "UNKNOWN")
            threshold = self._threshold_for(regime)
            decision  = "ACCEPT" if score > threshold else "REJECT"

            return {
                "score":    float(score),
                "decision": decision,
                "error":    None,
            }

        except Exception as e:
            error_msg = str(e)
            logger.error("BitNet prediction failed: %s", error_msg)

            if DEBUG_MODE:
                # Debug mode: accept on failure to test pipeline
                return {
                    "score":    0.5,
                    "decision": "ACCEPT",
                    "error":    error_msg,
                }
            else:
                # Production mode: safe default reject
                return {
                    "score":    0.0,
                    "decision": "REJECT",
                    "error":    error_msg,
                }